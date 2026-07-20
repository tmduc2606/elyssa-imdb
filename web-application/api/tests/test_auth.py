from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_register():
    r = client.post("/auth/register", json={
        "email": "testuser@example.com",
        "password": "testpass123",
        "display_name": "Test User",
    })
    assert r.status_code == 200, r.text[:200]
    data = r.json()
    assert data["user"]["email"] == "testuser@example.com"


def test_register_duplicate():
    r = client.post("/auth/register", json={
        "email": "testuser@example.com",
        "password": "testpass123",
        "display_name": "Test User",
    })
    assert r.status_code == 409


def test_login():
    r = client.post("/auth/login", json={
        "email": "testuser@example.com",
        "password": "testpass123",
    })
    assert r.status_code == 200, r.text[:200]
    assert "access_token" in r.json()


def test_login_bad_password():
    r = client.post("/auth/login", json={
        "email": "testuser@example.com",
        "password": "wrongpass",
    })
    assert r.status_code == 401


def test_me():
    r = client.post("/auth/login", json={
        "email": "testuser@example.com",
        "password": "testpass123",
    })
    token = r.json()["access_token"]
    r2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["email"] == "testuser@example.com"


def test_me_unauthorized():
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_watchlist():
    r = client.post("/auth/login", json={
        "email": "testuser@example.com",
        "password": "testpass123",
    })
    token = r.json()["access_token"]
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
