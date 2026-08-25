# Build context is the REPO ROOT (see docker-compose.yml) so runtime paths
# mirror the local layout: /repo/backend (code+DB), /repo/eval, /repo/data.
# config.py derives REPO_ROOT as parents[2] of backend/app/config.py -> /repo.
FROM python:3.12-slim

WORKDIR /repo
COPY backend/requirements.txt /repo/backend/requirements.txt
RUN pip install --no-cache-dir -r /repo/backend/requirements.txt
COPY backend/ /repo/backend/
COPY eval/ /repo/eval/

ENV PYTHONPATH=/repo/backend
WORKDIR /repo/backend

# Seed the catalog on first boot so `docker compose up` yields a working demo
CMD ["sh", "-c", "python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
