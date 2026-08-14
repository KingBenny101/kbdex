import asyncio
import logging
import re
from typing import Optional

import anitopy
import guessit
import httpx

from kbdex.anidb.dump import resolve_titles
from kbdex.cache import disk_search_cache, make_search_cache_key, search_cache
from kbdex.config import settings
from kbdex.indexers import get_indexer
from kbdex.models import (
    IndexerError,
    ParsedInfo,
    QueryParams,
    SearchResponse,
    TitleEntry,
    TorrentResult,
)

logger = logging.getLogger(__name__)

_INFO_HASH_RE = re.compile(
    r"xt=urn:btih:([a-fA-F0-9]{40}|[A-Z2-7]{32})", re.IGNORECASE
)


def _safe_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _extract_info_hash(magnet: str) -> str | None:
    m = _INFO_HASH_RE.search(magnet)
    return m.group(1).lower() if m else None


def _deduplicate(results: list[TorrentResult]) -> list[TorrentResult]:
    seen: set[str] = set()
    out: list[TorrentResult] = []
    for r in results:
        if r.magnet_link:
            key = _extract_info_hash(r.magnet_link) or r.title.lower()
        else:
            key = r.title.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _extract_title_queries(titles: list[TitleEntry]) -> list[str]:
    """Extract bare title strings for indexer queries, no season/episode formatting."""
    xjat = next(
        (t.value for t in titles if t.type == "main" and t.language == "x-jat"), None
    )
    _ja_raw = next(
        (t.value for t in titles if t.language == "ja" and t.type in ("main", "official")), None
    )
    # Strip romanised ASCII tail from Japanese titles (e.g. "進撃の巨人 attack on titan")
    ja = re.sub(r"\s+[a-zA-Z].*$", "", _ja_raw).strip() if _ja_raw else None
    en_official = next(
        (t.value for t in titles if t.type == "official" and t.language == "en"), None
    )

    seen: set[str] = set()
    queries: list[str] = []
    for v in [xjat, ja, en_official]:
        if v and v not in seen:
            seen.add(v)
            queries.append(v)

    if not queries and titles:
        queries = [titles[0].value]

    return queries


def _try_anitopy(title: str) -> ParsedInfo:
    try:
        p = anitopy.parse(title)
        return ParsedInfo(
            episode_number=p.get("episode_number"),
            anime_season=p.get("anime_season"),
            video_resolution=p.get("video_resolution"),
            release_group=p.get("release_group"),
            video_codec=p.get("video_codec"),
            source=p.get("source"),
            audio_codec=p.get("audio_codec"),
        )
    except Exception:
        return ParsedInfo()


def _try_guessit(title: str) -> ParsedInfo:
    try:
        g = guessit.guessit(title)

        ep = g.get("episode")
        if isinstance(ep, list):
            episode_number = f"{min(ep):02d}-{max(ep):02d}"
        elif isinstance(ep, int):
            episode_number = f"{ep:02d}"
        else:
            episode_number = None

        season = g.get("season")
        if isinstance(season, list):
            season = season[0]
        anime_season = f"{int(season):02d}" if season is not None else None

        return ParsedInfo(
            episode_number=episode_number,
            anime_season=anime_season,
            video_resolution=g.get("screen_size"),
            release_group=g.get("release_group"),
            video_codec=g.get("video_codec"),
            source=g.get("source"),
            audio_codec=g.get("audio_codec"),
        )
    except Exception:
        return ParsedInfo()


def _parse_torrent_info(title: str) -> ParsedInfo:
    a = _try_anitopy(title)
    g = _try_guessit(title)
    return ParsedInfo(
        episode_number=a.episode_number or g.episode_number,
        anime_season=a.anime_season or g.anime_season,
        video_resolution=a.video_resolution or g.video_resolution,
        release_group=a.release_group or g.release_group,
        video_codec=a.video_codec or g.video_codec,
        source=a.source or g.source,
        audio_codec=a.audio_codec or g.audio_codec,
    )


def _matches_episode(
    parsed: ParsedInfo,
    season: Optional[int],
    episode: Optional[int],
) -> bool:
    if season is None and episode is None:
        return True

    if season is not None and parsed.anime_season is not None:
        try:
            if int(parsed.anime_season) != season:
                return False
        except ValueError:
            pass

    if episode is not None:
        ep_str = parsed.episode_number
        if ep_str is None:
            return True  # no episode tag — likely a batch, include it
        if "-" in ep_str:
            try:
                lo, hi = ep_str.split("-", 1)
                if not (int(lo) <= episode <= int(hi)):
                    return False
            except ValueError:
                pass
        else:
            try:
                if int(ep_str) != episode:
                    return False
            except ValueError:
                pass

    return True


