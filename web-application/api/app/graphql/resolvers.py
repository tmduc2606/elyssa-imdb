from __future__ import annotations

import base64
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


GOLD_MARTS = [
    "dim_title",
    "dim_person",
    "fact_title_rating",
    "fact_title_principal",
    "fact_performance",
    "fact_episode",
]


def _genres_list(genre_str: str | None) -> list[str]:
    if not genre_str:
        return []
    return [g.strip() for g in genre_str.split(",") if g.strip()]


def _profession_list(prof_str: str | None) -> list[str]:
    if not prof_str:
        return []
    return [p.strip() for p in prof_str.split(",") if p.strip()]


def _encode_cursor(offset: int, sort_by: str) -> str:
    return base64.b64encode(json.dumps({"o": offset, "s": sort_by}).encode()).decode()


def _decode_cursor(cursor: str | None) -> tuple[int, str]:
    if not cursor:
        return 0, "rating"
    try:
        data = json.loads(base64.b64decode(cursor.encode()))
        return data.get("o", 0), data.get("s", "rating")
    except Exception:
        return 0, "rating"


def _row_to_summary(r) -> TitleSummary:
    return TitleSummary(
        id=r[0], primary_title=r[1], title_type=r[2],
        average_rating=r[3], start_year=r[4], num_votes=r[5],
        genres=_genres_list(r[6]),
    )


@lru_cache
def _get_con() -> duckdb.DuckDBPyConnection:
    settings = get_settings()
    con = duckdb.connect()
    gold_root = Path(settings.gold_marts_path)
    processed_dir = gold_root.parent / "processed"

    # Load Gold marts from data-science/marts/gold/
    for mart in GOLD_MARTS:
        parquet = gold_root / f"{mart}.parquet"
        if parquet.exists():
            path = str(parquet.resolve()).replace("'", "''")
            con.execute(
                f"CREATE OR REPLACE VIEW {mart} AS SELECT * FROM read_parquet('{path}')"
            )

    # Also load base_features from processed/ for backward compat
    base = processed_dir / "base_features.parquet"
    if base.exists():
        path = str(base.resolve()).replace("'", "''")
        con.execute(
            f"CREATE OR REPLACE VIEW base_features AS SELECT * FROM read_parquet('{path}')"
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
        "SELECT * FROM dim_title WHERE tconst = ?", [tconst]
    ).fetchone()
    if row is None:
        cache.set(cache_key, None, ttl=60)
        return None
    cols = [d[0] for d in con.description]
    data = dict(zip(cols, row))
    genre_str = data.get("genre_list") or ""
    result = TitleDetail(
        id=data["tconst"],
        primary_title=data.get("primary_title") or "",
        original_title=data.get("original_title"),
        title_type=data.get("title_type"),
        start_year=data.get("start_year"),
        end_year=data.get("end_year"),
        runtime_minutes=data.get("runtime_minutes"),
        genres=_genres_list(genre_str),
        average_rating=data.get("average_rating"),
        num_votes=data.get("num_votes"),
        poster_url=None,
        parent_tconst=data.get("parent_tconst"),
        series_title=data.get("series_title"),
        season_number=data.get("season_number"),
        episode_number=data.get("episode_number"),
        ratings=[],
    )
    cache.set(cache_key, result, ttl=300)
    return result


def _resolve_cast(tconst: str, limit: int = 20) -> list[CastMember]:
    con = _get_con()
    rows = con.execute("""
        SELECT p.nconst, p.primary_name,
               f.character_name, f.ordering, f.category, f.job
        FROM fact_title_principal f
        LEFT JOIN dim_person p ON f.name_key = p.nconst
        WHERE f.title_key = ?
          AND f.category IN ('actor', 'actress', 'self')
        ORDER BY f.ordering NULLS LAST
        LIMIT ?
    """, [tconst, limit]).fetchall()
    if not rows:
        return []
    results = []
    for r in rows:
        results.append(CastMember(
            person=PersonSummary(id=r[0] or "", primary_name=r[1] or "Unknown"),
            character=r[2],
            ordering=r[3],
            category=r[4],
            job=r[5],
        ))
    return results


def _resolve_crew(tconst: str) -> list[CrewMember]:
    con = _get_con()
    rows = con.execute("""
        SELECT p.nconst, p.primary_name,
               f.category, f.job
        FROM fact_title_principal f
        LEFT JOIN dim_person p ON f.name_key = p.nconst
        WHERE f.title_key = ?
          AND f.category NOT IN ('actor', 'actress', 'self')
        ORDER BY f.ordering NULLS LAST
    """, [tconst]).fetchall()
    if not rows:
        return []
    results = []
    for r in rows:
        results.append(CrewMember(
            person=PersonSummary(id=r[0] or "", primary_name=r[1] or "Unknown"),
            category=r[2],
            job=r[3],
        ))
    return results


