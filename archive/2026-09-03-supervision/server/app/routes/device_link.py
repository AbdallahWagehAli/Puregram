"""Puregram device linking — /v1/device/pairing/* and /v1/device/supervisors/*.

The managed phone drives the "Link a supervisor" flow entirely with its existing
per-device bearer token:

  POST   /v1/device/pairing/start                     mint a short-lived code + QR
  GET    /v1/device/pairing/status                    poll a pairing by its pair_id
  POST   /v1/device/pairing/confirm                   approve the named supervisor
  POST   /v1/device/pairing/reject                    reject a claimed pairing
  POST   /v1/device/pairing/cancel                    abort a still-pending pairing
  GET    /v1/device/supervisors                       who currently supervises me
  POST   /v1/device/supervisors/{id}/unlink-request   ask a supervisor to unlink

A supervisor redeems the code from the web app (POST /v1/control/pairings/redeem),
which only marks the pairing 'claimed'. The control_link is created HERE, on the
device, once the managed user CONFIRMS the named supervisor — so consent always
lives on the handset. Timestamps are ISO-8601 UTC TEXT (lexicographically
comparable). All queries are parameterized.
"""
from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..accounts import device_account_ids, provision_tg_user
from ..auth import require_device, utcnow_iso
from ..db import get_db
from ..pairing import format_code, generate_code, hash_code

router = APIRouter(prefix="/v1/device", tags=["device-link"])

# ── Constants ─────────────────────────────────────────────────────────────
# The code is a "كود متغير" (rotating code): short 60s TTL, and the managed phone
# auto-mints a fresh one on expiry. A tight window plus single-use redemption keeps
# the brute-force surface tiny.
_PAIRING_TTL_SECONDS = 60
# Once a supervisor CLAIMS a code, the managed user needs a comfortable window to
# see the "Allow <name>?" prompt and confirm — independent of the 60s code TTL.
_CONFIRM_TTL_SECONDS = 600
_MAX_PENDING_PER_DEVICE = 3        # cap live codes so a device can't spam-mint
_CODE_ALLOC_ATTEMPTS = 5           # retry budget for the (astronomically rare) hash clash
_REDEEM_WINDOW_S = 300.0           # per-device redeem throttle window
_REDEEM_MAX_ATTEMPTS = 15          # ...and its cap (blunts code brute-forcing)
_redeem_hits: dict[str, deque[float]] = defaultdict(deque)
# The code rides in the URL fragment, which browsers never send to the server, so
# the secret never lands in an nginx access log even when the supervisor scans it.
_PAIR_URL_TEMPLATE = "https://puregram.app/app/pair#%s"


# ── Pydantic models ───────────────────────────────────────────────────────
class PairRef(BaseModel):
    pair_id: str = Field(min_length=1, max_length=64)


