# Licensing and attribution

Puregram is an **unofficial, independent** project. It is not affiliated with,
endorsed by, or connected to Telegram FZ-LLC. "Telegram" and the Telegram logo
are trademarks of their respective owners.

## What this project is built on

| Component | Upstream | License |
|---|---|---|
| `telegram/telegram-android/` | [DrKLO/Telegram](https://github.com/DrKLO/Telegram) | GPL-2.0-or-later |
| `telegram/tdesktop/` | [telegramdesktop/tdesktop](https://github.com/telegramdesktop/tdesktop) | GPL-3.0-or-later, with the OpenSSL exception |
| `server/`, `site/`, this repository's own code | original to Puregram | GPL-3.0-or-later |

Both forks keep their upstream copyright notices and license files. The full
license texts are in each fork's directory (`LICENSE`).

## Your rights

Puregram is free software. You may use, study, modify and redistribute it under
the terms of the GNU General Public License as published by the Free Software
Foundation — version 2 or later for the Android client, version 3 or later for
the desktop client and for this project's own code.

This program is distributed in the hope that it will be useful, but **WITHOUT ANY
WARRANTY**; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

## Corresponding source

The complete corresponding source for every binary distributed at
<https://puregram.app/download/> is this repository, at the tag matching that
build's version. Build instructions are in [BUILDING.md](BUILDING.md).

Two things are deliberately **not** in the source, and neither is part of the
program:

- **Telegram API credentials** (`api_id` / `api_hash`). These are account
  credentials issued to a developer by Telegram, not code; Telegram's API terms
  forbid publishing them. Get your own free pair at <https://my.telegram.org> —
  BUILDING.md explains where to put it.
- **Signing keys.** A key identifies the publisher; it is not part of the
  program's source. Generate your own.

Every other file needed to build, install and run a modified version is here.

## Changes against upstream

The behavioural difference is deliberately small and is specified in
[POLICY_SPEC.md](POLICY_SPEC.md):

1. People and secret chats always open; channels, bots and groups are closed
   until the user allows them.
2. A block the user makes is permanent and cannot be undone (a one-way ratchet).
3. Discovery surfaces are removed: global channel/bot search, the Channels/Apps/
   Posts tabs, similar-channel suggestions, inline bots, web image search, and
   free-text GIF and sticker search. Local search is untouched.
4. Telegram's own `restriction_reason` is always enforced and the
   "show sensitive content" switch is removed.
5. Sponsored messages are not displayed.
6. Branding: the app is named Puregram and uses its own icon.

Nothing else about Telegram's messaging, encryption or protocol is modified.
