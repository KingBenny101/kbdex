# kbdex

A self-hosted API that finds anime torrents by AniDB ID.

**API docs:** https://kingbenny101.github.io/kbdex/

---

## How it works

Search by any anime database ID — AniDB, MAL, AniList, Kitsu, TVDB, and more. kbdex resolves it to an AniDB ID, looks up all known title variants, searches the configured indexers, and parses each torrent filename to filter and rank results by season and episode.

```
MAL ID / AniList ID / ...
        │
        ▼
 anime-lists mapping  ──►  AniDB ID  ──►  resolve titles  ──►  search indexers
                                                                      │
                                                                      ▼
                                                              parse filenames (anitopy + guessit)
                                                                      │
                                                                      ▼
                                                              filter by season / episode
                                                                      │
                                                                      ▼
                                                                JSON results
```

**At startup**, kbdex downloads two data files into the configured data directory and refreshes them weekly:
- **AniDB titles dump** — maps AniDB IDs to all known title variants (romanised, Japanese, English, synonyms)
- **anime-lists** ([Fribb/anime-lists](https://github.com/Fribb/anime-lists)) — maps MAL, AniList, Kitsu, TVDB, AniSearch, ANN, LiveChart, and Simkl IDs to AniDB IDs

**At search time**, the resolved titles are sent to each indexer (Nyaa.si, Sukebei by default). Every torrent filename is parsed with [anitopy](https://github.com/igorcmoura/anitopy) (with [guessit](https://github.com/guessit-io/guessit) as a fallback) to extract episode number, season, resolution, codec, and release group. Results are filtered to match the requested season/episode and sorted so exact episode matches rank above batch releases.

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

All settings are stored as XML files under the data volume and can be edited directly or via the web UI at `/ui/settings`.

| File | Contains |
|---|---|
| `data/config/app.xml` | AniDB/anime-lists URLs, refresh intervals, cache TTLs |
| `data/config/nyaa.xml` | Nyaa.si base URL, max pages, rate limiting, timeouts |
| `data/config/sukebei.xml` | Same as above for Sukebei |

Config files are created with defaults on first start. There are no environment variables.
