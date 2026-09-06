"""Puregram device-authed supervision — /v1/device/managed/* and /allowed-to-me.

LEGACY (2026-07-26): supervision moved to the web panel and the in-app screens
that called these endpoints were removed from both forks. The router stays
mounted so already-installed builds keep working until their users update; new
clients use /v1/control/* instead. Whitelist writes share one implementation
with the panel (routes.control.chats), so the two can never diverge.

The SUPERVISOR is identified by the DEVICE: its per-device bearer token resolves to
its Telegram account (tg_user_id), whose passwordless control_user is the "manager".
A link is an active control_links(manager, managed). Any account can be BOTH a
supervisor and managed at once.

Filtering is now PER-ACCOUNT: approvals are stored in telegram_account_whitelist keyed
by the managed account's tg_user_id (not per device), so all the account's devices —
and only that account — share one allowed set, and a newly-added account stays deny-all
until a supervisor approves chats for it.

  GET    /v1/device/managed                                accounts I supervise
  GET    /v1/device/managed/{tg_user_id}/chats             the managed account's chats
  PUT    /v1/device/managed/{tg_user_id}/chats/{chat_id}   allow/deny (per account)
  POST   /v1/device/managed/{tg_user_id}/chats/bulk        bulk-allow ids/@usernames/t.me
  DELETE /v1/device/managed/{tg_user_id}/chats/{chat_id}   deny (explicit revoke)
  GET    /v1/device/allowed-to-me                          my own whitelist + who supervises me

All queries are parameterized; timestamps are ISO-8601 UTC TEXT.
"""
from __future__ import annotations

from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import require_device, utcnow_iso
from ..db import get_db
from .control.chats import (
    _acct_version,
    _acct_write_chat,
    _known_meta,
    _parse_bulk_line,
)
from .device_link import _customer, _mask_email
from .telegram_admin import CHAT_KIND_RE

router = APIRouter(prefix="/v1/device", tags=["device-supervise"])


# ── Pydantic models ───────────────────────────────────────────────────────
class ToggleBody(BaseModel):
    allowed: bool
    kind: str | None = Field(default=None, pattern=CHAT_KIND_RE)
    label: str | None = Field(default=None, max_length=255)


class BulkBody(BaseModel):
    text: str = Field(min_length=1)


# ── Caller / authorization helpers ─────────────────────────────────────────
def _caller(db: psycopg.Connection, device_id: str) -> dict:
    customer = _customer(db, device_id)
    if customer is None or customer["tg_user_id"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "link_needs_tg_login")
    return customer


def _manager_user_id(db: psycopg.Connection, tg_user_id: int) -> int | None:
    row = db.execute(
        "SELECT id FROM control_users WHERE tg_user_id = %s", (tg_user_id,)
    ).fetchone()
    return row["id"] if row else None


def _require_manage(db: psycopg.Connection, manager_id: int, target_tg_user_id: int) -> int:
    """Return the managed control_user id iff `manager_id` actively manages the
    account `target_tg_user_id`; else 403 (never 404, so a manager can't probe ids)."""
    managed = db.execute(
        "SELECT id FROM control_users WHERE tg_user_id = %s", (target_tg_user_id,)
    ).fetchone()
    if managed is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_managed")
    link = db.execute(
        "SELECT 1 FROM control_links "
        "WHERE manager_user_id = %s AND managed_user_id = %s AND status = 'active'",
        (manager_id, managed["id"]),
    ).fetchone()
    if link is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_managed")
    return managed["id"]


def _manager_or_403(db: psycopg.Connection, device_id: str, target_tg_user_id: int) -> int:
    """Resolve caller → manager control_user, enforce active management of target."""
    caller = _caller(db, device_id)
    manager_id = _manager_user_id(db, caller["tg_user_id"])
    if manager_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_managed")
    _require_manage(db, manager_id, target_tg_user_id)
    return manager_id


