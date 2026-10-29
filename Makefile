# CHALK: local dev (Hybrid: Docker services + native Vite).
# Run `make setup` once, then `make dev`. Run `make test` for the suite.

.PHONY: help setup build up down restart logs ps frontend dev seed-r2 cache redis-cli backend-shell test

help:
	@echo "Targets:"
	@echo "  setup       First-run bootstrap (.env, build, up, health check)"
	@echo "  up          Start redis + minio + backend (detached)"
	@echo "  down        Stop all services"
	@echo "  restart     Restart the backend container"
	@echo "  logs        Tail all service logs"
	@echo "  ps          Show service status"
	@echo "  frontend    Install deps + run Vite natively on :8080"
	@echo "  dev         up + frontend"
	@echo "  seed-r2     One-time: push local data/artifacts into MinIO"
	@echo "  cache       Warm Redis baselines (the original failing command)"
	@echo "  redis-cli   Open redis-cli in the redis container"
	@echo "  test        Run the backend test suite in the pinned Python 3.10 image"

setup:
	./scripts/dev-setup.sh

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart backend

logs:
	docker compose logs -f

ps:
	docker compose ps

frontend:
	cd lovable && npm install && npm run dev

dev: up frontend

seed-r2:
	docker compose exec backend python -c "from utils.storage import upload_full_training_bundle; import os; upload_full_training_bundle(os.environ['R2_BUCKET_NAME'])"

cache:
	docker compose exec backend python pipeline/cache_baselines.py

redis-cli:
	docker compose exec redis redis-cli

backend-shell:
	docker compose exec backend /bin/bash

# Canonical test path: build the pinned Python 3.10 image (backend/Dockerfile),
# mount the code, run pytest. No external services needed (hermetic suite).
# NOT the checked-in venv and NOT anaconda base (see cache-baselines env skew).
test:
	docker build -t chalk-backend backend
	docker run --rm -v "$(CURDIR)/backend:/app/backend" chalk-backend python -m pytest tests/ -q
