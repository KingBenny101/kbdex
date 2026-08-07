from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class TitleEntry(BaseModel):
    type: str       # "main", "official", "short", "synonym"
    language: str   # "en", "ja", "x-jat", etc.
    value: str


class ParsedInfo(BaseModel):
    episode_number: Optional[str] = None   # "01", "01-12" for batches
    anime_season: Optional[str] = None     # "01", "02"
    video_resolution: Optional[str] = None
    release_group: Optional[str] = None
    video_codec: Optional[str] = None
    source: Optional[str] = None
    audio_codec: Optional[str] = None


class TorrentResult(BaseModel):
    title: str
    magnet_link: Optional[str] = None
    torrent_url: Optional[str] = None
    size_bytes: int = 0
    size_human: str = ""
    seeders: int = 0
    leechers: int = 0
    category: str = ""
    uploaded_at: Optional[datetime] = None
    source_indexer: str
    parsed: Optional[ParsedInfo] = None


class IndexerError(BaseModel):
    indexer: str
    code: str
    message: str
    retryable: bool = True


class QueryParams(BaseModel):
    anidb_id: Optional[int] = None
    q: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    indexers: list[str] = []


class SearchResponse(BaseModel):
    query: QueryParams
    resolved_titles: list[TitleEntry] = []
    results: list[TorrentResult] = []
    total_results: int = 0
    from_cache: bool = False
    errors: list[IndexerError] = []
    partial: bool = False


class TitleResponse(BaseModel):
    anidb_id: int
    titles: list[TitleEntry]
    mapped_ids: dict[str, Any] = {}
    source: str = "dump"
    dump_last_refreshed: Optional[datetime] = None
    from_cache: bool = False


class IndexerHealth(BaseModel):
    status: str  # "ok", "degraded", "down"
    last_checked: Optional[datetime] = None


class DumpHealth(BaseModel):
    status: str
    last_refreshed: Optional[datetime] = None
    entry_count: int = 0


class AnimeListsHealth(BaseModel):
    status: str
    last_refreshed: Optional[datetime] = None
    entry_count: int = 0


class HealthResponse(BaseModel):
    status: str  # "ok", "degraded"
    indexers: dict[str, IndexerHealth] = {}
    anidb_dump: DumpHealth
    animelists: AnimeListsHealth


class ErrorDetail(BaseModel):
    code: str
    message: str
    param: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
