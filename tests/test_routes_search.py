from fastapi.testclient import TestClient

from kbdex.models import QueryParams, SearchResponse

_NONETWORK_RESPONSE = SearchResponse(
    query=QueryParams(q="attack on titan"),
    results=[],
    total_results=0,
    from_cache=False,
    errors=[],
    partial=False,
)


def test_api_free_text_allows_season_filter(monkeypatch) -> None:
    captured: dict = {}

    async def fake_run_search(params):
        captured["params"] = params
        return _NONETWORK_RESPONSE.model_copy(update={"query": params})

    monkeypatch.setattr("kbdex.routes.search.run_search", fake_run_search)

    from kbdex.main import app

    with TestClient(app) as client:
        response = client.get("/search", params={"q": "attack on titan", "season": 1})

    assert response.status_code == 200
    assert captured["params"].season == 1


def test_api_free_text_search_allows_episode_filter(monkeypatch) -> None:
    captured: dict = {}

    async def fake_run_search(params):
        captured["params"] = params
        return _NONETWORK_RESPONSE.model_copy(update={"query": params})

    monkeypatch.setattr("kbdex.routes.search.run_search", fake_run_search)

    from kbdex.main import app

    with TestClient(app) as client:
        response = client.get("/search", params={"q": "attack on titan", "season": 1, "episode": 2})

    assert response.status_code == 200
    assert captured["params"].episode == 2


def test_api_episode_without_season_still_requires_id_or_query(monkeypatch) -> None:
    captured: dict = {}

    async def fake_run_search(params):
        captured["params"] = params
        return _NONETWORK_RESPONSE.model_copy(update={"query": params})

    monkeypatch.setattr("kbdex.routes.search.run_search", fake_run_search)

    from kbdex.main import app

    with TestClient(app) as client:
        response = client.get("/search", params={"q": "attack on titan", "episode": 2})

    assert response.status_code == 200
    assert captured["params"].season is None
    assert captured["params"].episode == 2