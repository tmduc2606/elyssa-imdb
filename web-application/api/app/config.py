from __future__ import annotations

import secrets
import warnings
from pathlib import Path
from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


_DEFAULT_JWT_SECRET = "dev-secret-change-in-production-32bytes!"


def _default_gold_marts_path() -> str:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / ".git").exists():
            return str(parent / "data-science" / "marts" / "gold")
    return str(p.parent.parent / "data" / "marts" / "gold")


class Settings(BaseSettings):
    app_name: str = "Elyssa API"
    debug: bool = False

    environment: str = "dev"

    host: str = "0.0.0.0"
    port: int = 8000

    gold_marts_path: str = _default_gold_marts_path()

    database_url: str = "sqlite:///" + str(
        Path(__file__).resolve().parent.parent / "data" / "elyssa.db"
    )
    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15
    jwt_refresh_days: int = 7
    secure_cookies: bool = True

    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True

    poster_enabled: bool = True
    poster_base_url: str = "http://localhost:3000"
    poster_api_key: str = "t0-free-rpdb"

    tmdb_api_key: str = ""
    enrichment_enabled: bool = True

    refresh_reuse_grace_seconds: int = 5

    model_artifacts_path: str = ""

    cors_origins: list[str] = ["http://localhost:5173"]

    rate_limit_per_minute: int = 100

    feature_genre_prediction: bool = True
    feature_rating_prediction: bool = True
    feature_watchlist: bool = True
    feature_recommendations: bool = False
    feature_gsap_animations: bool = True

    model_config = ConfigDict(env_file=".env", env_prefix="ELYSSA_")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.jwt_secret == _DEFAULT_JWT_SECRET:
        if settings.environment != "dev":
            raise RuntimeError(
                "ELYSSA_JWT_SECRET must be set to a secure random value when "
                "ELYSSA_ENVIRONMENT != 'dev'. Refusing to start."
            )
        warnings.warn(
            "JWT secret is still the default dev value. "
            "Set ELYSSA_JWT_SECRET to a secure random value in production. "
            f"Generated: {secrets.token_hex(32)}"
        )
    return settings
