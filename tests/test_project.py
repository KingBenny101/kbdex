from importlib import metadata
from pathlib import Path

import kbdex


def test_package_version_matches_pyproject() -> None:
    assert kbdex.__version__ == metadata.version("kbdex")


def test_version_is_expected() -> None:
    assert kbdex.__version__ == "0.2.0"


def test_console_script_registered() -> None:
    scripts = {
        ep.name: ep.value for ep in metadata.entry_points(group="console_scripts")
    }
    assert scripts["kbdex"] == "kbdex.main:main"


def test_app_importable_and_titled() -> None:
    from kbdex.main import app

    assert app.title == "kbdex"


def test_app_registers_core_routes() -> None:
    from kbdex.main import app

    paths = set(app.openapi()["paths"])
    assert {"/health", "/search", "/titles"} <= paths


def test_app_mounts_root_redirect() -> None:
    from kbdex.main import app

    assert any(getattr(route, "path", None) == "/" for route in app.routes)


def test_package_assets_ship_with_package() -> None:
    pkg_dir = Path(str(kbdex.__file__)).resolve().parent
    assert (pkg_dir / "static" / "style.css").is_file()
    assert (pkg_dir / "templates" / "base.html").is_file()


def test_cli_entry_launches_uvicorn(monkeypatch) -> None:
    import uvicorn

    calls: dict = {}

    def fake_run(app, **kwargs: object) -> None:
        calls["app"] = app
        calls.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)

    from kbdex.main import main

    main()

    assert calls["app"] == "kbdex.main:app"
    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 8000