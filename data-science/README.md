<div align="center">

# Elyssa Data Science — Multi-Modal ML Pipeline

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-green.svg)](../docs/SMOKE_TEST.md)
[![PyTorch](https://img.shields.io/badge/PyTorch-GMU%20%2F%20BiLSTM-red.svg)](src/models/genre/gmu.py)
[![CatBoost](https://img.shields.io/badge/CatBoost-Rating%20Regression-yellow.svg)](src/models/rating/catboost_regressor.py)
[![SVD](https://img.shields.io/badge/SVD-Hybrid%20Recsys-blue.svg)](src/models/recommender/svd_model.py)
[![NCF](https://img.shields.io/badge/NCF-Hybrid%20Recsys-blue.svg)](src/models/recommender/ncf_model.py)

</div>

## Overview

Multi-modal, multi-task ML pipeline over the frozen Gold-layer marts: genre classification (GMU + KG
embeddings), rating regression (CatBoost), and hybrid recommendation (SVD / NCF) — with MLflow
tracking and production-grade artifact handoff to the Web Application.

```
Gold Parquet → EDA → Feature Engineering → Modeling → Analytics → Production (MLflow + artifacts)
```

## Quality Gates

Quality is enforced by `src/evaluation/gates.py` and verified in the analytics notebook:

| Gate | Metric | Threshold |
|------|--------|-----------|
| Rating RMSE | regression | ≤ 0.55 |
| Genre Macro F1 | classification | > 0.60 |
| Temporal generalisation | Δ | < 0.10 |
| MLflow naming | regex | `_at_` / `_and_`, no `@` / `+` |
| Inference latency | p95 | < 100 ms |
| Artifacts present | 18 required | all loadable |
| No target leakage | feature audit | excluded features |

## Model Zoo

| Model | Type | Task |
|-------|------|------|
| GMU (Gated Multimodal Unit) | PyTorch | Genre classification |
| BiLSTM | PyTorch | Genre classification (sequence) |
| XGBoost (genre) | Gradient boosting | Genre baseline |
| CatBoost | Gradient boosting | Rating regression |
| XGBoost (rating) | Gradient boosting | Rating baseline |
| Hybrid | Ensemble | Genre + Rating combined |
| SVD | Matrix factorisation | Collaborative filtering |
| NCF | Neural CF | Collaborative filtering |

## Pipeline Usage

```bash
# Full pipeline (after DE marts are available at data-science/marts/gold/)
python scripts/run_pipeline.py --stage all

# Checkpoint resume — skip stages that already completed
python scripts/run_pipeline.py --stage features

# Validate model artifacts against contract
python scripts/validate_contracts.py

# Generate model cards from inventory
python scripts/generate_model_cards.py
```

## Notebook Pipeline (sequential)

Run in order — each notebook depends on the previous outputs (never skip a stage):

| # | Notebook | Purpose |
|---|----------|---------|
| 1 | `notebooks/phase_2_duke_manual_eda.ipynb` | Exploratory data analysis |
| 2 | `notebooks/phase_2_duke_manual_feature_engineering.ipynb` | Tabular + text feature extraction, schema |
| 3 | `notebooks/phase_2_duke_manual_modeling.ipynb` | GMU / CatBoost / baselines + MLflow |
| 4 | `notebooks/phase_2_duke_manual_analytics.ipynb` | SHAP, temporal validation, drift, handoff |

## Quick Start (sample data)

```powershell
python scripts/generate_sample_data.py
New-Item -ItemType Junction -Path marts\gold -Target marts\sample
New-Item -ItemType Junction -Path notebooks\models -Target marts\sample_models
python scripts/run_pipeline.py --stage all --sample
```

## Benchmarks

5% sample (~63k titles) on AMD Athlon 200GE, CPU-only: Feature Engineering ~15 min, Modeling
~35–45 min, Analytics ~5–10 min → **~55–70 min total**. DistilBERT text embedding ~29.2 titles/s
(CPU). Final model quality is validated against the gates above (RMSE ≤ 0.55, Macro F1 > 0.60);
exact run values are recorded in `notebooks/models/shared/standardized_results.json`.

## Contracts

| Contract | Path | Role |
|----------|------|------|
| Input | `contracts/gold-to-ds.md` | Frozen Gold schemas, quality guarantees, temporal split constants |
| Output | `contracts/ds-to-web.md` | Model registry, inference artifacts, prediction API contract |

## Required Outputs (for Web API)

| Artifact | Path |
|----------|------|
| GMU model | `marts/processed/gmu_genre_best.pt` |
| CatBoost model | `marts/processed/catboost_rating_model.cbm` |
| Feature schema | `marts/processed/feature_columns.json` |
| Preprocessor / Scaler | `marts/processed/preprocessor.joblib`, `scaler.joblib` |

## Hardware Constraints

| Resource | Value |
|----------|-------|
| CPU | AMD Athlon 200GE (4 threads) |
| RAM | 16 GB |
| GPU | None (CPU-only PyTorch) |
| Dev sample | 5% (`TABLESAMPLE SYSTEM`, `REPEATABLE 42`) |
| Temporal split | Train < 2015 · Val 2015–2018 · Test 2019+ |

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md) for DS module milestones (v3.0.0 → v3.1.0).