# Puregram — Admin Panel

The ONLY control surface of Puregram since ADR-001 (2026-09-03). Static
HTML/CSS/JS — no framework, no build step. Served by nginx at `/admin/`
alongside the API at `/control/`.

Brand: green `#2E9E4F` / `#1E7A3C`, gold `#D4AF37`, dark navy surfaces
`#070C18` / `#0C1426` / `#101B33`. Logo: `img/puregram-control.png`.

## Pages

| File | Purpose |
|---|---|
| `login.html` | Admin login (email + password → HttpOnly JWT cookie `puregram_admin`). |
| `policy.html` | **The global policy**: mode (allow / block), gated kinds, Telegram-restriction enforcement, add one entry, bulk paste, entries table with filter / relabel / delete. |

## Assets

| File | Purpose |
|---|---|
| `css/style.css` | Theme + components. |
| `js/api.js` | Fetch wrapper, auth guard, topbar. Holds the one configurable `API_BASE`. |
| `js/login.js` | Login form. |
| `js/policy.js` | Policy page logic. |

## Backend contract

See `POLICY_SPEC.md` §5 (repo root). All endpoints live under
`<API_BASE>/admin/policy`; read-only admins get `403` on mutations.

| Method & path | Body |
|---|---|
| `GET    policy` | — |
| `PUT    policy/settings` | `{mode?, gated_kinds?, block_restricted?}` |
| `POST   policy/entries` | `{target, kind?, label?}` |
| `POST   policy/entries/bulk` | `{text, kind?}` |
| `PATCH  policy/entries/{id}` | `{label?, kind?}` |
| `DELETE policy/entries/{id}` | — |

`target` accepts `@username`, a bare username, `t.me/…` links (including
`t.me/c/<id>/…`), or a numeric dialog id (the Bot-API `-100…` form is
normalised). Invite links are rejected.

## Deploy

```bash
rsync -av --delete panel/ root@puregram.app:/var/www/puregram.app/admin/
```

The previous per-device whitelist page (`telegram.html` + `js/telegram.js`)
is archived under `archive/2026-09-03-supervision/panel/`.
