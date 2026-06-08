from fastapi import APIRouter
from fastapi.responses import JSONResponse

from kbdex.anidb.dump import dump
from kbdex.cache import title_cache
from kbdex.config import settings
from kbdex.exceptions import AniDBIDNotFoundError, DumpNotReadyError
from kbdex.models import ErrorResponse, TitleResponse

router = APIRouter()


@router.get(
    "/titles/{anidb_id}",
    response_model=TitleResponse,
    responses={
        404: {"model": ErrorResponse, "description": "AniDB ID not found in local dump"},
        503: {"model": ErrorResponse, "description": "AniDB dump not yet loaded"},
    },
    summary="Resolve AniDB ID to title variants",
    description="Returns all title variants (romanised, Japanese, English, etc.) for the given AniDB ID without performing a torrent search.",
)
async def get_titles(anidb_id: int):
    cache_key = f"title:{anidb_id}"
    cached = title_cache.get(cache_key)
    from_cache = cached is not None

    if cached is not None:
        titles = cached
    else:
        if not dump.is_loaded:
            raise DumpNotReadyError()
        titles = dump.get_titles(anidb_id)
        if titles is None:
            raise AniDBIDNotFoundError(anidb_id)
        title_cache.set(cache_key, titles, settings.title_cache_ttl_seconds)

    response = TitleResponse(
        anidb_id=anidb_id,
        titles=titles,
        source="dump",
        dump_last_refreshed=dump.last_refreshed,
        from_cache=from_cache,
    )
    return JSONResponse(content=response.model_dump(mode="json"))
