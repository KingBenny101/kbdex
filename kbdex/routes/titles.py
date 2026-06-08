from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from kbdex.anidb.dump import dump, resolve_titles
from kbdex.animelists import mapper
from kbdex.exceptions import APIError
from kbdex.models import ErrorResponse, TitleResponse

router = APIRouter()


@router.get(
    "/titles",
    response_model=TitleResponse,
    responses={
        400: {"model": ErrorResponse, "description": "No ID parameter provided"},
        404: {"model": ErrorResponse, "description": "ID not found"},
        422: {"model": ErrorResponse, "description": "Multiple ID params provided"},
        503: {"model": ErrorResponse, "description": "AniDB dump or anime-lists not yet loaded"},
    },
    summary="Resolve any ID to titles and mapped IDs",
    description=(
        "Accepts an AniDB ID or any supported foreign ID (MAL, AniList, Kitsu, TVDB, etc.), "
        "resolves it to an AniDB ID, and returns all title variants plus cross-database ID mappings."
    ),
)
async def get_titles(
    anidb_id: Optional[int] = Query(None, description="AniDB series ID"),
    mal_id: Optional[int] = Query(None, description="MyAnimeList series ID"),
    anilist_id: Optional[int] = Query(None, description="AniList series ID"),
    kitsu_id: Optional[int] = Query(None, description="Kitsu series ID"),
    tvdb_id: Optional[int] = Query(None, description="TheTVDB series ID"),
    anisearch_id: Optional[int] = Query(None, description="AniSearch series ID"),
    animenewsnetwork_id: Optional[int] = Query(None, description="Anime News Network series ID"),
    livechart_id: Optional[int] = Query(None, description="LiveChart series ID"),
    simkl_id: Optional[int] = Query(None, description="Simkl series ID"),
):
    foreign = {k: v for k, v in {
        "mal_id": mal_id,
        "anilist_id": anilist_id,
        "kitsu_id": kitsu_id,
        "tvdb_id": tvdb_id,
        "anisearch_id": anisearch_id,
        "animenewsnetwork_id": animenewsnetwork_id,
        "livechart_id": livechart_id,
        "simkl_id": simkl_id,
    }.items() if v is not None}

    id_sources = ([anidb_id] if anidb_id is not None else []) + list(foreign.values())
    if len(id_sources) > 1:
        raise APIError(
            422,
            "AMBIGUOUS_ID",
            "Provide exactly one ID parameter (anidb_id, mal_id, anilist_id, ...).",
        )
    if not id_sources:
        raise APIError(
            400,
            "MISSING_REQUIRED_PARAM",
            "At least one ID parameter must be provided (anidb_id, mal_id, anilist_id, ...).",
        )

    if foreign:
        id_type, id_value = next(iter(foreign.items()))
        anidb_id = mapper.resolve(id_type, id_value)

    titles, from_cache = resolve_titles(anidb_id)
    mapped_ids = mapper.get_ids(anidb_id) or {}

    response = TitleResponse(
        anidb_id=anidb_id,
        titles=titles,
        mapped_ids=mapped_ids,
        source="dump",
        dump_last_refreshed=dump.last_refreshed,
        from_cache=from_cache,
    )
    return JSONResponse(content=response.model_dump(mode="json"))
