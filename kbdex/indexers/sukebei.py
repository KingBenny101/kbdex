from kbdex.indexers.nyaa import NyaaAdapter, NyaaSettings, _load_config


class SukebeiSettings(NyaaSettings):
    base_url: str = "https://sukebei.nyaa.si"


class SukebeiAdapter(NyaaAdapter):
    name = "sukebei"
    display_name = "Sukebei Nyaa.si"

    def __init__(self) -> None:
        super().__init__(SukebeiSettings(**_load_config("sukebei", SukebeiSettings())))