def _resolve_similar(tconst: str, genres: list[str] | None = None, limit: int = 12) -> list[TitleSummary]:
    con = _get_con()
    if not genres:
        return []
    params: list[str] = [f"%{g}%" for g in genres[:3]]
    placeholders = " OR ".join(["genre_list ILIKE ?"] * len(params))
    sql = f"""
        SELECT tconst, primary_title, title_type, average_rating, start_year, num_votes, genre_list
        FROM dim_title
        WHERE tconst != ?
          AND ({placeholders})
          AND average_rating IS NOT NULL
        ORDER BY average_rating DESC
        LIMIT ?
    """
    rows = con.execute(sql, [tconst, *params, limit]).fetchall()
    return [_row_to_summary(r) for r in rows]


def _resolve_episodes(tconst: str, limit: int = 100) -> list[EpisodeContent]:
    con = _get_con()
    rows = con.execute("""
        SELECT e.episode_key, e.season_number, e.episode_number,
               t.tconst, t.primary_title, t.title_type, t.average_rating, t.start_year, t.num_votes, t.genre_list
        FROM fact_episode e
        LEFT JOIN dim_title t ON e.episode_key = t.tconst
        WHERE e.series_key = ?
        ORDER BY e.season_number NULLS LAST, e.episode_number NULLS LAST
        LIMIT ?
    """, [tconst, limit]).fetchall()
    if not rows:
        return []
    results = []
    for r in rows:
        results.append(EpisodeContent(
            season_number=r[1],
            episode_number=r[2],
            title=_row_to_summary(r[3:]) if r[3] else None,
        ))
    return results


def _resolve_filmography(nconst: str, limit: int = 50) -> list[FilmographyEntry]:
    con = _get_con()
    rows = con.execute("""
        SELECT pf.tconst, pf.category, pf.character_name,
               t.primary_title, t.title_type, t.average_rating, t.start_year, t.num_votes, t.genre_list
        FROM fact_performance pf
        LEFT JOIN dim_title t ON pf.tconst = t.tconst
        WHERE pf.nconst = ?
        ORDER BY t.start_year DESC NULLS LAST
        LIMIT ?
    """, [nconst, limit]).fetchall()
    if not rows:
        return []
    results = []
    for r in rows:
        results.append(FilmographyEntry(
            title=_row_to_summary((r[0], r[3], r[4], r[5], r[6], r[7], r[8])),
            category=r[1],
            character=r[2],
            year=r[6],
        ))
    return results


def _resolve_known_for(nconst: str, limit: int = 10) -> list[TitleSummary]:
    con = _get_con()
    row = con.execute(
        "SELECT known_for_titles FROM dim_person WHERE nconst = ?", [nconst]
    ).fetchone()
    if not row or not row[0]:
        return []
    names = [t.strip() for t in row[0].split(",") if t.strip()]
    if not names:
        return []
    seen: set[str] = set()
    results: list[TitleSummary] = []
    for name in names:
        r = con.execute(
            """SELECT tconst, primary_title, title_type, average_rating, start_year, num_votes, genre_list
               FROM dim_title
               WHERE primary_title ILIKE ?
               ORDER BY num_votes DESC
               LIMIT 1""",
            [f"%{name.replace('%', '%%')}%"],
        ).fetchone()
        if r and r[0] not in seen:
            seen.add(r[0])
            results.append(_row_to_summary(r))
        if len(results) >= limit:
            break
    return results


def _resolve_collaborators(nconst: str, limit: int = 20) -> list[Collaborator]:
    con = _get_con()
    rows = con.execute("""
        SELECT c.nconst, c.primary_name, COUNT(*) AS collab_count
        FROM fact_performance pf
        JOIN fact_performance pf2 ON pf.tconst = pf2.tconst AND pf.nconst != pf2.nconst
        LEFT JOIN dim_person c ON pf2.nconst = c.nconst
        WHERE pf.nconst = ?
          AND c.nconst IS NOT NULL
        GROUP BY c.nconst, c.primary_name
        ORDER BY collab_count DESC
        LIMIT ?
    """, [nconst, limit]).fetchall()
    if not rows:
        return []
    results = []
    for r in rows:
        results.append(Collaborator(
            person=PersonSummary(id=r[0], primary_name=r[1] or "Unknown"),
            collaboration_count=r[2],
        ))
    return results


def resolve_person(nconst: str) -> Person | None:
    cache = get_cache()
    cache_key = f"person:{nconst}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data
    con = _get_con()
    row = con.execute(
        "SELECT * FROM dim_person WHERE nconst = ?", [nconst]
    ).fetchone()
    if row is None:
        cache.set(cache_key, None, ttl=60)
        return None
    cols = [d[0] for d in con.description]
    data = dict(zip(cols, row))
    result = Person(
        id=data["nconst"],
        primary_name=data.get("primary_name") or "",
        birth_year=data.get("birth_year"),
        death_year=data.get("death_year"),
        primary_profession=_profession_list(data.get("profession_list")),
        poster_url=None,
        known_for_titles=_resolve_known_for(nconst),
        filmography=_resolve_filmography(nconst),
        collaborators=_resolve_collaborators(nconst),
    )
    cache.set(cache_key, result, ttl=600)
    return result


