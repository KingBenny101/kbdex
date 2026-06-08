import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from kbdex.anidb.dump import dump
from kbdex.animelists import mapper
from kbdex.config import settings
from kbdex.exceptions import APIError
from kbdex.routes import health, search, titles, ui

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def _periodic_dump_refresh() -> None:
    while True:
        await asyncio.sleep(settings.dump_refresh_interval_seconds)
        try:
            logger.info("Starting scheduled AniDB dump refresh")
            await dump.refresh()
        except Exception:
            logger.exception("AniDB dump refresh failed")


async def _periodic_animelists_refresh() -> None:
    while True:
        await asyncio.sleep(settings.animelists_refresh_interval_seconds)
        try:
            logger.info("Starting scheduled anime-lists refresh")
            await mapper.refresh()
        except Exception:
            logger.exception("anime-lists refresh failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.gather(dump.ensure_loaded(), mapper.ensure_loaded())
    dump_task = asyncio.create_task(_periodic_dump_refresh())
    lists_task = asyncio.create_task(_periodic_animelists_refresh())
    yield
    dump_task.cancel()
    lists_task.cancel()
    for task in (dump_task, lists_task):
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="kbdex",
    description="Anime torrent search API — resolves AniDB IDs to torrent metadata",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "param": exc.param}},
    )


@app.get("/", response_class=RedirectResponse, include_in_schema=False)
async def root():
    return RedirectResponse(url="/ui/search")


app.mount("/static", StaticFiles(directory="kbdex/static"), name="static")

app.include_router(search.router)
app.include_router(titles.router)
app.include_router(health.router)
app.include_router(ui.router, prefix="/ui")


