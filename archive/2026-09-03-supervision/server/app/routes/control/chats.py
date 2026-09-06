"""Control API — chat whitelist control for a managed account.

  GET    /v1/control/managed/{user_id}/chats              known chats + version
  PUT    /v1/control/managed/{user_id}/chats/{chat_id}    allow / block one chat
  DELETE /v1/control/managed/{user_id}/chats/{chat_id}    block one chat
  POST   /v1/control/managed/{user_id}/chats/bulk         bulk-allow ids/usernames

Every endpoint is guarded by `require_manager_of` → 403 unless the caller
actively manages `{user_id}`.

Approvals are stored PER TELEGRAM ACCOUNT (`telegram_account_whitelist`, keyed by
tg_user_id) — that is the table the forks actually enforce, via
`GET /v1/device/telegram/whitelist/all`. All of the account's devices therefore
share one allowed set, and a newly added account stays deny-all until a
supervisor approves chats for it. Each write bumps the account's version so the
handset re-polls within seconds.
"""
from __future__ import annotations

from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ...auth import require_user, utcnow_iso
from ...db import get_db
from ..telegram_admin import (
    CHAT_KIND_RE,
    _extract_username,
    _synthetic_chat_id,
    _NUMERIC_ID_RE,
    _USERNAME_RE,
)
from .common import audit_user, require_manager_of

router = APIRouter(prefix="/v1/control/managed", tags=["control-chats"])

# Telegram's Bot API writes a channel id as -(1e12 + rawId). Both forks report and
# enforce the plain -rawId form, so a pasted Bot-API id is normalized on the way in.
_BOT_API_CHANNEL_OFFSET = 1_000_000_000_000


class ToggleChatBody(BaseModel):
    allowed: bool
    kind: str | None = Field(default=None, pattern=CHAT_KIND_RE)
    label: str | None = Field(default=None, max_length=255)


class BulkBody(BaseModel):
    text: str = Field(min_length=1)


# ── Account-scoped whitelist helpers (shared with the device API) ──────────
def _acct_bump(db: psycopg.Connection, tg_user_id: int, now: str) -> None:
    """Advance the account's whitelist version — the number every client polls."""
    db.execute(
        "INSERT INTO telegram_account_whitelist_meta (tg_user_id, version, updated_at) "
        "VALUES (%s, 1, %s) "
        "ON CONFLICT (tg_user_id) "
        "DO UPDATE SET version = telegram_account_whitelist_meta.version + 1, "
        "             updated_at = EXCLUDED.updated_at",
        (tg_user_id, now),
    )


def _acct_write_chat(
    db: psycopg.Connection, tg_user_id: int, chat_id: int, kind: str,
    label: str | None, allowed: bool, granted_by: str, now: str,
) -> None:
    """Upsert one chat's allowed flag for the ACCOUNT, then bump its version.

    COALESCE keeps an existing label when the caller passes none; granted_by
    records who approved it.
    """
    db.execute(
        "INSERT INTO telegram_account_whitelist "
        "  (tg_user_id, chat_id, kind, label, allowed, granted_by, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (tg_user_id, chat_id) "
        "DO UPDATE SET allowed = EXCLUDED.allowed, "
        "             kind = EXCLUDED.kind, "
        "             label = COALESCE(EXCLUDED.label, telegram_account_whitelist.label), "
        "             granted_by = EXCLUDED.granted_by, "
        "             updated_at = EXCLUDED.updated_at",
        (tg_user_id, chat_id, kind, label, 1 if allowed else 0, granted_by, now, now),
    )
    _acct_bump(db, tg_user_id, now)


def _acct_version(db: psycopg.Connection, tg_user_id: int) -> int:
    row = db.execute(
        "SELECT version FROM telegram_account_whitelist_meta WHERE tg_user_id = %s",
        (tg_user_id,),
    ).fetchone()
    return row["version"] if row else 0


def _known_meta(db: psycopg.Connection, tg_user_id: int, chat_id: int) -> dict | None:
    """Best-effort kind/title for a chat from the ACCOUNT's known chats (any of
    its devices)."""
    return db.execute(
        "SELECT MAX(kind) AS kind, MAX(title) AS title FROM telegram_known_chats "
        "WHERE tg_user_id = %s AND chat_id = %s",
        (tg_user_id, chat_id),
    ).fetchone()


