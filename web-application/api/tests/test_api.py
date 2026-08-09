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
    body = r.json()
    assert "data" in body
    assert "models" in body["data"]
    assert len(body["data"]["models"]) == 2


def test_predict_genre_at_least_valid_json():
    r = client.post("/api/v1/predict/genre", json={
        "runtime_minutes": 120,
        "start_year": 2020,
        "title_type": "movie",
        "is_adult": False,
    })
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert "genres" in body["data"]
    assert "probabilities" in body["data"]


def test_predict_rating_at_least_valid_json():
    r = client.post("/api/v1/predict/rating", json={
        "runtime_minutes": 120,
        "start_year": 2020,
        "title_type": "movie",
        "is_adult": False,
    })
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert "predicted_rating" in body["data"]


# ─── 4c.1 REST Endpoint Tests ──────────────────────────────────────────

def test_search_titles():
    r = client.get("/api/v1/search", params={"q": "Matrix", "type": "title", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert "titles" in body["data"]
    assert len(body["data"]["titles"]) > 0
    assert body["data"]["titles"][0]["title_id"].startswith("tt")


def test_search_persons():
    r = client.get("/api/v1/search", params={"q": "Keanu", "type": "person", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert "persons" in body["data"]
    assert len(body["data"]["persons"]) > 0
    assert body["data"]["persons"][0]["nconst"].startswith("nm")


def test_search_all():
    r = client.get("/api/v1/search", params={"q": "Matrix", "type": "all", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert "titles" in body["data"]
    assert "persons" in body["data"]


def test_search_no_results():
    r = client.get("/api/v1/search", params={"q": "ZZZZNOTFOUNDZZZZ", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert len(body["data"]["titles"]) == 0
    assert len(body["data"]["persons"]) == 0


def test_search_min_length():
    r = client.get("/api/v1/search", params={"q": "x"})
    assert r.status_code == 422


def test_title_detail():
    r = client.get("/api/v1/titles/tt28262612")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert body["data"]["title_id"] == "tt28262612"
    assert body["data"]["primary_title"]
    assert "principals" in body["data"]


def test_title_detail_not_found():
    r = client.get("/api/v1/titles/tt99999999")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "NOT_FOUND"


def test_title_principals():
    r = client.get("/api/v1/titles/tt28262612/principals")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert len(body["data"]) > 0
    assert body["data"][0]["nconst"].startswith("nm")


def test_title_principals_not_found():
    r = client.get("/api/v1/titles/tt99999999/principals")
    assert r.status_code == 404


def test_person_detail():
    r = client.get("/api/v1/persons/nm0000108")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert body["data"]["nconst"] == "nm0000108"
    assert body["data"]["primary_name"]


def test_person_detail_not_found():
    r = client.get("/api/v1/persons/nm99999999")
    assert r.status_code == 404


def test_person_credits():
    r = client.get("/api/v1/persons/nm0000108/credits")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert len(body["data"]) > 0
    assert "title_id" in body["data"][0]


def test_person_credits_not_found():
    r = client.get("/api/v1/persons/nm99999999/credits")
    assert r.status_code == 404


def test_list_titles_pagination():
    r = client.get("/api/v1/titles", params={"page": 1, "per_page": 5})
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert "meta" in body
    assert len(body["data"]) <= 5
    assert body["meta"]["page"] == 1
    assert body["meta"]["per_page"] == 5
    assert body["meta"]["total"] > 0


def test_list_titles_filter_genre():
    r = client.get("/api/v1/titles", params={"genre": "Action", "per_page": 5})
    assert r.status_code == 200
    body = r.json()
    for item in body["data"]:
        assert "Action" in item["genres"]


def test_models_readiness_payload(client: TestClient):
    r = client.get("/api/v1/models")
    assert r.status_code == 200, r.text[:200]
    body = r.json()["data"]
    assert "models" in body
    assert "loaded" in body
    assert isinstance(body["loaded"], bool)


def test_error_format_standard():
    r = client.get("/api/v1/titles/tt99999999")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"]
    assert "details" in body["error"]


# ─── WA-18: REST / GraphQL crew parity ────────────────────────────────
def test_crew_consistent_graphql_rest():
    tconst = "tt1375666"
    rest = client.get(f"/api/v1/titles/{tconst}")
    assert rest.status_code == 200, rest.text[:200]
    rest_body = rest.json()["data"]
    rest_directors = [n.strip() for n in rest_body.get("director_names", "").split(",") if n.strip()]
    rest_writers = [n.strip() for n in rest_body.get("writer_names", "").split(",") if n.strip()]
    assert len(rest_directors) > 0, "REST should return at least one director"

    gql = client.post("/graphql", json={
        "query": "{ title(tconst: \"%s\") { crew { person { primaryName } category } } }" % tconst,
    })
    assert gql.status_code == 200, gql.text[:200]
    crew = gql.json()["data"]["title"]["crew"]
    gql_directors = [c["person"]["primaryName"] for c in crew if c.get("category") == "director"]
    gql_writers = [c["person"]["primaryName"] for c in crew if c.get("category") == "writer"]

    assert sorted(rest_directors) == sorted(gql_directors), (
        f"director mismatch: rest={rest_directors} gql={gql_directors}"
    )
    assert sorted(rest_writers) == sorted(gql_writers), (
        f"writer mismatch: rest={rest_writers} gql={gql_writers}"
    )
