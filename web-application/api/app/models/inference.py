from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
from prometheus_client import Counter, Histogram

from app.config import get_settings

logger = logging.getLogger(__name__)

genre_predictions = Counter(
    "genre_predictions_total", "Total genre predictions", ["status"]
)
rating_predictions = Counter(
    "rating_predictions_total", "Total rating predictions", ["status"]
)
prediction_latency = Histogram(
    "prediction_latency_seconds", "Prediction latency", ["model"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)
)
prediction_confidence = Histogram(
    "prediction_confidence", "Prediction confidence", ["model"],
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
)


class ModelService:
    def __init__(self):
        self.ready = False
        self._feature_schema: dict | None = None
        self._genre_mlb: object | None = None
        self._preprocessor: object | None = None
        self._scaler: object | None = None
        self._gmu_model: object | None = None
        self._catboost_model: object | None = None
        self._title_embeddings: np.ndarray | None = None
        self._model_inventory: dict | None = None

    def load(self):
        settings = get_settings()
        artifacts_path = Path(settings.model_artifacts_path or settings.gold_marts_path)

        feature_columns_file = artifacts_path / "feature_columns.json"
        if feature_columns_file.exists():
            self._feature_schema = json.loads(feature_columns_file.read_text())
            logger.info("Loaded feature_columns.json (%d features)", self._feature_schema.get("total_features", 0))
        else:
            logger.warning("feature_columns.json not found — predictions disabled")

        mlb_file = artifacts_path / "genre_list_mlb.joblib"
        if mlb_file.exists():
            try:
                import joblib
                self._genre_mlb = joblib.load(str(mlb_file))
                logger.info("Loaded genre_list_mlb.joblib")
            except Exception as e:
                logger.warning("Failed to load genre_list_mlb.joblib: %s", e)

        preproc_file = artifacts_path / "preprocessor.joblib"
        if preproc_file.exists():
            try:
                import joblib
                self._preprocessor = joblib.load(str(preproc_file))
                logger.info("Loaded preprocessor.joblib")
            except Exception as e:
                logger.warning("Failed to load preprocessor.joblib: %s", e)

        scaler_file = artifacts_path / "scaler.joblib"
        if scaler_file.exists():
            try:
                import joblib
                self._scaler = joblib.load(str(scaler_file))
                logger.info("Loaded scaler.joblib")
            except Exception as e:
                logger.warning("Failed to load scaler.joblib: %s", e)

        gmu_file = artifacts_path / "gmu_genre_best.pt"
        if gmu_file.exists():
            try:
                from app.models.gmu import load_gmu_from_state_dict
                self._gmu_model = load_gmu_from_state_dict(str(gmu_file))
                logger.info("Loaded gmu_genre_best.pt")
            except Exception as e:
                logger.warning("Failed to load GMU model: %s", e)
        else:
            logger.warning("gmu_genre_best.pt not found — genre predictions disabled")

        catboost_file = artifacts_path / "catboost_rating_model.cbm"
        if catboost_file.exists():
            try:
                from catboost import CatBoostRegressor
                self._catboost_model = CatBoostRegressor()
                self._catboost_model.load_model(str(catboost_file))
                logger.info("Loaded catboost_rating_model.cbm")
            except Exception as e:
                logger.warning("Failed to load CatBoost model: %s", e)
        else:
            logger.warning("catboost_rating_model.cbm not found — rating predictions disabled")

        emb_file = artifacts_path / "title_embeddings.npy"
        if emb_file.exists():
            self._title_embeddings = np.load(str(emb_file))
            logger.info("Loaded title_embeddings.npy (%s)", self._title_embeddings.shape)

        inv_file = artifacts_path / "model_inventory.json"
        if inv_file.exists():
            try:
                raw = json.loads(inv_file.read_text())
                self._model_inventory = {m["name"]: m for m in raw}
                logger.info("Loaded model_inventory.json (%d models)", len(self._model_inventory))
            except Exception as e:
                logger.warning("Failed to load model_inventory.json: %s", e)
        else:
            logger.info("model_inventory.json not found — versions will default to 1")

        self.ready = True

    def _version_from_inventory(self, model_name: str) -> int:
        if self._model_inventory and model_name in self._model_inventory:
            return 1
        return 1

    def build_feature_vector(self, raw_input: dict, text_embedding: np.ndarray | None = None) -> np.ndarray | None:
        if self._feature_schema is None:
            return None

        if self._preprocessor is not None:
            try:
                import pandas as pd
                preprocessor = self._preprocessor
                numeric_cols = list(preprocessor.transformers_[0][2])
                categorical_cols = list(preprocessor.transformers_[1][2]) if len(preprocessor.transformers_) > 1 else []

                data = {}
                for col in numeric_cols:
                    val = raw_input.get(col)
                    import math
                    data[col] = val if val is not None and not (isinstance(val, float) and math.isnan(val)) else None
                for col in categorical_cols:
                    val = raw_input.get(col)
                    data[col] = val if val is not None else "missing"

                raw_df = pd.DataFrame([data])
                features = preprocessor.transform(raw_df)
                features = np.asarray(features).flatten().astype(np.float32)

                if text_embedding is not None:
                    return np.concatenate([features, text_embedding])
                return features
            except Exception as e:
                logger.warning("Preprocessor transform failed: %s — falling back to manual", e)

        return self._build_feature_vector_manual(raw_input, text_embedding)

    def _build_feature_vector_manual(self, raw_input: dict, text_embedding: np.ndarray | None = None) -> np.ndarray | None:
        if self._feature_schema is None:
            return None
        tab_cols = self._feature_schema["tabular_features"]
        tabular = np.zeros(len(tab_cols), dtype=np.float32)
        for i, col in enumerate(tab_cols):
            if col in raw_input:
                tabular[i] = float(raw_input[col])
            elif col.startswith("title_type_"):
                tt = raw_input.get("title_type", "")
                tabular[i] = 1.0 if tt == col.split("_", 2)[-1] else 0.0
            elif col.startswith("is_adult_"):
                adult_val = raw_input.get("is_adult", 0)
                adult = 0 if adult_val is None else int(adult_val)
                tabular[i] = 1.0 if adult == int(col.split("_")[-1]) else 0.0
        if text_embedding is not None:
            return np.concatenate([tabular, text_embedding])
        return tabular

    def _get_embedding(self, tconst: str | None = None) -> np.ndarray | None:
        if self._title_embeddings is not None and tconst is not None:
            try:
                return self._title_embeddings[tconst]
            except (KeyError, IndexError, TypeError):
                pass
        return np.zeros(768, dtype=np.float32)

    def get_title_embedding(self, title_id: str | None = None) -> np.ndarray | None:
        if self._title_embeddings is not None and title_id is not None:
            try:
                return self._title_embeddings[title_id]
            except (KeyError, IndexError, TypeError):
                pass
        if self._title_embeddings is not None:
            return np.zeros(self._title_embeddings.shape[1], dtype=np.float32)
        return None

    def predict_genre(self, features: np.ndarray) -> list[dict]:
        start = time.time()
        if self._gmu_model is not None:
            try:
                import torch
                with torch.no_grad():
                    tab_dim = len(self._feature_schema.get("tabular_features", [])) if self._feature_schema else 26
                    if len(features) > tab_dim:
                        tab = torch.from_numpy(features[:tab_dim]).float().unsqueeze(0)
                        text = torch.from_numpy(features[tab_dim:]).float().unsqueeze(0)
                    else:
                        tab = torch.from_numpy(features).float().unsqueeze(0)
                        text = torch.zeros(768).float().unsqueeze(0)
                    probs = torch.sigmoid(self._gmu_model(tab, text)).squeeze(0).numpy()
                if self._genre_mlb is not None and hasattr(self._genre_mlb, "classes_"):
                    results = []
                    for i, name in enumerate(self._genre_mlb.classes_):
                        results.append({"name": name, "confidence": float(probs[i])})
                    results.sort(key=lambda x: x["confidence"], reverse=True)
                    top = [r for r in results if r["confidence"] > 0.1]
                    for r in top:
                        prediction_confidence.labels(model="genre").observe(r["confidence"])
                    genre_predictions.labels(status="success").inc()
                    elapsed = time.time() - start
                    prediction_latency.labels(model="genre").observe(elapsed)
                    return top
                else:
                    genre_predictions.labels(status="success").inc()
                    return [{"name": f"genre_{i}", "confidence": float(p)} for i, p in enumerate(probs[:5]) if p > 0.1]
            except Exception as e:
                logger.warning("Genre prediction failed: %s", e)
                genre_predictions.labels(status="error").inc()
        genre_predictions.labels(status="no_model").inc()
        return [{"name": "unknown", "confidence": 0.0}]

    def predict_rating(self, features: np.ndarray) -> float:
        start = time.time()
        if self._catboost_model is not None:
            try:
                result = float(self._catboost_model.predict(features.reshape(1, -1))[0])
                elapsed = time.time() - start
                prediction_latency.labels(model="rating").observe(elapsed)
                rating_predictions.labels(status="success").inc()
                return result
            except Exception as e:
                logger.warning("Rating prediction failed: %s", e)
                rating_predictions.labels(status="error").inc()
        rating_predictions.labels(status="no_model").inc()
        return 0.0

    def get_models(self) -> list[dict]:
        models = []
        if self._gmu_model is not None:
            version = self._version_from_inventory("genre_gmu")
            metrics = {}
            if self._model_inventory and "genre_gmu" in self._model_inventory:
                metrics = self._model_inventory["genre_gmu"].get("metrics", {})
            models.append({
                "name": "Elyssa_Genre_GMU",
                "version": version or 1,
                "stage": "production",
                "metrics": metrics,
            })
        else:
            models.append({
                "name": "Elyssa_Genre_GMU",
                "version": 0,
                "stage": "unavailable",
                "metrics": {},
            })
        if self._catboost_model is not None:
            version = self._version_from_inventory("rating_catboost")
            metrics = {}
            if self._model_inventory and "rating_catboost" in self._model_inventory:
                metrics = self._model_inventory["rating_catboost"].get("metrics", {})
            models.append({
                "name": "Elyssa_Rating_CatBoost",
                "version": version or 1,
                "stage": "production",
                "metrics": metrics,
            })
        else:
            models.append({
                "name": "Elyssa_Rating_CatBoost",
                "version": 0,
                "stage": "unavailable",
                "metrics": {},
            })
        return models


_service: ModelService | None = None


def get_model_service() -> ModelService:
    global _service
    if _service is None:
        _service = ModelService()
        _service.load()
    return _service