def _parse_bulk_line(
    db: psycopg.Connection, tg_user_id: int, token: str
) -> tuple[int, str, str | None] | None:
    """Account-scoped variant of telegram_admin._parse_bulk_line.

    Numeric ids infer kind from sign/-100 prefix; @usernames / t.me links are
    resolved against the account's known chats (across all its devices), else
    synthesized to a stable negative id so repeated pastes stay idempotent.
    """
    if _NUMERIC_ID_RE.match(token):
        chat_id = int(token)
        if token.startswith("-100"):
            # A pasted Bot-API channel id (-100 + raw id). The clients report and
            # match plain -rawId, so strip the offset or the approval would sit in
            # the table matching nothing.
            return -(abs(chat_id) - _BOT_API_CHANNEL_OFFSET), "channel", None
        return (chat_id, "group", None) if chat_id < 0 else (chat_id, "private", None)

    if _USERNAME_RE.match(token):
        username = _extract_username(token)
        known = db.execute(
            "SELECT k.chat_id, k.kind FROM telegram_known_chats k "
            "WHERE k.tg_user_id = %s AND LOWER(k.username) = %s "
            "LIMIT 1",
            (tg_user_id, username.lower()),
        ).fetchone()
        if known is not None:
            return known["chat_id"], known["kind"], token
        return _synthetic_chat_id(username), "channel", token

    return None


def _granted_by(user: dict) -> str:
    """Provenance tag stored on whitelist rows, e.g. `user:<id>`."""
    return f"user:{user['id']}"


def _managed_account(db: psycopg.Connection, manager_id: int, user_id: int) -> int:
    """The managed account's tg_user_id, or 409 when no Telegram account is bound."""
    managed = require_manager_of(db, manager_id, user_id)
    if managed["tg_user_id"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Account has no Telegram bound")
    return managed["tg_user_id"]


# ── GET chats ──────────────────────────────────────────────────────────────
@router.get("/{user_id}/chats")
def get_chats(
    user_id: int,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Every chat the managed account has reported, with its effective allowed
    flag. Most recently active first — that is the order a supervisor scans."""
    managed = require_manager_of(db, user["id"], user_id)
    tg_user_id = managed["tg_user_id"]
    if tg_user_id is None:
        return {"tg_user_id": None, "version": 0, "chats": []}

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


# ── PUT toggle one chat ─────────────────────────────────────────────────────
@router.put("/{user_id}/chats/{chat_id}")
def toggle_chat(
    user_id: int,
    chat_id: int,
    body: ToggleChatBody,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Allow or block one chat for the managed ACCOUNT (+ bump its version).

    `kind` defaults to the known-chat kind (or 'channel' if unknown); `label`
    falls back to the known title.
    """
    tg_user_id = _managed_account(db, user["id"], user_id)
    known = _known_meta(db, tg_user_id, chat_id)
    kind = body.kind or (known["kind"] if known and known["kind"] else "channel")
    label = body.label if body.label is not None else (known["title"] if known else None)

    now = utcnow_iso()
    _acct_write_chat(db, tg_user_id, chat_id, kind, label, body.allowed, _granted_by(user), now)
    audit_user(db, user, "chat_toggle", str(chat_id),
               {"managed_user_id": user_id, "allowed": body.allowed, "by": user["email"]})
    db.commit()
    return {"ok": True, "allowed": body.allowed, "version": _acct_version(db, tg_user_id)}


# ── DELETE = block ──────────────────────────────────────────────────────────
@router.delete("/{user_id}/chats/{chat_id}")
def block_chat(
    user_id: int,
    chat_id: int,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Explicitly block a chat (an allowed=0 row, so it survives a re-report)."""
    tg_user_id = _managed_account(db, user["id"], user_id)
    known = _known_meta(db, tg_user_id, chat_id)
    kind = known["kind"] if known and known["kind"] else "channel"
    label = known["title"] if known else None

    now = utcnow_iso()
    _acct_write_chat(db, tg_user_id, chat_id, kind, label, False, _granted_by(user), now)
    audit_user(db, user, "chat_block", str(chat_id),
               {"managed_user_id": user_id, "by": user["email"]})
    db.commit()
    return {"ok": True, "allowed": False, "version": _acct_version(db, tg_user_id)}


# ── POST bulk-allow ─────────────────────────────────────────────────────────
@router.post("/{user_id}/chats/bulk")
def bulk_chats(
    user_id: int,
    body: BulkBody,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Bulk-allow a newline-separated list of chat ids / @usernames / t.me links."""
    tg_user_id = _managed_account(db, user["id"], user_id)

    now = utcnow_iso()
    granted_by = _granted_by(user)
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

    audit_user(db, user, "chat_bulk", str(user_id),
               {"added": added, "skipped": skipped, "by": user["email"]})
    db.commit()
    return {"ok": True, "added": added, "skipped": skipped,
            "version": _acct_version(db, tg_user_id)}
