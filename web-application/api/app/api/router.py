from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.models.inference import get_model_service

router = APIRouter(prefix="/api/v1")


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


@router.post("/predict/genre")
async def predict_genre(body: GenrePredictRequest):
    svc = get_model_service()
    features = svc.build_feature_vector(body.model_dump())
    if features is None:
        return {"genres": [], "probabilities": {}, "model_version": 0, "model_name": ""}
    results = svc.predict_genre(features)
    return {
        "genres": results,
        "probabilities": {r["name"]: r["confidence"] for r in results},
        "model_version": 1,
        "model_name": "Elyssa_Genre_GMU",
    }


@router.post("/predict/rating")
async def predict_rating(body: RatingPredictRequest):
    svc = get_model_service()
    features = svc.build_feature_vector(body.model_dump())
    if features is None:
        return {"predicted_rating": 0.0, "model_version": 0, "model_name": ""}
    rating = svc.predict_rating(features)
    return {
        "predicted_rating": round(float(rating), 2),
        "model_version": 1,
        "model_name": "Elyssa_Rating_CatBoost",
    }


@router.get("/models")
async def list_models():
    svc = get_model_service()
    return {"models": svc.get_models()}
