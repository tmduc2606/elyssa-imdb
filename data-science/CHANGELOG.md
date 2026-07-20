# Changelog

## v3.0.0 — 2026-07-19
### Added
- Modular `src/` package with importable Python modules
- `GoldDataLoader`, `temporal_split()`, `FeatureBuilder` extracted from notebooks
- `GatedMultimodalUnit`, `CatBoostRegressor`, NCF, SVD, Hybrid recommender as modules
- `QualityGateEvaluator` with G1–G6 check automation
- `ModelRegistry` with stage transitions (Staging → Production)
- `scripts/run_pipeline.py` — stage orchestrator
- `scripts/validate_contracts.py` — artifact schema validation
- `scripts/export_marts.py`, `scripts/generate_model_cards.py`
- `config/settings.yaml` — central config
- `config/environments.yaml` — dev/staging/prod profiles
- `pytest` suite: 7 test files, 50+ test cases
- `safe_minmax()` utility — zero-division–safe normalisation
- `verify_artifacts()` — required artifact checklist
- MLflow metric name sanitisation (`@` → `_at_`, `+` → `_and_`)
- Model card template (`docs/model_cards/TEMPLATE.md`)

### Changed
- Target leakage fixed: `average_rating` and `num_votes` removed from feature vector
- Feature vector expanded: added `actress_count`, `producer_count`, `editor_count`, `cinematographer_count`, `self_count`, `series_episode_count`, `series_avg_episode_rating`, `min_season`, `max_season`
- `requirements.txt` pinned to .venv versions (Phase 3 production compatibility)
- `ds-to-web.md` contract updated: corrected schema format, leakage-safe API examples
- Notebook verification cell added to FE notebook

### Removed
- Leaked features from rating regression feature construction
- Inline code duplication (extracted to modules)

## v2.0.0 — 2026-07-18
### Added
- Phase 2 Duke's Manual notebooks (EDA → FE → Modeling → Analytics)
- 52 EDA visualisations, 14 registered models
- MLflow tracking with try/except fallback
- GMU with gated multimodal fusion
- CatBoost with Optuna hyperparameter tuning
- SHAP explainability (TreeExplainer, KernelExplainer)
- Ablation studies for modality combinations

## v1.0.0 — 2026-07-10
### Added
- Initial Phase 1 pipeline setup
- Gold-layer Parquet export scripts
- DuckDB pushdown queries
