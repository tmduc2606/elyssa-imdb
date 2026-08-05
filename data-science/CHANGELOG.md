# Changelog

## v3.1.1 — 2026-08-05
### Changed
- `requirements.txt` fully pinned to `.venv`: added `pyarrow==24.0.0`, exact-pinned `polars==1.43.0`, `pycountry==26.2.16`, `psycopg2==2.9.12`, `ipykernel==7.3.0` (consistency with the "Pinned versions from .venv" header)

## v3.1.0 — 2026-08-03
### Added
- `src/data/interactions.py` — recommender interaction-table builder + persistence (`build_interactions`, `persist_interactions`, `load_interactions`, `interaction_summary`, `user_embeddings_from_interactions`) with FE-consistent `REPEATABLE(42)` dev sampling (plan §4.4)
- `parquet_row_count()` — Parquet row-group metadata counts, no full-table scan (plan §4.13)
- `evaluate_multilabel_detailed()` — prefixed metric keys per dataset (`{name}_macro_f1`, …) with backward-compatible `evaluate_multilabel` wrapper (plan §4.12)
- `build_split_masks()` in `src/evaluation/temporal.py` (plan §4.12)
- `gmu_best_params.json` / `catboost_best_params.json` persisted next to models (plan §4.10)
- `interactions.parquet` + `user_index.parquet` / `item_index.parquet` under `models/shared/` (plan §4.4)

### Changed
- **FE (A1/A2):** rating-pillar leakage guard — `average_rating`, `rating_bucket`, `num_votes` excluded from rating matrices (`feature_columns.json` gains `rating_tabular_features`); SQL pruning via `title_keys` semi-join CTEs (samples drop ~5M → ~250k rows); `dim_person` no longer sampled/counted; float32 end-to-end; file-backed DuckDB (`imdb_gold.db`, threads=4, 8 GB cap); embedding cache `exists()` short-circuit + batch 128
- **Modeling (A4):** XGBoost SHAP KernelExplainer → TreeExplainer (11 min 14 s → ~30 s); SVD batch `algo.test()` predict; NCF `EPOCHS 20→10` + early stop on val RMSE (patience 2); GMU Optuna epochs 15→10, patience 5→3, batch ∈ [128,256]; CatBoost `n_trials=3` in dev; BiLSTM `EPOCHS 20→8`, patience 2, batch 256
- **Analytics (A6):** cold-start cell loads persisted interactions instead of re-querying 5M rows (fixes drift 0.0182 → 0.0292); Keras BiLSTM re-predict subsampled to ≤5k rows; `parquet_row_count` metadata counts; seeded `default_rng`; inference `max_length 128→32`, `torch.set_num_threads(4)`, module-level DistilBERT singleton; honest DS.8/DS.9 gates (no hardcoded True)
- **src/ refactor (A8):** notebooks now import `load_title_embeddings`, `parquet_row_count`, `q_error`, `precision_recall_at_k`, `to_list`, `build_split_masks`, interactions helpers from `src/` instead of redefining them

### Fixed
- FE Cell 7: `episode_counts` referenced out-of-scope `e.series_key` in outer `SELECT`/`GROUP BY` — parity test caught it (DuckDB binder error)
- FE Cell 7: `title_keys` was a CTE but Cell 8 referenced it as a temp table — now materialised before the temporal aggregations
- Modeling Cell 54: `load_title_embeddings(MODELS_DIR / 'shared')` → `MODELS_DIR` (loader appends `/shared`)
- Modeling Cell 57: `global_item_emb` was referenced but never defined (NameError) — now computed from valid item embeddings
- Modeling Cell 63: XGBoost inventory entry read CatBoost-overwritten `best_params`/`test_rmse` — snapshotted in Cells 19/20
- Modeling Cell 9→48: CatBoost `.cbm` path in Analytics Cell 9 pointed at `shared/` instead of `rating/`
- Analytics Cell 14: `X_val_*`/`y_val_*` never loaded (NameError in stacking cells 15/16) — now loaded
- Analytics Cell 12: `plotly.express` used without import — added to Cell 2

### Notes
- Plan §4.7 temporal-features parity gate holds on synthetic Gold tables: `base_features` and `genre_year_stats` bit-identical old vs new; `temporal_features` row count + tconst set equal. Person-career aggregates (`dir_*`/`wri_*` career-length) shift slightly by design — restricted to the `title_keys` universe (video titles excluded) per plan §4.7
- float32 casts shift metrics at ~1e-7 — not visible at 4 dp (plan §4.6)
- Runtime gates (A3/A5/A7/A10, targets FE ≤ 90 min, Modeling ≤ 45 min, Analytics ≤ 15 min) pending end-to-end re-run on the data machine

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
