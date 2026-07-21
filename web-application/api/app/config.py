from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Elyssa API"
    debug: bool = True

    host: str = "0.0.0.0"
    port: int = 8000

    gold_marts_path: str = str(
        Path(__file__).resolve().parents[3] / "data-science" / "marts" / "processed"
    )

    database_url: str = "sqlite:///" + str(
        Path(__file__).resolve().parent.parent / "data" / "elyssa.db"
    )
    jwt_secret: str = "dev-secret-change-in-production-32bytes!"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15
    jwt_refresh_days: int = 7

    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True

    model_artifacts_path: str = ""

    cors_origins: list[str] = ["http://localhost:5173"]

    rate_limit_per_minute: int = 100

    class Config:
        env_file = ".env"
        env_prefix = "ELYSSA_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
