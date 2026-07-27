# Elyssa IMDb — ML API Reference

## Endpoints

### POST `/api/v1/predict/genre`

Predict genres for a title using the GMU model.

**Request:**

```json
{
  "runtime_minutes": 148,
  "start_year": 2010,
  "is_adult": false,
  "title_type": "movie"
}
```

**Response:**

```json
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

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| runtime_minutes | float | No | Runtime in minutes |
| start_year | int | No | Release year |
| is_adult | bool | No | Adult content flag |
| title_type | string | No | movie, tvseries, tvepisode, etc. |

---

### POST `/api/v1/predict/rating`

Predict rating for a title using CatBoost.

**Request:**

```json
{
  "runtime_minutes": 148,
  "start_year": 2010,
  "is_adult": false,
  "title_type": "movie"
}
```

**Response:**

```json
{
  "predicted_rating": 8.72,
  "model_version": 2,
  "model_name": "Elyssa_Rating_CatBoost"
}
```

---

### GET `/api/v1/models`

List all registered models and their current production status.

**Response:**

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

## Feature Construction

The inference pipeline builds a feature vector from:

- **Tabular features** (26 dims): runtime, year, credits, episode metadata, KG aggregates
- **Text embedding** (768 dims): DistilBERT pooled output
- **Total**: 794 dims

### Excluded Features (Target Leakage)

`average_rating` and `num_votes` are **never** used as input features — these are the prediction targets for rating regression.

---

## Model Files

| Artifact | Path | Format |
|----------|------|--------|
| GMU genre model | `processed/gmu_genre_best.pt` | PyTorch state_dict |
| CatBoost rating model | `processed/catboost_rating_model.cbm` | CatBoost native |
| Feature schema | `processed/feature_columns.json` | JSON |
| Genre MLB | `processed/genre_list_mlb.joblib` | Joblib |
| Preprocessor | `processed/preprocessor.joblib` | Joblib |
| Scaler | `processed/scaler.joblib` | Joblib |
| Model inventory | `processed/model_inventory.json` | JSON |

---

## Quality Gates

| Gate | Metric | Threshold |
|------|--------|-----------|
| G.1 | Rating RMSE | <= 0.55 |
| G.2 | Genre macro F1 | > 0.60 |
| G.3 | Temporal generalization | test set = post-2019 |
| G.4 | MLflow naming | regex compliant |
| G.5 | Inference latency | < 100ms p95 |
| G.6 | All artifacts present | required files exist |

---

## Temporal Split Constants

```
TRAIN_YEAR_MAX = 2014
VAL_YEAR_MIN   = 2015
VAL_YEAR_MAX   = 2018
TEST_YEAR_MIN  = 2019
```
