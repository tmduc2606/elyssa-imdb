from __future__ import annotations

import hashlib
import json
from pathlib import Path
from functools import lru_cache

import duckdb

from app.cache.memory import get_cache
from app.config import get_settings
from app.graphql.types import (
    CastMember,
    Collaborator,
    CrewMember,
    EpisodeContent,
    FilmographyEntry,
    HomePageData,
    Person,
    PersonSummary,
    RatingSnapshot,
    TitleDetail,
    TitleSummary,
)


def _genres_list(genre_str: str | None) -> list[str]:
    if not genre_str:
        return []
    return [g.strip() for g in genre_str.split(",") if g.strip()]


@lru_cache
def _get_con() -> duckdb.DuckDBPyConnection:
    settings = get_settings()
    con = duckdb.connect()
    marts = Path(settings.gold_marts_path)
    for parquet in sorted(marts.glob("*.parquet")):
        stem = parquet.stem
        con.execute(
            f"CREATE OR REPLACE VIEW {stem} AS SELECT * FROM read_parquet('{parquet}')"
        )
    return con


def resolve_title(tconst: str) -> TitleDetail | None:
    cache = get_cache()
    cache_key = f"title:{tconst}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data
    con = _get_con()
    row = con.execute(
        "SELECT * FROM base_features WHERE tconst = ?", [tconst]
    ).fetchone()
    if row is None:
        cache.set(cache_key, None, ttl=60)
        return None
    cols = [d[0] for d in con.description]
    data = dict(zip(cols, row))
    result = TitleDetail(
        id=data["tconst"],
        primary_title=data["primary_title"],
        original_title=None,
        title_type=data.get("title_type"),
        start_year=data.get("start_year"),
        end_year=data.get("end_year"),
        runtime_minutes=data.get("runtime_minutes"),
        genres=_genres_list(data.get("genre_list")),
        average_rating=data.get("average_rating"),
        num_votes=data.get("num_votes"),
        poster_url=None,
        cast=[],
        crew=[],
        episodes=[],
        similar=_resolve_similar(tconst, data.get("genre_list", "")),
        ratings=[],
    )
    cache.set(cache_key, result, ttl=300)
    return result


def _resolve_similar(tconst: str, genre_list: str, limit: int = 12) -> list[TitleSummary]:
    con = _get_con()
    genres = _genres_list(genre_list)
    if not genres:
        return []
    genre_conditions = " OR ".join(
        f"genre_list ILIKE '%{g}%'" for g in genres[:3]
    )
    sql = f"""
        SELECT tconst, primary_title, average_rating, start_year, genre_list
        FROM base_features
        WHERE tconst != ?
          AND ({genre_conditions})
          AND average_rating IS NOT NULL
        ORDER BY average_rating DESC
        LIMIT ?
    """
    rows = con.execute(sql, [tconst, limit]).fetchall()
    results = []
    for r in rows:
        results.append(
            TitleSummary(
                id=r[0],
                primary_title=r[1],
                average_rating=r[2],
                start_year=r[3],
                genres=_genres_list(r[4]),
            )
        )
    return results


def resolve_person(nconst: str) -> Person | None:
    return None


def resolve_search(query: str, first: int = 50) -> list[TitleSummary]:
    con = _get_con()
    like = f"%{query}%"
    rows = con.execute(
        """SELECT tconst, primary_title, average_rating, start_year, genre_list
           FROM base_features
           WHERE primary_title ILIKE ?
           ORDER BY num_votes DESC
           LIMIT ?""",
        [like, first],
    ).fetchall()
    results = []
    for r in rows:
        results.append(
            TitleSummary(
                id=r[0],
                primary_title=r[1],
                average_rating=r[2],
                start_year=r[3],
                genres=_genres_list(r[4]),
            )
        )
    return results


def resolve_browse(
    genres: list[str] | None = None,
    decade: int | None = None,
    title_type: str | None = None,
    min_rating: float | None = None,
    sort_by: str | None = None,
    first: int = 100,
) -> list[TitleSummary]:
    con = _get_con()
    conditions = []
    params = []

    if genres:
        genre_clauses = []
        for g in genres:
            genre_clauses.append("genre_list ILIKE ?")
            params.append(f"%{g}%")
        conditions.append("(" + " OR ".join(genre_clauses) + ")")

    if decade:
        conditions.append("start_year >= ? AND start_year < ?")
        params.extend([decade, decade + 10])

    if title_type:
        conditions.append("title_type = ?")
        params.append(title_type)

    if min_rating is not None:
        conditions.append("average_rating >= ?")
        params.append(min_rating)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    sort_col = "num_votes DESC"
    if sort_by == "rating":
        sort_col = "average_rating DESC NULLS LAST"
    elif sort_by == "year":
        sort_col = "start_year DESC NULLS LAST"
    elif sort_by == "title":
        sort_col = "primary_title ASC"

    sql = f"""SELECT tconst, primary_title, average_rating, start_year, genre_list
              FROM base_features {where}
              ORDER BY {sort_col}
              LIMIT ?"""
    params.append(first)

    rows = con.execute(sql, params).fetchall()
    results = []
    for r in rows:
        results.append(
            TitleSummary(
                id=r[0],
                primary_title=r[1],
                average_rating=r[2],
                start_year=r[3],
                genres=_genres_list(r[4]),
            )
        )
    return results


def resolve_homepage() -> HomePageData:
    cache = get_cache()
    cached_data = cache.get("homepage")
    if cached_data is not None:
        return cached_data
    con = _get_con()
    trending = []
    top_rated = []

    rows = con.execute(
        """SELECT tconst, primary_title, average_rating, start_year, genre_list
           FROM base_features
           WHERE average_rating IS NOT NULL AND num_votes > 100
           ORDER BY num_votes DESC
           LIMIT 20"""
    ).fetchall()
    for r in rows:
        trending.append(
            TitleSummary(
                id=r[0],
                primary_title=r[1],
                average_rating=r[2],
                start_year=r[3],
                genres=_genres_list(r[4]),
            )
        )

    rows = con.execute(
        """SELECT tconst, primary_title, average_rating, start_year, genre_list
           FROM base_features
           WHERE average_rating IS NOT NULL AND num_votes > 1000
           ORDER BY average_rating DESC
           LIMIT 20"""
    ).fetchall()
    for r in rows:
        top_rated.append(
            TitleSummary(
                id=r[0],
                primary_title=r[1],
                average_rating=r[2],
                start_year=r[3],
                genres=_genres_list(r[4]),
            )
        )

    result = HomePageData(
        trending=trending,
        top_rated=top_rated,
        featured=trending[:10] if trending else [],
    )
    cache.set("homepage", result, ttl=120)
    return result


def resolve_title_ratings(tconst: str) -> list[RatingSnapshot]:
    return []
