"""Puregram device API — /v1/device/* (LEGACY protocol, kept for old clients).

Clients built before ADR-002 (Android ≤ 12.8.13, desktop build ≤ 5) are
deny-by-default: they check in for a bearer token, report the chats they can
see, and poll a per-account whitelist every 15 s. New clients use `/v1/rules`
(routes/rules.py) and call nothing here except `/checkin`.

  POST /v1/device/checkin                      bootstrap the device row + bearer token
  GET  /v1/device/telegram/whitelist[/all]     LEGACY: per-account allowed set, DERIVED
                                               from that account's own rules
  POST /v1/device/telegram/chats               LEGACY: report the chats an account can see
  POST /v1/device/telegram/events              accountability events (append-only)
  GET  /v1/device/link-requests/pending        LEGACY stub: always empty

How the legacy whitelist is answered: the old client only opens a chat that is
in the set we return, and it cannot be told "open everything". But it still
reports every chat it can see, so we return exactly those reported chats that
that account's rules allow (`account_allows`). Old handsets therefore follow the
new model immediately, without waiting for the update. Drop this module's
telegram endpoints together with schema_legacy.sql once the old builds vanish.
"""
from __future__ import annotations

import json
import uuid
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..auth import new_device_token, require_device, utcnow_iso
from ..db import get_db
from .rules import account_allows

router = APIRouter(prefix="/v1/device", tags=["device"])

# ── Constants ─────────────────────────────────────────────────────────────
_MAX_CHATS_PER_REPORT = 500     # guard against oversized payloads
_MAX_EVENTS_PER_BATCH = 200

ChatKind = Literal["channel", "group", "private", "bot"]
# The legacy report vocabulary says "private" where the policy says "user".
_LEGACY_KIND_TO_POLICY = {"channel": "channel", "group": "group", "private": "user", "bot": "bot"}


# ── Pydantic models ───────────────────────────────────────────────────────
class CheckinBody(BaseModel):
    device_id: str = Field(min_length=1, max_length=255)
    brand: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    android_version: str | None = None
    sdk_int: int | None = None


class CheckinResult(BaseModel):
    token: str


class WhitelistChat(BaseModel):
    id: int                                  # Telegram int64 chat id
    kind: str
    label: str | None = None


class WhitelistBot(BaseModel):
    id: int                                  # Telegram int64 bot user id
    label: str | None = None


class WhitelistResult(BaseModel):
    version: int
    issued_at: str | None
    allowed_chats: list[WhitelistChat]
    allowed_bots: list[WhitelistBot]


class AccountWhitelist(BaseModel):
    tg_user_id: int
    supervised: bool
    version: int
    issued_at: str | None
    allowed_chats: list[WhitelistChat]
    allowed_bots: list[WhitelistBot]


class WhitelistAllResult(BaseModel):
    device_managed: bool
    accounts: list[AccountWhitelist]


class KnownChatIn(BaseModel):
    id: int
    kind: ChatKind
    title: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=64)


class PostChatsBody(BaseModel):
    chats: list[KnownChatIn] = Field(min_length=0, max_length=_MAX_CHATS_PER_REPORT)
    tg_user_id: int | None = None
    tg_username: str | None = Field(default=None, max_length=64)
    tg_name: str | None = Field(default=None, max_length=128)


