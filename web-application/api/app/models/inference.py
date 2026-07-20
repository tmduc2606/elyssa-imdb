from __future__ import annotations

from pathlib import Path

import numpy as np

from app.config import get_settings


class ModelService:
    def __init__(self):
        self.ready = False
        self._feature_schema: dict | None = None

    def load(self):
        settings = get_settings()
        artifacts_path = Path(settings.model_artifacts_path or settings.gold_marts_path)
        feature_columns_file = artifacts_path / "feature_columns.json"
        if feature_columns_file.exists():
            import json
            self._feature_schema = json.loads(feature_columns_file.read_text())
        self.ready = True

    def build_feature_vector(self, raw_input: dict, text_embedding: np.ndarray | None = None) -> np.ndarray | None:
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

    def predict_genre(self, features: np.ndarray) -> list[dict]:
        return [{"name": "unknown", "confidence": 0.0}]

    def predict_rating(self, features: np.ndarray) -> float:
        return 0.0

    def get_models(self) -> list[dict]:
        return [
            {"name": "Elyssa_Genre_GMU", "version": 1, "stage": "development", "metrics": {}},
            {"name": "Elyssa_Rating_CatBoost", "version": 1, "stage": "development", "metrics": {}},
        ]


_service: ModelService | None = None


def get_model_service() -> ModelService:
    global _service
    if _service is None:
        _service = ModelService()
        _service.load()
    return _service
