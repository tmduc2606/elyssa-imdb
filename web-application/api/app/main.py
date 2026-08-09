from __future__ import annotations

import threading
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
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
from app.services import get_poster_service

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

graphql_router = GraphQLRouter(schema)


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_model_service()

    def _prewarm_posters() -> None:
        _logger = structlog.get_logger()
        try:
            con = _prewarm_con()
            if con is None:
                return
            rows = con.execute(
                """SELECT tconst FROM dim_title
                   WHERE average_rating IS NOT NULL AND num_votes > 1000
                   ORDER BY average_rating DESC LIMIT 100"""
            ).fetchall()
            ids = [r[0] for r in rows]
            get_poster_service().prewarm(ids, limit=100)
        except Exception as exc:
            _logger.warning("poster prewarm failed", error=str(exc))

    def _prewarm_con():
        try:
            from app.graphql.resolvers import _get_con
            return _get_con()
        except Exception:
            return None

    t = threading.Thread(target=_prewarm_posters, daemon=True)
    t.start()

    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
    )

    instrumentor = Instrumentator().instrument(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Cookie"],
    )

    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=trace_id, service="api")
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not settings.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

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

    instrumentor.expose(app)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    logger = structlog.get_logger()
    logger.info("app_started", version="1.0.0", debug=settings.debug)

    return app


app = create_app()
