"""Telegram whitelist admin API — /v1/admin/telegram/*.

Per device, the admin manages which Telegram chats the Puregram client may show.
Devices report what their account can see into `telegram_known_chats`; the admin
approves entries into `telegram_whitelist`. Every mutation bumps
`telegram_whitelist_meta.version` so devices can poll cheaply. JWT cookie auth
via require_admin; readonly admins cannot mutate.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import require_admin, utcnow_iso
from ..db import get_db

router = APIRouter(prefix="/v1/admin/telegram", tags=["telegram-admin"])

CHAT_KIND_RE = r"^(channel|group|private|bot)$"

# A bare numeric chat id, optionally negative (-100… is a channel/supergroup).
_NUMERIC_ID_RE = re.compile(r"^-?\d+$")
# A @username or a t.me/<token> link → best-effort channel reference.
_USERNAME_RE = re.compile(r"^@[\w.]+$|^(?:https?://)?t\.me/[\w.+/]+$", re.IGNORECASE)


class WhitelistUpsert(BaseModel):
    chat_id: int
    kind: str = Field(pattern=CHAT_KIND_RE)
    label: str | None = Field(default=None, max_length=255)
    allowed: bool = True


class BulkWhitelistBody(BaseModel):
    text: str = Field(min_length=1)


# ── Helpers ──────────────────────────────────────────────────────────────
def _audit(db: psycopg.Connection, admin: dict, action: str,
           target: str | None, payload: dict[str, Any] | None) -> None:
    db.execute(
        "INSERT INTO audit_log (actor, action, target, payload, created_at) "
        "VALUES ('admin', %s, %s, %s, %s)",
        (action, target, json.dumps(payload or {"by": admin["email"]}), utcnow_iso()),
    )


def _forbid_readonly(admin: dict) -> None:
    if admin["role"] == "readonly":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Read-only admins cannot modify the Telegram whitelist",
        )


def _customer_id(db: psycopg.Connection, device_id: str) -> str:
    row = db.execute(
        "SELECT id FROM customers WHERE device_id = %s", (device_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return row["id"]


def _bump_whitelist_version(db: psycopg.Connection, customer_id: str) -> None:
    """Increment the per-customer whitelist version (devices poll on it)."""
    db.execute(
        """INSERT INTO telegram_whitelist_meta (customer_id, version, updated_at)
           VALUES (%s, 1, %s)
           ON CONFLICT (customer_id)
           DO UPDATE SET version = telegram_whitelist_meta.version + 1,
                         updated_at = EXCLUDED.updated_at""",
        (customer_id, utcnow_iso()),
    )


def _extract_username(token: str) -> str:
    """Strip @ / t.me/ wrapping down to the bare username token."""
    cleaned = token.strip()
    if cleaned.startswith("@"):
        return cleaned[1:]
    lowered = cleaned.lower()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if lowered.startswith(prefix):
            return cleaned[len(prefix):]
    return cleaned


def _synthetic_chat_id(username: str) -> int:
    """Deterministic negative pseudo-id for an unresolved username.

    Telegram real ids never fall in this reserved band, so a synthetic
    placeholder never collides with a genuine chat; the same username always maps
    to the same row, keeping repeated bulk pastes idempotent.
    """
    digest = int.from_bytes(
        hashlib.sha1(username.lower().encode("utf-8")).digest()[:6], "big"
    )
    return -(8_000_000_000_000_000 + digest)


def _parse_bulk_line(
    db: psycopg.Connection, customer_id: str, token: str
) -> tuple[int, str, str | None] | None:
    """Infer (chat_id, kind, label) from one bulk line, or None to skip it."""
    if _NUMERIC_ID_RE.match(token):
        chat_id = int(token)
        if token.startswith("-100"):
            return chat_id, "channel", None
        if chat_id < 0:
            return chat_id, "group", None
        return chat_id, "private", None

    if _USERNAME_RE.match(token):
        username = _extract_username(token)
        known = db.execute(
            "SELECT chat_id, kind FROM telegram_known_chats "
            "WHERE customer_id = %s AND LOWER(username) = %s",
            (customer_id, username.lower()),
        ).fetchone()
        if known is not None:
            return known["chat_id"], known["kind"], token
        # Unknown username: synthesize a stable id (idempotent re-pastes) and keep
        # the raw token in the label for the admin to reconcile.
        return _synthetic_chat_id(username), "channel", token

    return None


def _whitelist_row_dict(row: dict) -> dict[str, Any]:
    return {
        "chat_id": row["chat_id"],
        "kind": row["kind"],
        "label": row["label"],
        "allowed": bool(row["allowed"]),
        "granted_by": row["granted_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ── Devices with Telegram presence ───────────────────────────────────────
@router.get("/devices")
def list_telegram_devices(
    _: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    """Devices that have any Telegram presence (known chats or whitelist rows)."""
    rows = db.execute(
        """SELECT c.device_id, c.id AS customer_id, c.model, c.last_seen_at,
                  (SELECT COUNT(*) FROM telegram_known_chats k
                    WHERE k.customer_id = c.id) AS known_chats,
                  (SELECT COUNT(*) FROM telegram_whitelist w
                    WHERE w.customer_id = c.id AND w.allowed = 1) AS allowed_chats
             FROM customers c
            WHERE EXISTS (SELECT 1 FROM telegram_known_chats k
                           WHERE k.customer_id = c.id)
               OR EXISTS (SELECT 1 FROM telegram_whitelist w
                           WHERE w.customer_id = c.id)
            ORDER BY c.last_seen_at DESC NULLS LAST"""
    ).fetchall()
    return [
        {
            "device_id": r["device_id"],
            "customer_id": r["customer_id"],
            "model": r["model"],
            "known_chats": r["known_chats"],
            "allowed_chats": r["allowed_chats"],
            "last_seen_at": r["last_seen_at"],
        }
        for r in rows
    ]


# ── Per-device chats view (known + whitelist + version) ─────────────────
@router.get("/devices/{device_id}/chats")
def get_device_chats(
    device_id: str,
    _: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    customer_id = _customer_id(db, device_id)

    known_rows = db.execute(
        """SELECT k.chat_id, k.kind, k.title, k.username, k.last_seen_at,
                  COALESCE(w.allowed, 0) AS allowed
             FROM telegram_known_chats k
             LEFT JOIN telegram_whitelist w
               ON w.customer_id = k.customer_id AND w.chat_id = k.chat_id
            WHERE k.customer_id = %s
            ORDER BY k.last_seen_at DESC""",
        (customer_id,),
    ).fetchall()

    whitelist_rows = db.execute(
        """SELECT chat_id, kind, label, allowed, updated_at
             FROM telegram_whitelist
            WHERE customer_id = %s
            ORDER BY updated_at DESC""",
        (customer_id,),
    ).fetchall()

    meta = db.execute(
        "SELECT version FROM telegram_whitelist_meta WHERE customer_id = %s",
        (customer_id,),
    ).fetchone()

    return {
        "known": [
            {
                "id": r["chat_id"],
                "kind": r["kind"],
                "title": r["title"],
                "username": r["username"],
                "last_seen_at": r["last_seen_at"],
                "allowed": bool(r["allowed"]),
            }
            for r in known_rows
        ],
        "whitelist": [
            {
                "chat_id": r["chat_id"],
                "kind": r["kind"],
                "label": r["label"],
                "allowed": bool(r["allowed"]),
                "updated_at": r["updated_at"],
            }
            for r in whitelist_rows
        ],
        "version": meta["version"] if meta is not None else 0,
    }


# ── Whitelist mutations ──────────────────────────────────────────────────
@router.put("/devices/{device_id}/whitelist")
def upsert_whitelist_entry(
    device_id: str,
    body: WhitelistUpsert,
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    _forbid_readonly(admin)
    customer_id = _customer_id(db, device_id)
    now = utcnow_iso()
    db.execute(
        """INSERT INTO telegram_whitelist
             (customer_id, chat_id, kind, label, allowed, granted_by,
              created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (customer_id, chat_id)
           DO UPDATE SET kind = EXCLUDED.kind,
                         label = EXCLUDED.label,
                         allowed = EXCLUDED.allowed,
                         granted_by = EXCLUDED.granted_by,
                         updated_at = EXCLUDED.updated_at""",
        (customer_id, body.chat_id, body.kind, body.label,
         int(body.allowed), admin["email"], now, now),
    )
    _bump_whitelist_version(db, customer_id)
    _audit(db, admin, "tg_whitelist_set", str(body.chat_id),
           {"device_id": device_id, "kind": body.kind,
            "allowed": body.allowed, "by": admin["email"]})
    row = db.execute(
        """SELECT chat_id, kind, label, allowed, granted_by, created_at, updated_at
             FROM telegram_whitelist
            WHERE customer_id = %s AND chat_id = %s""",
        (customer_id, body.chat_id),
    ).fetchone()
    db.commit()
    return _whitelist_row_dict(row)


@router.delete("/devices/{device_id}/whitelist/{chat_id}")
def remove_whitelist_entry(
    device_id: str,
    chat_id: int,
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, bool]:
    _forbid_readonly(admin)
    customer_id = _customer_id(db, device_id)
    cur = db.execute(
        "DELETE FROM telegram_whitelist WHERE customer_id = %s AND chat_id = %s",
        (customer_id, chat_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not in whitelist")
    _bump_whitelist_version(db, customer_id)
    _audit(db, admin, "tg_whitelist_remove", str(chat_id),
           {"device_id": device_id, "by": admin["email"]})
    db.commit()
    return {"ok": True}


@router.post("/devices/{device_id}/bulk")
def bulk_whitelist(
    device_id: str,
    body: BulkWhitelistBody,
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Bulk-upsert a newline-separated list of chat ids / usernames as allowed."""
    _forbid_readonly(admin)
    customer_id = _customer_id(db, device_id)
    now = utcnow_iso()

    added = 0
    skipped = 0
    seen: set[int] = set()
    for raw_line in body.text.splitlines():
        token = raw_line.strip()
        if not token or token.startswith("#"):
            continue
        parsed = _parse_bulk_line(db, customer_id, token)
        if parsed is None:
            skipped += 1
            continue
        chat_id, kind, label = parsed
        if chat_id in seen:
            continue
        seen.add(chat_id)
        db.execute(
            """INSERT INTO telegram_whitelist
                 (customer_id, chat_id, kind, label, allowed, granted_by,
                  created_at, updated_at)
               VALUES (%s, %s, %s, %s, 1, %s, %s, %s)
               ON CONFLICT (customer_id, chat_id)
               DO UPDATE SET kind = EXCLUDED.kind,
                             label = EXCLUDED.label,
                             allowed = 1,
                             granted_by = EXCLUDED.granted_by,
                             updated_at = EXCLUDED.updated_at""",
            (customer_id, chat_id, kind, label, admin["email"], now, now),
        )
        added += 1

    if added:
        _bump_whitelist_version(db, customer_id)
    _audit(db, admin, "tg_whitelist_bulk", device_id,
           {"added": added, "skipped": skipped, "by": admin["email"]})
    db.commit()
    return {"ok": True, "added": added, "skipped": skipped}
