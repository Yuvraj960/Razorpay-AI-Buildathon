.PHONY: seed eval run test up down clean

# Windows-friendly: all python invocations go through the backend dir so
# `app` package imports resolve regardless of caller cwd.
PY ?= python

seed:
	cd backend && $(PY) -m app.seed

eval:
	cd backend && $(PY) ../eval/run_eval.py

eval-raw:
	cd backend && $(PY) ../eval/run_eval.py --catalog raw

mcp:
	cd backend && $(PY) ../mcp-server/server.py

test:
	cd backend && $(PY) -m pytest tests/ -q

run:
	cd backend && $(PY) -m uvicorn app.main:app --reload --port 8000

up:
	docker compose up --build

down:
	docker compose down

clean:
	rm -rf backend/data/app.db frontend/.next
