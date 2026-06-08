import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from kbdex.config import DATA_DIR, settings


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


class DiskSearchCache:
    """Persists search results to disk as one JSON file per AniDB ID."""

    def __init__(self, data_dir: Path, ttl_seconds: int) -> None:
        self._dir = data_dir / "cache"
        self._ttl = ttl_seconds

    def _path(self, anidb_id: int) -> Path:
        return self._dir / f"{anidb_id}.json"

    def _read(self, anidb_id: int) -> dict:
        path = self._path(anidb_id)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, anidb_id: int, data: dict) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(anidb_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def get(self, anidb_id: int, indexer: str) -> Optional[list[dict]]:
        data = self._read(anidb_id)
        entry = data.get(indexer)
        if not entry:
            return None
        try:
            expires_at = datetime.fromisoformat(entry["expires_at"]).replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            return None
        if datetime.now(timezone.utc) > expires_at:
            return None
        return entry.get("results")

    def set(self, anidb_id: int, indexer: str, results: list[dict]) -> None:
        now = datetime.now(timezone.utc)
        expires_at = datetime.fromtimestamp(now.timestamp() + self._ttl, tz=timezone.utc)
        data = self._read(anidb_id)
        data["anidb_id"] = anidb_id
        data[indexer] = {
            "cached_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%S"),
            "results": results,
        }
        self._write(anidb_id, data)


title_cache: TTLCache = TTLCache(settings.title_cache_ttl_seconds)
search_cache: TTLCache = TTLCache(settings.search_cache_ttl_seconds)
disk_search_cache: DiskSearchCache = DiskSearchCache(DATA_DIR, settings.search_cache_ttl_seconds)


def make_search_cache_key(query: str, indexer: str) -> str:
    normalised = " ".join(query.lower().split())
    raw = json.dumps({"q": normalised, "i": indexer}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()