class RedeemBody(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class StartResult(BaseModel):
    pair_id: str
    code: str
    qr_url: str
    expires_at: str


# ── Helpers ───────────────────────────────────────────────────────────────
def _iso_in_seconds(seconds: int) -> str:
    """A UTC ISO timestamp `seconds` from now, matching utcnow_iso()'s format so
    the two compare correctly with a plain string `<=` (no parsing)."""
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def _throttle_redeem(key: str) -> None:
    """Per-device sliding-window throttle for code redemption (in-memory; a single
    worker serves the API so a process-local window is sufficient)."""
    now = time.monotonic()
    hits = _redeem_hits[key]
    while hits and now - hits[0] > _REDEEM_WINDOW_S:
        hits.popleft()
    if len(hits) >= _REDEEM_MAX_ATTEMPTS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts")
    hits.append(now)


def _customer(db: psycopg.Connection, device_id: str) -> dict | None:
    return db.execute(
        "SELECT id, tg_user_id, brand, model FROM customers WHERE device_id = %s",
        (device_id,),
    ).fetchone()


def _device_label(customer: dict) -> str:
    """A human-friendly managed-account name derived from the device model."""
    parts = [p for p in (customer["brand"], customer["model"]) if p]
    return " ".join(parts) if parts else "Puregram device"


def _mask_email(email: str | None) -> str | None:
    """Show only the first character + domain, so the phone can name the
    supervisor without exposing their full address on a shared screen."""
    if not email or "@" not in email:
        return None
    name, _, domain = email.partition("@")
    return f"{name[0] if name else ''}***@{domain}"


def _expire_stale(db: psycopg.Connection, device_id: str) -> None:
    """Lazily flip this device's past-TTL pending/claimed codes to 'expired' so
    the pending cap and status reads stay honest without a cron."""
    db.execute(
        "UPDATE control_pairings SET status = 'expired' "
        "WHERE device_id = %s AND status IN ('pending','claimed') AND expires_at <= %s",
        (device_id, utcnow_iso()),
    )


def _audit_device(
    db: psycopg.Connection, customer_id: str | None, action: str,
    target: str | None, payload: dict,
) -> None:
    db.execute(
        "INSERT INTO audit_log (customer_id, actor, action, target, payload, created_at) "
        "VALUES (%s, 'device', %s, %s, %s, %s)",
        (customer_id, action, target, json.dumps(payload), utcnow_iso()),
    )


# The passwordless managed control_user lives in one place now (accounts.py), so
# the panel's link flow and this device flow can never diverge on how an account
# is provisioned. Kept under the old name for the modules that import it.
_provision_managed_user = provision_tg_user


def _supervisor_public(db: psycopg.Connection, supervisor_id: int) -> dict | None:
    row = db.execute(
        "SELECT display_name, email FROM control_users WHERE id = %s",
        (supervisor_id,),
    ).fetchone()
    if row is None:
        return None
    return {"display_name": row["display_name"], "email_masked": _mask_email(row["email"])}


# ── POST /v1/device/pairing/start ─────────────────────────────────────────
@router.post("/pairing/start", response_model=StartResult)
def start_pairing(
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> StartResult:
    """Mint a short-lived pairing code + QR for this device's Telegram account.

    409 `link_needs_tg_login` until the account has been reported (tg_user_id);
    429 `too_many_pending_codes` past the live-code cap.
    """
    customer = _customer(db, device_id)
    if customer is None or customer["tg_user_id"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "link_needs_tg_login")

    _expire_stale(db, device_id)
    pending = db.execute(
        "SELECT COUNT(*) AS n FROM control_pairings "
        "WHERE device_id = %s AND status IN ('pending','claimed')",
        (device_id,),
    ).fetchone()["n"]
    if pending >= _MAX_PENDING_PER_DEVICE:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_pending_codes")

    code_hash = None
    for _ in range(_CODE_ALLOC_ATTEMPTS):
        candidate = generate_code()
        candidate_hash = hash_code(candidate)
        if db.execute(
            "SELECT 1 FROM control_pairings WHERE code_hash = %s", (candidate_hash,)
        ).fetchone() is None:
            code, code_hash = candidate, candidate_hash
            break
    if code_hash is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "could_not_allocate_code"
        )

    pair_id = str(uuid.uuid4())
    now, expires_at = utcnow_iso(), _iso_in_seconds(_PAIRING_TTL_SECONDS)
    db.execute(
        "INSERT INTO control_pairings "
        "  (pair_id, code_hash, device_id, tg_user_id, status, created_at, expires_at) "
        "VALUES (%s, %s, %s, %s, 'pending', %s, %s)",
        (pair_id, code_hash, device_id, customer["tg_user_id"], now, expires_at),
    )
    _audit_device(db, customer["id"], "pairing_start", None, {"pair_id": pair_id})
    db.commit()

    display_code = format_code(code)
    return StartResult(
        pair_id=pair_id,
        code=display_code,
        qr_url=_PAIR_URL_TEMPLATE % display_code,
        expires_at=expires_at,
    )


# ── GET /v1/device/pairing/status ─────────────────────────────────────────
@router.get("/pairing/status")
def pairing_status(
    pair_id: str,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """Poll a pairing by its opaque pair_id (scoped to the calling device).

    Drives the waiting → claimed → confirmed UI; on 'claimed' it returns the
    supervisor's name for the on-device confirmation sheet.
    """
    _expire_stale(db, device_id)
    db.commit()
    pairing = db.execute(
        "SELECT status, expires_at, supervisor_user_id FROM control_pairings "
        "WHERE pair_id = %s AND device_id = %s",
        (pair_id, device_id),
    ).fetchone()
    if pairing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pairing_not_found")
    supervisor = (
        _supervisor_public(db, pairing["supervisor_user_id"])
        if pairing["supervisor_user_id"] is not None
        else None
    )
    return {
        "status": pairing["status"],
        "expires_at": pairing["expires_at"],
        "supervisor": supervisor,
    }


# ── GET /v1/device/pairing/pending ────────────────────────────────────────
@router.get("/pairing/pending")
def pairing_pending(
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """The most recent code THIS device minted that a supervisor has already
    CLAIMED and that is awaiting the managed user's confirmation — found by device,
    NOT by pair_id, so the "Allow <name>?" prompt shows even if the visible code
    has since auto-rotated to a fresh one."""
    _expire_stale(db, device_id)
    db.commit()
    row = db.execute(
        "SELECT pair_id, supervisor_user_id FROM control_pairings "
        "WHERE device_id = %s AND status = 'claimed' "
        "ORDER BY claimed_at DESC NULLS LAST LIMIT 1",
        (device_id,),
    ).fetchone()
    if row is None:
        return {"pair_id": None, "supervisor": None}
    supervisor = (
        _supervisor_public(db, row["supervisor_user_id"])
        if row["supervisor_user_id"] is not None else None
    )
    return {"pair_id": row["pair_id"], "supervisor": supervisor}


# ── POST /v1/device/pairing/confirm ───────────────────────────────────────
@router.post("/pairing/confirm")
def confirm_pairing(
    body: PairRef,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """The managed user approves the supervisor who claimed the code → the link
    goes active. Consent is proven by the device token, so this is the moment
    supervision actually begins.
    """
    customer = _customer(db, device_id)
    if customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_device")
    _expire_stale(db, device_id)
    pairing = db.execute(
        "SELECT id, tg_user_id, status, supervisor_user_id FROM control_pairings "
        "WHERE pair_id = %s AND device_id = %s",
        (body.pair_id, device_id),
    ).fetchone()
    if pairing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pairing_not_found")
    if pairing["status"] == "expired":
        raise HTTPException(status.HTTP_410_GONE, "code_expired")
    if pairing["status"] != "claimed" or pairing["supervisor_user_id"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_awaiting_confirmation")
    # Re-verify the account hasn't changed since the code was minted.
    if customer["tg_user_id"] != pairing["tg_user_id"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "account_changed")

    supervisor_id = pairing["supervisor_user_id"]
    managed_id = _provision_managed_user(db, pairing["tg_user_id"], _device_label(customer))
    if managed_id == supervisor_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "cannot_supervise_self")

    now = utcnow_iso()
    db.execute(
        "INSERT INTO control_links "
        "  (manager_user_id, managed_user_id, status, created_at, updated_at) "
        "VALUES (%s, %s, 'active', %s, %s) "
        "ON CONFLICT (manager_user_id, managed_user_id) "
        "DO UPDATE SET status = 'active', updated_at = EXCLUDED.updated_at",
        (supervisor_id, managed_id, now, now),
    )
    db.execute(
        "UPDATE control_pairings SET status = 'confirmed', confirmed_at = %s WHERE id = %s",
        (now, pairing["id"]),
    )
    _audit_device(
        db, customer["id"], "pairing_confirm", str(supervisor_id),
        {"managed_user_id": managed_id},
    )
    db.commit()
    return {"ok": True, "supervisor": _supervisor_public(db, supervisor_id)}


# ── POST /v1/device/pairing/reject | /cancel ──────────────────────────────
@router.post("/pairing/reject")
def reject_pairing(
    body: PairRef,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """The managed user declines a supervisor who already claimed the code."""
    cur = db.execute(
        "UPDATE control_pairings SET status = 'rejected' "
        "WHERE pair_id = %s AND device_id = %s AND status = 'claimed'",
        (body.pair_id, device_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_rejectable")
    db.commit()
    return {"ok": True}


@router.post("/pairing/cancel")
def cancel_pairing(
    body: PairRef,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """The managed user aborts a code before any supervisor claims it."""
    cur = db.execute(
        "UPDATE control_pairings SET status = 'cancelled' "
        "WHERE pair_id = %s AND device_id = %s AND status = 'pending'",
        (body.pair_id, device_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_cancellable")
    db.commit()
    return {"ok": True}


# ── POST /v1/device/pairing/redeem  (supervisor side, device-authed) ──────
@router.post("/pairing/redeem")
def redeem_pairing(
    body: RedeemBody,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """A SUPERVISOR device redeems a code shown on a managed phone.

    Identity is the device itself: the caller's Telegram account is auto-provisioned
    a passwordless control_user (the supervisor), then the pairing is atomically
    claimed. The control_link is still created on the managed handset via
    /pairing/confirm — consent stays there. Errors: 409 `link_needs_tg_login`
    (supervisor not logged in), 404 `invalid_code`, 410 `code_expired`/
    `code_unavailable`, 409 `code_already_used`, 422 `cannot_supervise_self`,
    429 `too_many_attempts`.
    """
    _throttle_redeem(device_id)

    customer = _customer(db, device_id)
    if customer is None or customer["tg_user_id"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "link_needs_tg_login")
    supervisor_tg = customer["tg_user_id"]
    supervisor_id = _provision_managed_user(db, supervisor_tg, _device_label(customer))

    pairing = db.execute(
        "SELECT id, device_id, tg_user_id, status, supervisor_user_id, expires_at "
        "FROM control_pairings WHERE code_hash = %s",
        (hash_code(body.code),),
    ).fetchone()
    if pairing is None:
        db.commit()  # persist the just-provisioned supervisor row
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invalid_code")

    now = utcnow_iso()
    if pairing["status"] in ("pending", "claimed") and pairing["expires_at"] <= now:
        db.execute(
            "UPDATE control_pairings SET status = 'expired' "
            "WHERE id = %s AND status IN ('pending','claimed')",
            (pairing["id"],),
        )
        db.commit()
        raise HTTPException(status.HTTP_410_GONE, "code_expired")

    if supervisor_tg == pairing["tg_user_id"]:
        db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "cannot_supervise_self")

    managed_name = None
    managed_customer = _customer(db, pairing["device_id"])
    if managed_customer is not None:
        managed_name = _device_label(managed_customer)

    if pairing["status"] == "claimed":
        # Idempotent for the same supervisor re-scanning; otherwise it's taken.
        if pairing["supervisor_user_id"] == supervisor_id:
            db.commit()
            return {"ok": True, "status": "claimed", "awaiting_confirmation": True,
                    "managed_name": managed_name}
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "code_already_used")
    if pairing["status"] != "pending":
        db.commit()
        raise HTTPException(status.HTTP_410_GONE, "code_unavailable")

    # Atomic single-use claim: only the first redeemer of a still-pending code wins.
    # Extend expires_at to the confirm window so the managed user has time to approve
    # even though the visible code rotates every 60s.
    cur = db.execute(
        "UPDATE control_pairings SET status = 'claimed', supervisor_user_id = %s, "
        "claimed_at = %s, expires_at = %s WHERE id = %s AND status = 'pending'",
        (supervisor_id, now, _iso_in_seconds(_CONFIRM_TTL_SECONDS), pairing["id"]),
    )
    if cur.rowcount == 0:
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "code_already_used")
    _audit_device(db, customer["id"], "pairing_redeem", str(pairing["tg_user_id"]),
                  {"supervisor_user_id": supervisor_id})
    db.commit()
    return {"ok": True, "status": "claimed", "awaiting_confirmation": True,
            "managed_name": managed_name}


# ── Panel-initiated link requests (notification flow) ─────────────────────
# Supervision UI no longer exists inside the messenger apps: the supervisor sends
# the request from the web panel, and the handset surfaces it as a NOTIFICATION
# carrying the verification code plus approve/decline actions. Consent still
# lives on the handset — only its own bearer token can approve.
def _device_accounts(db: psycopg.Connection, device_id: str) -> tuple[str | None, list[int]]:
    """This device's customer id and every Telegram account seen on it."""
    customer = _customer(db, device_id)
    if customer is None:
        return None, []
    accounts = set(device_account_ids(db, customer["id"]))
    if customer["tg_user_id"] is not None:
        accounts.add(customer["tg_user_id"])
    return customer["id"], sorted(accounts)


def _lapse_expired_requests(db: psycopg.Connection, target_ids: list[int]) -> None:
    """Cancel past-deadline pending requests so a stale one never pops a
    notification days later."""
    if not target_ids:
        return
    db.execute(
        "UPDATE control_link_requests SET status = 'cancelled', updated_at = %s "
        "WHERE target_user_id = ANY(%s) AND status = 'pending' "
        "  AND expires_at IS NOT NULL AND expires_at <= %s",
        (utcnow_iso(), target_ids, utcnow_iso()),
    )


def _managed_user_ids(db: psycopg.Connection, tg_ids: list[int]) -> dict[int, int]:
    """Map control_users.id → tg_user_id for the accounts on this device."""
    if not tg_ids:
        return {}
    rows = db.execute(
        "SELECT id, tg_user_id FROM control_users WHERE tg_user_id = ANY(%s)",
        (tg_ids,),
    ).fetchall()
    return {r["id"]: r["tg_user_id"] for r in rows}


@router.get("/link-requests/pending")
def pending_link_requests(
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """Live supervision requests aimed at any account on this device.

    The client polls this on its existing whitelist loop and raises one
    notification per request id. Returns `{"requests": []}` (never 404) so a
    device with nothing pending costs one cheap round-trip.
    """
    customer_id, tg_ids = _device_accounts(db, device_id)
    if customer_id is None or not tg_ids:
        return {"requests": []}

    managed = _managed_user_ids(db, tg_ids)
    if not managed:
        return {"requests": []}
    _lapse_expired_requests(db, list(managed))
    db.commit()

    rows = db.execute(
        "SELECT r.id, r.code, r.expires_at, r.created_at, r.target_user_id, "
        "       u.display_name, u.email "
        "FROM control_link_requests r "
        "JOIN control_users u ON u.id = r.requester_user_id "
        "WHERE r.target_user_id = ANY(%s) AND r.status = 'pending' "
        "ORDER BY r.created_at DESC LIMIT 5",
        (list(managed),),
    ).fetchall()
    return {
        "requests": [
            {
                "id": r["id"],
                "code": r["code"],
                "expires_at": r["expires_at"],
                "created_at": r["created_at"],
                "tg_user_id": managed[r["target_user_id"]],
                "supervisor": {
                    "display_name": r["display_name"],
                    "email_masked": _mask_email(r["email"]),
                },
            }
            for r in rows
        ]
    }


def _decide_link_request(
    db: psycopg.Connection, device_id: str, request_id: int, approve: bool
) -> dict:
    """Shared body of approve/decline: authorize, then settle the request.

    403 unless the request targets an account logged in on THIS device, so a
    device token can never approve supervision over somebody else.
    """
    customer_id, tg_ids = _device_accounts(db, device_id)
    if customer_id is None or not tg_ids:
        raise HTTPException(status.HTTP_409_CONFLICT, "link_needs_tg_login")
    managed = _managed_user_ids(db, tg_ids)

    req = db.execute(
        "SELECT id, requester_user_id, target_user_id, status, expires_at "
        "FROM control_link_requests WHERE id = %s",
        (request_id,),
    ).fetchone()
    if req is None or req["target_user_id"] not in managed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not_your_request")
    if req["status"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "request_not_pending")

    now = utcnow_iso()
    if req["expires_at"] is not None and req["expires_at"] <= now:
        db.execute(
            "UPDATE control_link_requests SET status = 'cancelled', updated_at = %s "
            "WHERE id = %s",
            (now, request_id),
        )
        db.commit()
        raise HTTPException(status.HTTP_410_GONE, "request_expired")

    if not approve:
        db.execute(
            "UPDATE control_link_requests SET status = 'declined', updated_at = %s "
            "WHERE id = %s",
            (now, request_id),
        )
        _audit_device(db, customer_id, "link_request_decline", str(req["requester_user_id"]), {})
        db.commit()
        return {"ok": True, "status": "declined"}

    db.execute(
        "INSERT INTO control_links "
        "  (manager_user_id, managed_user_id, status, created_at, updated_at) "
        "VALUES (%s, %s, 'active', %s, %s) "
        "ON CONFLICT (manager_user_id, managed_user_id) "
        "DO UPDATE SET status = 'active', updated_at = EXCLUDED.updated_at",
        (req["requester_user_id"], req["target_user_id"], now, now),
    )
    db.execute(
        "UPDATE control_link_requests SET status = 'approved', updated_at = %s WHERE id = %s",
        (now, request_id),
    )
    _audit_device(db, customer_id, "link_request_approve", str(req["requester_user_id"]),
                  {"managed_user_id": req["target_user_id"]})
    db.commit()
    return {
        "ok": True,
        "status": "approved",
        "supervisor": _supervisor_public(db, req["requester_user_id"]),
    }


@router.post("/link-requests/{request_id}/approve")
def approve_link_request(
    request_id: int,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """The managed user taps "Allow" on the notification → the link goes active."""
    return _decide_link_request(db, device_id, request_id, approve=True)


@router.post("/link-requests/{request_id}/decline")
def decline_link_request(
    request_id: int,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """The managed user taps "Decline" → the request is settled, no link made."""
    return _decide_link_request(db, device_id, request_id, approve=False)


# ── GET /v1/device/supervisors ────────────────────────────────────────────
@router.get("/supervisors")
def list_supervisors(
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """Active supervisors over this device's Telegram account, each flagged with
    whether an unlink request is already pending."""
    customer = _customer(db, device_id)
    if customer is None or customer["tg_user_id"] is None:
        return {"supervisors": []}
    managed = db.execute(
        "SELECT id FROM control_users WHERE tg_user_id = %s", (customer["tg_user_id"],)
    ).fetchone()
    if managed is None:
        return {"supervisors": []}

    rows = db.execute(
        "SELECT u.id AS manager_user_id, u.display_name, u.email, l.created_at AS since, "
        "  EXISTS (SELECT 1 FROM control_unlink_requests r "
        "           WHERE r.manager_user_id = u.id AND r.managed_user_id = %s "
        "             AND r.status = 'pending') AS unlink_pending "
        "FROM control_links l JOIN control_users u ON u.id = l.manager_user_id "
        "WHERE l.managed_user_id = %s AND l.status = 'active' "
        "ORDER BY l.created_at DESC",
        (managed["id"], managed["id"]),
    ).fetchall()
    return {
        "supervisors": [
            {
                "manager_user_id": r["manager_user_id"],
                "display_name": r["display_name"],
                "email_masked": _mask_email(r["email"]),
                "since": r["since"],
                "unlink_pending": bool(r["unlink_pending"]),
            }
            for r in rows
        ]
    }


# ── POST /v1/device/supervisors/{manager_user_id}/unlink-request ──────────
@router.post("/supervisors/{manager_user_id}/unlink-request")
def request_unlink(
    manager_user_id: int,
    device_id: str = Depends(require_device),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """The managed user asks a supervisor to unlink. Per policy this does NOT
    revoke the link — it files a request the supervisor is notified of and must
    approve. Idempotent while a request is already pending."""
    customer = _customer(db, device_id)
    if customer is None or customer["tg_user_id"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "link_needs_tg_login")
    managed = db.execute(
        "SELECT id FROM control_users WHERE tg_user_id = %s", (customer["tg_user_id"],)
    ).fetchone()
    if managed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_managed")
    link = db.execute(
        "SELECT 1 FROM control_links "
        "WHERE manager_user_id = %s AND managed_user_id = %s AND status = 'active'",
        (manager_user_id, managed["id"]),
    ).fetchone()
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_active_link")

    now = utcnow_iso()
    db.execute(
        "INSERT INTO control_unlink_requests "
        "  (manager_user_id, managed_user_id, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (manager_user_id, managed_user_id) WHERE status = 'pending' "
        "DO NOTHING",
        (manager_user_id, managed["id"], now, now),
    )
    _audit_device(db, customer["id"], "unlink_request", str(manager_user_id), {})
    db.commit()
    return {"ok": True, "status": "pending"}
