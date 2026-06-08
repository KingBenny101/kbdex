# kbdex

A self-hosted API that finds anime torrents by AniDB ID.

**API docs:** https://kingbenny101.github.io/kbdex/

---

## How it works

```
AniDB ID  ──►  resolve titles  ──►  build queries  ──►  search Nyaa.si  ──►  JSON results
```

---

## Installation

Requires [Docker](https://docs.docker.com/get-docker/).

```bash
docker run -d \
  --name kbdex \
  -p 8000:8000 \
  -v ./data:/app/data \
  ghcr.io/kingbenny101/kbdex:latest
```

Or with Docker Compose:

```bash
docker compose up -d
```

The API will be available at `http://localhost:8000`.

---

## Configuration

All settings use the `KBDEX_` prefix and can be set as environment variables or in a `.env` file.

| Variable | Default | Description |
|---|---|---|
| `KBDEX_DATA_DIR` | `data` | Directory for persistent data (AniDB dump, caches) |
| `KBDEX_ANIDB_DUMP_URL` | `https://anidb.net/api/anime-titles.dat.gz` | URL to fetch the AniDB titles dump from |
| `KBDEX_DUMP_REFRESH_INTERVAL_SECONDS` | `604800` (7 days) | How often to refresh the AniDB dump |
| `KBDEX_TITLE_CACHE_TTL_SECONDS` | `2592000` (30 days) | TTL for resolved title cache |
| `KBDEX_SEARCH_CACHE_TTL_SECONDS` | `7200` (2 hours) | TTL for search result cache |
| `KBDEX_NYAA_BASE_URL` | `https://nyaa.si` | Nyaa.si base URL |
| `KBDEX_NYAA_MIN_REQUEST_INTERVAL_MS` | `2000` | Minimum delay between Nyaa requests (ms) |
| `KBDEX_NYAA_MAX_RETRIES` | `3` | Max retries on failed Nyaa requests |
| `KBDEX_NYAA_BACKOFF_BASE_MS` | `1000` | Base backoff delay for retries (ms) |
| `KBDEX_NYAA_CIRCUIT_BREAKER_THRESHOLD` | `5` | Failures before circuit breaker opens |
| `KBDEX_NYAA_CIRCUIT_BREAKER_COOLDOWN_SECONDS` | `60` | Circuit breaker cooldown period |
| `KBDEX_NYAA_REQUEST_TIMEOUT_SECONDS` | `10.0` | Timeout per Nyaa request (seconds) |
| `KBDEX_NYAA_MAX_PAGES` | `3` | Max Nyaa result pages to fetch per query (75 results/page) |

Example with Docker Compose:

```yaml
services:
  kbdex:
    image: ghcr.io/kingbenny101/kbdex:latest
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      KBDEX_NYAA_MAX_PAGES: "5"
      KBDEX_SEARCH_CACHE_TTL_SECONDS: "3600"
```
