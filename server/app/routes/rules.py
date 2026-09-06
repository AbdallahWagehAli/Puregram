"""Per-account chat rules — Puregram's control model since ADR-002 (2026-09-05).

There is no curated global list any more. Every user governs their own client:

  * Kinds: people (non-bot users) always open. Channels, bots and groups are
    closed by default and open only if the user allowed them.
  * `allow` is reversible — the user may withdraw it at any time.
  * `block` is PERMANENT. Once a chat is blocked it can never be allowed again,
    by anyone, on any device. That one-way ratchet is the whole point: it lets
    someone bind their future self in a moment of resolve. It is enforced HERE,
    server-side, so a tampered client cannot undo it by syncing a fake state.

The rules live on the server keyed by the Telegram account id so they follow the
account across the Android and desktop clients with nothing for the user to move.

  GET    /v1/rules?tg_user_id=…          the account's rules (device bearer token)
  POST   /v1/rules                       apply one rule (ratchet enforced)
  DELETE /v1/rules/{chat_id}?tg_user_id= withdraw an ALLOW (never a block)
  DELETE /v1/rules?tg_user_id=…          SCHEDULE erasure (60-day wait, cancellable)
  POST   /v1/rules/erase/cancel          call off a scheduled erasure

Chat ids use the Telegram-Android dialog-id encoding: user/bot `+id`, group and
channel `-id` (plain negation, never the Bot-API `-100…` form).

ACCOUNT BINDING: the bearer token proves WHICH DEVICE is calling, but not that
it is signed into the Telegram account it claims — Telegram gives a third-party
client nothing our server could verify. So the first device to claim an account
owns it, and any later device stays `pending` until an already-active device
approves it (or the waiting period elapses). See `require_account_device`.
"""
from __future__ import annotations

from typing import Any, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from ..auth import iso_in_days, require_device, utcnow_iso
from ..db import get_db

router = APIRouter(prefix="/v1", tags=["rules"])

Kind = Literal["channel", "bot", "group", "user"]
Rule = Literal["allow", "block"]

# Kinds that are closed until the user opens them. People are never gated.
GATED_KINDS: tuple[str, ...] = ("channel", "bot", "group")
_MAX_RULES_PER_ACCOUNT = 5000
# Erasure is SCHEDULED, never immediate. Google Play requires a deletion path;
# it does not require it to be instant. Deleting the rules also clears the
# permanent blocks, so an instant button would be a one-tap escape from the
# ratchet at the exact moment someone most wants one. The blocks stay enforced
# for the whole wait and the user may cancel at any time.
_ERASURE_DELAY_DAYS = 60
# A device claiming an account another device already owns waits this long for
# approval before it is trusted anyway (POLICY_SPEC §8).
_DEVICE_CLAIM_DELAY_DAYS = 7


class RuleIn(BaseModel):
    tg_user_id: int = Field(gt=0)
    chat_id: int
    kind: Kind
    rule: Rule
    username: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=128)


class RuleOut(BaseModel):
    chat_id: int
    kind: str
    rule: str
    username: str | None
    title: str | None
    created_at: str


class RulesResult(BaseModel):
    tg_user_id: int
    version: int
    gated_kinds: list[str]
    rules: list[RuleOut]
    # Set while an erasure is counting down, so the clients can show
    # "your data will be deleted on <date>" with a Cancel action.
    erasure_requested_at: str | None = None
    erasure_effective_at: str | None = None


def _clean(value: str | None, *, strip_at: bool = False) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if strip_at:
        trimmed = trimmed.lstrip("@")
    return trimmed or None


def _version(db: psycopg.Connection, tg_user_id: int) -> int:
    row = db.execute(
        "SELECT version FROM account_rules_meta WHERE tg_user_id = %s", (tg_user_id,)
    ).fetchone()
    return int(row["version"]) if row else 0


def _bump(db: psycopg.Connection, tg_user_id: int) -> int:
    row = db.execute(
        "INSERT INTO account_rules_meta (tg_user_id, version, updated_at) "
        "VALUES (%s, 1, %s) "
        "ON CONFLICT (tg_user_id) DO UPDATE SET "
        "  version = account_rules_meta.version + 1, updated_at = EXCLUDED.updated_at "
        "RETURNING version",
        (tg_user_id, utcnow_iso()),
    ).fetchone()
    return int(row["version"])


