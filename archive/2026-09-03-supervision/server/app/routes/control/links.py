"""Control API — the consent (linking) flow and the relationship overview.

  POST   /v1/control/links/requests                 send a request (@username, id, email…)
  GET    /v1/control/links/requests/incoming        pending, target = me
  GET    /v1/control/links/requests/outgoing        pending, requester = me
  POST   /v1/control/links/requests/{id}/approve    target → creates active link
  POST   /v1/control/links/requests/{id}/decline    target
  POST   /v1/control/links/requests/{id}/cancel      requester
  GET    /v1/control/managed                         accounts I manage (+ chat counts)
  GET    /v1/control/managers                        people who manage me
  DELETE /v1/control/managed/{user_id}               I stop managing them
  DELETE /v1/control/managers/{user_id}              remove a manager over me

A link is consensual: the requester asks, the target approves. Approval flips the
request to 'approved' and upserts an active control_links row.

Since supervision moved out of the messenger apps (2026-07-26) the usual target
is a TELEGRAM ACCOUNT: the supervisor types `@username` / the numeric id here,
the request is delivered to that account's handset as a NOTIFICATION, and the
handset approves it with its own device token (POST /v1/device/link-requests/…).
Both sides display the same short `code` so the managed user can see that the
prompt on their screen is the one their supervisor is looking at — it is a
verification code, NOT a credential (approval needs the device token).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ...accounts import account_label, provision_tg_user, resolve_tg_identity
from ...auth import require_user, utcnow_iso
from ...db import get_db
from ...pairing import format_code, generate_code
from .common import audit_user

router = APIRouter(prefix="/v1/control/links", tags=["control-links"])

# How long a pending request stays actionable on the handset. Long enough for a
# phone that only polls every few seconds to surface the notification and for the
# managed user to actually read it; short enough that a forgotten request lapses.
_REQUEST_TTL_MINUTES = 30
# A second, separately-mounted router for the /managed and /managers overview +
# unlink endpoints. It carries its OWN /v1/control prefix and is included
# directly by the package (NOT nested under `router`, whose prefix would stack).
overview = APIRouter(prefix="/v1/control", tags=["control-links"])


class CreateRequestBody(BaseModel):
    target: str = Field(min_length=1, max_length=255)


def _public_user(row: dict) -> dict[str, Any]:
    """The minimal user shape embedded in request/overview responses."""
    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "email": row.get("email"),
        "tg_user_id": row.get("tg_user_id"),
        "username": row.get("username"),
    }


def _expires_at() -> str:
    """Request deadline in the same ISO-8601 UTC TEXT format used everywhere."""
    return (datetime.now(timezone.utc) + timedelta(minutes=_REQUEST_TTL_MINUTES)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def _resolve_target(db: psycopg.Connection, token: str) -> dict | None:
    """Find the account to supervise.

    Order matters: a web account (email / share_code) wins, then the Telegram
    roster every device reports (`@username`, a t.me link, or the numeric id).
    A Telegram account that has never run Puregram is unreachable by design — it
    has no device to approve the request — so it resolves to None.
    """
    cleaned = token.strip()
    row = db.execute(
        "SELECT id, display_name, email, tg_user_id FROM control_users "
        "WHERE email = %s OR share_code = %s",
        (cleaned.lower(), cleaned),
    ).fetchone()
    if row is not None:
        return dict(row)

    identity = resolve_tg_identity(db, cleaned)
    if identity is None:
        return None
    user_id = provision_tg_user(db, identity["tg_user_id"], account_label(identity))
    target = db.execute(
        "SELECT id, display_name, email, tg_user_id FROM control_users WHERE id = %s",
        (user_id,),
    ).fetchone()
    resolved = dict(target)
    resolved["username"] = identity.get("username")
    return resolved


def _active_link_exists(db: psycopg.Connection, manager_id: int, managed_id: int) -> bool:
    return db.execute(
        "SELECT 1 FROM control_links "
        "WHERE manager_user_id = %s AND managed_user_id = %s AND status = 'active'",
        (manager_id, managed_id),
    ).fetchone() is not None


def _pending_request(db: psycopg.Connection, request_id: int) -> dict:
    row = db.execute(
        "SELECT id, requester_user_id, target_user_id, status "
        "FROM control_link_requests WHERE id = %s",
        (request_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    return row


def _set_request_status(db: psycopg.Connection, request_id: int, new_status: str) -> None:
    db.execute(
        "UPDATE control_link_requests SET status = %s, updated_at = %s WHERE id = %s",
        (new_status, utcnow_iso(), request_id),
    )


# ── Create a link request ─────────────────────────────────────────────────
@router.post("/requests", status_code=status.HTTP_201_CREATED)
def create_request(
    body: CreateRequestBody,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """The signed-in supervisor requests to manage `target`.

    `target` is a Telegram `@username` / numeric id / t.me link, or a web
    account's email or share_code. Returns the verification code the managed
    handset will show in its notification. Re-sending to the same target is
    idempotent: the live request (with a refreshed deadline) comes back instead
    of a 409, so the panel can always re-display the code. 404 unknown, 422
    self, 409 already linked.
    """
    target = _resolve_target(db, body.target)
    if target is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No Puregram account matches that username, id, or email",
        )
    if target["id"] == user["id"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "You cannot link to yourself")
    if _active_link_exists(db, user["id"], target["id"]):
        raise HTTPException(status.HTTP_409_CONFLICT, "You already manage this account")

    now, expires_at = utcnow_iso(), _expires_at()
    code = format_code(generate_code())
    existing = db.execute(
        "SELECT id, code, expires_at FROM control_link_requests "
        "WHERE requester_user_id = %s AND target_user_id = %s AND status = 'pending'",
        (user["id"], target["id"]),
    ).fetchone()
    if existing is not None:
        # Keep the code the handset may already be displaying; only extend it.
        code = existing["code"] or code
        db.execute(
            "UPDATE control_link_requests "
            "SET code = %s, expires_at = %s, updated_at = %s WHERE id = %s",
            (code, expires_at, now, existing["id"]),
        )
        request_id = existing["id"]
    else:
        request_id = db.execute(
            "INSERT INTO control_link_requests "
            "  (requester_user_id, target_user_id, code, expires_at, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (user["id"], target["id"], code, expires_at, now, now),
        ).fetchone()["id"]
    audit_user(db, user, "link_request", str(target["id"]), {"by": user["email"]})
    db.commit()
    return {
        "id": request_id,
        "code": code,
        "expires_at": expires_at,
        "target": _public_user(target),
    }


# ── Incoming / outgoing pending requests ──────────────────────────────────
@router.get("/requests/incoming")
def incoming_requests(
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    """Pending requests where I am the target (someone wants to manage me)."""
    rows = db.execute(
        "SELECT r.id, r.created_at, u.id AS uid, u.display_name, u.email "
        "FROM control_link_requests r "
        "JOIN control_users u ON u.id = r.requester_user_id "
        "WHERE r.target_user_id = %s AND r.status = 'pending' "
        "ORDER BY r.created_at DESC",
        (user["id"],),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "requester": {"id": r["uid"], "display_name": r["display_name"], "email": r["email"]},
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.get("/requests/outgoing")
def outgoing_requests(
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    """Pending requests I sent, with the verification code and deadline the panel
    displays while it waits for the handset. Past-deadline rows are lapsed first,
    so a stale request never sits in the list looking actionable."""
    db.execute(
        "UPDATE control_link_requests SET status = 'cancelled', updated_at = %s "
        "WHERE requester_user_id = %s AND status = 'pending' "
        "  AND expires_at IS NOT NULL AND expires_at <= %s",
        (utcnow_iso(), user["id"], utcnow_iso()),
    )
    db.commit()
    rows = db.execute(
        "SELECT r.id, r.created_at, r.code, r.expires_at, "
        "       u.id AS uid, u.display_name, u.email, u.tg_user_id, "
        "       (SELECT MAX(a.username) FROM customer_accounts a "
        "         WHERE a.tg_user_id = u.tg_user_id) AS username "
        "FROM control_link_requests r "
        "JOIN control_users u ON u.id = r.target_user_id "
        "WHERE r.requester_user_id = %s AND r.status = 'pending' "
        "ORDER BY r.created_at DESC",
        (user["id"],),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "target": _public_user(r | {"id": r["uid"]}),
            "code": r["code"],
            "expires_at": r["expires_at"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ── Approve / decline / cancel ────────────────────────────────────────────
@router.post("/requests/{request_id}/approve")
def approve_request(
    request_id: int,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, bool]:
    """The target approves → an active control_link (requester manages target)."""
    req = _pending_request(db, request_id)
    if req["target_user_id"] != user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request to approve")
    if req["status"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Request is no longer pending")

    now = utcnow_iso()
    db.execute(
        "INSERT INTO control_links "
        "  (manager_user_id, managed_user_id, status, created_at, updated_at) "
        "VALUES (%s, %s, 'active', %s, %s) "
        "ON CONFLICT (manager_user_id, managed_user_id) "
        "DO UPDATE SET status = 'active', updated_at = EXCLUDED.updated_at",
        (req["requester_user_id"], user["id"], now, now),
    )
    _set_request_status(db, request_id, "approved")
    audit_user(db, user, "link_approve", str(req["requester_user_id"]), {"by": user["email"]})
    db.commit()
    return {"ok": True}


@router.post("/requests/{request_id}/decline")
def decline_request(
    request_id: int,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, bool]:
    req = _pending_request(db, request_id)
    if req["target_user_id"] != user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request to decline")
    if req["status"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Request is no longer pending")
    _set_request_status(db, request_id, "declined")
    audit_user(db, user, "link_decline", str(req["requester_user_id"]), {"by": user["email"]})
    db.commit()
    return {"ok": True}


@router.post("/requests/{request_id}/cancel")
def cancel_request(
    request_id: int,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, bool]:
    req = _pending_request(db, request_id)
    if req["requester_user_id"] != user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your request to cancel")
    if req["status"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Request is no longer pending")
    _set_request_status(db, request_id, "cancelled")
    db.commit()
    return {"ok": True}


# ── Overview: managed accounts / managers ─────────────────────────────────
@overview.get("/managed")
def list_managed(
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    """Accounts I supervise, most recently active first.

    `allowed_count` reads the per-ACCOUNT whitelist (the table the forks enforce)
    and `last_seen_at` the account's devices, so the list mirrors reality rather
    than the control_users row. An account with no bound Telegram id shows zeros.
    """
    rows = db.execute(
        """
        SELECT u.id AS user_id, u.display_name, u.email, u.tg_user_id, u.tg_verified,
               COALESCE((
                   SELECT COUNT(DISTINCT k.chat_id)
                     FROM telegram_known_chats k
                    WHERE k.tg_user_id = u.tg_user_id
               ), 0) AS known_count,
               COALESCE((
                   SELECT COUNT(*) FROM telegram_account_whitelist w
                    WHERE w.tg_user_id = u.tg_user_id AND w.allowed = 1
               ), 0) AS allowed_count,
               (SELECT MAX(a.username) FROM customer_accounts a
                 WHERE a.tg_user_id = u.tg_user_id) AS username,
               (SELECT MAX(c.last_seen_at) FROM customers c
                 WHERE c.tg_user_id = u.tg_user_id) AS last_seen_at
          FROM control_links l
          JOIN control_users u ON u.id = l.managed_user_id
         WHERE l.manager_user_id = %s AND l.status = 'active'
         ORDER BY (SELECT MAX(c.last_seen_at) FROM customers c
                    WHERE c.tg_user_id = u.tg_user_id) DESC NULLS LAST,
                  l.updated_at DESC
        """,
        (user["id"],),
    ).fetchall()
    return [
        {
            "user_id": r["user_id"],
            "display_name": r["display_name"],
            "email": r["email"],
            "tg_user_id": r["tg_user_id"],
            "username": r["username"],
            "tg_verified": bool(r["tg_verified"]),
            "known_count": r["known_count"] if r["tg_user_id"] is not None else 0,
            "allowed_count": r["allowed_count"] if r["tg_user_id"] is not None else 0,
            "last_seen_at": r["last_seen_at"],
        }
        for r in rows
    ]


@overview.get("/managers")
def list_managers(
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    """People who manage me (and since when)."""
    rows = db.execute(
        "SELECT u.id AS user_id, u.display_name, u.email, l.created_at AS since "
        "FROM control_links l "
        "JOIN control_users u ON u.id = l.manager_user_id "
        "WHERE l.managed_user_id = %s AND l.status = 'active' "
        "ORDER BY l.created_at DESC",
        (user["id"],),
    ).fetchall()
    return [
        {
            "user_id": r["user_id"],
            "display_name": r["display_name"],
            "email": r["email"],
            "since": r["since"],
        }
        for r in rows
    ]


@overview.delete("/managed/{user_id}")
def unlink_managed(
    user_id: int,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, bool]:
    """I (the manager) stop managing `user_id`."""
    cur = db.execute(
        "UPDATE control_links SET status = 'revoked', updated_at = %s "
        "WHERE manager_user_id = %s AND managed_user_id = %s AND status = 'active'",
        (utcnow_iso(), user["id"], user_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active link to remove")
    audit_user(db, user, "unlink_managed", str(user_id), {"by": user["email"]})
    db.commit()
    return {"ok": True}


@overview.delete("/managers/{user_id}")
def unlink_manager(
    user_id: int,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, bool]:
    """I (the managed user) remove `user_id` as a manager over me."""
    cur = db.execute(
        "UPDATE control_links SET status = 'revoked', updated_at = %s "
        "WHERE manager_user_id = %s AND managed_user_id = %s AND status = 'active'",
        (utcnow_iso(), user_id, user["id"]),
    )
    if cur.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active link to remove")
    audit_user(db, user, "unlink_manager", str(user_id), {"by": user["email"]})
    db.commit()
    return {"ok": True}
