"""One-time sign-in for the Play review-access relay.

Run this once, on your own machine, and answer three prompts: the review
account's phone number, the login code Telegram sends it, and its two-step
verification password. The result is a session file — the relay's equivalent
of a phone that stays signed in — written OUTSIDE the repository, beside the
other secrets. Nothing you type is kept except that session.

Usage (from the repository root):
    python review-relay/login.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from telethon import functions
from telethon.sync import TelegramClient

REPO = Path(__file__).resolve().parent.parent
PROPERTIES = REPO / "telegram" / "telegram-android" / "local.properties"
SECRETS_DIR = Path.home() / "Desktop" / "Puregram-secrets" / "review-relay"
SESSION_PATH = SECRETS_DIR / "review"  # Telethon appends ".session"

# A Google reviewer reads everything in this account. More chats than this
# means it is somebody's real account, and it should not be used for review.
PERSONAL_ACCOUNT_THRESHOLD = 5


def read_api_pair() -> tuple[int, str]:
    """The app's own Telegram API pair, from the gitignored local.properties."""
    if not PROPERTIES.exists():
        sys.exit(f"missing {PROPERTIES} — it holds the Telegram API pair")
    values: dict[str, str] = {}
    for line in PROPERTIES.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key.strip()] = value.strip()
    try:
        return int(values["PUREGRAM_API_ID"]), values["PUREGRAM_API_HASH"]
    except (KeyError, ValueError) as exc:
        sys.exit(f"cannot read the Telegram API pair from {PROPERTIES}: {exc}")


def main() -> int:
    api_id, api_hash = read_api_pair()
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    print("Signing the review relay into Telegram.")
    print("You will be asked for, in order:")
    print("  1. the review account's phone number, with country code (+20...)")
    print("  2. the login code Telegram sends to that account")
    print("  3. its two-step verification password (typing stays hidden)\n")

    with TelegramClient(str(SESSION_PATH), api_id, api_hash) as client:
        client.start()
        me = client.get_me()
        password = client(functions.account.GetPasswordRequest())
        dialogs = client.get_dialogs(limit=PERSONAL_ACCOUNT_THRESHOLD + 1)

        print(f"\nSigned in as: {me.first_name or ''} (id {me.id})")
        if not password.has_password:
            print("WARNING: two-step verification is OFF on this account.")
            print("         Turn it on before submitting to Google: the code")
            print("         page alone must never be enough to get in.")
        else:
            print("Two-step verification: ON")
        if len(dialogs) > PERSONAL_ACCOUNT_THRESHOLD:
            print("WARNING: this account has several chats. The reviewer will")
            print("         see all of them — use an empty account.")

    print(f"\nSession saved to: {SESSION_PATH}.session")
    print("Never commit or share this file. You can close this window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
