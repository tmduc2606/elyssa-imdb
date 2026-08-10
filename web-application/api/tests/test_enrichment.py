from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from app.services.enrichment import EnrichmentService


def _svc(api_key="k", enabled=True) -> EnrichmentService:
    svc = EnrichmentService.__new__(EnrichmentService)
    svc.api_key = api_key
    svc.enabled = enabled
    svc._db_path = None
    svc._lock = threading.Lock()
    svc._failures = 0
    svc._circuit_open_until = 0.0
    return svc


class _FakeDB:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        return self

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def commit(self):
        pass


def test_enrichment_disabled_returns_none():
    svc = _svc(enabled=False)
    assert svc.get_title_enrichment("tt0111161") is None
    assert svc.get_person_headshot("nm0000108") is None


def test_title_enrichment_cache_hit():
    svc = _svc()
    import datetime

    row = {
        "tmdb_id": "123",
        "overview": "A tale.",
        "tagline": "Hope.",
        "backdrop_url": None,
        "wikidata_qid": None,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    db = _FakeDB(rows=[row])
    with patch.object(svc, "_get_db", return_value=db):
        result = svc.get_title_enrichment("tt0111161")
    assert result["tmdb_id"] == "123"
    assert result["overview"] == "A tale."
    assert result["tagline"] == "Hope."


def test_title_enrichment_fetches_via_find():
    svc = _svc()
    db = _FakeDB(rows=[None])
    detail_payload = {
        "overview": "An overview",
        "tagline": "A tagline",
        "backdrop_path": "/abc.jpg",
    }
    with (
        patch.object(svc, "_get_db", return_value=db),
        patch.object(svc, "_find_tmdb_id", return_value="654321") as find,
        patch.object(svc, "_get", return_value=detail_payload) as getter,
    ):
        result = svc.get_title_enrichment("tt0111161")
    find.assert_called_once_with("tt0111161", kind="title")
    getter.assert_called_once_with("/movie/654321?append_to_response=external_ids")
    assert result["overview"] == "An overview"
    assert result["backdrop_url"] == "https://image.tmdb.org/t/p/w500/abc.jpg"


def test_title_enrichment_negative_cache():
    svc = _svc()
    row = {
        "tmdb_id": None,
        "overview": None,
        "tagline": None,
        "backdrop_url": None,
        "wikidata_qid": None,
        "updated_at": "2099-01-01T00:00:00+00:00",
    }
    db = _FakeDB(rows=[row])
    with patch.object(svc, "_get_db", return_value=db), patch.object(svc, "_find_tmdb_id") as find:
        assert svc.get_title_enrichment("tt0111161") is None
    find.assert_not_called()


def test_person_headshot_uses_first_profile():
    svc = _svc()
    db = _FakeDB(rows=[None])
    with (
        patch.object(svc, "_get_db", return_value=db),
        patch.object(svc, "_find_tmdb_id", return_value="42"),
        patch.object(
            svc,
            "_get",
            return_value={"profiles": [{"file_path": "/head.jpg"}, {"file_path": "/other.jpg"}]},
        ),
    ):
        assert svc.get_person_headshot("nm0000108") == "https://image.tmdb.org/t/p/w500/head.jpg"


def test_find_returns_none_after_404():
    svc = _svc()
    with patch.object(svc, "_get", return_value=None):
        assert svc._find_tmdb_id("tt9999999", kind="title") is None


def test_circuit_breaker_trips_after_threshold():
    svc = _svc()
    with patch.object(svc, "_get", return_value=None):
        for _ in range(5):
            svc._record_failure()
    assert svc._circuit_open()
    with patch("httpx.Client") as client_cls:
        assert svc._find_tmdb_id("tt1", kind="title") is None
    client_cls.assert_not_called()


def test_http_429_respected():
    svc = _svc()
    resp_429 = MagicMock()
    resp_429.status_code = 429
    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {"movie_results": [{"id": 9}]}
    with patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.side_effect = [resp_429, ok]
        assert svc._find_tmdb_id("tt0111161", kind="title") == "9"
