from kbdex.indexers.nyaa import NyaaAdapter
from kbdex.indexers.sukebei import SukebeiAdapter

_registry: dict = {
    "nyaa": NyaaAdapter(),
    "sukebei": SukebeiAdapter(),
}


def get_indexer(name: str):
    """Return the adapter for the given indexer name, or None if unknown."""
    return _registry.get(name)


def list_indexers() -> list[str]:
    return list(_registry.keys())
