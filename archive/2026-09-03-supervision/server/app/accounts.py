"""Telegram-account identity: the roster every Puregram device reports.

A device reports which Telegram accounts are logged in on it (`customer_accounts`)
together with each account's @username and display name. That roster is what lets
a supervisor find an account from the WEB PANEL by typing `@username` (or the
numeric Telegram id) — the handset no longer shows a pairing code anywhere, so
the panel is the only place a link can start.

Every managed Telegram account maps to exactly one *passwordless* control_user
row: the account is actable only through its device bearer token, never by web
login. `provision_tg_user` is the single place that row is created, so the
partial unique index on `control_users.tg_user_id` is honored everywhere.
"""
from __future__ import annotations

import re

import psycopg

from .auth import utcnow_iso

# Telegram's own username rule: 5–32 of [A-Za-z0-9_]. Accepted with or without a
# leading '@', and as a t.me / telegram.me link (with or without scheme).
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")
_TME_RE = re.compile(
    r"^(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:@)?([A-Za-z0-9_]{5,32})/?$",
    re.IGNORECASE,
)
_NUMERIC_RE = re.compile(r"^[1-9][0-9]{4,18}$")


def normalize_username(raw: str) -> str | None:
    """Extract a bare Telegram username from `@name`, `name`, or a t.me link."""
    token = raw.strip()
    if not token:
        return None
    link = _TME_RE.match(token)
    if link is not None:
        return link.group(1)
    candidate = token[1:] if token.startswith("@") else token
    return candidate if _USERNAME_RE.match(candidate) else None


def resolve_tg_identity(db: psycopg.Connection, raw: str) -> dict | None:
    """Look up a Telegram account in the reported roster.

    Accepts `@username`, a bare username, a t.me link, or the numeric account id.
    Returns `{tg_user_id, username, display_name}` or None when no Puregram
    device has ever reported that account (i.e. it cannot be supervised yet).
    """
    token = raw.strip()
    if not token:
        return None

    if _NUMERIC_RE.match(token):
        row = db.execute(
            "SELECT tg_user_id, MAX(username) AS username, MAX(display_name) AS display_name "
            "FROM customer_accounts WHERE tg_user_id = %s GROUP BY tg_user_id",
            (int(token),),
        ).fetchone()
        return dict(row) if row is not None else None

    username = normalize_username(token)
    if username is None:
        return None
    row = db.execute(
        "SELECT tg_user_id, MAX(username) AS username, MAX(display_name) AS display_name "
        "FROM customer_accounts WHERE LOWER(username) = %s "
        "GROUP BY tg_user_id ORDER BY MAX(updated_at) DESC LIMIT 1",
        (username.lower(),),
    ).fetchone()
    return dict(row) if row is not None else None


def account_label(row: dict | None, fallback: str = "Puregram account") -> str:
    """A human name for an account: reported display name → @username → fallback."""
    if row is None:
        return fallback
    name = (row.get("display_name") or "").strip()
    if name:
        return name
    username = (row.get("username") or "").strip()
    return f"@{username}" if username else fallback


def provision_tg_user(
    db: psycopg.Connection, tg_user_id: int, display_name: str
) -> int:
    """Reuse or auto-create the passwordless control_user for a Telegram account.

    `tg_verified = 1` because only a device bearer token (or a roster the devices
    themselves populate) can reach this path. The ON CONFLICT targets the partial
    unique index, so a concurrent call cannot create a duplicate; an existing
    (self-registered) row keeps its own email/password/display_name.
    """
    now = utcnow_iso()
    row = db.execute(
        "INSERT INTO control_users "
        "  (display_name, lang, tg_user_id, tg_verified, created_at, updated_at) "
        "VALUES (%s, 'ar', %s, 1, %s, %s) "
        "ON CONFLICT (tg_user_id) WHERE tg_user_id IS NOT NULL "
        "DO UPDATE SET tg_verified = 1, updated_at = EXCLUDED.updated_at "
        "RETURNING id",
        (display_name, tg_user_id, now, now),
    ).fetchone()
    return row["id"]


def device_account_ids(db: psycopg.Connection, customer_id: str) -> list[int]:
    """Every Telegram account seen on a device (its multi-account roster)."""
    rows = db.execute(
        "SELECT tg_user_id FROM customer_accounts WHERE customer_id = %s",
        (customer_id,),
    ).fetchall()
    return [r["tg_user_id"] for r in rows]
