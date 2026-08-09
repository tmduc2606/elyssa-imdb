# Elyssa-IMDb | Web Application — API Gateway
# FastAPI + GraphQL backend with DuckDB and model inference.
#
# Multi-stage: the builder installs compile-time deps; the final runtime
# carries only prod API deps (no torch/catboost — those live in the
# separate `model` service or are added via the `bake-models` profile).

FROM python:3.13-slim AS builder

WORKDIR /build

COPY requirements-api.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-api.txt

FROM python:3.13-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r -g 10001 elyssa \
    && useradd -r -u 10001 -g elyssa -d /app -s /sbin/nologin elyssa

COPY --from=builder /install /usr/local

WORKDIR /app

COPY app/ /app/app/

RUN chown -R elyssa:elyssa /app

ENV ELYSSA_GOLD_MARTS_PATH=/data/marts/gold \
    ELYSSA_DEBUG=false \
    ELYSSA_REDIS_ENABLED=false \
    ELYSSA_POSTER_ENABLED=true \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

USER elyssa

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
