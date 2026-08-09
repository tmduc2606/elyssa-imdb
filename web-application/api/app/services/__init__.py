from __future__ import annotations

from functools import lru_cache

from app.services.poster import PosterService


@lru_cache
def get_poster_service() -> PosterService:
    return PosterService()
