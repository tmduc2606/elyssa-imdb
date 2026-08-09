from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TEST_EMAIL = f"test_{uuid.uuid4().hex[:8]}@example.com"
TEST_PASSWORD = "testpass123"
TEST_DISPLAY = "Test User"


def test_register():
    r = client.post("/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "display_name": TEST_DISPLAY,
    })
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert data["user"]["email"] == TEST_EMAIL
    assert "accessToken" in data


def test_register_duplicate():
    r = client.post("/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "display_name": TEST_DISPLAY,
    })
    assert r.status_code == 409


def test_login():
    r = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    assert r.status_code == 200, r.text[:200]
    assert "accessToken" in r.json()


def test_login_bad_password():
    r = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": "wrongpass",
    })
    assert r.status_code == 401


def test_me():
    r = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    token = r.json()["accessToken"]
    r2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["email"] == TEST_EMAIL


def test_me_unauthorized():
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_watchlist():
    r = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    token = r.json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    r2 = client.get("/auth/watchlist", headers=headers)
    assert r2.status_code == 200
    assert r2.json() == []

    r3 = client.post("/auth/watchlist", headers=headers, json={"tconst": "tt1234567"})
    assert r3.status_code == 200
    entry = r3.json()
    assert entry["tconst"] == "tt1234567"

    entry_id = entry["id"]
    r4 = client.delete(f"/auth/watchlist/{entry_id}", headers=headers)
    assert r4.status_code == 200


def test_watchlist_unauthorized():
    r = client.get("/auth/watchlist")
    assert r.status_code == 401
    r = client.post("/auth/watchlist", json={"tconst": "tt1234567"})
    assert r.status_code == 401
    r = client.delete("/auth/watchlist/tt1234567")
    assert r.status_code == 401


def test_refresh_with_cookie():
    r = client.post("/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    assert r.status_code == 200
    assert "refresh_token" in r.cookies

    r2 = client.post("/auth/refresh")
    assert r2.status_code == 200, r2.text[:200]
    data = r2.json()
    assert "accessToken" in data
    assert data["user"]["email"] == TEST_EMAIL


def test_refresh_without_cookie():
    client.cookies.clear()
    r = client.post("/auth/refresh")
    assert r.status_code == 401, f"Expected 401 got {r.status_code}: {r.text[:200]}"
    assert "Missing refresh token" in r.text


# ─── WA-01: register sets a non-Secure cookie on HTTP ─────────────────
def test_register_sets_insecure_cookie_on_http(client: TestClient):
    email = f"wa01_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={
        "email": email, "password": "Qa1234567!", "display_name": "WA01",
    })
    assert r.status_code == 200, r.text[:200]
    set_cookie = r.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    # TestClient uses http://testserver → Secure must be ABSENT
    assert "Secure" not in set_cookie, f"Cookie must not be Secure on HTTP: {set_cookie}"


# ─── WA-02: refresh token rotation ────────────────────────────────────
def test_refresh_rotates_token(client: TestClient):
    email = f"wa02_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={
        "email": email, "password": "Qa1234567!", "display_name": "WA02",
    })
    r = client.post("/auth/login", json={"email": email, "password": "Qa1234567!"})
    assert r.status_code == 200
    old_cookie = r.cookies.get("refresh_token")
    assert old_cookie is not None

    r2 = client.post("/auth/refresh")
    assert r2.status_code == 200, r2.text[:200]
    new_cookie = r2.cookies.get("refresh_token")
    assert new_cookie is not None
    assert new_cookie != old_cookie, "Refresh token must rotate on use"


def test_refresh_reuse_detected_401(client: TestClient):
    email = f"wa02b_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={
        "email": email, "password": "Qa1234567!", "display_name": "WA02b",
    })
    r = client.post("/auth/login", json={"email": email, "password": "Qa1234567!"})
    assert r.status_code == 200
    spent_token = r.cookies.get("refresh_token")

    # First refresh rotates (spent token becomes invalid)
    r2 = client.post("/auth/refresh")
    assert r2.status_code == 200

    # Reusing the spent token must be rejected
    client.cookies.clear()
    client.cookies.set("refresh_token", spent_token)
    r3 = client.post("/auth/refresh")
    assert r3.status_code == 401, f"Expected 401 on reuse, got {r3.status_code}"
    assert "reused" in r3.text.lower() or "revoked" in r3.text.lower()


def test_refresh_family_revoked(client: TestClient):
    email = f"wa02c_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={
        "email": email, "password": "Qa1234567!", "display_name": "WA02c",
    })
    r = client.post("/auth/login", json={"email": email, "password": "Qa1234567!"})
    spent = r.cookies.get("refresh_token")

    # Rotate once
    assert client.post("/auth/refresh").status_code == 200
    # Rotate again (second-generation token is now current)
    assert client.post("/auth/refresh").status_code == 200

    # Reusing the original (now family-revoked) token must fail
    client.cookies.clear()
    client.cookies.set("refresh_token", spent)
    r4 = client.post("/auth/refresh")
    assert r4.status_code == 401


# ─── WA-03: logout revokes the whole family ───────────────────────────
def test_logout_revokes_family(client: TestClient):
    email = f"wa03_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={
        "email": email, "password": "Qa1234567!", "display_name": "WA03",
    })
    r = client.post("/auth/login", json={"email": email, "password": "Qa1234567!"})
    token = r.cookies.get("refresh_token")
    assert token is not None

    # Logout revokes the family
    assert client.post("/auth/logout").status_code == 200

    # Refresh with the now-revoked token must fail
    client.cookies.clear()
    client.cookies.set("refresh_token", token)
    r2 = client.post("/auth/refresh")
    assert r2.status_code == 401


# ─── WA-04: rate limiting on auth endpoints (5/min) ───────────────────
def test_auth_rate_limit_429(client: TestClient):
    email = f"wa04_{uuid.uuid4().hex[:8]}@example.com"
    for i in range(6):
        r = client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert r.status_code == 429, f"Expected 429 after 5 attempts, got {r.status_code}"
    assert r.headers.get("Retry-After") == "60"


# ─── WA-05: config rejects default JWT secret outside dev ─────────────
def test_config_rejects_default_secret_in_prod(monkeypatch: pytest.MonkeyPatch):
    from app.config import _DEFAULT_JWT_SECRET, get_settings
    get_settings.cache_clear()
    try:
        monkeypatch.setenv("ELYSSA_ENVIRONMENT", "prod")
        monkeypatch.setenv("ELYSSA_JWT_SECRET", _DEFAULT_JWT_SECRET)
        with pytest.raises(RuntimeError, match="ELYSSA_JWT_SECRET must be set"):
            get_settings()
    finally:
        get_settings.cache_clear()


# ─── WA-06: CORS preflight echoes exact origin ────────────────────────
def test_cors_preflight_origin_echoed(client: TestClient):
    r = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200, r.text[:200]
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "POST" in r.headers.get("access-control-allow-methods", "")