async def _search_one(
    indexer_name: str,
    query: str,
    anidb_id: Optional[int] = None,
) -> tuple[list[dict], bool, Optional[IndexerError]]:
    """
    Run a single (indexer, query) pair.
    Returns (result_dicts, from_cache, error_or_None).
    Result dicts are TorrentResult-serialised (model_dump mode='json').
    """
    adapter = get_indexer(indexer_name)
    if adapter is None:
        return [], False, IndexerError(
            indexer=indexer_name,
            code="UNKNOWN_INDEXER",
            message=f"Indexer '{indexer_name}' is not registered.",
            retryable=False,
        )

    if anidb_id is not None:
        cached = disk_search_cache.get(anidb_id, indexer_name)
        if cached is not None:
            return cached, True, None
    else:
        cache_key = make_search_cache_key(query, indexer_name)
        cached = search_cache.get(cache_key)
        if cached is not None:
            return cached, True, None

    try:
        raw = await adapter.search(query)
        results = adapter.parse(raw)
        # Serialise to JSON-compatible dicts (mode="json" converts datetime → ISO string)
        result_dicts = [r.model_dump(mode="json") for r in results]

        try:
            if anidb_id is not None:
                disk_search_cache.set(anidb_id, indexer_name, result_dicts)
            else:
                cache_key = make_search_cache_key(query, indexer_name)
                search_cache.set(cache_key, result_dicts, settings.search_cache_ttl_seconds)
        except Exception as exc:
            logger.warning("Failed to cache results for %s: %s", indexer_name, exc)

        return result_dicts, False, None
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
    # Step 1 – Resolve AniDB titles
    resolved_titles: list[TitleEntry] = []
    if params.anidb_id is not None:
        resolved_titles, _ = resolve_titles(params.anidb_id)

    # Step 2 – Build queries (title strings only, no season/episode formatting)
    queries = [params.q] if params.q else _extract_title_queries(resolved_titles)

    # Step 3 – Fan out: each (indexer, query) pair runs concurrently
    tasks = [
        _search_one(indexer_name, query, params.anidb_id)
        for indexer_name in params.indexers
        for query in queries
    ]
    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    # Step 4 – Aggregate
    all_dicts: list[dict] = []
    errors_by_indexer: dict[str, IndexerError] = {}
    successful_tasks = 0
    all_from_cache = True

    for outcome in outcomes:
        if isinstance(outcome, Exception):
            logger.exception("Unexpected error during search gather: %s", outcome)
            continue
        result_dicts, from_cache, error = outcome
        if error:
            errors_by_indexer[error.indexer] = error
        else:
            successful_tasks += 1
            all_dicts.extend(result_dicts)
            if not from_cache:
                all_from_cache = False

    if successful_tasks == 0:
        all_from_cache = False

    # Step 5 – Reconstruct TorrentResult objects and attach parsed info
    all_results: list[TorrentResult] = []
    for item in all_dicts:
        result = TorrentResult.model_validate(item)
        result.parsed = _parse_torrent_info(result.title)
        all_results.append(result)

    # Step 6 – Filter by season/episode if requested
    if params.season is not None or params.episode is not None:
        all_results = [
            r for r in all_results
            if _matches_episode(r.parsed, params.season, params.episode)
        ]

    # Step 7 – Deduplicate and sort
    # When filtering by episode, exact single-episode matches rank before batches/unparsed.
    all_results = _deduplicate(all_results)
    episode = params.episode
    def _sort_key(r: TorrentResult) -> tuple[int, int]:
        if episode is not None and r.parsed and r.parsed.episode_number:
            ep_str = r.parsed.episode_number
            is_exact = "-" not in ep_str and _safe_int(ep_str) == episode
            tier = 0 if is_exact else 1
        else:
            tier = 0 if episode is None else 1
        return (tier, -r.seeders)

    all_results.sort(key=_sort_key)

    errors = list(errors_by_indexer.values())

    return SearchResponse(
        query=params,
        resolved_titles=resolved_titles,
        results=all_results,
        total_results=len(all_results),
        from_cache=all_from_cache and bool(all_results),
        errors=errors,
        partial=bool(errors) and bool(all_results),
    )
