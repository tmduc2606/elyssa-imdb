<div align="center">

# Elyssa Data Science — Multi-Modal ML Pipeline

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-green.svg)](docs/SMOKE_TEST.md)
[![PyTorch](https://img.shields.io/badge/PyTorch-GMU%20%2F%20BiLSTM-red.svg)](data-science/src/models/genre/gmu.py)
[![CatBoost](https://img.shields.io/badge/CatBoost-Rating%20Regression-yellow.svg)](data-science/src/models/rating/catboost_regressor.py)
[![SVD](https://img.shields.io/badge/SVD-Hybrid%20Recsys-blue.svg)](data-science/src/models/recommender/svd_model.py)
[![NCF](https://img.shields.io/badge/NCF-Hybrid%20Recsys-blue.svg)](data-science/src/models/recommender/ncf_model.py)

</div>

## Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Model Zoo](#model-zoo)
- [Pipeline Usage](#pipeline-usage)
- [Quality Gates](#quality-gates)
- [Required Outputs](#required-outputs)
- [Notebooks Index](#notebooks-index)
- [Hardware Constraints](#hardware-constraints)

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

## Model Zoo

| Model | Path | Type | Task | Parameters |
|-------|------|------|------|------------|
| GMU | `src/models/genre/gmu.py` | PyTorch | Genre classification | 794 input (26 tabular + 768 text) |
| BiLSTM | `src/models/genre/bilstm.py` | PyTorch | Genre classification (sequence) | — |
| XGBoost (genre) | `src/models/genre/xgboost.py` | Gradient boosting | Genre baseline | — |
| CatBoost | `src/models/rating/catboost_regressor.py` | Gradient boosting | Rating regression | Same feature vector |
| XGBoost (rating) | `src/models/rating/xgboost.py` | Gradient boosting | Rating baseline | — |
| Hybrid | `src/models/recommender/hybrid.py` | Ensemble | Genre + Rating combined | — |
| SVD | `src/models/recommender/svd_model.py` | Matrix factorisation | Collaborative filtering | — |
| NCF | `src/models/recommender/ncf_model.py` | Neural CF | Collaborative filtering | — |

## Pipeline Usage

```bash
# Full pipeline (after DE marts are available at marts/gold/)
python scripts/run_pipeline.py --stage all

# Checkpoint resume — skip stages that already completed
python scripts/run_pipeline.py --stage features   # skip EDA if already done

# Single stage
python scripts/run_pipeline.py --stage features

# Validate model artifacts against contract
python scripts/validate_contracts.py

# Generate model cards from inventory
python scripts/generate_model_cards.py
```

## Quick Start

```powershell
# Use pre-packaged sample data
python scripts/generate_sample_data.py
New-Item -ItemType Junction -Path marts\gold -Target marts\sample
New-Item -ItemType Junction -Path notebooks\models -Target marts\sample_models
python scripts/run_pipeline.py --stage all --sample
```

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

## Benchmarks

### Pipeline Stage Timings (5% sample, ~63k titles)

| Stage | Runtime | Throughput / Notes |
|-------|---------|--------------------|
| Feature Engineering | ~15 min | DuckDB push-down + pandas (~3 min SQL, ~12 min text embedding) |
| Modeling | ~35–45 min | CatBoost 874 iter, XGBoost GridSearch 32 combos, GMU Optuna |
| Analytics | ~5–10 min | SHAP, temporal validation, feature importance |
| **Total** | **~55–70 min** | **5% sample on AMD Athlon 200GE, CPU-only** |

### Per-Model Throughput

| Model / Operation | Observed Rate | Constraint |
|-------------------|---------------|------------|
| DistilBERT text embedding | 29.2 titles/s | CPU, single-threaded |
| CatBoost final (874 iter × 5,171 rows) | 2.35e-4 s/(row·iter) | CPU, depth 9 |
| SHAP (2 calls) | ~2 min | O(n·background·features) |

### Model Quality

| Metric | Threshold | Observed Baseline |
|--------|-----------|-------------------|
| Rating RMSE | ≤ 0.55 | Validated in `src/evaluation/gates.py` |
| Genre Macro F1 | > 0.60 | Validated in `src/evaluation/gates.py` |

## Required Outputs

| Artifact | Path | Consumer |
|----------|------|----------|
| GMU model | `marts/processed/gmu_genre_best.pt` | Web API |
| CatBoost model | `marts/processed/catboost_rating_model.cbm` | Web API |
| Feature schema | `marts/processed/feature_columns.json` | Web API |
| Preprocessor | `marts/processed/preprocessor.joblib` | Web API |
| Scaler | `marts/processed/scaler.joblib` | Web API |

## Upstream Dependency

Gold Parquet marts from `data-engineering/` pipeline at `marts/gold/`.

## Downstream Consumer

Web Application API at `web-application/` reads from `marts/processed/` and `marts/gold/`.

## Checkpoint Resume

After each stage, artifacts are saved in `marts/processed/`. The pipeline detects existing artifacts and can skip completed stages:

```python
from pathlib import Path
processed = Path("marts/processed")
if (processed / "X_tab.npy").exists():
    print("Features already built — skipping FE stage")
```

## Config Management

`config/settings.yaml` is the single source of truth for:
- Temporal split constants (train < 2015, val 2015–2018, test 2019+)
- Feature columns (tabular + text embedding)
- Model hyperparameters (GMU, CatBoost)
- Quality gate thresholds
- MLflow tracking URI

Switch environments via `config/environments.yaml` (dev/staging/prod).

## Notebooks Index

| Notebook | Path | Purpose |
|----------|------|---------|
| EDA | `notebooks/phase_2_duke_manual_eda.ipynb` | Exploratory data analysis, univariate + bivariate |
| Feature Engineering | `notebooks/phase_2_duke_manual_feature_engineering.ipynb` | Tabular + text feature extraction, schema definition |
| Modeling | `notebooks/phase_2_duke_manual_modeling.ipynb` | GMU, CatBoost, baseline training + comparison |
| Analytics | `notebooks/phase_2_duke_manual_analytics.ipynb` | Drift analysis, SHAP, temporal validation |

## Hardware Constraints

| Resource | Value |
|----------|-------|
| CPU | AMD Athlon 200GE (4 threads) |
| RAM | 16 GB |
| GPU | None |
| Dev sample | 5% (TABLESAMPLE SYSTEM) |
