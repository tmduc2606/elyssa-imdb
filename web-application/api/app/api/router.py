from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.config import get_settings
from app.exceptions import AppError
from app.models.inference import get_model_service
from app.graphql.resolvers import (
    _resolve_cast,
    _resolve_crew,
    _resolve_filmography,
    resolve_person,
    resolve_search,
    resolve_title,
)

router = APIRouter(prefix="/api/v1")


# ─── Predict Request Models ───────────────────────────────────────────
class GenrePredictRequest(BaseModel):
    runtime_minutes: int | None = None
    start_year: int | None = None
    title_type: str | None = None
    is_adult: bool | None = None


class RatingPredictRequest(BaseModel):
    runtime_minutes: int | None = None
    start_year: int | None = None
    title_type: str | None = None
    is_adult: bool | None = None


# ─── Helpers ──────────────────────────────────────────────────────────
def _director_names(principals: list) -> str:
    names = [p["primary_name"] for p in principals if p.get("category") == "director"]
    return ", ".join(sorted(set(names))) if names else ""


def _writer_names(principals: list) -> str:
    names = [p["primary_name"] for p in principals if p.get("category") == "writer"]
    return ", ".join(sorted(set(names))) if names else ""


def _prune_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _inv_exists() -> bool:
    return (Path(get_settings().gold_marts_path) / "model_inventory.json").exists()


# ─── GET /api/v1/titles ──────────────────────────────────────────────
@router.get("/titles")
async def list_titles(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    title_type: str | None = None,
    genre: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    rating_min: float | None = None,
    sort: str = "start_year",
    order: str = "desc",
):
    from app.graphql.resolvers import resolve_browse

    items, total, _has_more, _cursor = resolve_browse(
        genres=[genre] if genre else None,
        title_type=title_type,
        min_rating=rating_min,
        sort_by=sort if sort != "start_year" else "year",
        first=per_page,
        after=None,
    )
    # Apply year filter if needed (resolve_browse supports decade, not year range)
    if year_min is not None or year_max is not None:
        filtered = []
        for item in items:
            y = item.start_year
            if year_min is not None and (y is None or y < year_min):
                continue
            if year_max is not None and (y is None or y > year_max):
                continue
            filtered.append(item)
        items = filtered
        total = len(items)

    # Apply year filters via manual offset
    offset = (page - 1) * per_page
    page_items = items[offset:offset + per_page] if offset < len(items) else []

    data = [
        {
            "title_id": t.id,
            "primary_title": t.primary_title,
            "title_type": t.title_type,
            "start_year": t.start_year,
            "runtime_minutes": None,
            "genres": ",".join(t.genres) if t.genres else "",
            "average_rating": t.average_rating,
            "num_votes": t.num_votes,
        }
        for t in page_items
    ]
    return {"data": data, "meta": {"page": page, "per_page": per_page, "total": total}}


# ─── GET /api/v1/titles/{id} ─────────────────────────────────────────
@router.get("/titles/{tconst}")
async def get_title_detail(tconst: str):
    title = resolve_title(tconst)
    if title is None:
        raise AppError("NOT_FOUND", "Title not found", 404)

    try:
        cast = _resolve_cast(tconst, limit=50)
        crew = _resolve_crew(tconst)
    except Exception:
        cast = []
        crew = []

    principals_raw = []
    for c in cast:
        principals_raw.append({
            "nconst": c.person.id,
            "primary_name": c.person.primary_name,
            "ordering": c.ordering,
            "category": c.category,
            "job": c.job,
            "characters": c.character,
        })
    for c in crew:
        principals_raw.append({
            "nconst": c.person.id,
            "primary_name": c.person.primary_name,
            "ordering": None,
            "category": c.category,
            "job": c.job,
            "characters": None,
        })

    data = _prune_none({
        "title_id": title.id,
        "primary_title": title.primary_title,
        "original_title": title.original_title,
        "title_type": title.title_type,
        "is_adult": None,
        "start_year": title.start_year,
        "end_year": title.end_year,
        "runtime_minutes": title.runtime_minutes,
        "genres": ",".join(title.genres) if title.genres else "",
        "average_rating": title.average_rating,
        "num_votes": title.num_votes,
        "director_names": _director_names(principals_raw),
        "writer_names": _writer_names(principals_raw),
        "principals": [
            _prune_none({
                "nconst": p["nconst"],
                "primary_name": p["primary_name"],
                "ordering": p["ordering"],
                "category": p["category"],
                "characters": p["characters"],
            })
            for p in principals_raw
        ],
    })
    return {"data": data}


# ─── GET /api/v1/titles/{id}/principals ──────────────────────────────
@router.get("/titles/{tconst}/principals")
async def get_title_principals(tconst: str):
    title = resolve_title(tconst)
    if title is None:
        raise AppError("NOT_FOUND", "Title not found", 404)

    try:
        cast = _resolve_cast(tconst, limit=100)
        crew = _resolve_crew(tconst)
    except Exception:
        cast = []
        crew = []

    data = []
    for c in cast:
        data.append(_prune_none({
            "nconst": c.person.id,
            "primary_name": c.person.primary_name,
            "ordering": c.ordering,
            "category": c.category,
            "job": c.job,
            "characters": c.character,
        }))
    for c in crew:
        data.append(_prune_none({
            "nconst": c.person.id,
            "primary_name": c.person.primary_name,
            "ordering": None,
            "category": c.category,
            "job": c.job,
            "characters": None,
        }))
    return {"data": data}


