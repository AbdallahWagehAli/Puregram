# Puregram Control — Web App (`app/`)

A real-time, bilingual (Arabic RTL default / English LTR) control panel where a
**manager** decides which Telegram chats a **managed** account is allowed to
open. Built as a static SPA served at `https://puregram.app/app/`.

## Stack

- **React 18** + **TypeScript** (strict) + **Vite 5**
- **Tailwind CSS 3** (brand tokens from `CONTROL_SPEC.md` §2, dark default + light)
- **react-router-dom 6** (history routing under base `/app/`)
- **Server-Sent Events** for live updates (`EventSource`)
- No state library — React Context for auth, i18n, theme, toasts, realtime

## Requirements

- Node **≥ 18**

## Develop

```bash
npm install
npm run dev          # http://localhost:5173/app/
```

The dev server proxies `'/control'` → `http://localhost:8020` (stripping the
`/control` prefix), so it talks to the real FastAPI backend during development.
Run the backend (`server/`) on port `8020` alongside it.

## Build

```bash
npm run build        # tsc --noEmit, then vite build → app/dist/
npm run typecheck    # tsc --noEmit only
npm run preview      # serve the production build locally
```

Output is fully static in **`app/dist/`**.

## Configuration

| Env var         | Default        | Purpose                                            |
| --------------- | -------------- | -------------------------------------------------- |
| `VITE_API_BASE` | `/control/v1`  | API base URL. Same-origin in prod; proxied in dev. |

All requests use `credentials: 'include'`; auth is a cookie-based JWT issued by
the backend. A `401` clears the session and routes to `/login`.

## Deploy

The app is static — only nginx is required. Serve `app/dist/` at `/app/` with a
history fallback to `index.html`:

```nginx
location /app/ {
    alias /srv/puregram/app/dist/;
    try_files $uri /app/index.html;
}
```

Keep `/control/` proxied to the backend (`127.0.0.1:8020`) on the same origin so
the auth cookie and the `EventSource` stream travel correctly. See
`CONTROL_SPEC.md` §7 for the full nginx + security-header setup.

## Structure

```
app/
├─ index.html               # entry; loads Google Fonts + favicon
├─ public/puregram_control.png
└─ src/
   ├─ main.tsx · App.tsx     # bootstrap + router
   ├─ types.ts               # API response types (CONTROL_SPEC §4)
   ├─ lib/                   # api client, error mapping, formatters
   ├─ i18n/dictionary.ts     # bilingual strings
   ├─ context/               # Auth, I18n, Theme, Toast, Realtime
   ├─ hooks/                 # useAsyncData, useManagedChats
   ├─ components/            # shell, UI primitives, icons
   └─ pages/                 # login, register, dashboard, managed,
                             #   managed/:id, managers, link, settings, 404
```

## Routes

| Path             | Page                                                        |
| ---------------- | ----------------------------------------------------------- |
| `/login`         | Sign in (anonymous only)                                    |
| `/register`      | Create account (anonymous only)                             |
| `/`              | Dashboard — stats + quick actions                           |
| `/managed`       | Accounts I manage                                           |
| `/managed/:userId` | Detail — live chat allow/block toggles, bulk add, unlink  |
| `/managers`      | Who manages me + incoming/outgoing link requests            |
| `/link`          | Send a link request by email or share code                  |
| `/settings`      | Profile, language, theme, Telegram bind, password, logout   |
```
