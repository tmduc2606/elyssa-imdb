from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.router import _auth_limiter
from app.main import app


@pytest.fixture(autouse=True)
def _reset_auth_limiter():
    """Reset the shared auth rate limiter so tests are independent."""
    _auth_limiter._clients.clear()
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
