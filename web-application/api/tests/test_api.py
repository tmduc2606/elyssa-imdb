from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_models():
    r = client.get("/api/v1/models")
    assert r.status_code == 200
    data = r.json()
    assert "models" in data
    assert len(data["models"]) == 2


def test_predict_genre_at_least_valid_json():
    r = client.post("/api/v1/predict/genre", json={
        "runtime_minutes": 120,
        "start_year": 2020,
        "title_type": "movie",
        "is_adult": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert "genres" in data
    assert "probabilities" in data


def test_predict_rating_at_least_valid_json():
    r = client.post("/api/v1/predict/rating", json={
        "runtime_minutes": 120,
        "start_year": 2020,
        "title_type": "movie",
        "is_adult": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert "predicted_rating" in data