def resolve_search(
    query: str, first: int = 50, after: str | None = None
) -> tuple[list[TitleSummary], int, bool, str | None]:
    con = _get_con()
    offset, _sort = _decode_cursor(after)

    count_row = con.execute(
        "SELECT COUNT(*) FROM dim_title WHERE primary_title ILIKE ?",
        [f"%{query}%"],
    ).fetchone()
    total = count_row[0] if count_row else 0

    rows = con.execute(
        """SELECT tconst, primary_title, title_type, average_rating, start_year, num_votes, genre_list
           FROM dim_title
           WHERE primary_title ILIKE ?
           ORDER BY num_votes DESC
           LIMIT ? OFFSET ?""",
        [f"%{query}%", first, offset],
    ).fetchall()
    items = [_row_to_summary(r) for r in rows]

    has_more = (offset + first) < total
    next_cursor = _encode_cursor(offset + first, "votes") if has_more else None
    return items, total, has_more, next_cursor


def resolve_browse(
    genres: list[str] | None = None,
    decade: int | None = None,
    title_type: str | None = None,
    min_rating: float | None = None,
    sort_by: str | None = None,
    first: int = 100,
    after: str | None = None,
) -> tuple[list[TitleSummary], int, bool, str | None]:
    con = _get_con()
    offset, _sort = _decode_cursor(after)
    conditions: list[str] = []
    params: list = []

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

    current_sort = sort_by or "rating"

    count_sql = "SELECT COUNT(*) FROM dim_title"
    if conditions:
        count_sql += " WHERE " + " AND ".join(conditions)
    count_row = con.execute(count_sql, params).fetchone()
    total = count_row[0] if count_row else 0

    sort_col = "num_votes DESC"
    if current_sort == "rating":
        sort_col = "average_rating DESC NULLS LAST"
    elif current_sort == "year":
        sort_col = "start_year DESC NULLS LAST"
    elif current_sort == "title":
        sort_col = "primary_title ASC"

    sql = f"""SELECT tconst, primary_title, title_type, average_rating, start_year, num_votes, genre_list
              FROM dim_title
              {('WHERE ' + ' AND '.join(conditions)) if conditions else ''}
              ORDER BY {sort_col}
              LIMIT ? OFFSET ?"""
    params.extend([first, offset])

    rows = con.execute(sql, params).fetchall()
    items = [_row_to_summary(r) for r in rows]

    has_more = (offset + first) < total
    next_cursor = _encode_cursor(offset + first, current_sort) if has_more else None
    return items, total, has_more, next_cursor


def resolve_trending(limit: int = 20) -> list[TitleSummary]:
    cache = get_cache()
    cached_data = cache.get(f"trending:{limit}")
    if cached_data is not None:
        return cached_data
    con = _get_con()
    rows = con.execute(
        """SELECT tconst, primary_title, title_type, average_rating, start_year, num_votes, genre_list
           FROM dim_title
           WHERE average_rating IS NOT NULL AND num_votes > 100
           ORDER BY num_votes DESC
           LIMIT ?""",
        [limit],
    ).fetchall()
    results = [_row_to_summary(r) for r in rows]
    cache.set(f"trending:{limit}", results, ttl=120)
    return results


def resolve_top_rated(limit: int = 20) -> list[TitleSummary]:
    cache = get_cache()
    cached_data = cache.get(f"top_rated:{limit}")
    if cached_data is not None:
        return cached_data
    con = _get_con()
    rows = con.execute(
        """SELECT tconst, primary_title, title_type, average_rating, start_year, num_votes, genre_list
           FROM dim_title
           WHERE average_rating IS NOT NULL AND num_votes > 1000
           ORDER BY average_rating DESC
           LIMIT ?""",
        [limit],
    ).fetchall()
    results = [_row_to_summary(r) for r in rows]
    cache.set(f"top_rated:{limit}", results, ttl=120)
    return results


def resolve_featured(limit: int = 10) -> list[TitleSummary]:
    return resolve_trending(limit)[:limit]


def resolve_homepage() -> HomePageData:
    cache = get_cache()
    cached_data = cache.get("homepage")
    if cached_data is not None:
        return cached_data
    trending = resolve_trending(20)
    top_rated = resolve_top_rated(20)
    result = HomePageData(
        trending=trending,
        top_rated=top_rated,
        featured=trending[:10] if trending else [],
    )
    cache.set("homepage", result, ttl=120)
    return result


def resolve_title_ratings(tconst: str) -> list[RatingSnapshot]:
    cache = get_cache()
    cache_key = f"ratings:{tconst}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data
    con = _get_con()
    rows = con.execute(
        """SELECT snapshot_date, average_rating, num_votes
           FROM fact_title_rating
           WHERE title_key = ? AND average_rating IS NOT NULL
           ORDER BY snapshot_date DESC
           LIMIT 100""",
        [tconst],
    ).fetchall()
    results: list[RatingSnapshot] = []
    for r in rows:
        results.append(RatingSnapshot(
            snapshot_date=str(r[0]) if r[0] else "latest",
            average_rating=float(r[1]),
            num_votes=int(r[2]),
        ))
    cache.set(cache_key, results, ttl=300)
    return results