# ── Which devices may act for an account ───────────────────────────────────
class DeviceClaimPending(HTTPException):
    """Raised as 409 so a client can tell "waiting for approval" apart from a
    plain refusal and show the right screen."""

    def __init__(self, auto_approve_at: str) -> None:
        super().__init__(
            status.HTTP_409_CONFLICT,
            {"error": "device_claim_pending", "auto_approve_at": auto_approve_at},
        )


def require_account_device(
    db: psycopg.Connection, device_id: str, tg_user_id: int
) -> None:
    """Authorise this device to act for this account, or raise.

    Trust on first use: if nobody owns the account yet, the caller becomes its
    first active device. Otherwise an unknown device is recorded as `pending`
    (auto-approving after `_DEVICE_CLAIM_DELAY_DAYS`) and refused until then.
    """
    now = utcnow_iso()
    row = db.execute(
        "SELECT status, auto_approve_at FROM account_devices "
        "WHERE tg_user_id = %s AND device_id = %s",
        (tg_user_id, device_id),
    ).fetchone()

    if row is not None:
        if row["status"] == "active":
            return
        if row["status"] == "denied":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "this device was denied for this account"
            )
        # Pending: promote once the waiting period has elapsed.
        if row["auto_approve_at"] and row["auto_approve_at"] <= now:
            db.execute(
                "UPDATE account_devices SET status = 'active', updated_at = %s "
                "WHERE tg_user_id = %s AND device_id = %s",
                (now, tg_user_id, device_id),
            )
            db.commit()
            return
        raise DeviceClaimPending(row["auto_approve_at"])

    owners = db.execute(
        "SELECT count(*) AS n FROM account_devices "
        "WHERE tg_user_id = %s AND status = 'active'",
        (tg_user_id,),
    ).fetchone()["n"]
    model = db.execute(
        "SELECT model FROM customers WHERE device_id = %s", (device_id,)
    ).fetchone()
    first = owners == 0
    auto_at = None if first else iso_in_days(_DEVICE_CLAIM_DELAY_DAYS)
    db.execute(
        "INSERT INTO account_devices "
        "  (tg_user_id, device_id, status, model, created_at, updated_at, auto_approve_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (tg_user_id, device_id) DO NOTHING",
        (tg_user_id, device_id, "active" if first else "pending",
         model["model"] if model else None, now, now, auto_at),
    )
    db.commit()
    if first:
        return
    raise DeviceClaimPending(auto_at)


def run_due_erasures(db: psycopg.Connection, tg_user_id: int | None = None) -> int:
    """Carry out every erasure whose waiting period has elapsed.

    Timestamps are zero-padded ISO-8601 UTC, so a plain string compare is
    chronological. Called from load_rules (i.e. on every rules request) and at
    boot, instead of running a scheduler: clients poll often enough that a due
    erasure executes within a minute of falling due.
    """
    now = utcnow_iso()
    if tg_user_id is None:
        due = db.execute(
            "SELECT tg_user_id FROM account_erasures "
            "WHERE status = 'pending' AND effective_at <= %s", (now,)).fetchall()
    else:
        due = db.execute(
            "SELECT tg_user_id FROM account_erasures "
            "WHERE status = 'pending' AND effective_at <= %s AND tg_user_id = %s",
            (now, tg_user_id)).fetchall()
    for row in due:
        account = row["tg_user_id"]
        db.execute("DELETE FROM account_rules WHERE tg_user_id = %s", (account,))
        db.execute("DELETE FROM account_rules_meta WHERE tg_user_id = %s", (account,))
        db.execute(
            "UPDATE account_erasures SET status = 'done', updated_at = %s "
            "WHERE tg_user_id = %s", (utcnow_iso(), account))
    if due:
        db.commit()
    return len(due)


def _pending_erasure(db: psycopg.Connection, tg_user_id: int) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT requested_at, effective_at FROM account_erasures "
        "WHERE tg_user_id = %s AND status = 'pending'", (tg_user_id,)).fetchone()
    return dict(row) if row else None


