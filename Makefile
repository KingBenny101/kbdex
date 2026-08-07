.PHONY: dev test up down release

dev:
	uv run uvicorn kbdex.main:app --reload --reload-dir src/kbdex --host 0.0.0.0 --port 8000

test:
	uv run pytest

up:
	docker compose up --build

down:
	docker compose down

release:
	scripts/release.sh
