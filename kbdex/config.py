import xml.etree.ElementTree as ET
from pathlib import Path

from pydantic import BaseModel, ConfigDict

DATA_DIR = Path("data")


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=False)

    anidb_dump_url: str = "https://anidb.net/api/anime-titles.dat.gz"
    dump_refresh_interval_seconds: int = 7 * 24 * 3600

    animelists_url: str = "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json"
    animelists_refresh_interval_seconds: int = 7 * 24 * 3600

    title_cache_ttl_seconds: int = 30 * 24 * 3600
    search_cache_ttl_seconds: int = 2 * 3600


def _write_app_config(path: Path, data: dict) -> None:
    root = ET.Element("app")
    for tag, value in data.items():
        ET.SubElement(root, tag).text = str(value)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tmp = path.with_suffix(".tmp")
    tree.write(tmp, encoding="unicode", xml_declaration=True)
    tmp.replace(path)


def _load_config() -> AppSettings:
    config_dir = DATA_DIR / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "app.xml"
    defaults = AppSettings()
    if not path.exists():
        _write_app_config(path, defaults.model_dump())
    try:
        root = ET.parse(path).getroot()
        data = {child.tag: child.text for child in root if child.text is not None}
        return AppSettings(**data)
    except Exception:
        return defaults


def reload_settings() -> None:
    """Reload app.xml into the live settings object in-place."""
    new = _load_config()
    for field in settings.model_fields:
        setattr(settings, field, getattr(new, field))


def save_app_settings(**kwargs) -> None:
    """Update specific fields, write to app.xml, and reload in memory."""
    config_dir = DATA_DIR / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    updated = settings.model_copy(update=kwargs)
    _write_app_config(config_dir / "app.xml", updated.model_dump())
    reload_settings()


settings = _load_config()
