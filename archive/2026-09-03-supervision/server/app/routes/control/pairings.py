"""Control API — supervisor pairing redemption + managed-side unlink requests.

  POST /v1/control/pairings/redeem                supervisor redeems a device code
  GET  /v1/control/unlink-requests                pending unlink requests over my accounts
  POST /v1/control/unlink-requests/{id}/approve   approve → revoke the control_link
  POST /v1/control/unlink-requests/{id}/deny      keep the link

Redeeming only marks the pairing 'claimed' and records the supervisor; the
control_link is created on the device (POST /v1/device/pairing/confirm) after the
managed user approves the named supervisor. Redeem is throttled per client IP to
blunt code brute-forcing (single-use + short TTL already bound the window).
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ...auth import require_user, utcnow_iso
from ...db import get_db
from ...pairing import hash_code
from .common import audit_user

router = APIRouter(prefix="/v1/control", tags=["control-pairings"])

# In-memory per-IP throttle (mirrors the login throttle used elsewhere). A single
# worker serves the SSE/control API, so a process-local window is sufficient.
_REDEEM_WINDOW_S = 300.0
_REDEEM_MAX_ATTEMPTS = 10
_redeem_hits: dict[str, deque[float]] = defaultdict(deque)


class RedeemBody(BaseModel):
    code: str = Field(min_length=1, max_length=32)


def _throttle_redeem(ip: str) -> None:
    now = time.monotonic()
    hits = _redeem_hits[ip]
    while hits and now - hits[0] > _REDEEM_WINDOW_S:
        hits.popleft()
    if len(hits) >= _REDEEM_MAX_ATTEMPTS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts")
    hits.append(now)


# ── POST /v1/control/pairings/redeem ──────────────────────────────────────
@router.post("/pairings/redeem")
def redeem_pairing(
    body: RedeemBody,
    request: Request,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Supervisor submits a code shown on a managed phone.

    On success the pairing flips to 'claimed' (awaiting the managed user's
    on-device confirmation); the link itself is created there. Errors: 404
    `invalid_code`, 410 `code_expired`/`code_unavailable`, 409 `code_already_used`,
    422 `cannot_supervise_self`.
    """
    _throttle_redeem(request.client.host if request.client else "unknown")

    pairing = db.execute(
        "SELECT id, tg_user_id, status, supervisor_user_id, expires_at "
        "FROM control_pairings WHERE code_hash = %s",
        (hash_code(body.code),),
    ).fetchone()
    if pairing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invalid_code")

    now = utcnow_iso()
    if pairing["status"] in ("pending", "claimed") and pairing["expires_at"] <= now:
        db.execute(
            "UPDATE control_pairings SET status = 'expired' WHERE id = %s AND status IN ('pending','claimed')",
            (pairing["id"],),
        )
        db.commit()
        raise HTTPException(status.HTTP_410_GONE, "code_expired")

    if pairing["status"] == "claimed":
        # Idempotent for the same supervisor re-scanning; otherwise it's taken.
        if pairing["supervisor_user_id"] == user["id"]:
            return {"ok": True, "status": "claimed", "awaiting_confirmation": True}
        raise HTTPException(status.HTTP_409_CONFLICT, "code_already_used")
    if pairing["status"] != "pending":
        raise HTTPException(status.HTTP_410_GONE, "code_unavailable")

    if user["tg_user_id"] is not None and user["tg_user_id"] == pairing["tg_user_id"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "cannot_supervise_self")

    # Atomic single-use claim: only the first redeemer of a still-pending code wins.
    cur = db.execute(
        "UPDATE control_pairings SET status = 'claimed', supervisor_user_id = %s, claimed_at = %s "
        "WHERE id = %s AND status = 'pending'",
        (user["id"], now, pairing["id"]),
    )
    if cur.rowcount == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "code_already_used")
    audit_user(db, user, "pairing_redeem", str(pairing["tg_user_id"]), {"by": user["email"]})
    db.commit()
    return {"ok": True, "status": "claimed", "awaiting_confirmation": True}


# ── Managed-side unlink requests (supervisor decides) ─────────────────────
@router.get("/unlink-requests")
def list_unlink_requests(
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    """Pending unlink requests filed by accounts this supervisor manages."""
    rows = db.execute(
        "SELECT r.id, r.managed_user_id, u.display_name, r.created_at "
        "FROM control_unlink_requests r "
        "JOIN control_users u ON u.id = r.managed_user_id "
        "WHERE r.manager_user_id = %s AND r.status = 'pending' "
        "ORDER BY r.created_at DESC",
        (user["id"],),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "managed_user_id": r["managed_user_id"],
            "display_name": r["display_name"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.post("/unlink-requests/{req_id}/approve")
def approve_unlink(
    req_id: int,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, bool]:
    """Supervisor approves an unlink request → revoke the control_link."""
    req = db.execute(
        "SELECT id, managed_user_id FROM control_unlink_requests "
        "WHERE id = %s AND manager_user_id = %s AND status = 'pending'",
        (req_id, user["id"]),
    ).fetchone()
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")

    now = utcnow_iso()
    db.execute(
        "UPDATE control_links SET status = 'revoked', updated_at = %s "
        "WHERE manager_user_id = %s AND managed_user_id = %s AND status = 'active'",
        (now, user["id"], req["managed_user_id"]),
    )
    db.execute(
        "UPDATE control_unlink_requests SET status = 'approved', updated_at = %s WHERE id = %s",
        (now, req_id),
    )
    audit_user(db, user, "unlink_approve", str(req["managed_user_id"]), {"by": user["email"]})
    db.commit()
    return {"ok": True}


@router.post("/unlink-requests/{req_id}/deny")
def deny_unlink(
    req_id: int,
    user: dict = Depends(require_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, bool]:
    """Supervisor keeps the link; the managed user stays supervised."""
    cur = db.execute(
        "UPDATE control_unlink_requests SET status = 'denied', updated_at = %s "
        "WHERE id = %s AND manager_user_id = %s AND status = 'pending'",
        (utcnow_iso(), req_id, user["id"]),
    )
    if cur.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    audit_user(db, user, "unlink_deny", str(req_id), {"by": user["email"]})
    db.commit()
    return {"ok": True}
