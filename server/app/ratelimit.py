"""Rate limiting for the control API.

The service runs as a single uvicorn worker (see the systemd unit), so a table
in memory is the whole store — no Redis, no extra dependency. That is the one
assumption to re-check: add `--workers` and these counters become per-worker,
and the limits have to move to a shared store.

Two different keys, because they defend against two different things:

  * **by address** — for minting device tokens. `POST /device/checkin` hands a
    bearer token to anyone who invents a `device_id`, so it is the cheapest
    place to start abusing the API.
  * **by device** — for writing rules. The write is the damaging call: `block`
    is permanent by design and the server refuses to lift it. One token can
    address any number of accounts, so capping the token matters far more than
    capping the address it arrived from.

Address limits are deliberately loose. Mobile users sit behind carrier-grade
NAT in their thousands; a limit tight enough to inconvenience a determined
attacker would lock out a whole carrier's worth of legitimate ones. The tight
limits live on the device key, where a real client's behaviour is predictable.

This does not close the account-verification gap — nothing here proves the
caller owns the Telegram account it names. It raises the cost of abusing that
gap at scale. See LEGAL-COMPLIANCE.md.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

# Counters are bucketed into fixed windows; a caller gets `calls` per `window`.
_HOUR = 3600.0
# Drop cold entries occasionally so a long-running process cannot grow forever.
_PRUNE_INTERVAL_SECONDS = 600.0


@dataclass(frozen=True)
class Limit:
    """`calls` requests per `window` seconds, for one caller in one bucket."""

    calls: int
    window: float = _HOUR

    def __post_init__(self) -> None:
        if self.calls < 1 or self.window <= 0:
            raise ValueError("a limit needs a positive call count and window")


class _FixedWindowCounters:
    """Fixed-window counters, safe to call from several threads.

    FastAPI runs this app's `def` handlers in a worker threadpool, so more than
    one request really can land here at once — hence the lock. A fixed window
    is coarser than a sliding one (a caller may burst across a boundary), which
    is a fair trade for defence that costs nothing to operate.
    """

    def __init__(self) -> None:
        self._windows: dict[tuple[str, str], tuple[float, int]] = {}
        self._lock = threading.Lock()
        self._pruned_at = time.monotonic()

    def hit(self, bucket: str, caller: str, limit: Limit) -> float:
        """Record one call. Returns 0.0 when allowed, else seconds to wait."""
        now = time.monotonic()
        key = (bucket, caller)
        with self._lock:
            self._prune(now)
            started, count = self._windows.get(key, (now, 0))
            if now - started >= limit.window:
                started, count = now, 0
            count += 1
            self._windows[key] = (started, count)
            if count <= limit.calls:
                return 0.0
            return max(1.0, limit.window - (now - started))

    def _prune(self, now: float) -> None:
        """Drop windows that have expired. Caller holds the lock."""
        if now - self._pruned_at < _PRUNE_INTERVAL_SECONDS:
            return
        self._pruned_at = now
        stale = [
            key for key, (started, _) in self._windows.items()
            if now - started >= _HOUR
        ]
        for key in stale:
            del self._windows[key]


_counters = _FixedWindowCounters()


def client_address(request: Request) -> str:
    """The caller's address, as nginx saw it.

    `X-Real-IP` and not `X-Forwarded-For`: the site config sets X-Real-IP from
    `$remote_addr`, which nginx alone controls, while X-Forwarded-For is
    `$proxy_add_x_forwarded_for` — it appends to whatever the client sent, so
    its first entry is attacker-chosen and useless as a limiter key.
    """
    forwarded = request.headers.get("x-real-ip")
    if forwarded:
        return forwarded.strip()
    return request.client.host if request.client else "unknown"


def enforce(bucket: str, caller: str, limit: Limit) -> None:
    """Count this call, or raise 429 with how long to wait."""
    retry_after = _counters.hit(bucket, caller, limit)
    if retry_after:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"too many requests; retry in {int(retry_after)}s",
            headers={"Retry-After": str(int(retry_after))},
        )


def by_address(bucket: str, limit: Limit):
    """A dependency that limits a route by caller address."""

    def dependency(request: Request) -> None:
        enforce(bucket, client_address(request), limit)

    return dependency
