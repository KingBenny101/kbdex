import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from kbdex.anidb.dump import dump
from kbdex.indexers.registry import get_indexer, list_indexers
from kbdex.models import DumpHealth, HealthResponse, IndexerHealth

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Service degraded"}},
    summary="Service health check",
    description="Reports the status of the AniDB dump and each registered indexer.",
)
async def health():
    # Check all indexers concurrently
    indexer_names = list_indexers()
    checks = await asyncio.gather(
        *[get_indexer(name).health_check() for name in indexer_names],
        return_exceptions=True,
    )
    indexer_health = {}
    for name, result in zip(indexer_names, checks):
        if isinstance(result, Exception):
            from kbdex.models import IndexerHealth
            from datetime import datetime, timezone
            indexer_health[name] = IndexerHealth(
                status="down", last_checked=datetime.now(timezone.utc)
            )
        else:
            indexer_health[name] = result

    # AniDB dump status
    if dump.is_loaded:
        dump_status = "ok"
    else:
        dump_status = "loading"

    dump_health = DumpHealth(
        status=dump_status,
        last_refreshed=dump.last_refreshed,
        entry_count=dump.entry_count,
    )

    all_ok = (
        dump.is_loaded
        and all(h.status == "ok" for h in indexer_health.values())
    )
    overall = "ok" if all_ok else "degraded"

    response = HealthResponse(
        status=overall,
        indexers=indexer_health,
        anidb_dump=dump_health,
    )
    status_code = 200 if all_ok else 503
    return JSONResponse(
        content=response.model_dump(mode="json"),
        status_code=status_code,
    )
