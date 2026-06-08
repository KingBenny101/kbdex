from pydantic_settings import SettingsConfigDict

from kbdex.indexers.nyaa import NyaaAdapter, NyaaSettings


class SukebeiSettings(NyaaSettings):
    model_config = SettingsConfigDict(env_prefix="KBDEX_SUKEBEI_", env_file=".env")

    base_url: str = "https://sukebei.nyaa.si"


class SukebeiAdapter(NyaaAdapter):
    name = "sukebei"
    display_name = "Sukebei Nyaa.si"

    def __init__(self) -> None:
        super().__init__(SukebeiSettings())
