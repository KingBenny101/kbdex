import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from kbdex.config import DATA_DIR, settings
from kbdex.exceptions import AnimeListsNotReadyError, IDMappingNotFoundError

logger = logging.getLogger(__name__)

# ID fields that can be used to look up an anidb_id (all integer-valued)
SUPPORTED_FIELDS = [
    "mal_id",
    "anilist_id",
    "kitsu_id",
    "tvdb_id",
    "anisearch_id",
    "animenewsnetwork_id",
    "livechart_id",
    "simkl_id",
]

# All cross-DB ID fields stored per entry (superset — includes non-integer and sparse ones)
_ALL_ID_FIELDS = SUPPORTED_FIELDS + [
    "imdb_id",
    "anime-planet_id",
    "animecountdown_id",
    "themoviedb_id",
]


class AnimeListMapper:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._loaded = False
        self._last_refreshed: Optional[datetime] = None
        self._entry_count: int = 0
        self._indices: dict[str, dict[str, int]] = {}
        self._id_map: dict[int, dict[str, Any]] = {}  # anidb_id → all non-null cross-DB IDs

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def last_refreshed(self) -> Optional[datetime]:
        return self._last_refreshed

    @property
    def entry_count(self) -> int:
        return self._entry_count

    async def ensure_loaded(self) -> None:
        async with self._lock:
            if not self._loaded:
                await self._load()

    async def refresh(self) -> None:
        async with self._lock:
            await self._load()

    async def _load(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = DATA_DIR / "anime-list-full.json"

        if not path.exists() or self._is_stale(path):
            await self._download(path)

        indices, id_map, count = await asyncio.to_thread(self._parse, path)
        self._indices = indices
        self._id_map = id_map
        self._entry_count = count
        self._loaded = True
        self._last_refreshed = datetime.now(timezone.utc)
        logger.info("anime-lists loaded: %d entries", count)

    def _is_stale(self, path: Path) -> bool:
        age_seconds = time.time() - path.stat().st_mtime
        return age_seconds > settings.animelists_refresh_interval_seconds

    async def _download(self, dest: Path) -> None:
        logger.info("Downloading anime-lists from %s", settings.animelists_url)
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(settings.animelists_url)
            resp.raise_for_status()
        tmp = dest.with_suffix(".tmp")
        tmp.write_bytes(resp.content)
        tmp.replace(dest)
        logger.info("anime-lists saved to %s (%d bytes)", dest, len(resp.content))

    @staticmethod
    def _parse(path: Path) -> tuple[dict[str, dict[str, int]], dict[int, dict[str, Any]], int]:
        data = json.loads(path.read_text(encoding="utf-8"))
        indices: dict[str, dict[str, int]] = {f: {} for f in SUPPORTED_FIELDS}
        id_map: dict[int, dict[str, Any]] = {}
        count = 0
        for entry in data:
            anidb_id = entry.get("anidb_id")
            if not anidb_id:
                continue
            count += 1
            for field in SUPPORTED_FIELDS:
                val = entry.get(field)
                if val is not None:
                    indices[field][str(val)] = anidb_id
            ids = {f: entry[f] for f in _ALL_ID_FIELDS if entry.get(f) is not None}
            if ids:
                id_map[anidb_id] = ids
        return indices, id_map, count

    def resolve(self, id_type: str, id_value: int) -> int:
        if not self._loaded:
            raise AnimeListsNotReadyError()
        idx = self._indices.get(id_type, {})
        anidb_id = idx.get(str(id_value))
        if anidb_id is None:
            raise IDMappingNotFoundError(id_type, id_value)
        return anidb_id

    def get_ids(self, anidb_id: int) -> Optional[dict[str, Any]]:
        """Return all cross-DB IDs for the given anidb_id, or None if not in the mapping."""
        if not self._loaded:
            raise AnimeListsNotReadyError()
        return self._id_map.get(anidb_id)


mapper = AnimeListMapper()
