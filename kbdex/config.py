from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KBDEX_", env_file=".env")

    host: str = "0.0.0.0"
    port: int = 8000

    data_dir: Path = Path("data")
    anidb_dump_url: str = "https://anidb.net/api/anime-titles.dat.gz"
    dump_refresh_interval_seconds: int = 7 * 24 * 3600  # weekly

    title_cache_ttl_seconds: int = 30 * 24 * 3600  # 30 days
    search_cache_ttl_seconds: int = 2 * 3600        # 2 hours

    nyaa_base_url: str = "https://nyaa.si"
    nyaa_min_request_interval_ms: int = 2000
    nyaa_max_retries: int = 3
    nyaa_backoff_base_ms: int = 1000
    nyaa_circuit_breaker_threshold: int = 5
    nyaa_circuit_breaker_cooldown_seconds: int = 60
    nyaa_request_timeout_seconds: float = 10.0
    nyaa_max_pages: int = 3          # max HTML pages to fetch per query (75 results/page)


settings = Settings()
