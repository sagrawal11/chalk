#!/usr/bin/env bash
# First-run bootstrap for the local dev stack. Idempotent, safe to re-run.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> CHALK local dev setup"

# 1. Ensure .env exists (compose requires it).
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    Created .env from .env.example."
else
  echo "    .env already present, leaving as-is."
fi

# 2. Preconditions.
if ! docker info >/dev/null 2>&1; then
  echo "    ERROR: Docker daemon is not running. Start Docker Desktop and retry." >&2
  exit 1
fi

# 3. Build + start services.
echo "==> Building backend image (Python 3.10.14)..."
docker compose build

echo "==> Starting services (redis, minio, minio-init, backend)..."
docker compose up -d

cat <<'EOF'

==> Services are up (backend is an idle dev container; no web API). Next steps:

  make test            # run the backend suite in the pinned Python 3.10 image
  make seed-r2         # one-time: push local data + model artifacts into MinIO
  make backend-shell   # shell into the backend container

Diagnostics:
  make ps          # service status
  make logs        # tail logs
  make redis-cli   # then run: PING   (expect PONG)
  MinIO console:   http://localhost:9001  (login with MINIO_ROOT_USER/PASSWORD)
EOF
