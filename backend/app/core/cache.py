"""In-process caching for data that is (nearly) the same for everyone.

What is cached, and why that cannot mislead anyone:

  - Reference data -- categories, municipalities, the ward directory. It
    changes only when someone re-runs the seed script; ten minutes of TTL is
    the worst case after a reseed, and a restart clears it at once. It used
    to cost a database round trip (~145 ms) on nearly every request: every
    pin move on the report form re-read all 94 wards.
  - Public transparency statistics: city-wide aggregates, cached for 30 s.

What is never cached here: tickets, comments, notifications, hazards,
anything about a user. Those are always read fresh -- the browser-side cache
(frontend/src/lib/cache.ts) handles fast repaints of those, and revalidates.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

REFERENCE_TTL_S = 600
STATS_TTL_S = 30


class TTLCache:
    def __init__(self) -> None:
        self._items: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get_or_load(self, key: str, loader: Callable[[], T], ttl_s: float) -> T:
        now = time.monotonic()
        with self._lock:
            hit = self._items.get(key)
            if hit is not None and hit[0] > now:
                return hit[1]  # type: ignore[return-value]

        # Load outside the lock: a slow query must not block other keys. Two
        # concurrent misses may both load; the result is identical either way.
        value = loader()
        with self._lock:
            self._items[key] = (now + ttl_s, value)
        return value

    def invalidate(self, prefix: str = "") -> None:
        with self._lock:
            for key in [k for k in self._items if k.startswith(prefix)]:
                del self._items[key]


cache = TTLCache()
