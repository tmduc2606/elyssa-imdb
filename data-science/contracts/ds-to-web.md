# DataScience-to-WebApplication Contract

## Overview

This contract defines the **output interface** between Data Science and
the Web Application API gateway. Data Science produces trained models,
feature schemas, and inference artifacts. The Web Application consumes
them via MLflow model registry and local artifact files.

**Producer:** Data Science
**Consumer:** Web Application (API gateway)
**Registry:** MLflow (local or remote)

---

## MLflow Registered Models

### Elyssa_Genre_GMU

| Field | Value |
|-------|-------|
| Purpose | Multi-label genre classification |
| Architecture | Gated Multimodal Unit (GMU) |
| Input | Tabular (26 dims) + Text embedding (768 dims) = 794 dims |
| Output | 28-dim sigmoid (multi-label) |
| Primary metric | `macro_f1` |
| Threshold | `macro_f1 > 0.60` |
| Model file | `processed/gmu_genre_best.pt` |
| Feature schema | `processed/feature_columns.json` (see below) |

### Elyssa_Rating_CatBoost

| Field | Value |
|-------|-------|
| Purpose | Rating regression (1.0–10.0) |
| Architecture | CatBoost regressor |
| Input | All features (794 dims) — average_rating/num_votes EXCLUDED |
| Output | Single float (predicted rating) |
| Primary metric | `rmse` |
| Threshold | `rmse <= 0.55` |
| Model file | `processed/catboost_rating_model.cbm` |
| Leakage protection | Rating target columns stripped upstream |

### Elyssa_Ensemble_Genre

| Field | Value |
|-------|-------|
| Purpose | Stacking ensemble for genre classification |
| Base learners | BiLSTM, GMU, Dummy |
| Meta-learner | Ridge classifier |
| Primary metric | `macro_f1` |
| Model file | `ensemble_models/stacking_meta_genre.pkl` |

---

## Inference Artifacts

| Artifact | Path (relative to processed/) | Format | Required |
|----------|-------------------------------|--------|----------|
| Feature columns schema | `feature_columns.json` | JSON | Yes |
| Genre multi-label binarizer | `genre_list_mlb.joblib` | Joblib | Yes |
| Region multi-label binarizer | `region_list_mlb.joblib` | Joblib | No |
| Preprocessor (ColumnTransformer) | `preprocessor.joblib` | Joblib | Yes |
| Feature scaler | `scaler.joblib` | Joblib | Yes |
| GMU genre model | `gmu_genre_best.pt` | PyTorch state_dict | Yes |
| CatBoost rating model | `catboost_rating_model.cbm` | CatBoost native | Yes |
| Stacking meta (genre) | `stacking_meta_genre.pkl` | Pickle | No |
| Stacking meta (rating) | `stacking_meta_rating.pkl` | Pickle | No |
| Content recommender | `content_cosine_recommender.pkl` | Pickle | No |
| Title embeddings | `title_embeddings.npy` or `title_embeddings_shard_*.npy` | NumPy | No |
| Model inventory | `model_inventory.json` | JSON | Yes |
| Temporal split info | `temporal_split.parquet` | Parquet | No |

---

## API Contract (for Web Application)

### POST /api/v1/predict/genre

```json
// Request — NOTE: average_rating and num_votes are NOT features
{
  "runtime_minutes": 148,
  "start_year": 2010,
  "title_type": "movie",
  "is_adult": false
}

// Response
{
  "genres": [
    { "name": "Action", "confidence": 0.92 },
    { "name": "Sci-Fi", "confidence": 0.87 },
    { "name": "Thriller", "confidence": 0.74 }
  ],
  "probabilities": { "Action": 0.92, "Sci-Fi": 0.87, ... },
  "model_version": 3,
  "model_name": "Elyssa_Genre_GMU"
}
```

### POST /api/v1/predict/rating

```json
// Request — NOTE: average_rating and num_votes are NOT allowed (target leakage)
{
  "runtime_minutes": 148,
  "start_year": 2010,
  "title_type": "movie",
  "is_adult": false
}

// Response
{
  "predicted_rating": 8.72,
  "model_version": 2,
  "model_name": "Elyssa_Rating_CatBoost"
}
```

### GET /api/v1/models

```json
{
  "models": [
    {
      "name": "Elyssa_Genre_GMU",
      "version": 3,
      "stage": "production",
      "metrics": { "macro_f1": 0.642 }
    },
    {
      "name": "Elyssa_Rating_CatBoost",
      "version": 2,
      "stage": "production",
      "metrics": { "rmse": 0.52 }
    }
  ]
}
```

---

## Quality Gate (Gold-Layer Gate C.4)

No model reaches production without passing ALL:

| Gate | Metric | Threshold | Verified In |
|------|--------|-----------|-------------|
| G.1 | Rating RMSE | <= 0.55 | Analytics notebook |
| G.2 | Genre macro_f1 | > 0.60 | Analytics notebook |
| G.3 | Temporal generalization | test set = post-2019 | All notebooks |
| G.4 | MLflow metric naming | `[a-zA-Z0-9_\-\. /]+` | Modeling notebook |
| G.5 | Inference latency | < 100ms per prediction | Analytics notebook |
| G.6 | Model artifacts exist | All required artifacts present | Analytics notebook |

---

## Feature Construction (Inference-time)

The API must construct the feature vector using `feature_columns.json`:

```python
import json, numpy as np

with open("feature_columns.json") as f:
    schema = json.load(f)

# schema = {
#   "tabular_features": ["start_year", "runtime_minutes", ...],  # 26 columns (avg_genre_year_* removed)
#   "text_features": ["text_emb_0", ..., "text_emb_767"],         # 768 columns
#   "total_features": 794
# }

def build_feature_vector(raw_input: dict, text_embedding: np.ndarray) -> np.ndarray:
    """Build N-dim vector from raw API input + pre-computed text embedding."""
    tab_cols = schema["tabular_features"]
    tabular = np.zeros(len(tab_cols), dtype=np.float32)
    for i, col in enumerate(tab_cols):
        if col in raw_input:
            tabular[i] = float(raw_input[col])
        elif col.startswith("title_type_"):
            tt = raw_input.get("title_type", "")
            tabular[i] = 1.0 if tt == col.split("_", 2)[-1] else 0.0
        elif col.startswith("is_adult_"):
            adult = int(raw_input.get("is_adult", 0))
            tabular[i] = 1.0 if adult == int(col.split("_")[-1]) else 0.0
    return np.concatenate([tabular, text_embedding])
```

**Note:** `average_rating` and `num_votes` are excluded from `tabular_features` — these columns are the prediction target for rating regression and must not be passed as input features.

---

## Versioning

- Model versions are auto-incremented in MLflow
- `model_version` in API responses must match MLflow registry
- Artifact paths are stable (no version suffixes in filenames)
- Web Application caches `GET /api/v1/models` and refreshes on page load
