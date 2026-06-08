import hashlib
import json
import time
from typing import Any, Optional

from kbdex.config import settings


class TTLCache:
    def __init__(self, default_ttl_seconds: int) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        self._store[key] = (value, time.monotonic() + ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


title_cache: TTLCache = TTLCache(settings.title_cache_ttl_seconds)
search_cache: TTLCache = TTLCache(settings.search_cache_ttl_seconds)


def make_search_cache_key(query: str, indexer: str) -> str:
    normalised = " ".join(query.lower().split())
    raw = json.dumps({"q": normalised, "i": indexer}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()
