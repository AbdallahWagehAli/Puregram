# Puregram — Control Server

The backend behind `https://puregram.app/control/`. Since ADR-001 (2026-09-03) it does
three things:

1. Serves the **global policy** every client applies — `GET /v1/policy` (public).
2. Lets admins edit that policy — `/v1/admin/policy/*` (cookie auth, the static panel in
   `../panel/` drives it).
3. Keeps the **legacy device protocol** alive for handsets that have not updated yet, and
   publishes the client **update manifests**.

- **Stack:** FastAPI + PostgreSQL (psycopg 3) + Argon2id (admin passwords) + HS256 JWT.
- **API base (behind nginx):** `https://puregram.app/control` → uvicorn on `127.0.0.1:8020`.
  nginx strips the `/control` prefix, so the app itself serves `/v1/...`.
- **Contract:** [`../POLICY_SPEC.md`](../POLICY_SPEC.md).
- **Schema:** [`schema.sql`](schema.sql) then [`schema_legacy.sql`](schema_legacy.sql),
  both idempotent, applied on every startup.

---

## Layout

```
server/
  app/
    __init__.py            package + __version__
    config.py              env-sourced settings (DB url, JWT secret, cookie flags)
    db.py                  psycopg connection pool + schema bootstrap
    auth.py                Argon2id passwords, admin JWT, device-token guard, time helpers
    main.py                FastAPI app + router wiring
    cli.py                 init-db / create-admin / set-password
    routes/
      policy.py            GET /v1/policy (public) + /v1/admin/policy/* (admin)
      telegram_device.py   LEGACY: /v1/device/checkin, /telegram/whitelist[/all], /telegram/chats, /telegram/events
      device_update.py     GET /v1/android/version, GET /v1/desktop/version
      admin.py             admin login/logout/me
      admins.py            admin-account management (superadmin)
  schema.sql               devices, admins, audit_log, legacy telegram tables, policy_settings, policy_entries
  schema_legacy.sql        columns/tables only the legacy shim needs (drop together with it)
  requirements.txt
  deploy/                  systemd unit + nginx snippet
```

The retired supervision code (control users, link requests, SSE, per-device whitelist
admin) is in `../archive/2026-09-03-supervision/server/`.

---

## Data model

| Table | Purpose |
|---|---|
| `policy_settings` | Single row: `mode` (`allow`/`block`), `gated_kinds` (CSV), `block_restricted`, `version`, `updated_at`. |
| `policy_entries` | The list: `chat_id` and/or `username`, `kind` (`channel`/`bot`/`group`/`user`), `label`, `added_by`. Unique per id and per username. |
| `admins` | Admin accounts; Argon2id `password_hash`; roles `admin`/`superadmin`/`readonly`. |
| `audit_log` | Append-only; every policy mutation + device accountability event writes a row. |
| `customers`, `device_tokens` | LEGACY device rows + bearer tokens (old clients). |
| `customer_accounts`, `telegram_known_chats` | LEGACY: accounts on a device + the chats they reported; the shim filters these through the policy. |
| `telegram_whitelist`, `telegram_whitelist_meta` | LEGACY per-device tables, no longer written. |

`chat_id` uses the Telegram-Android dialog-id encoding: user/bot `+id`, group and
channel `-id`. The Bot-API `-100…` prefix is stripped when an admin pastes it.

---

## Auth

- **Admin:** `POST /v1/admin/login` (email + password, throttled) sets the HttpOnly
  cookie `puregram_admin` (HS256 JWT, `PUREGRAM_JWT_TTL_HOURS`). `require_admin`
  resolves it; `readonly` admins are refused on every mutation.
- **Public:** `GET /v1/policy` needs nothing. It carries `ETag: "v<version>"` and
  `Cache-Control: public, max-age=30`; clients send `If-None-Match` and get `304`.
- **Legacy devices:** opaque bearer token from `POST /v1/device/checkin`.

---

## Running

```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # PUREGRAM_DATABASE_URL, PUREGRAM_JWT_SECRET, …
uvicorn app.main:app --host 127.0.0.1 --port 8020 --reload
python -m app.cli create-admin admin@puregram.app    # first admin
```

Quick checks without a database:

```bash
python -c "import app.main"                          # wiring + syntax
python - <<'EOF'
from app.routes.policy import parse_target
print(parse_target("t.me/c/1234567890/5"), parse_target("@quran_daily"), parse_target("-1001234567890"))
EOF
```

---

## Releasing a client

Bump the constants in `app/routes/device_update.py` (`_ANDROID_BUILD` / `_ANDROID_SHA256`,
`_DESKTOP_BUILD` / `_DESKTOP_SHA256`) to match the artifact you host under
`https://puregram.app/download/`, then redeploy the server. The clients compare the
advertised build number with their own and download the raw artifact.

---

## Deploy

```bash
rsync -av --exclude .env --exclude venv --exclude __pycache__ server/ root@puregram.app:/opt/puregram-server/
ssh root@puregram.app 'systemctl restart puregram-server && sleep 2 && curl -s http://127.0.0.1:8020/health && curl -sI http://127.0.0.1:8020/v1/policy | head -5'
```

Secrets live in `/opt/puregram-server/.env` on the VPS (never in git).
