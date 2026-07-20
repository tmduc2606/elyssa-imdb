# Elyssa IMDb — Data Science Module

## Overview
Multi-modal, multi-task ML pipeline for IMDb data: genre classification (GMU + KG embeddings), rating regression (CatBoost), and hybrid recommendation — with production-grade artifact management and MLflow tracking.

## Architecture

```
Gold Parquet → src/data/loader.py → src/features/ → src/models/ → src/evaluation/ → src/inference/
                                         ↓                    ↓                    ↓
                                   Feature matrices      Trained models      Inference pipeline
                                   (npy/joblib)         (pt/cbm/joblib)     (predict_genre/rating)
```

## Directory Structure

| Directory | Purpose |
|-----------|---------|
| `src/` | Importable Python modules |
| `config/` | Central YAML config + environment profiles |
| `scripts/` | Pipeline orchestrator, contract validation |
| `notebooks/` | Thin EDA → FE → Modeling → Analytics wrappers |
| `tests/` | Pytest suite (splitter, features, models, inference) |
| `contracts/` | gold-to-ds.md (input), ds-to-web.md (output) |
| `marts/` | Gold-layer Parquet snapshots |
| `docs/` | Phase 3 plan, assessment report, model cards |

## Pipeline Usage

```bash
# Full pipeline
python scripts/run_pipeline.py --stage all

# Single stage
python scripts/run_pipeline.py --stage features

# Validate model artifacts against contract
python scripts/validate_contracts.py

# Generate model cards from inventory
python scripts/generate_model_cards.py
```

## Config Management

`config/settings.yaml` is the single source of truth for:
- Temporal split constants (train < 2015, val 2015–2018, test 2019+)
- Feature columns (tabular + text embedding)
- Model hyperparameters (GMU, CatBoost)
- Quality gate thresholds
- MLflow tracking URI

Switch environments via `config/environments.yaml` (dev/staging/prod).

## Quality Gates

| Gate | Metric | Threshold | Enforced By |
|------|--------|-----------|-------------|
| G.1 | Rating RMSE | ≤ 0.55 | `src/evaluation/gates.py` |
| G.2 | Genre Macro F1 | > 0.60 | `src/evaluation/gates.py` |
| G.3 | Temporal generalisation | Δ < 0.10 | `src/evaluation/temporal.py` |
| G.4 | MLflow naming compliance | regex | `src/utils/naming.py` |
| G.5 | Inference latency | < 100ms p95 | `tests/test_inference.py` |
| G.6 | All artifacts present | 18 required | `src/utils/verification.py` |
| G.7 | No target leakage | excluded features | `tests/test_features.py` |

## Hardware Constraints

| Resource | Value |
|----------|-------|
| CPU | AMD Athlon 200GE (4 threads) |
| RAM | 16 GB |
| GPU | None |
| Dev sample | 5% (TABLESAMPLE SYSTEM) |
