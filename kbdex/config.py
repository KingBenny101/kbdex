from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KBDEX_", env_file=".env")

    data_dir: Path = Path("data")
    anidb_dump_url: str = "https://anidb.net/api/anime-titles.dat.gz"
    dump_refresh_interval_seconds: int = 7 * 24 * 3600

    title_cache_ttl_seconds: int = 30 * 24 * 3600
    search_cache_ttl_seconds: int = 2 * 3600


settings = Settings()
