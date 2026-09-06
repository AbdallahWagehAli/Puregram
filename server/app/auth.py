"""Authentication.

Devices only. A device holds an opaque per-device bearer token stored in
`device_tokens`; it grants that device's own allow/block reads and writes and
nothing else — no database or service credential ships in the client.

There is no admin authentication here, and no admin. Under ADR-002 each user
governs their own lists, so nothing in this service has a privileged operator.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import Depends, Header, HTTPException, status

from .db import get_db


# ── Device tokens ────────────────────────────────────────────────────────
def new_device_token() -> str:
    return secrets.token_urlsafe(32)


def require_device(
    authorization: str | None = Header(default=None),
    db: psycopg.Connection = Depends(get_db),
) -> str:
    """Dependency: validate the client's bearer token, return its device_id."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing device token")
    token = authorization[7:].strip()
    row = db.execute(
        "SELECT device_id FROM device_tokens WHERE token = %s", (token,)
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid device token")
    db.execute(
        "UPDATE device_tokens SET last_used_at = %s WHERE token = %s",
        (utcnow_iso(), token),
    )
    db.commit()
    return row["device_id"]


# ── Time helpers ─────────────────────────────────────────────────────────
# ISO-8601 UTC timestamps are zero-padded, so lexicographic string comparison
# is chronologically correct — no parsing needed to compare two of them.
def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def iso_in_days(days: int) -> str:
    """A UTC ISO timestamp `days` from now, in the SAME format as utcnow_iso()
    so the two compare correctly with a plain string `<=` (no parsing)."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def iso_plus_days(base_iso: str, days: int) -> str:
    """`days` after an existing ISO timestamp (used when a renew extends an
    unexpired window). Falls back to now if the input can't be parsed."""
    try:
        base = datetime.strptime(base_iso, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        base = datetime.now(timezone.utc)
    return (base + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
