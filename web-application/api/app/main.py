from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from app.api.router import router as api_router
from app.auth.router import router as auth_router
from app.cache.rate_limiter import get_rate_limiter
from app.config import get_settings
from app.exceptions import (
    http_error_handler,
    validation_error_handler,
)
from app.graphql.schema import schema
from app.models.inference import get_model_service

graphql_router = GraphQLRouter(schema)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_model_service()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        limiter = get_rate_limiter()
        if not limiter.check(client_ip):
            return Response(
                content='{"error":{"code":"RATE_LIMITED","message":"Too many requests","details":{}}}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(limiter.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start
        remaining = limiter.remaining(client_ip)
        response.headers["X-RateLimit-Limit"] = str(limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-Response-Time-Ms"] = str(round(elapsed * 1000))
        return response

    @app.middleware("http")
    async def cache_control_middleware(request: Request, call_next):
        response = await call_next(request)
        if request.method == "GET" and response.status_code == 200:
            if not response.headers.get("Cache-Control"):
                response.headers["Cache-Control"] = "public, max-age=30"
        return response

    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    app.include_router(graphql_router, prefix="/graphql")
    app.include_router(auth_router, prefix="/auth")
    app.include_router(api_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
