# Puregram Chat Rules — Contract (ADR-002, 2026-09-05)

> Single source of truth for the control model. Every implementer (server,
> Android fork, Desktop fork) conforms to this file exactly.
>
> **History.** ADR-001 (2026-09-03) replaced per-account *supervision* with ONE
> curated global list. ADR-002 replaces that global list with **per-user rules**:
> nobody curates anything for anybody else. The ADR-001 code is archived under
> `archive/2026-09-05-global-policy/`; the supervision code before it under
> `archive/2026-09-03-supervision/`. `CONTROL_SPEC.md` survives only for its
> brand system (§2) and backend conventions (§6).

## 1. Model in one paragraph

Every account governs its own client. **People** (non-bot users) and secret chats
always open. **Channels, bots and groups are closed by default** and open only if
that account allowed them. The user manages two lists in Settings: *allowed* and
*blocked*. **`allow` is reversible; `block` is permanent** — once a chat is
blocked it can never be allowed again. That one-way ratchet is the product: it
lets someone bind their future self in a moment of resolve. The rules live on the
server keyed by the Telegram account id, so they follow the account across the
Android and desktop clients with nothing to move by hand. Independently, any peer
Telegram itself marks restricted/sensitive is refused, and discovery surfaces
(global channel/bot search, the Channels/Apps/Posts tabs, similar channels,
inline bots, web image search, free-text GIF and sticker search) are removed from
the clients. Local search of the user's own chats, messages and contacts stays.

## 2. Decision rule (both forks, identical semantics)

```
canOpen(peer):
  if peer is self (Saved Messages)                → ALLOW
  if rule(peer) == "block"                        → DENY   // permanent, never overridable
  if block_restricted and peer.restricted ≠ ∅     → DENY   // "sensitive" is never ignored
  if peer is a secret chat                        → ALLOW
  kind = user | bot | group | channel             // group = basic group or megagroup
  if kind == "user"                               → ALLOW  // people are never gated
  if rule(peer) == "allow"                        → ALLOW
  → DENY
```

- `rule(peer)` is looked up by **chat id** (dialog-id encoding: user/bot `+id`,
  group and channel `-id`, never the Bot-API `-100…` form).
- Gated kinds are fixed: `channel`, `bot`, `group`. There is no server setting.
- Offline / before the first sync: the locally cached rules apply. A fresh
  install with no cache opens people only, which is the safe direction.
- The gate lives at the universal "open chat" chokepoint on each platform
  (Android `ChatActivity.onFragmentCreate` + `onResume`, Desktop
  `SessionController::showPeerHistory`). Links, @mentions, forwards, invite
  links, search results and notifications all funnel through it. Stories use the
  story owner as the peer.

## 3. The ratchet

| From | To `allow` | To `block` | Remove the rule |
|---|---|---|---|
| no rule | yes | yes | n/a |
| `allow` | — | **yes** | yes (a tightening) |
| `block` | **never** | — | **never** |

Enforced in three places so a tampered client cannot defeat it:
1. the clients refuse to offer "unblock" in the UI;
2. the server's upsert keeps `block` whatever is posted
   (`rule = CASE WHEN account_rules.rule = 'block' THEN 'block' ELSE EXCLUDED.rule END`);
3. `DELETE /v1/rules/{chat_id}` refuses when the stored rule is `block`.

**The only way out is erasure, and erasure waits.** See §5.

## 4. API

All endpoints take the device bearer token from `POST /v1/device/checkin` and the
account's `tg_user_id`.

| Method & path | Body / query | Returns |
|---|---|---|
| `GET /v1/rules?tg_user_id=` | — | `{tg_user_id, version, gated_kinds, rules[], erasure_requested_at?, erasure_effective_at?}` |
| `GET /v1/rules/meta?tg_user_id=` | — | `{tg_user_id, version}` — cheap poll |
| `POST /v1/rules` | `{tg_user_id, chat_id, kind, rule, username?, title?}` | the full rules result (ratchet applied) |
| `DELETE /v1/rules/{chat_id}?tg_user_id=` | — | rules result; **403** if the rule is `block` |
| `DELETE /v1/rules?tg_user_id=&confirm=erase` | — | `{scheduled, requested_at, effective_at, delay_days}` |
| `POST /v1/rules/erase/cancel?tg_user_id=` | — | rules result |

A rule row is `{chat_id, kind, rule, username, title, created_at}`. `username`
and `title` are for display only; matching is always by `chat_id`.

Clients poll `/v1/rules/meta` every 60 s and refetch only when `version` changed.

## 5. Erasure — the Play deletion path, with a wait

Google Play requires an in-app data-deletion path when an app stores
account-linked data. It does **not** require it to be instant. Deleting the rules
also clears the permanent blocks, so an instant button would be a one-tap escape
from the ratchet at exactly the moment someone most wants one.

