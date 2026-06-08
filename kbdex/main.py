import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from kbdex.anidb.dump import dump
from kbdex.animelists import mapper
from kbdex.config import settings
from kbdex.exceptions import APIError
from kbdex.routes import health, search, titles

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "This service provides metadata only. "
    "No copyrighted content is hosted or distributed. "
    "Use at your own risk."
)

_TERMS = """\
kbdex — Anime Torrent Search API
=================================

Terms of Use
------------
- This service is for personal, non-commercial informational use only.
- The operator does not host, distribute, or endorse any copyrighted content.
- Only torrent metadata (titles, sizes, magnet links) is returned; no files are proxied.
- Users are responsible for complying with the laws of their jurisdiction.
- Automated bulk scraping or circumvention of rate limiting is prohibited.

Disclaimer
----------
This API returns metadata sourced from public torrent indexers.
The operator makes no warranty regarding the accuracy or legality of results.
"""


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


@app.middleware("http")
async def disclaimer_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Disclaimer"] = _DISCLAIMER
    return response


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "param": exc.param}},
        headers={"X-Disclaimer": _DISCLAIMER},
    )


@app.get("/", response_class=PlainTextResponse, include_in_schema=False)
async def terms():
    return _TERMS


app.include_router(search.router)
app.include_router(titles.router)
app.include_router(health.router)


