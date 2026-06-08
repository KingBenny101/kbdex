import asyncio
import gzip
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from kbdex.config import settings
from kbdex.models import TitleEntry

logger = logging.getLogger(__name__)

# AniDB type codes in the titles dump
_TYPE_MAP = {
    "1": "main",
    "2": "synonym",
    "3": "short",
    "4": "official",
}


class AniDBDump:
    def __init__(self) -> None:
        self._index: dict[int, list[TitleEntry]] = {}
        self._last_refreshed: Optional[datetime] = None
        self._lock = asyncio.Lock()

    @property
    def last_refreshed(self) -> Optional[datetime]:
        return self._last_refreshed

    @property
    def entry_count(self) -> int:
        return len(self._index)

    @property
    def is_loaded(self) -> bool:
        return bool(self._index)

    def get_titles(self, anidb_id: int) -> Optional[list[TitleEntry]]:
        return self._index.get(anidb_id)

    async def ensure_loaded(self) -> None:
        async with self._lock:
            if not self._index:
                await self._load()

    async def refresh(self) -> None:
        async with self._lock:
            await self._load()

    async def _load(self) -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        dump_path = settings.data_dir / "anime-titles.dat.gz"

        if not dump_path.exists() or self._is_stale(dump_path):
            await self._download(dump_path)

        self._index = await asyncio.to_thread(self._parse, dump_path)
        self._last_refreshed = datetime.now(timezone.utc)
        logger.info("AniDB dump loaded: %d entries", len(self._index))

    def _is_stale(self, path: Path) -> bool:
        age_seconds = time.time() - path.stat().st_mtime
        return age_seconds > settings.dump_refresh_interval_seconds

    async def _download(self, dest: Path) -> None:
        logger.info("Downloading AniDB titles dump from %s", settings.anidb_dump_url)
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(settings.anidb_dump_url)
            resp.raise_for_status()
        dest.write_bytes(resp.content)
        logger.info("AniDB dump saved to %s (%d bytes)", dest, len(resp.content))

    @staticmethod
    def _parse(path: Path) -> dict[int, list[TitleEntry]]:
        index: dict[int, list[TitleEntry]] = {}
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("|", 3)
                if len(parts) != 4:
                    continue
                aid_str, type_code, language, title = parts
                try:
                    aid = int(aid_str)
                except ValueError:
                    continue
                title_type = _TYPE_MAP.get(type_code, "synonym")
                index.setdefault(aid, []).append(
                    TitleEntry(type=title_type, language=language, value=title)
                )
        return index


dump = AniDBDump()
