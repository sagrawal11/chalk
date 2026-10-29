# Pinned to backend/.python-version (3.10.14) to kill the local 3.12-vs-3.10 skew.
FROM python:3.10.14-slim

# Runtime system libs: libgomp1 provides OpenMP for LightGBM / XGBoost.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# Dependency layer first so it caches unless requirements.txt changes.
COPY config/requirements.txt config/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r config/requirements.txt

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

# Code, data, and model artifacts are bind-mounted by docker-compose at runtime,
# so the image stays small. The image runs the test suite (`make test` overrides
# the command with pytest) and serves as an idle dev container; no web API.
CMD ["sleep", "infinity"]
