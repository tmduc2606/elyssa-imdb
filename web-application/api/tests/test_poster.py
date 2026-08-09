from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.poster import POSTER_TTL, PosterService


def _svc(base_url="http://poster.test", api_key="k") -> PosterService:
    svc = PosterService.__new__(PosterService)
    svc.base_url = base_url
    svc.api_key = api_key
    svc.enabled = True
    return svc


def test_get_poster_url_returns_none_when_disabled():
    svc = _svc()
    svc.enabled = False
    assert svc.get_poster_url("tt0111161") is None


def test_get_poster_url_returns_none_for_empty_id():
    svc = _svc()
    assert svc.get_poster_url("") is None


def test_get_poster_url_cache_hit():
    svc = _svc()
    with patch("app.services.poster.cache_get", return_value="http://img/p.jpg") as cg:
        assert svc.get_poster_url("tt0111161") == "http://img/p.jpg"
        cg.assert_called_once()


def test_get_poster_url_http_success():
    svc = _svc()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"url": "http://img/tt0111161.jpg"}
    with patch("app.services.poster.cache_get", return_value=None), \
         patch("app.services.poster.cache_set") as cs, \
         patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = resp
        assert svc.get_poster_url("tt0111161") == "http://img/tt0111161.jpg"
        cs.assert_called_once()
        assert cs.call_args.kwargs.get("ttl") == POSTER_TTL


def test_poster_timeout_returns_none():
    svc = _svc()
    import httpx
    with patch("app.services.poster.cache_get", return_value=None), \
         patch("app.services.poster.cache_set") as cs, \
         patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.side_effect = (
            httpx.TimeoutException("timed out")
        )
        assert svc.get_poster_url("tt0111161") is None
        cs.assert_called_once_with(  # caches the miss so we don't hammer downstream
            svc._cache_key("tt0111161"), "", ttl=POSTER_TTL
        )


def test_poster_404_returns_none():
    svc = _svc()
    resp = MagicMock()
    resp.status_code = 404
    with patch("app.services.poster.cache_get", return_value=None), \
         patch("app.services.poster.cache_set"), \
         patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = resp
        assert svc.get_poster_url("tt0111161") is None


def test_extract_url_from_plain_string():
    svc = _svc()
    assert svc._extract_url("http://img/x.jpg") == "http://img/x.jpg"


def test_extract_url_from_nested_data():
    svc = _svc()
    assert svc._extract_url({"data": {"url": "http://img/n.jpg"}}) == "http://img/n.jpg"
