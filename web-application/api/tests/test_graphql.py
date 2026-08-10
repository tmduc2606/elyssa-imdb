from __future__ import annotations

from unittest.mock import patch

import duckdb
from fastapi.testclient import TestClient

from app.graphql.resolvers import _resolve_known_for
from app.main import app

client = TestClient(app)


def test_graphql_introspection():
    q = """
    query {
      __schema {
        queryType { name }
        types { name kind }
      }
    }
    """
    r = client.post("/graphql", json={"query": q})
    assert r.status_code == 200
    data = r.json()
    types = {t["name"] for t in data["data"]["__schema"]["types"]}
    assert "TitleDetail" in types
    assert "TitleSummary" in types
    assert "HomePageData" in types
    assert "Person" in types
    assert "PaginatedTitles" in types


def test_graphql_homepage():
    q = "{ homepage { trending { id primaryTitle averageRating } topRated { id primaryTitle } featured { id } } }"
    r = client.post("/graphql", json={"query": q})
    assert r.status_code == 200
    data = r.json()["data"]["homepage"]
    assert len(data["trending"]) > 0
    assert len(data["topRated"]) > 0
    assert len(data["featured"]) > 0


def test_graphql_top_level_trending():
    q = '{ trending(limit: 5) { id primaryTitle titleType averageRating numVotes } }'
    r = client.post("/graphql", json={"query": q})
    assert r.status_code == 200
    data = r.json()["data"]["trending"]
    assert len(data) == 5
    assert "titleType" in data[0]
    assert "numVotes" in data[0]


def test_graphql_search():
    q = '{ search(query: "Star") { items { id primaryTitle averageRating } total } }'
    r = client.post("/graphql", json={"query": q})
    assert r.status_code == 200
    data = r.json()["data"]["search"]
    assert data["total"] > 0
    assert len(data["items"]) > 0


def test_graphql_title_detail():
    q = '{ title(tconst: "tt28262612") { id primaryTitle titleType startYear genres cast { person { id primaryName } } similar { id } } }'
    r = client.post("/graphql", json={"query": q})
    assert r.status_code == 200
    data = r.json()["data"]["title"]
    assert data is not None
    assert len(data["id"]) > 0


def test_graphql_browse():
    q = '{ browse(genres: ["Action"], sortBy: "rating", first: 5) { items { id primaryTitle averageRating } total } }'
    r = client.post("/graphql", json={"query": q})
    assert r.status_code == 200
    data = r.json()["data"]["browse"]
    assert data["total"] > 0
    assert len(data["items"]) > 0


def test_graphql_person():
    q = """{ person(nconst: "nm0000108") { id primaryName birthYear deathYear primaryProfession knownForTitles { id primaryTitle } } }"""
    r = client.post("/graphql", json={"query": q})
    assert r.status_code == 200
    data = r.json()["data"]["person"]
    assert data is not None
    assert data["id"] == "nm0000108"
    assert len(data["primaryName"]) > 0


def test_graphql_person_not_found():
    q = '{ person(nconst: "nm9999999") { id primaryName } }'
    r = client.post("/graphql", json={"query": q})
    assert r.status_code == 200
    assert r.json()["data"]["person"] is None


def test_graphql_title_cast_crew():
    q = """{ title(tconst: "tt28262612") { id primaryTitle cast(limit: 5) { person { id primaryName } character category ordering } crew { person { id primaryName } category job } } }"""
    r = client.post("/graphql", json={"query": q})
    assert r.status_code == 200
    data = r.json()["data"]["title"]
    assert data is not None
    assert data["id"] == "tt28262612"


def test_graphql_title_ratings():
    q = '{ titleRatings(tconst: "tt28262612") { snapshotDate averageRating numVotes } }'
    r = client.post("/graphql", json={"query": q})
    assert r.status_code == 200
    data = r.json()["data"]["titleRatings"]
    assert isinstance(data, list)


def test_graphql_search_pagination():
    q = '{ search(query: "Star", first: 3) { items { id primaryTitle } total hasMore cursor } }'
    r = client.post("/graphql", json={"query": q})
    assert r.status_code == 200
    data = r.json()["data"]["search"]
    assert data["total"] > 0
    assert len(data["items"]) > 0
    if data["hasMore"]:
        assert data["cursor"] is not None


def test_graphql_browse_pagination():
    q = '{ browse(genres: ["Action"], first: 3) { items { id primaryTitle } total hasMore cursor } }'
    r = client.post("/graphql", json={"query": q})
    assert r.status_code == 200
    data = r.json()["data"]["browse"]
    assert data["total"] > 0
    assert len(data["items"]) <= 3


def test_rate_limit_headers():
    r = client.get("/health")
    assert "X-RateLimit-Limit" in r.headers
    assert "X-RateLimit-Remaining" in r.headers
    assert int(r.headers["X-RateLimit-Limit"]) > 0


def test_response_time_header():
    r = client.get("/health")
    assert "X-Response-Time-Ms" in r.headers


def test_cache_control_header():
    r = client.get("/health")
    cc = r.headers.get("Cache-Control", "")
    assert "max-age=30" in cc


# ─── P5: known_for_ids exact-ID path (resolvers.py:311) ──────────────
def _known_for_con(with_ids: bool):
    con = duckdb.connect()
    cols = (
        "nconst VARCHAR, primary_name VARCHAR, known_for_titles VARCHAR"
        + (", known_for_ids VARCHAR" if with_ids else "")
    )
    con.execute(f"CREATE TABLE dim_person ({cols})")
    con.execute(
        """CREATE TABLE dim_title (
            tconst VARCHAR, primary_title VARCHAR, title_type VARCHAR,
            average_rating DOUBLE, start_year INTEGER, num_votes INTEGER,
            genre_list VARCHAR
        )"""
    )
    con.execute("""INSERT INTO dim_title VALUES
        ('tt100', 'The Shawshank Redemption', 'movie', 9.3, 1994, 2800000, 'Drama'),
        ('tt200', 'The Matrix', 'movie', 8.7, 1999, 2000000, 'Action, Sci-Fi')""")
    return con


def test_known_for_resolves_via_exact_ids_when_column_present():
    con = _known_for_con(with_ids=True)
    con.execute(
        "INSERT INTO dim_person VALUES ('nm1', 'Keanu Reeves', "
        "'The Matrix, The Shawshank Redemption', 'tt200,tt100')"
    )

    with patch("app.graphql.resolvers._get_con", return_value=con):
        result = _resolve_known_for("nm1")

    assert [t.id for t in result] == ["tt200", "tt100"]
    assert result[0].primary_title == "The Matrix"


def test_known_for_falls_back_to_fuzzy_names_without_ids_column():
    con = _known_for_con(with_ids=False)
    con.execute(
        "INSERT INTO dim_person VALUES ('nm1', 'Keanu Reeves', "
        "'The Matrix, Something Else')"
    )

    with patch("app.graphql.resolvers._get_con", return_value=con):
        result = _resolve_known_for("nm1")

    assert [t.id for t in result] == ["tt200"]
