.venv:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

dev: .venv
	.venv/bin/uvicorn kbdex.main:app --reload --reload-dir kbdex --host 0.0.0.0 --port 8000

up:
	docker compose up --build

down:
	docker compose down