So: the request is recorded, `effective_at = now + 60 days`
(`_ERASURE_DELAY_DAYS`), **the blocks stay enforced for the whole wait**, and the
user may cancel at any point. Due erasures are executed lazily on any rules
request and once at server boot — no scheduler.

Clients must word this as "delete my data", never as "unblock", and must show the
effective date plus a Cancel action while one is pending.

## 6. Schema (`server/schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS account_rules (
  tg_user_id BIGINT NOT NULL,
  chat_id    BIGINT NOT NULL,
  kind       TEXT   NOT NULL CHECK (kind IN ('channel','bot','group','user')),
  username   TEXT,
  title      TEXT,
  rule       TEXT   NOT NULL CHECK (rule IN ('allow','block')),
  created_at TEXT   NOT NULL,
  updated_at TEXT   NOT NULL,
  PRIMARY KEY (tg_user_id, chat_id)
);
CREATE TABLE IF NOT EXISTS account_rules_meta (
  tg_user_id BIGINT PRIMARY KEY,
  version    INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS account_erasures (
  tg_user_id   BIGINT PRIMARY KEY,
  status       TEXT NOT NULL CHECK (status IN ('pending','cancelled','done')),
  requested_at TEXT NOT NULL,
  effective_at TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
```

## 7. Client UI

**Settings → Puregram** carries two lists:

- **Allowed** — every chat the user opened up. Each row has *Withdraw* (back to
  the default closed state) and *Block permanently*.
- **Blocked** — permanent. Rows are read-only; there is no unblock control, and
  the screen says so plainly.

The refusal screen (shown at the gate) names the peer, shows its identity, and
offers: **Allow**, **Block permanently**, **Copy identifier**, *Close*. That is
also how a chat gets onto either list in the first place — the user never has to
type an id.

Blocking is a deliberate act: confirm with a dialog that states, in the user's
language, that it can never be undone.

## 8. Account binding — which device may act for an account

The device bearer token from `POST /v1/device/checkin` proves **which device** is
calling. It does not prove that the device is signed into the Telegram account it
claims: the client states its own `tg_user_id`, and Telegram gives a third-party
client nothing our server could verify against Telegram.

So the server binds accounts to devices (`account_devices`, `require_account_device`):

| Situation | Result |
|---|---|
| Nobody owns the account yet | the caller becomes its first **active** device (trust on first use) |
| The device is already `active` | allowed |
| A different device claims the account | recorded **pending**, refused with `409 device_claim_pending` |
| A pending claim older than `_DEVICE_CLAIM_DELAY_DAYS` (7) | auto-promoted to active |
| The claim was denied | refused permanently |

An already-active device sees pending claims in `GET /v1/rules/meta`
(`pending_devices`) and answers with
`POST /v1/rules/devices/{device_id}/approve` or `/deny`. Denying also cancels the
auto-approval.

This is the same shape as Telegram's own multi-device list, so it reads as
familiar rather than as a security chore. The 7-day auto-approval exists so
someone who reinstalls on their only handset is not locked out for ever — and an
attacker's claim sits visible on the real device for that entire window.

Clients must handle `409 device_claim_pending` by showing "waiting for approval
from your other device" with the effective date, not a generic error.

## 9. Discovery surfaces removed from the clients

| Surface | Android | Desktop |
|---|---|---|
| Global username search | `SearchAdapterHelper`: both result paths filtered through `canOpenPeer` — people always show | `api_peer_search.cpp`: `my_results`, `results` and sponsored peers filtered |
| Channels + Apps + Posts search tabs | `SearchViewPager` tabs removed | `dialogs_suggestions.cpp` tabs removed |
| Public-post (hashtag) search | `DialogsSearchAdapter` skips `channels.searchPosts` | `dialogs_search_posts.cpp` / `dialogs_widget.cpp` skip it |
| Similar channels / bots | `MessagesController.getChannelRecommendations` returns null | `api_chat_participants.cpp` never requests |
| Inline bots in the composer | `MentionsAdapter.searchForContextBot` returns early | `history_widget.cpp`, compose controls |
| Web image / GIF search | `PhotoPickerActivity.searchImages` returns early | — |
| Free-text GIF search | `EmojiView` GIF adapters + preloader | `GifsListWidget::sendInlineRequest` |
| Free-text sticker / emoji-set search | `MediaDataController.searchStickerSets` | `sendSearchSetsRequest`, `requestSearchStickers`, `requestSearchCloud` |
| Popular apps | — | `bot_attach_web_view.cpp` |
| Sponsored messages | `HIDE_SPONSORED_MESSAGES` | already hidden |
| Sensitive-content toggle | hidden; `"sensitive"` never ignored | hidden; never ignored |

Local search and saved/installed/trending stickers, GIFs and emoji are untouched.

## 10. Versions

- Android: `APP_VERSION_CODE` in `gradle.properties`; final versionCode = `×10 + 9`.
- Desktop: `kPuregramBuild` in `puregram_updater.cpp`.
- Both must match `_ANDROID_BUILD` / `_DESKTOP_BUILD` in `device_update.py`.
