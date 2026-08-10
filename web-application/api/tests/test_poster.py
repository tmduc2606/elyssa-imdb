from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

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
    resp.headers = {"content-type": "image/jpeg"}
    with patch("app.services.poster.cache_get", return_value=None), \
         patch("app.services.poster.cache_set") as cs, \
         patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.head.return_value = resp
        url = svc.get_poster_url("tt0111161")
        assert url == "http://poster.test/k/imdb/poster-default/tt0111161.jpg"
        cs.assert_called_once()
        assert cs.call_args.kwargs.get("ttl") == POSTER_TTL


def test_poster_timeout_returns_none_without_negative_cache():
    svc = _svc()
    with patch("app.services.poster.cache_get", return_value=None), \
         patch("app.services.poster.cache_set") as cs, \
         patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.head.side_effect = (
            httpx.TimeoutException("timed out")
        )
        assert svc.get_poster_url("tt0111161") is None
        cs.assert_not_called()


def test_poster_head_unsupported_falls_back_to_documented_url():
    svc = _svc()
    resp = MagicMock()
    resp.status_code = 405
    with patch("app.services.poster.cache_get", return_value=None), \
         patch("app.services.poster.cache_set"), \
         patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.head.return_value = resp
        assert svc.get_poster_url("tt0111161") == "http://poster.test/k/imdb/poster-default/tt0111161.jpg"


def test_poster_404_returns_none():
    svc = _svc()
    resp = MagicMock()
    resp.status_code = 404
    with patch("app.services.poster.cache_get", return_value=None), \
         patch("app.services.poster.cache_set"), \
         patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.head.return_value = resp
        assert svc.get_poster_url("tt0111161") is None


def test_poster_non_image_response_returns_none():
    svc = _svc()
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"content-type": "text/html"}
    with patch("app.services.poster.cache_get", return_value=None), \
         patch("app.services.poster.cache_set"), \
         patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.head.return_value = resp
        assert svc.get_poster_url("tt0111161") is None