import asyncio
import logging
import re
from typing import Optional

import httpx

from kbdex.anidb.dump import resolve_titles
from kbdex.cache import make_search_cache_key, search_cache
from kbdex.config import settings
from kbdex.indexers import get_indexer
from kbdex.models import (
    IndexerError,
    QueryParams,
    SearchResponse,
    TitleEntry,
    TorrentResult,
)

logger = logging.getLogger(__name__)

_INFO_HASH_RE = re.compile(
    r"xt=urn:btih:([a-fA-F0-9]{40}|[A-Z2-7]{32})", re.IGNORECASE
)


def _extract_info_hash(magnet: str) -> str | None:
    m = _INFO_HASH_RE.search(magnet)
    return m.group(1).lower() if m else None


def _deduplicate(results: list[TorrentResult]) -> list[TorrentResult]:
    seen: set[str] = set()
    out: list[TorrentResult] = []
    for r in results:
        key = (
            _extract_info_hash(r.magnet_link)
            if r.magnet_link
            else r.title.lower()
        )
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def build_queries(
    titles: list[TitleEntry],
    q: Optional[str],
    season: Optional[int],
    episode: Optional[int],
) -> list[str]:
    """Construct prioritised, deduplicated search query strings."""
    if q:
        return [q]

    xjat = next(
        (t.value for t in titles if t.type == "main" and t.language == "x-jat"), None
    )
    _ja_raw = next(
        (t.value for t in titles if t.language == "ja" and t.type in ("main", "official")), None
    )
    # AniDB often appends a romanised subtitle after the Japanese script
    # e.g. "進撃の巨人 attack on titan" → strip the ASCII tail so Nyaa finds raw releases
    ja = re.sub(r"\s+[a-zA-Z].*$", "", _ja_raw).strip() if _ja_raw else None
    en_official = next(
        (t.value for t in titles if t.type == "official" and t.language == "en"), None
    )
    # Deduplicate while preserving priority order: romanised → japanese → english
    seen_titles: set[str] = set()
    candidates: list[str] = []
    for v in [xjat, ja, en_official]:
        if v and v not in seen_titles:
            seen_titles.add(v)
            candidates.append(v)
    if not candidates and titles:
        candidates = [titles[0].value]

    if not candidates:
        return []

    queries: list[str] = []

    if season is not None and episode is not None:
        ep = f"{episode:02d}"
        seas = f"{season:02d}"
        for title in candidates:
            queries.append(f"{title} - {ep}")
            queries.append(f"{title} S{seas}E{ep}")
        if candidates:
            queries.append(f"{candidates[0]} {ep}")
    elif season is not None:
        for title in candidates:
            queries.append(f"{title} Season {season}")
            queries.append(f"{title} S{season:02d}")
    else:
        for title in candidates:
            queries.append(title)

    seen: set[str] = set()
    deduped: list[str] = []
    for query in queries:
        norm = " ".join(query.lower().split())
        if norm not in seen:
            seen.add(norm)
            deduped.append(query)

    return deduped


async def _search_one(
    indexer_name: str,
    query: str,
) -> tuple[list[TorrentResult], bool, Optional[IndexerError]]:
    """
    Run a single (indexer, query) pair.
    Returns (results, from_cache, error_or_None).
    """
    adapter = get_indexer(indexer_name)
    if adapter is None:
        return [], False, IndexerError(
            indexer=indexer_name,
            code="UNKNOWN_INDEXER",
            message=f"Indexer '{indexer_name}' is not registered.",
            retryable=False,
        )

    cache_key = make_search_cache_key(query, indexer_name)
    cached = search_cache.get(cache_key)
    if cached is not None:
        return cached, True, None

    try:
        raw = await adapter.search(query)
        results = adapter.parse(raw)
        search_cache.set(cache_key, results, settings.search_cache_ttl_seconds)
        return results, False, None
    except RuntimeError as exc:
        return [], False, IndexerError(
            indexer=indexer_name,
            code="CIRCUIT_OPEN",
            message=str(exc),
            retryable=False,
        )
    except Exception as exc:
        code = "TIMEOUT" if isinstance(exc, httpx.TimeoutException) else "HTTP_ERROR"
        return [], False, IndexerError(
            indexer=indexer_name,
            code=code,
            message=str(exc),
            retryable=True,
        )


async def run_search(params: QueryParams) -> SearchResponse:
    warnings: list[str] = []

    # Step 1 – Resolve AniDB titles
    resolved_titles: list[TitleEntry] = []
    if params.anidb_id is not None:
        resolved_titles, _ = resolve_titles(params.anidb_id)

    # Step 2 – Build queries
    queries = build_queries(resolved_titles, params.q, params.season, params.episode)

    if params.season is not None and params.episode is not None:
        warnings.append(
            "season/episode is used for query formatting only; "
            "verify the absolute episode number in release filenames."
        )

    # Step 3 – Fan out: each (indexer, query) pair runs concurrently
    tasks = [
        _search_one(indexer_name, query)
        for indexer_name in params.indexers
        for query in queries
    ]
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    # Step 4 – Aggregate
    all_results: list[TorrentResult] = []
    errors_by_indexer: dict[str, IndexerError] = {}
    all_from_cache = True

    for outcome in outcomes:
        if isinstance(outcome, Exception):
            logger.exception("Unexpected error during search gather: %s", outcome)
            continue
        results, from_cache, error = outcome
        if error:
            errors_by_indexer[error.indexer] = error
        else:
            all_results.extend(results)
            if not from_cache:
                all_from_cache = False

    all_results = _deduplicate(all_results)
    all_results.sort(key=lambda r: r.seeders, reverse=True)

    errors = list(errors_by_indexer.values())
    partial = bool(errors) and bool(all_results)

    return SearchResponse(
        query=params,
        resolved_titles=resolved_titles,
        queries_executed=queries,
        results=all_results,
        total_results=len(all_results),
        from_cache=all_from_cache and bool(all_results),
        errors=errors,
        warnings=warnings,
        partial=partial,
    )
