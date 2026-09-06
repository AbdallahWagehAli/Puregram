"""Control API — Server-Sent Events for live sync.

  GET /v1/control/stream   text/event-stream (cookie-authenticated)

One async loop per connection polls the DB every ~3s and emits ONLY on change:
- `ping`           heartbeat every ~25s (keep-alive through proxies).
- `incoming`        {count} when my pending incoming link-request count changes.
- `outgoing`        {count} when a request I sent is answered on the handset.
- `links`           {count} when the number of accounts I supervise changes.
- `unlink_request`  {count} when a managed account of mine asks to be unlinked.
- `chats`           {managed_user_id, version} when a managed account's whitelist
                    version changes, and {self, version} when MY own changes.

A short-lived pooled connection is taken for each poll (never held across the
loop's sleeps), so the SSE generator does not pin a pool slot. The SPA opens an
EventSource; the cookie travels same-origin.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from ...config import settings
from ...db import pool

router = APIRouter(prefix="/v1/control", tags=["control-stream"])

_POLL_INTERVAL_S = 3.0       # DB poll cadence
_PING_INTERVAL_S = 25.0      # keep-alive heartbeat cadence
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Disable proxy buffering so events flush immediately (nginx).
    "X-Accel-Buffering": "no",
}


def _resolve_user_id(token: str | None) -> int:
    """Authenticate the SSE connection from the user cookie, or 401.

    EventSource cannot send custom headers, but same-origin cookies travel, so
    the cookie is the only credential. We validate signature + `typ` here.
    """
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    if claims.get("typ") != "user":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    return int(claims["sub"])


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format one SSE frame (`event:`/`data:` lines, blank-line terminated)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _read_snapshot(user_id: int) -> dict[str, Any]:
    """Read the change-detection snapshot in one short-lived pooled connection.

    Whitelist versions come from `telegram_account_whitelist_meta` — the
    per-ACCOUNT table the forks actually enforce — so the panel reacts to the
    same number the handset polls. `links` counts the accounts I supervise: it
    ticks up the instant a handset approves a request, which is what flips the
    panel's "waiting for approval" card to "linked" without a refresh.
    """
    with pool.connection() as conn:
        incoming = conn.execute(
            "SELECT COUNT(*) AS n FROM control_link_requests "
            "WHERE target_user_id = %s AND status = 'pending'",
            (user_id,),
        ).fetchone()["n"]

        outgoing = conn.execute(
            "SELECT COUNT(*) AS n FROM control_link_requests "
            "WHERE requester_user_id = %s AND status = 'pending'",
            (user_id,),
        ).fetchone()["n"]

        links = conn.execute(
            "SELECT COUNT(*) AS n FROM control_links "
            "WHERE manager_user_id = %s AND status = 'active'",
            (user_id,),
        ).fetchone()["n"]

        unlink = conn.execute(
            "SELECT COUNT(*) AS n FROM control_unlink_requests "
            "WHERE manager_user_id = %s AND status = 'pending'",
            (user_id,),
        ).fetchone()["n"]

        managed_rows = conn.execute(
            "SELECT u.id AS managed_user_id, COALESCE(m.version, 0) AS version "
            "FROM control_links l "
            "JOIN control_users u ON u.id = l.managed_user_id "
            "LEFT JOIN telegram_account_whitelist_meta m ON m.tg_user_id = u.tg_user_id "
            "WHERE l.manager_user_id = %s AND l.status = 'active'",
            (user_id,),
        ).fetchall()

        self_row = conn.execute(
            "SELECT COALESCE(m.version, 0) AS version FROM control_users u "
            "LEFT JOIN telegram_account_whitelist_meta m ON m.tg_user_id = u.tg_user_id "
            "WHERE u.id = %s",
            (user_id,),
        ).fetchone()
    return {
        "incoming": incoming,
        "outgoing": outgoing,
        "links": links,
        "unlink": unlink,
        "managed": {r["managed_user_id"]: r["version"] for r in managed_rows},
        "self": self_row["version"] if self_row else 0,
    }


# Scalar snapshot fields → the SSE event name the SPA listens for.
_COUNTERS = (
    ("incoming", "incoming"),
    ("outgoing", "outgoing"),
    ("links", "links"),
    ("unlink", "unlink_request"),
)


def _diff_events(prev: dict[str, Any], curr: dict[str, Any]) -> list[str]:
    """Emit only the frames whose underlying value changed between two polls."""
    events: list[str] = []
    for key, name in _COUNTERS:
        if curr[key] != prev[key]:
            events.append(_sse(name, {"count": curr[key]}))
    for managed_id, version in curr["managed"].items():
        if version != prev["managed"].get(managed_id):
            events.append(_sse("chats", {"managed_user_id": managed_id, "version": version}))
    if curr["self"] != prev["self"]:
        events.append(_sse("chats", {"self": True, "version": curr["self"]}))
    return events


async def _event_loop(request: Request, user_id: int) -> AsyncIterator[str]:
    """Per-connection generator: initial snapshot, then change-only + heartbeat."""
    prev = await asyncio.to_thread(_read_snapshot, user_id)
    for key, name in _COUNTERS:
        yield _sse(name, {"count": prev[key]})
    for managed_id, version in prev["managed"].items():
        yield _sse("chats", {"managed_user_id": managed_id, "version": version})
    yield _sse("chats", {"self": True, "version": prev["self"]})

    since_ping = 0.0
    while not await request.is_disconnected():
        await asyncio.sleep(_POLL_INTERVAL_S)
        since_ping += _POLL_INTERVAL_S
        # Run the blocking DB read off the event loop so other connections flow.
        curr = await asyncio.to_thread(_read_snapshot, user_id)
        for frame in _diff_events(prev, curr):
            yield frame
        prev = curr
        if since_ping >= _PING_INTERVAL_S:
            since_ping = 0.0
            yield _sse("ping", {})


@router.get("/stream")
async def stream(
    request: Request,
    token: str | None = Cookie(default=None, alias=settings.user_cookie_name),
) -> StreamingResponse:
    """Open the authenticated SSE stream (cookie auth; resolved before streaming)."""
    user_id = _resolve_user_id(token)
    return StreamingResponse(
        _event_loop(request, user_id),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
