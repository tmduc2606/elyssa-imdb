from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_error_format_on_404():
    response = client.get("/api/v1/titles/nonexistent")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]


def test_error_format_on_validation():
    response = client.post("/api/v1/predict/rating", json={})
    assert response.status_code == 422
    body = response.json()
    assert "error" in body or "detail" in body


def test_rate_limit_headers_present():
    response = client.get("/health")
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers


def test_cors_headers():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" in response.headers


def test_openapi_docs():
    response = client.get("/docs")
    assert response.status_code == 200


def test_graphql_playground():
    response = client.get("/graphql")
    assert response.status_code in (200, 405, 400)


def test_models_endpoint():
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert "models" in body
    for model in body["models"]:
        assert "name" in model
        assert "version" in model
        assert "stage" in model
