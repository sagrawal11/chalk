# CHALK: local dev (Docker services + pinned Python 3.10 backend).
# Run `make setup` once, then `make up`. Run `make test` for the suite.

.PHONY: help setup build up down restart logs ps seed-r2 redis-cli backend-shell test

help:
	@echo "Targets:"
	@echo "  setup       First-run bootstrap (.env, build, up, health check)"
	@echo "  up          Start redis + minio + backend (detached)"
	@echo "  down        Stop all services"
	@echo "  restart     Restart the backend container"
	@echo "  logs        Tail all service logs"
	@echo "  ps          Show service status"
	@echo "  seed-r2     One-time: push local data/artifacts into MinIO"
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

seed-r2:
	docker compose exec backend python -c "from utils.storage import upload_full_training_bundle; import os; upload_full_training_bundle(os.environ['R2_BUCKET_NAME'])"

redis-cli:
	docker compose exec redis redis-cli

backend-shell:
	docker compose exec backend /bin/bash

# Canonical test path: build the pinned Python 3.10 image (backend/Dockerfile),
# mount the code, run pytest. No external services needed (hermetic suite).
test:
	docker build -t chalk-backend backend
	docker run --rm -v "$(CURDIR)/backend:/app/backend" chalk-backend python -m pytest tests/ -q
