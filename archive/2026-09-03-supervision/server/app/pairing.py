"""Pairing-code helpers for the device→supervisor linking flow.

The managed phone mints a short, human-readable code; a supervisor redeems it.
Codes use an unambiguous alphabet (no 0/O/1/I/L/U) so they read cleanly aloud and
inside Arabic RTL layouts. Only the keyed HMAC of the normalized code is
persisted — a database leak alone cannot brute-force a live code because the
server secret is required to compute the hash, and the lookup stays a plain
indexed equality (unlike a per-row-salted Argon2 hash).
"""
from __future__ import annotations

import hmac
import re
import secrets
from hashlib import sha256

from .config import settings

# Crockford-style minus vowels and ambiguous glyphs → no accidental words and no
# 0/O, 1/I/L, or U confusion when a code is read aloud or typed.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
_CODE_LEN = 8
_NON_CODE = re.compile(r"[^0-9A-Z]")


def generate_code() -> str:
    """A fresh 8-char code (~40 bits) drawn from the unambiguous alphabet."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))


def format_code(code: str) -> str:
    """Group a raw 8-char code as ``XXXX-XXXX`` for display; pass through others."""
    return f"{code[:4]}-{code[4:]}" if len(code) == _CODE_LEN else code


def normalize_code(raw: str) -> str:
    """Canonicalize user input (uppercase, drop spaces/dashes) before hashing.

    The alphabet is ambiguity-free, so no character folding is needed — only
    formatting noise is stripped.
    """
    return _NON_CODE.sub("", raw.upper())


def hash_code(raw: str) -> str:
    """Keyed HMAC-SHA256 of the normalized code — deterministic, so it can be a
    unique-indexed column, yet unforgeable without the server secret."""
    normalized = normalize_code(raw)
    return hmac.new(
        settings.jwt_secret.encode(), normalized.encode(), sha256
    ).hexdigest()
