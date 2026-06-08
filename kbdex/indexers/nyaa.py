"""
Nyaa.si indexer adapter — HTML scraping.

Search URL: https://nyaa.si/?f={filter}&c={category}&q={query}&p={page}
  f=0  no filter (include all uploads)
  c=0_0  all categories  |  c=1_0  anime only  |  c=1_2  anime english-translated
  p=1,2,3…  pagination (75 results per page)

Nyaa's table structure (8 physical <td> elements per row):
  0  category  — <img alt="Category Name">
  1  title     — <a href="/view/N" title="full title"> (colspan="2" visually)
  2  links     — <a href="/download/N.torrent"> and <a href="magnet:?…">
  3  size      — plain text e.g. "1.20 GiB"
  4  date      — data-timestamp Unix epoch attribute
  5  seeders   — integer text, styled green
  6  leechers  — integer text, styled red
  7  completed — integer text (downloads count)
"""
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic_settings import BaseSettings, SettingsConfigDict

from kbdex.indexers.base import CircuitBreaker, RateLimiter
from kbdex.models import IndexerHealth, TorrentResult

logger = logging.getLogger(__name__)

_SIZE_UNITS: dict[str, int] = {
    "B": 1,
    "KiB": 1024,
    "MiB": 1024**2,
    "GiB": 1024**3,
    "TiB": 1024**4,
}
_SIZE_RE = re.compile(r"^([\d.]+)\s+([KMGT]?i?B)$", re.ASCII)
_VIEW_HREF = re.compile(r"^/view/\d+$")
_DL_HREF = re.compile(r"^/download/\d+\.torrent$")
_MAGNET_HREF = re.compile(r"^magnet:")

_RESULTS_PER_PAGE = 75


class NyaaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KBDEX_NYAA_", env_file=".env")

    base_url: str = "https://nyaa.si"
    min_request_interval_ms: int = 2000
    max_retries: int = 3
    backoff_base_ms: int = 1000
    circuit_breaker_threshold: int = 5
    circuit_breaker_cooldown_seconds: int = 60
    request_timeout_seconds: float = 10.0
    max_pages: int = 3


def _parse_size(size_str: str) -> int:
    m = _SIZE_RE.match(size_str.strip())
    if not m:
        return 0
    try:
        return int(float(m.group(1)) * _SIZE_UNITS.get(m.group(2), 1))
    except (ValueError, KeyError):
        return 0


def _parse_row(row: Tag, base_url: str) -> dict | None:
    cells = row.find_all("td")
    if len(cells) < 7:
        return None

    # Title — find the view link (no #fragment = not a comments link)
    title_tag = row.find("a", href=_VIEW_HREF)
    if not title_tag:
        return None
    title = title_tag.get("title") or title_tag.get_text(strip=True)
    if not title:
        return None

    # .torrent download URL
    dl_tag = row.find("a", href=_DL_HREF)
    torrent_url = (base_url + dl_tag["href"]) if dl_tag else None

    # Magnet link (already fully formed in the HTML)
    mag_tag = row.find("a", href=_MAGNET_HREF)
    magnet_link = mag_tag["href"] if mag_tag else None

    # Upload date from data-timestamp (Unix epoch, UTC)
    date_td = row.find("td", attrs={"data-timestamp": True})
    uploaded_at: datetime | None = None
    if date_td:
        try:
            uploaded_at = datetime.fromtimestamp(
                int(date_td["data-timestamp"]), tz=timezone.utc
            )
        except (ValueError, TypeError):
            pass

    # Category from the alt text of the icon in cell 0
    cat_img = cells[0].find("img")
    category = cat_img.get("alt", "") if cat_img else ""

    # Size — cell index 3
    size_str = cells[3].get_text(strip=True)

    # Seeders / leechers — cell indices 5 and 6
    def _int(td: Tag) -> int:
        try:
            return int(td.get_text(strip=True))
        except (ValueError, AttributeError):
            return 0

    seeders = _int(cells[5])
    leechers = _int(cells[6])

    return {
        "title": title,
        "torrent_url": torrent_url,
        "magnet_link": magnet_link,
        "size": size_str,
        "uploaded_at": uploaded_at,
        "seeders": seeders,
        "leechers": leechers,
        "category": category,
    }


