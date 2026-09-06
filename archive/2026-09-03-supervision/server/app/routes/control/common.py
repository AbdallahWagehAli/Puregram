"""Shared helpers for the Control API package.

Profile serialization, the user-auth cookie write/clear, the audit-log writer
(actor `'user'`), and the manager-guard used by every chat-control endpoint.
Kept in one place so auth/links/chats/stream stay focused on their flows.
"""
from __future__ import annotations

import json
from typing import Any

import psycopg
from fastapi import HTTPException, Response, status

from ...auth import utcnow_iso
from ...config import settings

# Columns selected wherever a profile is returned, so every endpoint emits the
# exact §4 shape (the SPA codes against these field names).
USER_PROFILE_COLUMNS = (
    "id, email, display_name, lang, tg_user_id, tg_verified, share_code"
)


def profile_dict(row: dict) -> dict[str, Any]:
    """Serialize a control_users row into the §4 user-profile object.

    `tg_verified` is stored as INTEGER (0/1) but exposed as a real bool so the
    frontend never has to coerce it.
    """
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "lang": row["lang"],
        "tg_user_id": row["tg_user_id"],
        "tg_verified": bool(row["tg_verified"]),
        "share_code": row["share_code"],
    }


def set_user_cookie(response: Response, token: str) -> None:
    """Write the HttpOnly user-session cookie (Secure in prod, SameSite=Lax)."""
    response.set_cookie(
        key=settings.user_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.user_jwt_ttl_hours * 3600,
        path="/",
    )


def clear_user_cookie(response: Response) -> None:
    response.delete_cookie(settings.user_cookie_name, path="/")


def audit_user(
    db: psycopg.Connection,
    user: dict,
    action: str,
    target: str | None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append a sensitive-mutation row to audit_log with actor `'user'`.

    Never serialize secrets here — only ids, emails, and flags. The default
    payload records the acting user's email for traceability.
    """
    db.execute(
        "INSERT INTO audit_log (actor, action, target, payload, created_at) "
        "VALUES ('user', %s, %s, %s, %s)",
        (action, target, json.dumps(payload or {"by": user["email"]}), utcnow_iso()),
    )


def require_manager_of(db: psycopg.Connection, manager_id: int, managed_id: int) -> dict:
    """Return the managed user's row, or raise 403/404.

    Enforces the core authorization invariant: a manager may only read or mutate
    an account they ACTIVELY manage (a revoked link grants nothing). 404 when the
    target user does not exist; 403 when no active link binds them.
    """
    managed = db.execute(
        f"SELECT {USER_PROFILE_COLUMNS} FROM control_users WHERE id = %s",
        (managed_id,),
    ).fetchone()
    if managed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    link = db.execute(
        "SELECT 1 FROM control_links "
        "WHERE manager_user_id = %s AND managed_user_id = %s AND status = 'active'",
        (manager_id, managed_id),
    ).fetchone()
    if link is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "You do not manage this account"
        )
    return managed