def load_rules(db: psycopg.Connection, tg_user_id: int) -> RulesResult:
    run_due_erasures(db, tg_user_id)
    rows = db.execute(
        "SELECT chat_id, kind, rule, username, title, created_at "
        "FROM account_rules WHERE tg_user_id = %s ORDER BY created_at DESC, chat_id",
        (tg_user_id,),
    ).fetchall()
    pending = _pending_erasure(db, tg_user_id)
    return RulesResult(
        tg_user_id=tg_user_id,
        version=_version(db, tg_user_id),
        gated_kinds=list(GATED_KINDS),
        rules=[RuleOut(**dict(r)) for r in rows],
        erasure_requested_at=pending["requested_at"] if pending else None,
        erasure_effective_at=pending["effective_at"] if pending else None,
    )


def account_allows(
    db: psycopg.Connection, tg_user_id: int, chat_id: int, kind: str
) -> bool:
    """Server-side mirror of the client decision rule (POLICY_SPEC §3).

    Used by the legacy device shim so pre-ADR-002 clients follow the same rules.
    """
    row = db.execute(
        "SELECT rule FROM account_rules WHERE tg_user_id = %s AND chat_id = %s",
        (tg_user_id, chat_id),
    ).fetchone()
    if row is not None and row["rule"] == "block":
        return False
    if kind not in GATED_KINDS:
        return True
    return row is not None and row["rule"] == "allow"


@router.get("/rules", response_model=RulesResult)
def get_rules(
    tg_user_id: int = Query(gt=0),
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> RulesResult:
    """Every rule this account has set, on any of its devices."""
    require_account_device(db, device_id, tg_user_id)
    return load_rules(db, tg_user_id)


@router.post("/rules", response_model=RulesResult)
def put_rule(
    body: RuleIn,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> RulesResult:
    """Apply one rule.

    The ratchet lives in the ON CONFLICT clause: a row already at `block` stays
    at `block` whatever is posted, so an allow can never overwrite a block — not
    from a stale device, not from a patched client.
    """
    if body.chat_id == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "chat_id must not be 0")
    require_account_device(db, device_id, body.tg_user_id)

    count = db.execute(
        "SELECT count(*) AS n FROM account_rules WHERE tg_user_id = %s", (body.tg_user_id,)
    ).fetchone()["n"]
    existing = db.execute(
        "SELECT rule FROM account_rules WHERE tg_user_id = %s AND chat_id = %s",
        (body.tg_user_id, body.chat_id),
    ).fetchone()
    if existing is None and count >= _MAX_RULES_PER_ACCOUNT:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"this account already has {_MAX_RULES_PER_ACCOUNT} rules",
        )

    now = utcnow_iso()
    db.execute(
        "INSERT INTO account_rules "
        "  (tg_user_id, chat_id, kind, username, title, rule, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (tg_user_id, chat_id) DO UPDATE SET "
        # The ratchet: block is final.
        "  rule = CASE WHEN account_rules.rule = 'block' THEN 'block' ELSE EXCLUDED.rule END, "
        "  kind = EXCLUDED.kind, "
        "  username = COALESCE(EXCLUDED.username, account_rules.username), "
        "  title = COALESCE(EXCLUDED.title, account_rules.title), "
        "  updated_at = EXCLUDED.updated_at",
        (body.tg_user_id, body.chat_id, body.kind, _clean(body.username, strip_at=True),
         _clean(body.title), body.rule, now, now),
    )
    _bump(db, body.tg_user_id)
    db.commit()
    return load_rules(db, body.tg_user_id)


