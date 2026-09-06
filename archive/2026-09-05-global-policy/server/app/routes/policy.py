"""Global chat policy — Puregram's single control surface (ADR-001, 2026-09-03).

One policy applies to EVERY client. The messenger forks download it (and upload
nothing); the admin panel edits it. Private chats and groups are never gated by
the policy — only the kinds listed in `gated_kinds` (default: channels + bots).

  GET    /v1/policy                        public, cacheable (ETag = version)
  GET    /v1/admin/policy                  admin: settings + entries + audit info
  PUT    /v1/admin/policy/settings         admin: mode / gated_kinds / block_restricted
  POST   /v1/admin/policy/entries          admin: add one entry
  POST   /v1/admin/policy/entries/bulk     admin: paste a list, one per line
  PATCH  /v1/admin/policy/entries/{id}     admin: relabel / re-kind
  DELETE /v1/admin/policy/entries/{id}     admin: remove

Chat-id encoding is Telegram-Android's `dialog_id`: user/bot = +id, basic group
= -id, channel/supergroup = -id (plain negation, NOT the Bot-API `-100…` form;
the parser strips that prefix). An entry may carry an id, a username, or both;
clients match on either.
"""
from __future__ import annotations

import json
import re
from typing import Any, Literal, NamedTuple

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ..auth import require_admin, utcnow_iso
from ..db import get_db

public_router = APIRouter(prefix="/v1", tags=["policy"])
admin_router = APIRouter(prefix="/v1/admin/policy", tags=["policy-admin"])

Kind = Literal["channel", "bot", "group", "user"]
Mode = Literal["allow", "block"]

ALL_KINDS: tuple[str, ...] = ("channel", "bot", "group", "user")
DEFAULT_GATED_KINDS: tuple[str, ...] = ("channel", "bot")
POLICY_CACHE_MAX_AGE_S = 30
_MAX_BULK_LINES = 2000
_MAX_LABEL_LEN = 128

# Bot-API channel ids are written as -100<id>; clients use plain -<id>.
_BOT_API_CHANNEL_OFFSET = 1_000_000_000_000
# Telegram usernames: 5–32 chars, letters/digits/underscore, must start with a letter.
_USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{4,31}$")
_NUMERIC_RE = re.compile(r"^-?\d{1,20}$")
_LINK_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/(.+)$", re.IGNORECASE
)


# ── Target parsing ────────────────────────────────────────────────────────
class ParsedTarget(NamedTuple):
    chat_id: int | None
    username: str | None
    kind: str


def parse_target(raw: str, kind_hint: str | None = None) -> ParsedTarget:
    """Turn what an admin pasted into (chat_id, username, kind).

    Accepts a numeric dialog id (Bot-API `-100…` form is normalised), `@name`,
    a bare username, or a t.me / telegram.me link (`t.me/name`, `t.me/s/name`,
    `t.me/c/<id>/…`). Invite links (`t.me/+…`, `joinchat/…`) carry no stable
    identity and are rejected. Raises ValueError with a human-readable reason.
    """
    text = raw.strip()
    if not text:
        raise ValueError("empty line")

    if _NUMERIC_RE.match(text):
        value = int(text)
        if value == 0:
            raise ValueError("0 is not a chat id")
        if value < 0 and abs(value) >= _BOT_API_CHANNEL_OFFSET:
            value = -(abs(value) - _BOT_API_CHANNEL_OFFSET)
        default_kind = "bot" if value > 0 else "channel"
        return ParsedTarget(value, None, kind_hint or default_kind)

    match = _LINK_RE.match(text)
    path = (match.group(1) if match else text).strip("/")
    if path.startswith("+") or path.lower().startswith("joinchat/"):
        raise ValueError("invite links cannot be listed — use the chat's numeric id")

    parts = [p for p in path.split("/") if p]
    if not parts:
        raise ValueError("not a username, id or t.me link")
    if parts[0].lower() == "c" and len(parts) >= 2 and parts[1].isdigit():
        return ParsedTarget(-int(parts[1]), None, kind_hint or "channel")
    if parts[0].lower() == "s" and len(parts) >= 2:
        parts = parts[1:]

    name = parts[0].split("?", 1)[0].lstrip("@").lower()
    if not _USERNAME_RE.match(name):
        raise ValueError("not a username, id or t.me link")
    default_kind = "bot" if name.endswith("bot") else "channel"
    return ParsedTarget(None, name, kind_hint or default_kind)


def _validate_kind(kind: str | None) -> str | None:
    if kind is None:
        return None
    if kind not in ALL_KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"unknown kind: {kind}")
    return kind


