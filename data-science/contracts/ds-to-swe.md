# DataScience-to-SoftwareEngineering Contract

## Overview

This contract defines the **output interface** between Data Science and
Software Engineering (the Elyssa frontend). Data Science produces trained
models, feature schemas, and inference artifacts. Software Engineering
consumes them via MLflow model registry and local artifact files.

**Producer:** Data Science
**Consumer:** Software Engineering (elyssa-frontend)
**Registry:** MLflow (local or remote)

---

## MLflow Registered Models

### Elyssa_Genre_GMU

| Field | Value |
|-------|-------|
| Purpose | Multi-label genre classification |
| Architecture | Gated Multimodal Unit (GMU) |
| Input | Tabular (28 dims) + Text embedding (768 dims) = 796 dims |
| Output | 28-dim sigmoid (multi-label) |
| Primary metric | `macro_f1` |
| Threshold | `macro_f1 > 0.60` |
| Model file | `processed/gmu_genre_best.pt` |

### Elyssa_Rating_CatBoost

| Field | Value |
|-------|-------|
| Purpose | Rating regression (1.0–10.0) |
| Architecture | CatBoost regressor |
| Input | All features (796 dims) |
| Output | Single float (predicted rating) |
| Primary metric | `rmse` |
| Threshold | `rmse <= 0.55` |
| Model file | `processed/catboost_rating_model.cbm` |

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
| Feature scaler | `scaler.joblib` | Joblib | Yes |
| Label encoders | `label_encoders.joblib` | Joblib | Yes |
| GMU genre model | `gmu_genre_best.pt` | PyTorch state_dict | Yes |
| CatBoost rating model | `catboost_rating_model.cbm` | CatBoost native | Yes |
| Stacking meta (genre) | `stacking_meta_genre.pkl` | Pickle | No |
| Stacking meta (rating) | `stacking_meta_rating.pkl` | Pickle | No |
| Content recommender | `content_cosine_recommender.pkl` | Pickle | No |
| Title embeddings | `title_embeddings.npy` or `title_embeddings_shard_*.npy` | NumPy | No |

---

## API Contract (for elyssa-frontend)

### POST /api/v1/predict/genre

```json
// Request
{
  "title": "Inception",
  "runtime_minutes": 148,
  "start_year": 2010,
  "title_type": "movie",
  "is_adult": false,
  "num_votes": 2300000,
  "primary_name": "Christopher Nolan"
}

// Response
{
  "genres": [
    { "name": "Action", "confidence": 0.92 },
    { "name": "Sci-Fi", "confidence": 0.87 },
    { "name": "Thriller", "confidence": 0.74 }
  ],
  "model_version": 3,
  "model_name": "Elyssa_Genre_GMU"
}
```

### POST /api/v1/predict/rating

```json
// Request
{
  "title": "Inception",
  "runtime_minutes": 148,
  "start_year": 2010,
  "title_type": "movie",
  "is_adult": false,
  "num_votes": 2300000,
  "average_rating": 8.8,
  "primary_name": "Christopher Nolan"
}

// Response
{
  "predicted_rating": 8.72,
  "confidence_interval": [8.45, 8.99],
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

The frontend must construct the feature vector using `feature_columns.json`:

```python
import json, numpy as np

with open("feature_columns.json") as f:
    schema = json.load(f)

# schema = {
#   "tabular_columns": ["runtime_minutes", "start_year", ...],  # 28 columns
#   "embedding_dim": 768,
#   "total_dim": 796
# }

def build_feature_vector(raw_input: dict, embeddings: np.ndarray) -> np.ndarray:
    """Build 796-dim vector from raw API input + pre-computed embedding."""
    tabular = np.zeros(len(schema["tabular_columns"]))
    for i, col in enumerate(schema["tabular_columns"]):
        if col in raw_input:
            tabular[i] = raw_input[col]
    return np.concatenate([tabular, embeddings])
```

---

## Versioning

- Model versions are auto-incremented in MLflow
- `model_version` in API responses must match MLflow registry
- Artifact paths are stable (no version suffixes in filenames)
- Frontend caches `GET /api/v1/models` and refreshes on page load
