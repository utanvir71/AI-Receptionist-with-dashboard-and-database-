"""Small in-process idempotency cache for duplicate Vapi tool calls."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable
from threading import Lock
from typing import Generic, TypeVar


T = TypeVar("T")


class IdempotencyCache(Generic[T]):
    """Store a bounded number of responses by caller-provided idempotency keys."""

    def __init__(self, *, max_entries: int = 512) -> None:
        self._max_entries = max_entries
        self._responses: OrderedDict[Hashable, T] = OrderedDict()
        self._lock = Lock()

    def get(self, key: Hashable) -> T | None:
        """Return a cached response and mark it recently used."""
        with self._lock:
            response = self._responses.get(key)
            if response is not None:
                self._responses.move_to_end(key)
            return response

    def set(self, key: Hashable, response: T) -> T:
        """Cache and return a response."""
        with self._lock:
            self._responses[key] = response
            self._responses.move_to_end(key)
            while len(self._responses) > self._max_entries:
                self._responses.popitem(last=False)
            return response

    def clear(self) -> None:
        """Clear cached responses. Intended for tests and process lifecycle resets."""
        with self._lock:
            self._responses.clear()
