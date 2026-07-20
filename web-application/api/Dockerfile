# Elyssa-IMDb | Web Application — API Gateway
# FastAPI + GraphQL backend with DuckDB and model inference

FROM python:3.13-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

COPY app/ /app/app/

ENV ELYSSA_GOLD_MARTS_PATH=/data/marts/processed \
    ELYSSA_DEBUG=false \
    ELYSSA_REDIS_ENABLED=false

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
