# To add a new indexer:
# 1. Create kbdex/indexers/yourindexer.py implementing the IndexerAdapter protocol
# 2. Import it below and append an instance to INDEXERS.
from kbdex.indexers.base import IndexerAdapter
from kbdex.indexers.nyaa import NyaaAdapter
from kbdex.indexers.sukebei import SukebeiAdapter

INDEXERS: list[IndexerAdapter] = [
    NyaaAdapter(),
    SukebeiAdapter(),
]

_registry: dict[str, IndexerAdapter] = {i.name: i for i in INDEXERS}


def get_indexer(name: str) -> IndexerAdapter | None:
    return _registry.get(name)


def list_indexers() -> list[str]:
    return list(_registry.keys())
