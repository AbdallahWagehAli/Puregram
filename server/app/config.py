"""Runtime configuration, sourced from environment variables.

Secrets (PUREGRAM_JWT_SECRET, the DB password inside DATABASE_URL) MUST be
provided via the environment in production (systemd unit), never hard-coded.
The defaults below are for local development only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # .../Puregram/server


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    return value if value != "" else default


@dataclass(frozen=True)
class Settings:
    # PostgreSQL connection string (libpq URI). Override in production via the
    # systemd unit. The DB user/password/host live there, never in git.
    database_url: str = _env(
        "PUREGRAM_DATABASE_URL",
        "postgresql://puregram:puregram@localhost:5432/puregram",
    )

    # Connection-pool sizing. max_size caps concurrent DB connections; tune to
    # the VPS Postgres max_connections.
    db_pool_min: int = int(_env("PUREGRAM_DB_POOL_MIN", "2"))
    db_pool_max: int = int(_env("PUREGRAM_DB_POOL_MAX", "10"))

    # Allowed browser origins. Nothing in the service is browser-facing any more
    # — the clients are the apps — but the header costs nothing and keeps a
    # stray page from calling the API from another site.
    allowed_origins: tuple[str, ...] = tuple(
        o.strip()
        for o in _env(
            "PUREGRAM_ALLOWED_ORIGINS",
            "https://puregram.app",
        ).split(",")
        if o.strip()
    )


settings = Settings()
