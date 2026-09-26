"""Play review-access relay.

Google's reviewers cannot receive a Telegram login code, so they could not sign
in and the production release was rejected ("login details unavailable").

This service stays signed into a dedicated, empty review account. When the
reviewer asks Telegram for a login code on their device, Telegram delivers it
to this session as a message from its service account (777000). The relay
writes the code to an unguessable page whose address exists only in the
private Play Console "App access" form.

The code alone does not open the account: two-step verification is on, and its
password is in that same private form. If the page ever leaked, the exposure is
an account with nothing in it.

Configuration comes from the environment (see the systemd unit):
    REVIEW_API_ID, REVIEW_API_HASH   the app's Telegram API pair
    REVIEW_SESSION                   session path, without ".session"
    REVIEW_PAGE_DIR                  directory the page is written into
"""
from __future__ import annotations

import html
import logging
import os
import re
import sys
import tempfile
import time
from pathlib import Path

from telethon import TelegramClient, events

TELEGRAM_SERVICE_ACCOUNT = 777000
# Seconds a code stays on the page before the page stops showing it. Telegram
# codes expire on their own; this just keeps a stale one from confusing anyone.
CODE_LIFETIME_SECONDS = 600
PAGE_REFRESH_SECONDS = 5

# The code must sit next to a word that names it. A bare "first 5-6 digit run"
# would also catch digits in Telegram's "new login from device X" notices and
# overwrite the real code with a device model number.
CODE_PATTERNS = (
    re.compile(r"(?i)login code\D{0,20}(\d{5,6})"),
    re.compile(r"(?i)\bcode\D{0,20}(\d{5,6})"),
    re.compile(r"رمز\D{0,40}(\d{5,6})"),
)

log = logging.getLogger("review-relay")


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"missing environment variable {name}")
    return value


def extract_code(text: str) -> str | None:
    for pattern in CODE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def render_page(code: str | None, received_at: float | None) -> str:
    if code is None or received_at is None:
        body = (
            "<p class=\"state\">No code yet.</p>"
            "<p>In the app, enter the phone number and request a login code. "
            "It will appear here within a few seconds.</p>"
        )
        stamp = "0"
    else:
        when = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(received_at))
        body = (
            f"<p class=\"code\" id=\"code\">{html.escape(code)}</p>"
            f"<p>Received {html.escape(when)}. Enter it in the app, then the "
            "two-step verification password from the App access form.</p>"
            "<p id=\"stale\" hidden>This code is old. Request a new one in the "
            "app.</p>"
        )
        stamp = str(int(received_at))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{PAGE_REFRESH_SECONDS}">
<title>Puregram review login code</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:32rem;margin:3rem auto;padding:0 1rem;color:#1a1a1a;background:#fff}}
h1{{font-size:1.1rem;color:#2e9e4f}}
.code{{font-size:3rem;font-weight:700;letter-spacing:.3rem;margin:1rem 0}}
.state{{font-size:1.4rem;font-weight:600}}
</style></head><body>
<h1>Puregram — login code for Google Play review</h1>
{body}
<script>
(function(){{var at={stamp},c=document.getElementById('code'),s=document.getElementById('stale');
if(at&&c&&(Date.now()/1000-at)>{CODE_LIFETIME_SECONDS}){{c.hidden=true;if(s)s.hidden=false;}}}})();
</script>
</body></html>
"""


def write_page(page_dir: Path, content: str) -> None:
    """Replace the page in one step, so the reviewer never reads half a file."""
    page_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=page_dir, prefix=".page-", suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(tmp, 0o644)
        os.replace(tmp, page_dir / "index.html")
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    api_id = int(required_env("REVIEW_API_ID"))
    api_hash = required_env("REVIEW_API_HASH")
    session = required_env("REVIEW_SESSION")
    page_dir = Path(required_env("REVIEW_PAGE_DIR"))

    write_page(page_dir, render_page(None, None))
    client = TelegramClient(session, api_id, api_hash)

    @client.on(events.NewMessage(from_users=TELEGRAM_SERVICE_ACCOUNT))
    async def on_service_message(event: events.NewMessage.Event) -> None:
        code = extract_code(event.raw_text or "")
        if code is None:
            log.info("service message without a login code, ignored")
            return
        write_page(page_dir, render_page(code, time.time()))
        log.info("login code published")

    client.start()
    if not client.is_connected():
        sys.exit("could not connect to Telegram")
    log.info("relay running")
    client.run_until_disconnected()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
