# Puregram

An unofficial, independent build of Telegram's open-source clients for Android
and Windows, with one added idea: **you decide once what you will not open
again, and the decision holds.**

- People and secret chats always open, exactly as in Telegram.
- Channels, bots and groups start closed. The first time you open one, the app
  asks: allow it, or block it forever?
- An **allow** you can withdraw at any time. A **block is permanent** — it cannot
  be undone, on this device or any other. That asymmetry is the whole product.

Not affiliated with Telegram FZ-LLC. See **[NOTICE.md](NOTICE.md)** for licensing
and attribution.

## Read these first

| Document | What it covers |
|---|---|
| **[POLICY_SPEC.md](POLICY_SPEC.md)** | The contract every client implements: the decision rule, the ratchet, the API, erasure, device binding. Start here. |
| **[BUILDING.md](BUILDING.md)** | How to build each piece — including the Telegram API credentials you must supply yourself. |
| **[NOTICE.md](NOTICE.md)** | GPL licensing, attribution, and exactly what changed against upstream. |

`CONTROL_SPEC.md` describes a retired supervision model; only its brand section
(§2) still applies.

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│  Puregram client (Android / Desktop)                       │
│  · enforces the user's own rules locally, works offline    │
│  · syncs them:  GET/POST /v1/rules?tg_user_id=…      ──┐   │
└───────────────────────────────────────────────────────┼────┘
                                                        │
  https://puregram.app                                  │
  ┌─────────────────────────────────────────────────┐   │
  │  nginx                                          │   │
  │  /          → site/      (marketing site)       │   │
  │  /download/              (apk / exe / zip)      │   │
  │  /control/  → 127.0.0.1:8020 (FastAPI)   ───────┼───┘
  └─────────────────────────────────────────────────┘
                        │
               puregram-server.service
               uvicorn app.main:app --host 127.0.0.1 --port 8020
                        │
               PostgreSQL — DB: puregram
```

The server stores three things per account: the rules, a version counter, and
which devices may sync them. It never sees a message, a contact, or a chat the
user did not put on a list.

---

## Directory map

| Path | Purpose |
|---|---|
| `telegram/telegram-android/` | Android fork. The rules live in `messenger/PuregramRules.java`; the UI in `ui/PuregramRulesActivity.java`. |
| `telegram/tdesktop/` | Desktop fork. The rules live in `SourceFiles/puregram/`. |
| `server/` | FastAPI: `/v1/rules/*`, the legacy device shim, update manifests. |
| `site/` | Public site (`index.html`, `privacy.html`, `terms.html`). |
| `deploy/` | nginx, systemd, and `release-policy.sh` (the deploy script). |
| `play-assets/` | Google Play listing, data-safety and policy material. |
| `brand/` | Logo and sized derivatives. |
| `archive/` | Two retired control models, kept for history. Not built, not deployed. |

---

## Running locally

```bash
cd server
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # PUREGRAM_DATABASE_URL, PUREGRAM_JWT_SECRET
uvicorn app.main:app --host 127.0.0.1 --port 8020 --reload

cd ../site && python -m http.server 3000
```

The schema is applied on startup; every statement is idempotent.

Building the clients is covered in **[BUILDING.md](BUILDING.md)** — it needs your
own Telegram API credentials, which are deliberately not in this repository.

---

## Deploying

`deploy/release-policy.sh` does each step, in this order:

```bash
bash deploy/release-policy.sh server                       # backend + restart + health
bash deploy/release-policy.sh apk <path/to/app.apk>        # atomic swap of /download/puregram.apk
bash deploy/release-policy.sh desktop <Puregram.exe> <zip> # raw exe (updater) + zip (site card)
bash deploy/release-policy.sh site                         # index/privacy/terms only
bash deploy/release-policy.sh verify                       # live checks
```

Server first: it also answers the old device protocol, so handsets that have not
updated keep working. Transfers use `tar` over ssh (Git Bash has no rsync). The
SSH identity comes from `~/.ssh/config`; set `PUREGRAM_HOST` to override the host
(useful when local DNS is unreliable).

After shipping a client, mirror its build number **and** its sha256 in
`server/app/routes/device_update.py`, then redeploy the server — the in-app
updater compares against those values and refuses a mismatched download.

Backend secrets live in `/opt/puregram-server/.env` on the VPS and are never
committed:

```env
PUREGRAM_DATABASE_URL=postgresql://puregram:<password>@127.0.0.1:5432/puregram
PUREGRAM_JWT_SECRET=<long random string — min 64 chars>
PUREGRAM_COOKIE_SECURE=true
PUREGRAM_ALLOWED_ORIGINS=https://puregram.app
```

---

## nginx notes (`deploy/nginx-final.conf`)

- HTTP → 301 HTTPS; TLS 1.2/1.3 only. Security headers are repeated inside child
  `location` blocks, because nginx drops inherited `add_header` directives in any
  block that defines one of its own.
- `/control/` proxies to `127.0.0.1:8020` with the prefix stripped.
- The `/app/` and `/admin/` locations served two retired surfaces and can be
  removed; nothing links to them any more.

---

## Quick reference

| Task | Command |
|---|---|
| Backend dev | `cd server && uvicorn app.main:app --port 8020 --reload` |
| Import check (no DB needed) | `cd server && python -c "import app.main"` |
| Restart backend | `sudo systemctl restart puregram-server` |
| Tail backend logs | `sudo journalctl -u puregram-server -f` |
| Reload nginx | `sudo nginx -t && sudo systemctl reload nginx` |