# ── Policy loading / evaluation (shared with the legacy device shim) ──────
def load_policy(db: psycopg.Connection) -> dict[str, Any]:
    """The whole policy as a plain dict (settings + entries, newest first)."""
    settings_row = db.execute(
        "SELECT mode, gated_kinds, block_restricted, version, updated_at "
        "FROM policy_settings WHERE id = 1"
    ).fetchone()
    if settings_row is None:
        settings_row = {
            "mode": "allow",
            "gated_kinds": ",".join(DEFAULT_GATED_KINDS),
            "block_restricted": 1,
            "version": 0,
            "updated_at": None,
        }
    entries = db.execute(
        "SELECT id, chat_id, username, kind, label, added_by, created_at "
        "FROM policy_entries ORDER BY created_at DESC, id DESC"
    ).fetchall()
    gated = [k for k in settings_row["gated_kinds"].split(",") if k in ALL_KINDS]
    return {
        "version": settings_row["version"],
        "updated_at": settings_row["updated_at"],
        "mode": settings_row["mode"],
        "gated_kinds": gated,
        "block_restricted": bool(settings_row["block_restricted"]),
        "entries": [dict(e) for e in entries],
    }


def policy_allows(
    policy: dict[str, Any], kind: str, chat_id: int | None, username: str | None
) -> bool:
    """Server-side mirror of the client decision rule (minus restriction reasons,
    which only the client can see). `kind` uses the policy vocabulary."""
    if kind not in policy["gated_kinds"]:
        return True
    ids = {e["chat_id"] for e in policy["entries"] if e["chat_id"] is not None}
    names = {e["username"] for e in policy["entries"] if e["username"]}
    listed = (chat_id is not None and chat_id in ids) or (
        bool(username) and username.lower() in names
    )
    return listed if policy["mode"] == "allow" else not listed


def _public_payload(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": policy["version"],
        "updated_at": policy["updated_at"],
        "mode": policy["mode"],
        "gated_kinds": policy["gated_kinds"],
        "block_restricted": policy["block_restricted"],
        "entries": [
            {
                "id": e["chat_id"],
                "username": e["username"],
                "kind": e["kind"],
                "label": e["label"],
            }
            for e in policy["entries"]
        ],
    }


def _admin_payload(policy: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {k: 0 for k in ALL_KINDS}
    for e in policy["entries"]:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    return {**policy, "counts": counts}


# ── Mutation helpers ──────────────────────────────────────────────────────
def _forbid_readonly(admin: dict) -> None:
    if admin.get("role") == "readonly":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Read-only admins cannot change the policy")


def _bump_version(db: psycopg.Connection) -> int:
    row = db.execute(
        "UPDATE policy_settings SET version = version + 1, updated_at = %s "
        "WHERE id = 1 RETURNING version",
        (utcnow_iso(),),
    ).fetchone()
    return int(row["version"]) if row else 0


def _audit(db: psycopg.Connection, admin: dict, action: str, target: str | None,
           payload: dict[str, Any]) -> None:
    db.execute(
        "INSERT INTO audit_log (customer_id, actor, action, target, payload, created_at) "
        "VALUES (NULL, 'admin', %s, %s, %s, %s)",
        (action, target, json.dumps({**payload, "admin": admin.get("email")}, ensure_ascii=False),
         utcnow_iso()),
    )


def _insert_entry(db: psycopg.Connection, parsed: ParsedTarget, label: str | None,
                  added_by: str | None) -> dict[str, Any] | None:
    """Insert one entry; None when an identical id/username already exists."""
    row = db.execute(
        "INSERT INTO policy_entries (chat_id, username, kind, label, added_by, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING "
        "RETURNING id, chat_id, username, kind, label, added_by, created_at",
        (parsed.chat_id, parsed.username, parsed.kind, label, added_by, utcnow_iso()),
    ).fetchone()
    return dict(row) if row else None


def _clean_label(label: str | None) -> str | None:
    if label is None:
        return None
    trimmed = label.strip()[:_MAX_LABEL_LEN]
    return trimmed or None


# ── Public: GET /v1/policy ────────────────────────────────────────────────
@public_router.get("/policy")
def get_public_policy(
    request: Request, response: Response, db: psycopg.Connection = Depends(get_db)
) -> Any:
    """The policy every client applies. Unauthenticated by design: it names
    public channels/bots and no user, so it is not a secret. ETag lets a client
    poll every minute for ~0 bytes."""
    policy = load_policy(db)
    etag = f'"v{policy["version"]}"'
    cache = f"public, max-age={POLICY_CACHE_MAX_AGE_S}"
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED,
                        headers={"ETag": etag, "Cache-Control": cache})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = cache
    return _public_payload(policy)


# ── Admin ─────────────────────────────────────────────────────────────────
class SettingsBody(BaseModel):
    mode: Mode | None = None
    gated_kinds: list[Kind] | None = None
    block_restricted: bool | None = None


