# kbdex

A self-hosted app for searching anime torrents by title or any major database ID.

---

## Installation

Requires [Docker](https://docs.docker.com/get-docker/).

```bash
docker volume create kbdex-data

docker run -d \
  --name kbdex \
  -p 8000:8000 \
  -v kbdex-data:/app/data \
  --restart unless-stopped \
  ghcr.io/kingbenny101/kbdex:latest
```

Or with Docker Compose:

```bash
git clone https://github.com/kingbenny101/kbdex.git
cd kbdex
docker compose up -d
```

The app will be available at `http://localhost:8000`. API docs are at `/docs`.

---

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync          # install dependencies from uv.lock
uv run pytest    # run tests
uv run kbdex     # start the server on 0.0.0.0:8000
```

Or use the Makefile targets: `make dev` (auto-reload), `make test`, `make up`.

---

## How it works

Search by title or any anime database ID — AniDB, MAL, AniList, Kitsu, TVDB, and more. kbdex resolves it to an AniDB ID, looks up all known title variants, searches the configured indexers, and parses each torrent filename to filter and rank results by season and episode.

```
MAL ID / AniList ID / ...          free-text query
        │                                 │
        ▼                                 │
 anime-lists mapping                      │
        │                                 │
        ▼                                 │
    AniDB ID  ──►  resolve titles         │
                        │                 │
                        └────────┬────────┘
                                 ▼
                          search indexers
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

**At startup**, kbdex downloads two data files and refreshes them weekly:
- **AniDB titles dump** — maps AniDB IDs to all known title variants (romanised, Japanese, English, synonyms)
- **anime-lists** ([Fribb/anime-lists](https://github.com/Fribb/anime-lists)) — maps MAL, AniList, Kitsu, TVDB, AniSearch, ANN, LiveChart, and Simkl IDs to AniDB IDs

**At search time**, the resolved titles are sent to each indexer. Every torrent filename is parsed with [anitopy](https://github.com/igorcmoura/anitopy) (with [guessit](https://github.com/guessit-io/guessit) as a fallback) to extract episode number, season, resolution, codec, and release group. Results are filtered to match the requested season/episode and sorted so exact episode matches rank above batch releases.

---

## Configuration

All settings are stored as XML files under the data volume and can be edited directly or via the web UI at `/ui/settings`.

| File | Contains |
|---|---|
| `data/config/app.xml` | AniDB/anime-lists URLs, refresh intervals, cache TTLs |
| `data/config/nyaa.xml` | Nyaa.si base URL, max pages, rate limiting, timeouts |
| `data/config/sukebei.xml` | Same as above for Sukebei |

Config files are created with defaults on first start. There are no environment variables.

---

## Indexers

| Indexer | URL |
|---|---|
| Nyaa.si | [nyaa.si](https://nyaa.si) |
| Sukebei | [sukebei.nyaa.si](https://sukebei.nyaa.si) |

Both are enabled by default. Each can be excluded per-request via the `indexers` parameter, or disabled entirely by setting an unreachable base URL in its config file.

---

## Disclaimer

This tool returns metadata from public torrent indexers. No content is hosted or proxied. Use responsibly and in accordance with the laws of your jurisdiction.

---

## License

MIT
