import html
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from kbdex.config import DATA_DIR, save_app_settings, settings
from kbdex.exceptions import APIError
from kbdex.indexers import get_indexer, list_indexers, reload_indexers
from kbdex.indexers.nyaa import _write_config
from kbdex.models import QueryParams
from kbdex.search import run_search

router = APIRouter()
templates = Jinja2Templates(directory="kbdex/templates")

logger = logging.getLogger(__name__)

_ID_TYPE_PARAMS = [
    "anidb_id", "mal_id", "anilist_id", "kitsu_id", "tvdb_id",
    "anisearch_id", "animenewsnetwork_id", "livechart_id", "simkl_id",
]


@router.get("/", response_class=RedirectResponse, include_in_schema=False)
async def ui_root():
    return RedirectResponse(url="/ui/search")


@router.get("/search", response_class=HTMLResponse, include_in_schema=False)
async def search_page(request: Request):
    return templates.TemplateResponse(
        request, "search.html",
        {"active": "search", "indexers": list_indexers()},
    )


@router.post("/search", response_class=HTMLResponse, include_in_schema=False)
async def search_post(
    request: Request,
    id_type: Optional[str] = Form(None),
    id_value: Optional[str] = Form(None),
    q: Optional[str] = Form(None),
    season: Optional[str] = Form(None),
    episode: Optional[str] = Form(None),
):
    form = await request.form()
    selected_indexers = form.getlist("indexers") or list_indexers()

    def _int(v: Optional[str]) -> Optional[int]:
        try:
            return int(v) if v and v.strip() else None
        except ValueError:
            return None

    id_val = _int(id_value)
    season_val = _int(season)
    episode_val = _int(episode)
    q_val = q.strip() if q and q.strip() else None

    # Build QueryParams — resolve foreign ID type to the right param name
    anidb_id: Optional[int] = None
    foreign: dict = {}
    if id_type and id_val is not None:
        if id_type == "anidb_id":
            anidb_id = id_val
        elif id_type in _ID_TYPE_PARAMS:
            foreign[id_type] = id_val

    try:
        if not anidb_id and not foreign and not q_val:
            raise APIError(400, "MISSING_REQUIRED_PARAM", "Enter an ID or a search query.")

        # Resolve foreign ID via the mapper
        if foreign:
            from kbdex.animelists import mapper
            id_type_key, id_val_key = next(iter(foreign.items()))
            anidb_id = mapper.resolve(id_type_key, id_val_key)

        params = QueryParams(
            anidb_id=anidb_id,
            q=q_val,
            season=season_val,
            episode=episode_val,
            indexers=selected_indexers,
        )
        response = await run_search(params)
    except APIError as exc:
        return templates.TemplateResponse(
            request, "_results.html",
            {"error": exc.message, "results": [], "from_cache": False, "partial": False},
        )
    except Exception as exc:
        logger.exception("Unexpected error during UI search")
        return templates.TemplateResponse(
            request, "_results.html",
            {"error": str(exc), "results": [], "from_cache": False, "partial": False},
        )

    return templates.TemplateResponse(
        request, "_results.html",
        {
            "error": None,
            "results": response.results,
            "from_cache": response.from_cache,
            "partial": response.partial,
        },
    )


@router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_page(request: Request):
    nyaa = get_indexer("nyaa")
    sukebei = get_indexer("sukebei")
    return templates.TemplateResponse(
        request, "settings.html",
        {
            "active": "settings",
            "nyaa": {"base_url": nyaa._cfg.base_url, "max_pages": nyaa._cfg.max_pages},
            "sukebei": {"base_url": sukebei._cfg.base_url, "max_pages": sukebei._cfg.max_pages},
            "search_cache_ttl": settings.search_cache_ttl_seconds,
        },
    )


@router.post("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_post(
    request: Request,
    nyaa_base_url: str = Form(...),
    nyaa_max_pages: int = Form(...),
    sukebei_base_url: str = Form(...),
    sukebei_max_pages: int = Form(...),
    search_cache_ttl_seconds: int = Form(...),
):
    indexers_dir: Path = DATA_DIR / "config"
    try:
        indexers_dir.mkdir(parents=True, exist_ok=True)

        nyaa_adapter = get_indexer("nyaa")
        sukebei_adapter = get_indexer("sukebei")

        nyaa_cfg = nyaa_adapter._cfg.model_copy(update={
            "base_url": nyaa_base_url.rstrip("/"),
            "max_pages": max(1, nyaa_max_pages),
        })
        sukebei_cfg = sukebei_adapter._cfg.model_copy(update={
            "base_url": sukebei_base_url.rstrip("/"),
            "max_pages": max(1, sukebei_max_pages),
        })

        _write_config(indexers_dir / "nyaa.xml", "nyaa", nyaa_cfg.model_dump())
        _write_config(indexers_dir / "sukebei.xml", "sukebei", sukebei_cfg.model_dump())

        save_app_settings(search_cache_ttl_seconds=max(60, search_cache_ttl_seconds))
        reload_indexers()
        return HTMLResponse(
            '<p style="color:var(--pico-ins-color)">Settings saved. Adapters reloaded.</p>'
        )
    except Exception as exc:
        logger.exception("Failed to save settings")
        return HTMLResponse(
            f'<p style="color:var(--pico-del-color)">Error: {html.escape(str(exc))}</p>'
        )
