from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.router import _auth_limiter
from app.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def _reset_auth_limiter():
    """Reset the shared auth rate limiter so tests are independent."""
    _auth_limiter._clients.clear()
    yield


@pytest.fixture(autouse=True)
def _disable_poster(monkeypatch: pytest.MonkeyPatch):
    """Disable poster HTTP calls in tests (no OpenPosterDB server)."""
    monkeypatch.setenv("ELYSSA_POSTER_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
