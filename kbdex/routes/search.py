from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from kbdex.exceptions import APIError
from kbdex.indexers.registry import list_indexers
from kbdex.models import ErrorResponse, QueryParams, SearchResponse
from kbdex.search import run_search

router = APIRouter()


@router.get(
    "/search",
    response_model=SearchResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Missing or invalid parameter"},
        404: {"model": ErrorResponse, "description": "AniDB ID not found"},
        422: {"model": ErrorResponse, "description": "Invalid parameter combination"},
        502: {"model": SearchResponse, "description": "All indexers failed"},
        206: {"model": SearchResponse, "description": "Partial results — some indexers failed"},
    },
    summary="Search for anime torrents",
    description=(
        "Resolves an AniDB ID to all title variants (romanised, Japanese, English), "
        "constructs search queries, and returns matching torrents from the requested indexers."
    ),
)
async def search(
    anidb_id: Optional[int] = Query(None, description="AniDB series ID"),
    q: Optional[str] = Query(None, description="Free-text search query"),
    season: Optional[int] = Query(None, description="Season number (with anidb_id only)"),
    episode: Optional[int] = Query(None, description="Episode number (with anidb_id + season only)"),
    indexers: list[str] = Query(default=None, description="Indexers to query (default: all)"),
):
    # Support comma-separated values: ?indexers=nyaa,sukebei
    indexers = [name.strip() for item in (indexers or []) for name in item.split(",") if name.strip()]
    if not indexers:
        indexers = list_indexers()

    # Validation
    if anidb_id is None and q is None:
        raise APIError(
            400,
            "MISSING_REQUIRED_PARAM",
            "At least one of 'anidb_id' or 'q' must be provided.",
        )
    if season is not None and anidb_id is None:
        raise APIError(
            422,
            "INVALID_PARAM_COMBO",
            "'season' is only meaningful when 'anidb_id' is also provided.",
            param="season",
        )
    if episode is not None and season is None:
        raise APIError(
            422,
            "INVALID_PARAM_COMBO",
            "'episode' requires 'season' to also be provided.",
            param="episode",
        )
    unknown = [i for i in indexers if i not in list_indexers()]
    if unknown:
        raise APIError(
            400,
            "UNKNOWN_INDEXER",
            f"Unknown indexer(s): {', '.join(unknown)}. Supported: {', '.join(list_indexers())}.",
            param="indexers",
        )

    params = QueryParams(
        anidb_id=anidb_id,
        q=q,
        season=season,
        episode=episode,
        indexers=indexers,
    )
    response = await run_search(params)

    # Determine HTTP status from response content
    all_failed = bool(response.errors) and not response.results
    if all_failed:
        status_code = 502
    elif response.partial:
        status_code = 206
    else:
        status_code = 200

    return JSONResponse(
        content=response.model_dump(mode="json"),
        status_code=status_code,
        headers={"X-Cache": "HIT" if response.from_cache else "MISS"},
    )
