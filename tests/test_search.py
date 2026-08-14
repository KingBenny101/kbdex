import asyncio

import pytest

from kbdex.models import TorrentResult
from kbdex.search import _search_one


class _FakeAdapter:
    name = "nyaa"
    display_name = "Nyaa.si"
    base_url = "https://nyaa.si"
    supports_category_filter = True
    supports_magnet = True
    supports_torrent_url = True
    min_request_interval_ms = 0
    max_retries = 0
    backoff_base_ms = 0

    def __init__(self) -> None:
        self.called = False

    async def search(self, query):
        self.called = True
        return [{"title": f"{query} 01", "size": "1.00 GiB", "seeders": 5}]

    def parse(self, raw_results):
        return [
            TorrentResult(
                title=item["title"],
                size_human=item["size"],
                size_bytes=1073741824,
                seeders=item["seeders"],
                source_indexer=self.name,
            )
            for item in raw_results
        ]


def test_cache_write_failure_does_not_discard_results(monkeypatch) -> None:
    adapter = _FakeAdapter()
    monkeypatch.setattr("kbdex.search.get_indexer", lambda name: adapter)

    def raise_permission_error(anidb_id, indexer, results):
        raise PermissionError("data/cache is not writable")

    monkeypatch.setattr("kbdex.search.disk_search_cache.set", raise_permission_error)

    result_dicts, from_cache, error = asyncio.run(
        _search_one("nyaa", "Attack on Titan", anidb_id=19600)
    )

    assert error is None
    assert from_cache is False
    assert result_dicts == [
        {
            "title": "Attack on Titan 01",
            "magnet_link": None,
            "torrent_url": None,
            "size_bytes": 1073741824,
            "size_human": "1.00 GiB",
            "seeders": 5,
            "leechers": 0,
            "category": "",
            "uploaded_at": None,
            "source_indexer": "nyaa",
            "parsed": None,
        }
    ]