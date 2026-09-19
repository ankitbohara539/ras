"""TTLCache: the reference-data cache and the rate-limit gate built on it.

A fresh TTLCache per test, not the module-level singleton, so these never
leak state into anything else that touches app.core.cache.
"""

import time

from app.core.cache import TTLCache


class TestGetOrLoad:
    def test_a_hit_never_calls_the_loader_again(self) -> None:
        cache = TTLCache()
        calls = []
        cache.get_or_load("k", lambda: calls.append(1) or "v", ttl_s=60)
        cache.get_or_load("k", lambda: calls.append(1) or "v", ttl_s=60)
        assert len(calls) == 1

    def test_expired_entries_are_reloaded(self) -> None:
        cache = TTLCache()
        calls = []
        cache.get_or_load("k", lambda: calls.append(1) or "v", ttl_s=0)
        time.sleep(0.01)
        cache.get_or_load("k", lambda: calls.append(1) or "v", ttl_s=0)
        assert len(calls) == 2

    def test_invalidate_by_prefix(self) -> None:
        cache = TTLCache()
        cache.get_or_load("summary:a", lambda: "a", ttl_s=60)
        cache.get_or_load("summary:b", lambda: "b", ttl_s=60)
        cache.get_or_load("ref:categories", lambda: "c", ttl_s=60)
        cache.invalidate("summary:")
        calls = []
        cache.get_or_load("summary:a", lambda: calls.append(1) or "a2", ttl_s=60)
        cache.get_or_load("ref:categories", lambda: calls.append(1) or "c2", ttl_s=60)
        # Only the invalidated key was reloaded.
        assert len(calls) == 1


class TestSeenRecently:
    def test_first_call_says_go_ahead(self) -> None:
        cache = TTLCache()
        assert cache.seen_recently("k", ttl_s=60) is False

    def test_a_second_call_within_the_window_says_wait(self) -> None:
        cache = TTLCache()
        cache.seen_recently("k", ttl_s=60)
        assert cache.seen_recently("k", ttl_s=60) is True

    def test_after_the_window_it_is_go_ahead_again(self) -> None:
        cache = TTLCache()
        cache.seen_recently("k", ttl_s=0)
        time.sleep(0.01)
        assert cache.seen_recently("k", ttl_s=60) is False

    def test_different_keys_do_not_interfere(self) -> None:
        cache = TTLCache()
        cache.seen_recently("citizen-a", ttl_s=60)
        assert cache.seen_recently("citizen-b", ttl_s=60) is False