class EntryBody(BaseModel):
    target: str = Field(min_length=1, max_length=256)
    kind: Kind | None = None
    label: str | None = Field(default=None, max_length=_MAX_LABEL_LEN)


class EntryPatchBody(BaseModel):
    kind: Kind | None = None
    label: str | None = Field(default=None, max_length=_MAX_LABEL_LEN)


class BulkBody(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)
    kind: Kind | None = None


@admin_router.get("")
def get_admin_policy(
    _: dict = Depends(require_admin), db: psycopg.Connection = Depends(get_db)
) -> dict[str, Any]:
    return _admin_payload(load_policy(db))


@admin_router.put("/settings")
def update_settings(
    body: SettingsBody,
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    _forbid_readonly(admin)
    changes: dict[str, Any] = {}
    if body.mode is not None:
        db.execute("UPDATE policy_settings SET mode = %s WHERE id = 1", (body.mode,))
        changes["mode"] = body.mode
    if body.gated_kinds is not None:
        gated = ",".join(dict.fromkeys(body.gated_kinds))  # de-dup, keep order
        db.execute("UPDATE policy_settings SET gated_kinds = %s WHERE id = 1", (gated,))
        changes["gated_kinds"] = gated
    if body.block_restricted is not None:
        db.execute(
            "UPDATE policy_settings SET block_restricted = %s WHERE id = 1",
            (1 if body.block_restricted else 0,),
        )
        changes["block_restricted"] = body.block_restricted
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "nothing to change")
    version = _bump_version(db)
    _audit(db, admin, "policy_settings", None, {**changes, "version": version})
    db.commit()
    return _admin_payload(load_policy(db))


@admin_router.post("/entries", status_code=status.HTTP_201_CREATED)
def add_entry(
    body: EntryBody,
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    _forbid_readonly(admin)
    try:
        parsed = parse_target(body.target, _validate_kind(body.kind))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    entry = _insert_entry(db, parsed, _clean_label(body.label), admin.get("email"))
    if entry is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already listed")
    version = _bump_version(db)
    _audit(db, admin, "policy_entry_add",
           str(parsed.chat_id if parsed.chat_id is not None else parsed.username),
           {"kind": parsed.kind, "version": version})
    db.commit()
    return {**entry, "version": version}


@admin_router.post("/entries/bulk")
def add_entries_bulk(
    body: BulkBody,
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    """One target per line; blank lines and `#` comments are ignored. Bad lines
    are reported, never fatal — the good ones still land."""
    _forbid_readonly(admin)
    kind_hint = _validate_kind(body.kind)
    lines = body.text.splitlines()
    if len(lines) > _MAX_BULK_LINES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"at most {_MAX_BULK_LINES} lines per paste")
    added = 0
    skipped = 0
    errors: list[dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        text = line.split("#", 1)[0].strip()
        if not text:
            continue
        try:
            parsed = parse_target(text, kind_hint)
        except ValueError as exc:
            errors.append({"line": number, "text": text, "reason": str(exc)})
            continue
        if _insert_entry(db, parsed, None, admin.get("email")) is None:
            skipped += 1
        else:
            added += 1
    version = _bump_version(db) if added else load_policy(db)["version"]
    if added:
        _audit(db, admin, "policy_entries_bulk", None,
               {"added": added, "skipped": skipped, "version": version})
    db.commit()
    return {"ok": True, "added": added, "skipped": skipped, "errors": errors,
            "version": version}


@admin_router.patch("/entries/{entry_id}")
def patch_entry(
    entry_id: int,
    body: EntryPatchBody,
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> dict[str, Any]:
    _forbid_readonly(admin)
    if body.kind is None and body.label is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "nothing to change")
    existing = db.execute(
        "SELECT id FROM policy_entries WHERE id = %s", (entry_id,)
    ).fetchone()
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    if body.kind is not None:
        db.execute("UPDATE policy_entries SET kind = %s WHERE id = %s", (body.kind, entry_id))
    if body.label is not None:
        db.execute("UPDATE policy_entries SET label = %s WHERE id = %s",
                   (_clean_label(body.label), entry_id))
    version = _bump_version(db)
    _audit(db, admin, "policy_entry_patch", str(entry_id),
           {"kind": body.kind, "label": body.label, "version": version})
    db.commit()
    row = db.execute(
        "SELECT id, chat_id, username, kind, label, added_by, created_at "
        "FROM policy_entries WHERE id = %s", (entry_id,)
    ).fetchone()
    return {**dict(row), "version": version}


@admin_router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> Response:
    _forbid_readonly(admin)
    row = db.execute(
        "DELETE FROM policy_entries WHERE id = %s RETURNING chat_id, username, kind",
        (entry_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    version = _bump_version(db)
    _audit(db, admin, "policy_entry_delete",
           str(row["chat_id"] if row["chat_id"] is not None else row["username"]),
           {"kind": row["kind"], "version": version})
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
