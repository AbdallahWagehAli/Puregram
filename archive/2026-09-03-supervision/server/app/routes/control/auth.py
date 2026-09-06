"""Control API — auth, profile, and Telegram-account binding.

  POST   /v1/control/register
  POST   /v1/control/login
  POST   /v1/control/logout
  GET    /v1/control/me
  PATCH  /v1/control/me
  POST   /v1/control/account/password
  POST   /v1/control/me/telegram          bind the Telegram account this user owns
  DELETE /v1/control/me/telegram          unbind it

Email/password accounts (Argon2id), independent of Telegram. The session is an
HS256 JWT in the HttpOnly `puregram_user` cookie. Login is throttled with the
same in-memory pattern as the admin panel (single-worker server).
"""
from __future__ import annotations

import secrets
import time

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field

from ...auth import (
    hash_password,
    issue_user_jwt,
    require_user,
    utcnow_iso,
    verify_password,
)
from ...db import get_db
from .common import (
    USER_PROFILE_COLUMNS,
    audit_user,
    clear_user_cookie,
    profile_dict,
    set_user_cookie,
)

router = APIRouter(prefix="/v1/control", tags=["control-auth"])

# Linking-by-code prefix; the random token is generated with the CSPRNG.
SHARE_CODE_PREFIX = "PGU-"

# In-memory login throttle (single-worker server), mirroring routes/admin.py.
_LOGIN_WINDOW_S = 300
_LOGIN_MAX_FAILS = 5
_login_fails: dict[str, list[float]] = {}


def _too_many_attempts(key: str) -> bool:
    now = time.time()
    recent = [t for t in _login_fails.get(key, []) if now - t < _LOGIN_WINDOW_S]
    _login_fails[key] = recent
    return len(recent) >= _LOGIN_MAX_FAILS


def _record_login_fail(key: str) -> None:
    _login_fails.setdefault(key, []).append(time.time())


def _new_share_code() -> str:
    """A URL-safe, collision-resistant share code (CSPRNG, ~72 bits)."""
    return SHARE_CODE_PREFIX + secrets.token_urlsafe(9)


def _fetch_profile(db: psycopg.Connection, user_id: int) -> dict:
    row = db.execute(
        f"SELECT {USER_PROFILE_COLUMNS} FROM control_users WHERE id = %s",
        (user_id,),
    ).fetchone()
    return profile_dict(row)


# ── Pydantic bodies ───────────────────────────────────────────────────────
class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)
    display_name: str | None = Field(default=None, max_length=120)
    lang: str | None = Field(default=None, pattern=r"^(ar|en)$")


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=255)


class PatchMeBody(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    lang: str | None = Field(default=None, pattern=r"^(ar|en)$")


class ChangePasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)


class BindTelegramBody(BaseModel):
    tg_user_id: int = Field(gt=0)


# ── Register / login / logout ─────────────────────────────────────────────
@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterBody,
    response: Response,
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """Create an account, set the session cookie, and return the profile."""
    email = body.email.strip().lower()
    if db.execute(
        "SELECT 1 FROM control_users WHERE email = %s", (email,)
    ).fetchone() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    now = utcnow_iso()
    display_name = (body.display_name or "").strip() or None
    row = db.execute(
        """INSERT INTO control_users
             (email, password_hash, display_name, lang, share_code,
              created_at, updated_at, last_seen_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING """ + USER_PROFILE_COLUMNS,
        (email, hash_password(body.password), display_name,
         body.lang or "ar", _new_share_code(), now, now, now),
    ).fetchone()
    db.commit()

    set_user_cookie(response, issue_user_jwt(row["id"]))
    return profile_dict(row)


@router.post("/login")
def login(
    body: LoginBody,
    response: Response,
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """Verify credentials, set the session cookie, return the profile."""
    key = body.email.strip().lower()
    if _too_many_attempts(key):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed attempts. Try again in a few minutes.",
        )
    row = db.execute(
        "SELECT id, password_hash FROM control_users WHERE email = %s", (key,)
    ).fetchone()
    if row is None or not verify_password(row["password_hash"], body.password):
        _record_login_fail(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    _login_fails.pop(key, None)  # clear on success
    db.execute(
        "UPDATE control_users SET last_seen_at = %s WHERE id = %s",
        (utcnow_iso(), row["id"]),
    )
    db.commit()
    set_user_cookie(response, issue_user_jwt(row["id"]))
    return _fetch_profile(db, row["id"])


@router.post("/logout")
def logout(
    response: Response, _: dict = Depends(require_user)
) -> dict[str, bool]:
    clear_user_cookie(response)
    return {"ok": True}


# ── Profile ───────────────────────────────────────────────────────────────
@router.get("/me")
def me(user: dict = Depends(require_user)) -> dict:
    return profile_dict(user)


@router.patch("/me")
def update_me(
    body: PatchMeBody,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """Update display name and/or language (any subset). No-op returns current."""
    sets: list[str] = []
    vals: list[object] = []
    if body.display_name is not None:
        sets.append("display_name = %s")
        vals.append(body.display_name.strip() or None)
    if body.lang is not None:
        sets.append("lang = %s")
        vals.append(body.lang)
    if not sets:
        return profile_dict(user)

    sets.append("updated_at = %s")
    vals.extend([utcnow_iso(), user["id"]])
    db.execute(
        "UPDATE control_users SET " + ", ".join(sets) + " WHERE id = %s", tuple(vals)
    )
    db.commit()
    return _fetch_profile(db, user["id"])


@router.post("/account/password")
def change_password(
    body: ChangePasswordBody,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, bool]:
    """Rotate the password after re-verifying the current one."""
    row = db.execute(
        "SELECT password_hash FROM control_users WHERE id = %s", (user["id"],)
    ).fetchone()
    if row is None or not verify_password(row["password_hash"], body.current_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect")

    db.execute(
        "UPDATE control_users SET password_hash = %s, updated_at = %s WHERE id = %s",
        (hash_password(body.new_password), utcnow_iso(), user["id"]),
    )
    db.commit()
    return {"ok": True}


# ── Telegram-account binding (managed side) ───────────────────────────────
@router.post("/me/telegram")
def bind_telegram(
    body: BindTelegramBody,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """Declare the Telegram account this user owns (managed side).

    Self-declared for now (`tg_verified` stays false). A future device-issued
    one-time code would flip tg_verified=1 here. The partial unique index
    enforces one Telegram account per control user; 409 on collision.
    """
    taken = db.execute(
        "SELECT id FROM control_users WHERE tg_user_id = %s AND id <> %s",
        (body.tg_user_id, user["id"]),
    ).fetchone()
    if taken is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That Telegram account is already bound"
        )
    db.execute(
        "UPDATE control_users SET tg_user_id = %s, tg_verified = 0, updated_at = %s "
        "WHERE id = %s",
        (body.tg_user_id, utcnow_iso(), user["id"]),
    )
    audit_user(db, user, "tg_bind", str(body.tg_user_id), {"by": user["email"]})
    db.commit()
    return _fetch_profile(db, user["id"])


@router.delete("/me/telegram")
def unbind_telegram(
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    db.execute(
        "UPDATE control_users SET tg_user_id = NULL, tg_verified = 0, updated_at = %s "
        "WHERE id = %s",
        (utcnow_iso(), user["id"]),
    )
    audit_user(db, user, "tg_unbind", None, {"by": user["email"]})
    db.commit()
    return _fetch_profile(db, user["id"])