# ── GET /v1/device/managed ─────────────────────────────────────────────────
@router.get("/managed")
def list_managed(
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    """Accounts I supervise, most-recently-active first. Empty if I manage none."""
    caller = _caller(db, device_id)
    manager_id = _manager_user_id(db, caller["tg_user_id"])
    if manager_id is None:
        return []

    rows = db.execute(
        """
        SELECT u.id AS managed_user_id, u.tg_user_id, u.display_name,
               COALESCE((
                   SELECT COUNT(DISTINCT k.chat_id) FROM telegram_known_chats k
                     JOIN customers c ON c.id = k.customer_id
                    WHERE c.tg_user_id = u.tg_user_id), 0) AS known_count,
               COALESCE((
                   SELECT COUNT(*) FROM telegram_account_whitelist w
                    WHERE w.tg_user_id = u.tg_user_id AND w.allowed = 1), 0) AS allowed_count,
               (SELECT MAX(c.last_seen_at) FROM customers c
                 WHERE c.tg_user_id = u.tg_user_id) AS last_seen_at
          FROM control_links l
          JOIN control_users u ON u.id = l.managed_user_id
         WHERE l.manager_user_id = %s AND l.status = 'active'
         ORDER BY (SELECT MAX(c.last_seen_at) FROM customers c
                    WHERE c.tg_user_id = u.tg_user_id) DESC NULLS LAST,
                  l.updated_at DESC
        """,
        (manager_id,),
    ).fetchall()
    return [
        {
            "tg_user_id": r["tg_user_id"],
            "display_name": r["display_name"] or "Puregram device",
            "known_count": r["known_count"],
            "allowed_count": r["allowed_count"],
            "last_seen_at": r["last_seen_at"],
        }
        for r in rows
    ]


# ── GET /v1/device/managed/{tg_user_id}/chats ──────────────────────────────
@router.get("/managed/{tg_user_id}/chats")
def managed_chats(
    tg_user_id: int,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """The managed account's known chats (effective-allowed), most-recent first."""
    _manager_or_403(db, device_id, tg_user_id)
    rows = db.execute(
        """
        SELECT k.chat_id,
               MAX(k.kind)                  AS kind,
               MAX(k.title)                 AS title,
               MAX(k.username)              AS username,
               MAX(k.last_seen_at)          AS last_seen_at,
               COALESCE(MAX(w.allowed), 0)  AS allowed
          FROM telegram_known_chats k
          LEFT JOIN telegram_account_whitelist w
            ON w.tg_user_id = k.tg_user_id AND w.chat_id = k.chat_id
         WHERE k.tg_user_id = %s
         GROUP BY k.chat_id
         ORDER BY MAX(k.last_seen_at) DESC NULLS LAST, MAX(k.title) NULLS LAST
        """,
        (tg_user_id,),
    ).fetchall()
    return {
        "tg_user_id": tg_user_id,
        "version": _acct_version(db, tg_user_id),
        "chats": [
            {
                "chat_id": r["chat_id"],
                "kind": r["kind"],
                "title": r["title"],
                "username": r["username"],
                "allowed": bool(r["allowed"]),
                "last_seen_at": r["last_seen_at"],
            }
            for r in rows
        ],
    }


# ── PUT /v1/device/managed/{tg_user_id}/chats/{chat_id} ────────────────────
@router.put("/managed/{tg_user_id}/chats/{chat_id}")
def toggle_managed_chat(
    tg_user_id: int,
    chat_id: int,
    body: ToggleBody,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Allow/deny one chat for the managed ACCOUNT (+ bump its version)."""
    manager_id = _manager_or_403(db, device_id, tg_user_id)
    known = _known_meta(db, tg_user_id, chat_id)
    kind = body.kind or (known["kind"] if known and known["kind"] else "channel")
    label = body.label if body.label is not None else (known["title"] if known else None)
    now = utcnow_iso()
    _acct_write_chat(db, tg_user_id, chat_id, kind, label, body.allowed, f"user:{manager_id}", now)
    db.commit()
    return {"ok": True, "allowed": body.allowed}


# ── DELETE /v1/device/managed/{tg_user_id}/chats/{chat_id} ─────────────────
@router.delete("/managed/{tg_user_id}/chats/{chat_id}")
def deny_managed_chat(
    tg_user_id: int,
    chat_id: int,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Explicitly deny (revoke) a chat for the managed account."""
    manager_id = _manager_or_403(db, device_id, tg_user_id)
    known = _known_meta(db, tg_user_id, chat_id)
    kind = known["kind"] if known and known["kind"] else "channel"
    label = known["title"] if known else None
    now = utcnow_iso()
    _acct_write_chat(db, tg_user_id, chat_id, kind, label, False, f"user:{manager_id}", now)
    db.commit()
    return {"ok": True}


# ── POST /v1/device/managed/{tg_user_id}/chats/bulk ────────────────────────
@router.post("/managed/{tg_user_id}/chats/bulk")
def bulk_managed_chats(
    tg_user_id: int,
    body: BulkBody,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Bulk-allow newline-separated chat ids / @usernames / t.me links."""
    manager_id = _manager_or_403(db, device_id, tg_user_id)
    now = utcnow_iso()
    granted_by = f"user:{manager_id}"
    added = 0
    skipped = 0
    seen: set[int] = set()
    for raw_line in body.text.splitlines():
        token = raw_line.strip()
        if not token or token.startswith("#"):
            continue
        parsed = _parse_bulk_line(db, tg_user_id, token)
        if parsed is None:
            skipped += 1
            continue
        chat_id, kind, label = parsed
        if chat_id in seen:
            continue
        seen.add(chat_id)
        _acct_write_chat(db, tg_user_id, chat_id, kind, label, True, granted_by, now)
        added += 1
    db.commit()
    return {"ok": True, "added": added, "skipped": skipped}


# ── GET /v1/device/allowed-to-me ───────────────────────────────────────────
@router.get("/allowed-to-me")
def allowed_to_me(
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """My own effective whitelist (chats I can open) + who supervises my account."""
    caller = _caller(db, device_id)
    tg_user_id = caller["tg_user_id"]

    allowed_rows = db.execute(
        """
        SELECT k.chat_id,
               MAX(k.kind)         AS kind,
               MAX(k.title)        AS title,
               MAX(k.username)     AS username,
               MAX(k.last_seen_at) AS last_seen_at
          FROM telegram_known_chats k
          JOIN telegram_account_whitelist w
            ON w.tg_user_id = k.tg_user_id AND w.chat_id = k.chat_id AND w.allowed = 1
         WHERE k.tg_user_id = %s
         GROUP BY k.chat_id
         ORDER BY MAX(k.last_seen_at) DESC NULLS LAST, MAX(k.title) NULLS LAST
        """,
        (tg_user_id,),
    ).fetchall()

    managers: list[dict[str, Any]] = []
    my_id = _manager_user_id(db, tg_user_id)
    if my_id is not None:
        manager_rows = db.execute(
            "SELECT u.id AS manager_user_id, u.display_name, u.email, l.created_at AS since "
            "FROM control_links l JOIN control_users u ON u.id = l.manager_user_id "
            "WHERE l.managed_user_id = %s AND l.status = 'active' "
            "ORDER BY l.created_at DESC",
            (my_id,),
        ).fetchall()
        managers = [
            {
                "manager_user_id": r["manager_user_id"],
                "display_name": r["display_name"],
                "email_masked": _mask_email(r["email"]),
                "since": r["since"],
            }
            for r in manager_rows
        ]

    return {
        "tg_user_id": tg_user_id,
        "allowed_chats": [
            {
                "chat_id": r["chat_id"],
                "kind": r["kind"],
                "title": r["title"],
                "username": r["username"],
                "last_seen_at": r["last_seen_at"],
            }
            for r in allowed_rows
        ],
        "managers": managers,
    }
