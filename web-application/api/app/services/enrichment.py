from __future__ import annotations

import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
REQUEST_TIMEOUT = 4.0
MAX_RETRIES = 2
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
CIRCUIT_TRIP_THRESHOLD = 5
CIRCUIT_OPEN_SECONDS = 600

_local = threading.local()


class EnrichmentService:
    """TMDB-backed enrichment for person headshots and title prose.

    Results are persisted in a SQLite cache (``api/data/enrichment.db``) with a
    30-day TTL. A circuit breaker trips after consecutive upstream failures so
    the API degrades to cache-only rather than hammering TMDB. No API key in
    the environment -> every call resolves to None (feature disabled).
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = (settings.tmdb_api_key or "").strip()
        self.enabled = bool(self.api_key) and settings.enrichment_enabled
        self._db_path = Path(settings.database_url.replace("sqlite:///", "")).parent / "enrichment.db"
        self._lock = threading.Lock()
        self._failures = 0
        self._circuit_open_until = 0.0

    # ── cache plumbing ────────────────────────────────────────────────
    def _get_db(self) -> sqlite3.Connection:
        db = getattr(_local, "conn", None)
        if db is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(str(self._db_path))
            db.row_factory = sqlite3.Row
            db.execute(
                """CREATE TABLE IF NOT EXISTS enrich_title (
                    tconst TEXT PRIMARY KEY,
                    tmdb_id TEXT,
                    overview TEXT,
                    tagline TEXT,
                    backdrop_url TEXT,
                    wikidata_qid TEXT,
                    updated_at TEXT NOT NULL
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS enrich_person (
                    nconst TEXT PRIMARY KEY,
                    tmdb_id TEXT,
                    headshot_url TEXT,
                    updated_at TEXT NOT NULL
                )"""
            )
            db.commit()
            _local.conn = db
        return db

    def _circuit_open(self) -> bool:
        return time.time() < self._circuit_open_until

    def _record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= CIRCUIT_TRIP_THRESHOLD:
                self._circuit_open_until = time.time() + CIRCUIT_OPEN_SECONDS
                self._failures = 0
                logger.warning("enrichment circuit breaker opened for 10 minutes")

    def _record_success(self) -> None:
        with self._lock:
            self._failures = 0

    @staticmethod
    def _fresh(updated_at: str, ttl: int = CACHE_TTL_SECONDS) -> bool:
        try:
            parsed = datetime.fromisoformat(updated_at)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - parsed).total_seconds() < ttl
        except (TypeError, ValueError):
            return False

    # ── HTTP ──────────────────────────────────────────────────────────
    def _get(self, path: str, params: dict | None = None) -> dict | None:
        if self._circuit_open():
            return None
        url = f"https://api.themoviedb.org/3{path}"
        request_params = {"api_key": self.api_key, **(params or {})}
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
                    resp = client.get(url, params=request_params)
                if resp.status_code == 200:
                    self._record_success()
                    return resp.json()
                if resp.status_code == 404:
                    self._record_success()
                    return None
                if resp.status_code in (429, 500, 502, 503, 504):
                    self._record_failure()
                    time.sleep(0.5 * (attempt + 1))
                    continue
                logger.warning("TMDB %s -> HTTP %s", path, resp.status_code)
                self._record_failure()
                return None
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("TMDB attempt %s for %s failed: %s", attempt + 1, path, exc)
                time.sleep(0.5 * (attempt + 1))
        self._record_failure()
        logger.warning("TMDB %s exhausted retries: %s", path, last_exc)
        return None

    # ── title enrichment ──────────────────────────────────────────────
    def get_title_enrichment(self, tconst: str) -> dict | None:
        if not self.enabled:
            return None
        db = self._get_db()
        row = db.execute(
            "SELECT tmdb_id, overview, tagline, backdrop_url, wikidata_qid, updated_at "
            "FROM enrich_title WHERE tconst = ?",
            [tconst],
        ).fetchone()
        if row is not None:
            if row["tmdb_id"] is None and self._fresh(row["updated_at"]):
                return None  # negative cache — miss stays cached for the TTL
            if self._fresh(row["updated_at"]):
                return {
                    "tmdb_id": row["tmdb_id"],
                    "overview": row["overview"],
                    "tagline": row["tagline"],
                    "backdrop_url": row["backdrop_url"],
                    "wikidata_qid": row["wikidata_qid"],
                }

        found = self._find_tmdb_id(tconst, kind="title")
        data: dict | None = None
        if found:
            details = self._get(f"/movie/{found}?append_to_response=external_ids")
            if details:
                backdrop = details.get("backdrop_path")
                data = {
                    "tmdb_id": found,
                    "overview": details.get("overview"),
                    "tagline": details.get("tagline"),
                    "backdrop_url": f"{IMAGE_BASE}{backdrop}" if backdrop else None,
                    "wikidata_qid": None,
                }
        db.execute(
            "INSERT OR REPLACE INTO enrich_title "
            "(tconst, tmdb_id, overview, tagline, backdrop_url, wikidata_qid, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                tconst,
                (data or {}).get("tmdb_id"),
                (data or {}).get("overview"),
                (data or {}).get("tagline"),
                (data or {}).get("backdrop_url"),
                (data or {}).get("wikidata_qid"),
                datetime.now(timezone.utc).isoformat(),
            ],
        )
        db.commit()
        return data

    # ── person enrichment ─────────────────────────────────────────────
    def get_person_headshot(self, nconst: str) -> str | None:
        if not self.enabled:
            return None
        db = self._get_db()
        row = db.execute(
            "SELECT tmdb_id, headshot_url, updated_at FROM enrich_person WHERE nconst = ?",
            [nconst],
        ).fetchone()
        if row is not None and self._fresh(row["updated_at"]):
            return row["headshot_url"] or None
        if row is not None and row["tmdb_id"] is None:
            return None  # negative cache

        found = self._find_tmdb_id(nconst, kind="person")
        headshot: str | None = None
        if found:
            images = self._get(f"/person/{found}/images")
            if images and images.get("profiles"):
                path = images["profiles"][0].get("file_path")
                if path:
                    headshot = f"{IMAGE_BASE}{path}"
        db.execute(
            "INSERT OR REPLACE INTO enrich_person (nconst, tmdb_id, headshot_url, updated_at) VALUES (?, ?, ?, ?)",
            [
                nconst,
                found,
                headshot,
                datetime.now(timezone.utc).isoformat(),
            ],
        )
        db.commit()
        return headshot

    # ── TMDB find bridge ──────────────────────────────────────────────
    def _find_tmdb_id(self, imdb_id: str, kind: str) -> str | None:
        """Resolve an IMDb id (tt… / nm…) to a TMDB id via the find endpoint.

        ``external_source`` must be sent as a query *param*: TMDB returns
        HTTP 404 when it is embedded in the URL string, even for valid ids.
        """
        result = self._get(f"/find/{imdb_id}", params={"external_source": "imdb_id"})
        if not result:
            return None
        if kind == "title":
            movie_results = result.get("movie_results") or []
            tv_results = result.get("tv_results") or []
            if movie_results:
                return str(movie_results[0].get("id"))
            if tv_results:
                return str(tv_results[0].get("id"))
            return None
        people = result.get("person_results") or []
        if people:
            return str(people[0].get("id"))
        return None


_service: EnrichmentService | None = None


def get_enrichment_service() -> EnrichmentService:
    global _service
    if _service is None:
        _service = EnrichmentService()
    return _service