def _parse_html(content: bytes, base_url: str) -> list[dict]:
    soup = BeautifulSoup(content, "html.parser")
    table = soup.find("table", class_="torrent-list")
    if not table:
        return []
    tbody = table.find("tbody")
    if not tbody:
        return []
    results = []
    for row in tbody.find_all("tr"):
        item = _parse_row(row, base_url)
        if item:
            results.append(item)
    return results


class NyaaAdapter:
    name = "nyaa"
    display_name = "Nyaa.si"
    supports_category_filter = True
    supports_magnet = True
    supports_torrent_url = True

    def __init__(self, cfg: NyaaSettings | None = None) -> None:
        self._cfg = cfg or NyaaSettings()
        self.base_url = self._cfg.base_url
        self.min_request_interval_ms = self._cfg.min_request_interval_ms
        self.max_retries = self._cfg.max_retries
        self.backoff_base_ms = self._cfg.backoff_base_ms
        self._rate_limiter = RateLimiter(self._cfg.min_request_interval_ms)
        self._circuit_breaker = CircuitBreaker(
            threshold=self._cfg.circuit_breaker_threshold,
            cooldown_seconds=self._cfg.circuit_breaker_cooldown_seconds,
        )

    async def search(
        self, query: str, options: dict[str, Any] | None = None
    ) -> list[dict]:
        if self._circuit_breaker.is_open:
            raise RuntimeError(f"{self.name} circuit breaker is open")

        opts = options or {}
        category = opts.get("category", "1_0")
        filter_flag = opts.get("filter", "0")
        max_pages = int(opts.get("max_pages", self._cfg.max_pages))

        all_items: list[dict] = []
        for page in range(1, max_pages + 1):
            url = (
                f"{self.base_url}/?f={filter_flag}&c={category}"
                f"&q={quote(query)}&p={page}"
            )
            content = await self._fetch_with_retry(url)
            items = _parse_html(content, self.base_url)
            all_items.extend(items)

            if len(items) < _RESULTS_PER_PAGE:
                break

        return all_items

    def parse(self, raw_results: list[dict]) -> list[TorrentResult]:
        results = []
        for item in raw_results:
            size_str = item.get("size", "")
            results.append(
                TorrentResult(
                    title=item.get("title", ""),
                    magnet_link=item.get("magnet_link"),
                    torrent_url=item.get("torrent_url"),
                    size_bytes=_parse_size(size_str),
                    size_human=size_str,
                    seeders=int(item.get("seeders", 0) or 0),
                    leechers=int(item.get("leechers", 0) or 0),
                    category=item.get("category", ""),
                    uploaded_at=item.get("uploaded_at"),
                    source_indexer=self.name,
                )
            )
        return results

    async def health_check(self) -> IndexerHealth:
        import time as _time

        if self._circuit_breaker.is_open:
            return IndexerHealth(
                status="down",
                last_checked=datetime.now(timezone.utc),
            )
        start = _time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=self._cfg.request_timeout_seconds
            ) as client:
                resp = await client.head(self.base_url)
                resp.raise_for_status()
            elapsed_ms = int((_time.monotonic() - start) * 1000)
            status = "ok" if elapsed_ms < 3000 else "degraded"
        except Exception:
            status = "down"
        return IndexerHealth(
            status=status,
            last_checked=datetime.now(timezone.utc),
        )

    async def _fetch_with_retry(self, url: str) -> bytes:
        last_exc: Exception = RuntimeError("no attempts made")
        for attempt in range(self.max_retries + 1):
            try:
                await self._rate_limiter.acquire()
                async with httpx.AsyncClient(
                    timeout=self._cfg.request_timeout_seconds,
                    follow_redirects=True,
                    headers={"User-Agent": "kbdex/0.1 (personal anime torrent search)"},
                ) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                self._circuit_breaker.record_success()
                return resp.content
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_exc = exc
                self._circuit_breaker.record_failure()
                logger.warning(
                    "%s request failed (attempt %d/%d): %s",
                    self.name,
                    attempt + 1,
                    self.max_retries + 1,
                    exc,
                )
                if attempt < self.max_retries:
                    delay = (self.backoff_base_ms / 1000.0) * (2**attempt)
                    await asyncio.sleep(delay)
        raise last_exc
