from typing import Any, Protocol, runtime_checkable

from kbdex.models import IndexerHealth, TorrentResult


@runtime_checkable
class IndexerAdapter(Protocol):
    name: str
    display_name: str
    base_url: str
    supports_category_filter: bool
    supports_magnet: bool
    supports_torrent_url: bool
    min_request_interval_ms: int
    max_retries: int
    backoff_base_ms: int

    async def search(
        self, query: str, options: dict[str, Any] | None = None
    ) -> list[dict]:
        """Fetch raw results from the indexer for the given query string."""
        ...

    def parse(self, raw_results: list[dict]) -> list[TorrentResult]:
        """Transform raw indexer results into the standard TorrentResult shape."""
        ...

    async def health_check(self) -> IndexerHealth:
        """Probe the indexer and return its current availability status."""
        ...
