"""FastAPI entrypoint for the Puregram control API.

Mounted behind nginx at https://puregram.app/control/ -> 127.0.0.1:8020 (the
/control prefix is stripped by nginx, so the app sees /v1/...).
Run: uvicorn app.main:app --host 127.0.0.1 --port 8020

Surfaces (ADR-002, 2026-09-05):
  /v1/rules             per-account allow/block rules, synced across a user's devices
  /v1/device/*          device check-in + the legacy protocol for older clients
  /v1/admin/*           admin login (kept only for the data-deletion support path)
  /v1/{android,desktop}/version   client self-update manifests
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import settings
from .db import init_db, pool
from .routes import device_update, rules, telegram_device


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield
    pool.close()


app = FastAPI(title="Puregram Control API", version=__version__, lifespan=lifespan)

# Same-origin in production; credentials are needed for the admin cookie.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "If-None-Match"],
    expose_headers=["ETag"],
)

app.include_router(rules.router)
app.include_router(telegram_device.router)
app.include_router(device_update.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