# ─── GET /api/v1/persons/{id} ────────────────────────────────────────
@router.get("/persons/{nconst}")
async def get_person_detail(nconst: str):
    person = resolve_person(nconst)
    if person is None:
        raise AppError("NOT_FOUND", "Person not found", 404)

    known_for_ids = ",".join(t.id for t in (person.known_for_titles or []))
    data = _prune_none({
        "nconst": person.id,
        "primary_name": person.primary_name,
        "birth_year": person.birth_year,
        "death_year": person.death_year,
        "primary_profession": ",".join(person.primary_profession) if person.primary_profession else "",
        "known_for_titles": known_for_ids,
    })
    return {"data": data}


# ─── GET /api/v1/persons/{id}/credits ────────────────────────────────
@router.get("/persons/{nconst}/credits")
async def get_person_credits(nconst: str):
    person = resolve_person(nconst)
    if person is None:
        raise AppError("NOT_FOUND", "Person not found", 404)

    try:
        filmography = _resolve_filmography(nconst, limit=100)
    except Exception:
        filmography = []

    data = []
    for entry in filmography:
        data.append(_prune_none({
            "category": entry.category,
            "title_id": entry.title.id,
            "primary_title": entry.title.primary_title,
            "start_year": entry.year,
            "genre_list": entry.title.genres,
            "average_rating": entry.title.average_rating,
        }))
    return {"data": data}


# ─── GET /api/v1/search ──────────────────────────────────────────────
@router.get("/search")
async def search(
    q: str = Query(..., min_length=2),
    type: str = Query("all", pattern="^(title|person|all)$"),
    limit: int = Query(20, ge=1, le=50),
):
    titles_data: list = []
    persons_data: list = []

    if type in ("title", "all"):
        try:
            title_items, _total, _has_more, _cursor = resolve_search(q, first=limit)
        except Exception:
            title_items = []
        for t in title_items:
            titles_data.append(_prune_none({
                "title_id": t.id,
                "primary_title": t.primary_title,
                "start_year": t.start_year,
            }))

    if type in ("person", "all"):
        try:
            from app.graphql.resolvers import _get_con
            con = _get_con()
            rows = con.execute(
                "SELECT nconst, primary_name, birth_year FROM dim_person WHERE primary_name ILIKE ? LIMIT ?",
                [f"%{q}%", limit],
            ).fetchall()
            for r in rows:
                persons_data.append(_prune_none({
                    "nconst": r[0],
                    "primary_name": r[1],
                    "birth_year": r[2],
                }))
        except Exception:
            pass

    return {"data": {"titles": titles_data, "persons": persons_data}}


# ─── POST /api/v1/predict/genre ──────────────────────────────────────
@router.post("/predict/genre")
async def predict_genre(body: GenrePredictRequest):
    svc = get_model_service()
    features = svc.build_feature_vector(body.model_dump())
    version = 1 if _inv_exists() else 0
    if features is None:
        return {
            "data": {"genres": [], "probabilities": {}, "model_version": 0, "model_name": ""},
            "meta": {"latency_ms": 0, "cached": False},
        }
    results = svc.predict_genre(features)
    return {
        "data": {
            "genres": results,
            "probabilities": {r["name"]: r["confidence"] for r in results},
            "model_version": version,
            "model_name": "Elyssa_Genre_GMU",
        },
        "meta": {"latency_ms": 0, "cached": False},
    }


# ─── POST /api/v1/predict/rating ─────────────────────────────────────
@router.post("/predict/rating")
async def predict_rating(body: RatingPredictRequest):
    svc = get_model_service()
    features = svc.build_feature_vector(body.model_dump())
    version = 1 if _inv_exists() else 0
    if features is None:
        return {
            "data": {"predicted_rating": 0.0, "confidence_interval": [], "model_version": 0, "model_name": ""},
            "meta": {"latency_ms": 0, "cached": False},
        }
    rating = svc.predict_rating(features)
    return {
        "data": {
            "predicted_rating": round(float(rating), 2),
            "confidence_interval": [],
            "model_version": version,
            "model_name": "Elyssa_Rating_CatBoost",
        },
        "meta": {"latency_ms": 0, "cached": False},
    }


# ─── GET /api/v1/models ──────────────────────────────────────────────
@router.get("/models")
async def list_models():
    svc = get_model_service()
    models = svc.get_models()

    exists = _inv_exists()
    for m in models:
        m["version"] = 1 if exists else 0

    return {"data": models}


# ─── POST /api/v1/admin/reload-cache ────────────────────────────────
@router.post("/admin/reload-cache")
async def reload_cache():
    from app.graphql.resolvers import _get_con
    from app.cache.memory import get_cache
    _get_con.cache_clear()
    cache = get_cache()
    cache.clear()
    svc = get_model_service()
    svc.load()
    return {"status": "ok", "message": "DuckDB connection, cache, and models reloaded"}
