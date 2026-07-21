from __future__ import annotations

import uuid
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