@router.delete("/rules/{chat_id}", response_model=RulesResult)
def withdraw_rule(
    chat_id: int,
    tg_user_id: int = Query(gt=0),
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> RulesResult:
    """Withdraw an ALLOW (a tightening, always permitted).

    Refuses to remove a block: undoing a block is exactly what the ratchet
    forbids, and deleting the row would be a back door to the same effect.
    """
    require_account_device(db, device_id, tg_user_id)
    row = db.execute(
        "SELECT rule FROM account_rules WHERE tg_user_id = %s AND chat_id = %s",
        (tg_user_id, chat_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such rule")
    if row["rule"] == "block":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "a blocked chat cannot be unblocked",
        )
    db.execute(
        "DELETE FROM account_rules WHERE tg_user_id = %s AND chat_id = %s",
        (tg_user_id, chat_id),
    )
    _bump(db, tg_user_id)
    db.commit()
    return load_rules(db, tg_user_id)


@router.delete("/rules")
def schedule_erasure(
    tg_user_id: int = Query(gt=0),
    confirm: str = Query(..., description="must be the literal string 'erase'"),
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """SCHEDULE erasure of everything stored for this account.

    Recorded now, carried out after the waiting period. Re-requesting does not
    shorten a countdown already running.
    """
    if confirm != "erase":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "confirm=erase is required")
    require_account_device(db, device_id, tg_user_id)
    existing = _pending_erasure(db, tg_user_id)
    if existing is not None:
        return {"scheduled": True, "already_pending": True,
                "delay_days": _ERASURE_DELAY_DAYS, **existing}
    now = utcnow_iso()
    effective = iso_in_days(_ERASURE_DELAY_DAYS)
    db.execute(
        "INSERT INTO account_erasures "
        "  (tg_user_id, status, requested_at, effective_at, updated_at) "
        "VALUES (%s, 'pending', %s, %s, %s) "
        "ON CONFLICT (tg_user_id) DO UPDATE SET "
        "  status = 'pending', requested_at = EXCLUDED.requested_at, "
        "  effective_at = EXCLUDED.effective_at, updated_at = EXCLUDED.updated_at",
        (tg_user_id, now, effective, now),
    )
    db.commit()
    return {"scheduled": True, "already_pending": False, "requested_at": now,
            "effective_at": effective, "delay_days": _ERASURE_DELAY_DAYS}


@router.post("/rules/erase/cancel", response_model=RulesResult)
def cancel_erasure(
    tg_user_id: int = Query(gt=0),
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> RulesResult:
    """Call off a scheduled erasure. Always permitted — cancelling keeps data,
    which is the safe direction."""
    require_account_device(db, device_id, tg_user_id)
    db.execute(
        "UPDATE account_erasures SET status = 'cancelled', updated_at = %s "
        "WHERE tg_user_id = %s AND status = 'pending'",
        (utcnow_iso(), tg_user_id),
    )
    db.commit()
    return load_rules(db, tg_user_id)


@router.get("/rules/meta")
def get_meta(
    tg_user_id: int = Query(gt=0),
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Cheap poll: the version, plus any device claim waiting on this account
    so an already-trusted device can surface "a new device wants to sync"."""
    require_account_device(db, device_id, tg_user_id)
    waiting = db.execute(
        "SELECT device_id, model, auto_approve_at FROM account_devices "
        "WHERE tg_user_id = %s AND status = 'pending' ORDER BY created_at",
        (tg_user_id,),
    ).fetchall()
    return {
        "tg_user_id": tg_user_id,
        "version": _version(db, tg_user_id),
        "pending_devices": [dict(r) for r in waiting],
    }


@router.post("/rules/devices/{claim_device_id}/approve", response_model=RulesResult)
def approve_device(
    claim_device_id: str,
    tg_user_id: int = Query(gt=0),
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> RulesResult:
    """Approve another device's claim on this account. Only an already-active
    device may do this — which is what makes the claim gate mean anything."""
    require_account_device(db, device_id, tg_user_id)
    updated = db.execute(
        "UPDATE account_devices SET status = 'active', updated_at = %s "
        "WHERE tg_user_id = %s AND device_id = %s AND status = 'pending' "
        "RETURNING device_id",
        (utcnow_iso(), tg_user_id, claim_device_id),
    ).fetchone()
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no pending claim for that device")
    db.commit()
    return load_rules(db, tg_user_id)


@router.post("/rules/devices/{claim_device_id}/deny", response_model=RulesResult)
def deny_device(
    claim_device_id: str,
    tg_user_id: int = Query(gt=0),
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> RulesResult:
    """Deny a claim for good — this also cancels its auto-approval."""
    require_account_device(db, device_id, tg_user_id)
    db.execute(
        "UPDATE account_devices SET status = 'denied', auto_approve_at = NULL, "
        "  updated_at = %s "
        "WHERE tg_user_id = %s AND device_id = %s AND status = 'pending'",
        (utcnow_iso(), tg_user_id, claim_device_id),
    )
    db.commit()
    return load_rules(db, tg_user_id)
