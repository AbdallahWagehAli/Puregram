# Review relay — Google Play "App access"

Puregram signs in with a Telegram account: phone number, a one-time login code,
then a two-step verification password. A Google reviewer on an arbitrary device
cannot receive that code, so the first production submission was rejected
with *"login details unavailable"*.

This relay stays signed into a dedicated, **empty** review account. When the
reviewer requests a code, Telegram delivers it to this session as a message
from its service account (`777000`); the relay publishes it on a page whose
address is a random token given only in the private App access form.

The code alone does not open the account — two-step verification is on and its
password lives only in that same form. A leak exposes an account with nothing
in it.

## Files

| File | Where it runs | Purpose |
|------|---------------|---------|
| `login.py` | once, on a developer machine | interactive sign-in; writes the session outside the repo |
| `relay.py` | the VPS, as `puregram-review` | publishes each login code to `/var/www/puregram.app/r/<token>/` |
| `puregram-review-relay.service` | `/etc/systemd/system/` | sandboxed unit: can write only its own dir and the page dir |

The nginx site has a `location /r/` block: `autoindex off` (a listing would
reveal the token), `Cache-Control: no-store` (a cached page would show a stale
code), `X-Robots-Tag: noindex`.

## Never committed

- the session file — `~/Desktop/Puregram-secrets/review-relay/review.session`
- `/opt/puregram-review-relay/.env` — API pair, session path, page directory
- the page token itself

## Operating notes

- Do not run the session from two places at once; Telegram can revoke an auth
  key used concurrently from different addresses. The copy on the VPS is the
  live one.
- `journalctl -u puregram-review-relay` shows each published code event.
- Once the app is approved and review access is no longer needed, stop the unit
  and terminate the relay's session from Telegram's *Devices* screen.
