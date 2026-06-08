import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from kbdex.anidb.dump import dump
from kbdex.animelists import mapper
from kbdex.indexers import get_indexer, list_indexers
from kbdex.models import AnimeListsHealth, DumpHealth, HealthResponse, IndexerHealth

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Service degraded"}},
    summary="Service health check",
    description="Reports the status of the AniDB dump, anime-lists mapping, and each registered indexer.",
)
async def health():
    indexer_names = list_indexers()
    checks = await asyncio.gather(
        *[get_indexer(name).health_check() for name in indexer_names],
        return_exceptions=True,
    )
    indexer_health = {}
    for name, result in zip(indexer_names, checks):
        if isinstance(result, Exception):
            indexer_health[name] = IndexerHealth(
                status="down", last_checked=datetime.now(timezone.utc)
            )
        else:
            indexer_health[name] = result

    dump_health = DumpHealth(
        status="ok" if dump.is_loaded else "loading",
        last_refreshed=dump.last_refreshed,
        entry_count=dump.entry_count,
    )

    animelists_health = AnimeListsHealth(
        status="ok" if mapper.is_loaded else "loading",
        last_refreshed=mapper.last_refreshed,
        entry_count=mapper.entry_count,
    )

    all_ok = (
        dump.is_loaded
        and mapper.is_loaded
        and all(h.status == "ok" for h in indexer_health.values())
    )
    response = HealthResponse(
        status="ok" if all_ok else "degraded",
        indexers=indexer_health,
        anidb_dump=dump_health,
        animelists=animelists_health,
    )
    return JSONResponse(
        content=response.model_dump(mode="json"),
        status_code=200 if all_ok else 503,
    )
