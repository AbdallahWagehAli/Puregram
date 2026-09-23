"""Puregram client self-update manifests.

  GET /v1/desktop/version   -> Windows desktop fork
  GET /v1/android/version   -> Android fork (sideloaded APK)

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

To publish a new ANDROID build: bump `APP_VERSION_CODE` (gradle.properties) AND
`_ANDROID_BUILD` below to the same number, host the new APK at `_ANDROID_URL`,
set `_ANDROID_SHA256`, redeploy.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/v1", tags=["client-update"])

# ── Desktop (Windows) ──────────────────────────────────────────────────────
_DESKTOP_BUILD = 14
_DESKTOP_URL = "https://puregram.app/download/puregram-desktop.exe"
_DESKTOP_SHA256 = "8cded60b3e11abd3b96e709712beef9700d032f21302118c522fcabb97e9b61e"

# ── Android ────────────────────────────────────────────────────────────────
# Latest published APK's APP_VERSION_CODE (gradle.properties). PuregramUpdater
# compares BuildConfig.PUREGRAM_BUILD against this and, if lower, downloads
# `url` through DownloadManager and opens the system installer.
_ANDROID_BUILD = 6781
_ANDROID_URL = "https://puregram.app/download/puregram.apk"
_ANDROID_SHA256 = "9f5f979df35f1c511ae08496a0ae5bc8873197c51a1ed48a9c54ad40f73a94b1"


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
    """Advertise the latest Android build code + the APK to download."""
    payload: dict[str, Any] = {"version": _ANDROID_BUILD, "url": _ANDROID_URL}
    sha = _ANDROID_SHA256.strip().lower()
    if len(sha) == 64:
        payload["sha256"] = sha
    return payload
