"""Puregram Control API — /v1/control/*.

The email/password Puregram Control web app. A
manager controls which Telegram chats a managed account may open; sync happens
in real time over SSE.

Submodules:
  auth.py    register/login/logout/me/password + Telegram-account binding
  links.py   consent flow (link requests) + managed/managers overview + unlink
  chats.py   per-managed-account chat whitelist control (fans out to all devices)
  stream.py  Server-Sent Events for live sync
  common.py  shared profile/cookie/audit/manager-guard helpers

`router` aggregates every submodule router so main.py mounts the whole API with
a single include_router call.
"""
from __future__ import annotations

from fastapi import APIRouter

from . import auth, chats, links, pairings, stream

router = APIRouter()
router.include_router(auth.router)
router.include_router(links.router)
router.include_router(links.overview)  # /v1/control/managed + /managers (own prefix)
router.include_router(chats.router)
router.include_router(pairings.router)  # /v1/control/pairings + /unlink-requests
router.include_router(stream.router)

__all__ = ["router"]
