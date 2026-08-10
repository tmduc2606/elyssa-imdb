from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.router import _auth_limiter
from app.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def _reset_global_rate_limiters():
    """Reset shared rate limiters so tests are independent."""
    from app.cache.rate_limiter import get_rate_limiter
    _auth_limiter._clients.clear()
    try:
        get_rate_limiter()._clients.clear()
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _disable_external_services(monkeypatch: pytest.MonkeyPatch):
    """Disable poster/enrichment HTTP calls in tests (no external servers)."""
    monkeypatch.setenv("ELYSSA_POSTER_ENABLED", "false")
    monkeypatch.setenv("ELYSSA_ENRICHMENT_ENABLED", "false")
    monkeypatch.setenv("ELYSSA_TMDB_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