class TelegramEventIn(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    detail: str | None = Field(default=None, max_length=1024)
    created_at: str | None = None


class PostEventsBody(BaseModel):
    events: list[TelegramEventIn] = Field(min_length=0, max_length=_MAX_EVENTS_PER_BATCH)


# ── Helpers ───────────────────────────────────────────────────────────────
def _clean(value: str | None, *, strip_at: bool = False) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if strip_at:
        trimmed = trimmed.lstrip("@")
    return trimmed or None


def _customer_id_or_none(db: psycopg.Connection, device_id: str) -> str | None:
    row = db.execute(
        "SELECT id FROM customers WHERE device_id = %s", (device_id,)
    ).fetchone()
    return row["id"] if row is not None else None


def _event_payload(detail: str | None, device_id: str) -> str:
    try:
        return json.dumps({"detail": detail, "device_id": device_id}, ensure_ascii=False)
    except (TypeError, ValueError):
        return "{}"


def build_account_whitelist(db: psycopg.Connection, tg_user_id: int | None) -> WhitelistResult:
    """LEGACY: the allowed set for one account = its reported chats that pass that
    account's own rules (ADR-002). Old clients re-apply the whole response on
    every poll, so `version` only needs to be monotonic."""
    from .rules import _version  # local import: same module family, avoids a cycle
    if tg_user_id is None:
        return WhitelistResult(version=0, issued_at=None, allowed_chats=[], allowed_bots=[])
    version = _version(db, tg_user_id)

    allowed_chats: list[WhitelistChat] = []
    allowed_bots: list[WhitelistBot] = []
    for row in db.execute(
        "SELECT chat_id, kind, title, username FROM telegram_known_chats "
        "WHERE tg_user_id = %s",
        (tg_user_id,),
    ):
        policy_kind = _LEGACY_KIND_TO_POLICY.get(row["kind"], row["kind"])
        if not account_allows(db, tg_user_id, row["chat_id"], policy_kind):
            continue
        if row["kind"] == "bot":
            allowed_bots.append(WhitelistBot(id=row["chat_id"], label=row["title"]))
        else:
            allowed_chats.append(WhitelistChat(id=row["chat_id"], kind=row["kind"], label=row["title"]))

    allowed_chats.sort(key=lambda c: c.id)
    allowed_bots.sort(key=lambda b: b.id)
    return WhitelistResult(
        version=version, issued_at=None,
        allowed_chats=allowed_chats, allowed_bots=allowed_bots,
    )


def record_known_chats(
    db: psycopg.Connection,
    customer_id: str,
    chats: list["KnownChatIn"],
    tg_user_id: int | None = None,
) -> None:
    """LEGACY: upsert the chats an old client can see, per (device, account)."""
    if not chats:
        return
    now = utcnow_iso()
    account = tg_user_id or 0
    rows = [
        (customer_id, account, chat.id, chat.kind, chat.title, chat.username, now, now)
        for chat in chats
    ]
    with db.cursor() as cur:
        cur.executemany(
            """INSERT INTO telegram_known_chats
                 (customer_id, tg_user_id, chat_id, kind, title, username,
                  first_seen_at, last_seen_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (customer_id, tg_user_id, chat_id)
               DO UPDATE SET
                 kind         = EXCLUDED.kind,
                 title        = EXCLUDED.title,
                 username     = EXCLUDED.username,
                 last_seen_at = EXCLUDED.last_seen_at""",
            rows,
        )
    db.commit()


# ── POST /v1/device/checkin ───────────────────────────────────────────────
@router.post("/checkin", response_model=CheckinResult)
def checkin(body: CheckinBody, db: psycopg.Connection = Depends(get_db)) -> CheckinResult:
    """Upsert the device row and return its bearer token (idempotent)."""
    now = utcnow_iso()
    existing = db.execute(
        "SELECT id FROM customers WHERE device_id = %s", (body.device_id,)
    ).fetchone()

    if existing is None:
        customer_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO customers
                 (id, device_id, brand, manufacturer, model, android_version,
                  sdk_int, last_seen_at, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (customer_id, body.device_id, body.brand, body.manufacturer, body.model,
             body.android_version, body.sdk_int, now, now, now),
        )
    else:
        db.execute(
            """UPDATE customers SET brand=%s, manufacturer=%s, model=%s,
                 android_version=%s, sdk_int=%s, last_seen_at=%s, updated_at=%s
               WHERE device_id=%s""",
            (body.brand, body.manufacturer, body.model, body.android_version,
             body.sdk_int, now, now, body.device_id),
        )

    token_row = db.execute(
        "SELECT token FROM device_tokens WHERE device_id = %s", (body.device_id,)
    ).fetchone()
    if token_row is None:
        token = new_device_token()
        db.execute(
            "INSERT INTO device_tokens (device_id, token, created_at, last_used_at) "
            "VALUES (%s, %s, %s, %s)",
            (body.device_id, token, now, now),
        )
    else:
        token = token_row["token"]

    db.commit()
    return CheckinResult(token=token)


# ── LEGACY stub: link requests (old clients poll this every 15 s) ─────────
@router.get("/link-requests/pending")
def legacy_link_requests(_: str = Depends(require_device)) -> dict[str, list]:
    """Supervision links no longer exist; keep old handsets quiet."""
    return {"requests": []}


# ── Telegram-scoped LEGACY endpoints ──────────────────────────────────────
tg_router = APIRouter(prefix="/telegram", tags=["telegram-device"])


@tg_router.get("/whitelist", response_model=WhitelistResult)
def get_whitelist(
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> WhitelistResult:
    row = db.execute(
        "SELECT tg_user_id FROM customers WHERE device_id = %s", (device_id,)
    ).fetchone()
    tg_user_id = row["tg_user_id"] if row else None
    return build_account_whitelist(db, tg_user_id)


@tg_router.get("/whitelist/all", response_model=WhitelistAllResult)
def get_whitelist_all(
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> WhitelistAllResult:
    """Every account on this device, each with its policy-derived allowed set.
    `supervised`/`device_managed` are always True: the old client treats an
    unsupervised account as locked, and we want it to apply the set we send."""
    cust = db.execute(
        "SELECT id, tg_user_id FROM customers WHERE device_id = %s", (device_id,)
    ).fetchone()
    if cust is None:
        return WhitelistAllResult(device_managed=True, accounts=[])

    tg_ids: set[int] = set()
    if cust["tg_user_id"] is not None:
        tg_ids.add(cust["tg_user_id"])
    for r in db.execute(
        "SELECT tg_user_id FROM customer_accounts WHERE customer_id = %s", (cust["id"],)
    ):
        tg_ids.add(r["tg_user_id"])

    accounts = []
    for tg in sorted(tg_ids):
        w = build_account_whitelist(db, tg)
        accounts.append(AccountWhitelist(
            tg_user_id=tg, supervised=True, version=w.version, issued_at=w.issued_at,
            allowed_chats=w.allowed_chats, allowed_bots=w.allowed_bots,
        ))
    return WhitelistAllResult(device_managed=True, accounts=accounts)


@tg_router.post("/chats")
def report_chats(
    body: PostChatsBody,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, bool]:
    """LEGACY: an old client reports the chats it can see. Needed only so the
    whitelist shim above knows what to allow; new clients never call this."""
    customer_id = _customer_id_or_none(db, device_id)
    if customer_id is None:
        return {"ok": True}
    if body.tg_user_id is not None:
        now = utcnow_iso()
        db.execute(
            "UPDATE customers SET tg_user_id = %s WHERE id = %s",
            (body.tg_user_id, customer_id),
        )
        db.execute(
            "INSERT INTO customer_accounts "
            "  (customer_id, tg_user_id, username, display_name, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (customer_id, tg_user_id) DO UPDATE SET "
            "  username     = COALESCE(EXCLUDED.username, customer_accounts.username), "
            "  display_name = COALESCE(EXCLUDED.display_name, customer_accounts.display_name), "
            "  updated_at   = EXCLUDED.updated_at",
            (customer_id, body.tg_user_id, _clean(body.tg_username, strip_at=True),
             _clean(body.tg_name), now, now),
        )
        db.commit()
    if body.chats:
        record_known_chats(db, customer_id, body.chats, body.tg_user_id)
    return {"ok": True}


@tg_router.post("/events")
def report_events(
    body: PostEventsBody,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, bool]:
    """Accountability events → append-only audit_log (blocked_chat, …)."""
    if not body.events:
        return {"ok": True}

    customer_id = _customer_id_or_none(db, device_id)
    rows = [
        (
            customer_id,
            "telegram",
            f"tg_{event.type}",
            None,
            _event_payload(event.detail, device_id),
            event.created_at or utcnow_iso(),
        )
        for event in body.events
    ]
    with db.cursor() as cur:
        cur.executemany(
            "INSERT INTO audit_log (customer_id, actor, action, target, payload, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            rows,
        )
    db.commit()
    return {"ok": True}


router.include_router(tg_router)
