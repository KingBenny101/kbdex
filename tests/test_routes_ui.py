from fastapi.testclient import TestClient

from kbdex.models import QueryParams, SearchResponse

_EMPTY_RESPONSE = SearchResponse(
    query=QueryParams(q="attack on titan"),
    results=[],
    total_results=0,
    from_cache=False,
    errors=[],
    partial=False,
)


def _form_payload(**overrides) -> dict:
    payload = {
        "id_type": "",
        "id_value": "",
        "q": "attack on titan",
        "season": "",
        "episode": "",
    }
    payload.update(overrides)
    return payload


def test_ui_free_text_with_season_filter(monkeypatch) -> None:
    captured: dict = {}

    async def fake_run_search(params):
        captured["params"] = params
        return _EMPTY_RESPONSE.model_copy(update={"query": params})

    monkeypatch.setattr("kbdex.routes.ui.run_search", fake_run_search)

    from kbdex.main import app

    with TestClient(app) as client:
        response = client.post("/ui/search", data=_form_payload(season="1"))

    assert response.status_code == 200
    assert "That didn't work" not in response.text
    assert captured["params"].season == 1
    assert captured["params"].q == "attack on titan"


def test_ui_free_text_with_episode_filter(monkeypatch) -> None:
    captured: dict = {}

    async def fake_run_search(params):
        captured["params"] = params
        return _EMPTY_RESPONSE.model_copy(update={"query": params})

    monkeypatch.setattr("kbdex.routes.ui.run_search", fake_run_search)

    from kbdex.main import app

    with TestClient(app) as client:
        response = client.post("/ui/search", data=_form_payload(season="1", episode="2"))

    assert response.status_code == 200
    assert captured["params"].season == 1
    assert captured["params"].episode == 2


def test_ui_free_text_ignores_stale_season_when_cleared(monkeypatch) -> None:
    """User clears the season input, then runs a free search — must not error."""
    captured: dict = {}

    async def fake_run_search(params):
        captured["params"] = params
        return _EMPTY_RESPONSE.model_copy(update={"query": params})

    monkeypatch.setattr("kbdex.routes.ui.run_search", fake_run_search)

    from kbdex.main import app

    with TestClient(app) as client:
        response = client.post("/ui/search", data=_form_payload(season="", episode=""))

    assert response.status_code == 200
    assert "That didn't work" not in response.text
    assert captured["params"].season is None
    assert captured["params"].episode is None