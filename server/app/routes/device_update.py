"""Puregram client self-update manifests.

  GET /v1/desktop/version   -> Windows desktop fork
  GET /v1/android/version   -> always 404: Android ships through Google Play

Both clients poll their endpoint periodically and compare the advertised integer
`version` against their own build number. If newer, they raise a notification and
offer a Download/Update button that fetches `url` and hands it to the platform's
installer — Android to the package installer, desktop to a staged swap applied on
the next launch. Nothing installs without the user confirming.

`url` must point at the RAW artifact (the .apk / .exe), not a web page: the
clients download it directly. `sha256` lets a client refuse a corrupted or
tampered download.

To publish a new DESKTOP build: bump `kPuregramBuild` (puregram_updater.cpp) AND
`_DESKTOP_BUILD` below, host the new raw Telegram.exe at `_DESKTOP_URL`, set
`_DESKTOP_SHA256` (= `sha256sum Telegram.exe`), redeploy the server.

A new ANDROID build goes to Google Play only; nothing here changes for it.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/v1", tags=["client-update"])

# ── Desktop (Windows) ──────────────────────────────────────────────────────
_DESKTOP_BUILD = 15
_DESKTOP_URL = "https://puregram.app/download/puregram-desktop.exe"
_DESKTOP_SHA256 = "3f4a06b9abf13a3c0540d2c3fcb5f30be255a852b66b5d12c7f66fcaf75d9faf"

# ── Android ────────────────────────────────────────────────────────────────
# Android ships through Google Play only since 2026-09-28; the direct APK is
# retired and no longer hosted. Play builds carry no self-updater
# (PUREGRAM_SELF_UPDATE=false). Older direct installs still poll this route:
# PuregramUpdater treats 404 as "no update advertised" and stays quiet, which is
# the right answer now that there is no APK left to hand them.


@router.get("/desktop/version")
def desktop_version(app: str = "telegram_desktop") -> dict[str, str]:
    """Advertise the latest Windows desktop build. 404 for unknown apps."""
    if app != "telegram_desktop":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_update")
    payload = {"version": str(_DESKTOP_BUILD), "url": _DESKTOP_URL}
    sha = _DESKTOP_SHA256.strip().lower()
    if len(sha) == 64:
        payload["sha256"] = sha
    return payload


@router.get("/android/version")
def android_version() -> dict[str, Any]:
    """No direct APK is published any more; see the note above."""
    raise HTTPException(status.HTTP_404_NOT_FOUND, "no_update")
