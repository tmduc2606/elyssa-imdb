from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from app.api.router import router as api_router
from app.auth.router import router as auth_router
from app.config import get_settings
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

    app.include_router(graphql_router, prefix="/graphql")
    app.include_router(auth_router, prefix="/auth")
    app.include_router(api_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
