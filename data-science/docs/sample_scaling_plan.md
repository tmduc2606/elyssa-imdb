# Sample Scaling Plan: Elyssa-IMDb Notebooks

## 1. Current Baseline

| Metric | Value |
|--------|-------|
| Working titles (after joins) | ~12,756 |
| Representing | ~0.1% of dim_title (12.6M), ~0.75% of fact_title_rating (1.69M) |
| FE total runtime | ~15 min |
| Modeling total runtime | ~35–45 min |
| Analytics runtime | ~5–10 min |
| **Total** | **~55–70 min** |

## 2. Bottleneck Breakdown

| Stage | Current Time | Scaling Factor | Constraint |
|-------|-------------|----------------|------------|
| **Text embedding** (DistilBERT CPU) | 7.3 min (12,756 titles × 29.2/s) | **O(n)** — ~0.034 s/title | CPU, single-threaded |
| **CatBoost final** (874 iter × 5,171 rows) | 17.7 min | ~O(n·iter) — 2.35e-4 s/(row·iter) | CPU, depth 9 |
| **CatBoost Optuna** (10 trials × 3 folds) | ~25 min | O(n·trials·folds·iter) | CPU |
| **XGBoost GridSearch** (32 combos) | ~8 min | O(n·combos·iter) | CPU |
| **GMU Optuna** (10 trials × 30 epochs) | ~5–8 min | O(n·trials·epochs) | PyTorch CPU |
| **FE SQL + pandas** | ~3 min | Sub-linear (DuckDB push-down) | 16 GB RAM |
| **SHAP** (2 calls) | ~2 min | O(n·background·features) | CPU |

**Dominant terms:** Embedding (`O(n)`) and CatBoost (`O(n·iter·depth)`). At 5x data, CatBoost alone with current parameters would hit ~90 min.

## 3. Recommended Sample: **5%**

Increase `SAMPLE_PERCENT` to `5` and `LIMIT 50000` to `250000`. This yields ~63,780 working titles.

### Required Mitigations (to fit <= 2.5 h)

| Bottleneck | Change | Estimated Time at 5% |
|------------|--------|----------------------|
| **Embedding** (63,780 × 0.034s) | No change needed | 36 min |
| **CatBoost final** | Reduce iterations: 874 → **200**, depth: 9 → **6** | 15 min (vs 88 min at 874/9) |
| **CatBoost Optuna** | Reduce trials: 10 → **5**, folds: 3 → **2**, cap iterations: 200 | 8 min |
| **XGBoost GridSearch** | Reduce combos: 32 → **8** (prune `subsample`, `colsample_bytree`) | 6 min |
| **GMU Optuna** | Reduce trials: 10 → **5**, epochs: 30 → **15** | 6 min |
| **GMU final** | Keep patience=5, max 30 epochs (will stop early) | 5 min |
| **SHAP** | Reduce background: 200 → **100**, test: 500 → **200** | 1 min |
| **FE SQL + overhead** | DuckDB handles 5x push-down fine; pandas `.df()` ~64k rows | 5 min |
| **Analytics** | Negligible scaling | 10 min |
| **Total** | | **~92 min** (well within 2.5 h) |

## 4. Code Changes Required

### FE Notebook (`phase_2_duke_manual_feature_engineering.ipynb`)

| Cell | Change |
|------|--------|
| Cell 2, L121 | `SAMPLE_PERCENT = 5 if DEVELOPMENT_MODE else 100` |
| Cell 7, dev branch | `LIMIT 50000` → `LIMIT 250000` |
| Cell 4, sampled temp tables | Update print message to show 5% |

### Modeling Notebook (`phase_2_duke_manual_modeling.ipynb`)

| Cell | Change |
|------|--------|
| Cell 42 (CatBoost Optuna) | `n_trials=10` → `n_trials=5`; cap `iterations` to 200; `TimeSeriesSplit(n_splits=3)` → `n_splits=2` |
| Cell 43 (CatBoost final) | Hard-code `iterations=200` instead of using `best_params['iterations']`; cap `depth=6` |
| Cell 17 (XGBoost GridSearch) | Reduce `ParameterGrid` from 32 to 8 combos: remove `subsample` and `colsample_bytree` variations; keep only `n_estimators=[100]`, `max_depth=[5,7]`, `learning_rate=[0.05,0.1]` |
| Cell 36 (GMU Optuna) | `n_trials=10` → `n_trials=5`; reduce inner epochs to 15 |
| Cell 19 (SHAP XGBoost) | `min(200,...)` → `min(100,...)`; `X_test[:500]` → `X_test[:200]` |
| Cell 44 (SHAP CatBoost) | `X_test_full[:500]` → `X_test_full[:200]` |

### Analytics Notebook — No changes needed. Only loads pre-saved models; runtime is negligible.

## 5. Additional Optimizations (Bonus)

| Optimization | Impact | Effort |
|-------------|--------|--------|
| Add `PRAGMA threads=4` to DuckDB connection (exploit 200GE's 4 threads) | 20–30% SQL speedup | 1 line |
| Set `PRAGMA memory_limit='8GB'` for DuckDB to avoid swapping | Prevents OOM at 5% | 1 line |
| Save intermediate `.npy` files as `.npy.gz` (compressed) to reduce I/O | 2–3x less disk write time | Minor |
| Replace DistilBERT `model.eval()` with `torch.inference_mode()` (PyTorch >= 1.9) | ~10% embedding speedup | 1 line |
| Use `X_train = X_train.astype(np.float32)` before CatBoost to reduce memory | 2x memory reduction for training matrix | 1 line |

## 6. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| **OOM at 5%** during CatBoost (depth 6 x 64k rows x 796 feats) | Low | 16 GB is sufficient; fallback: reduce to 3% |
| **Embedding exceeds 45 min** if CPU throttles | Medium | Embedding is the only non-preemptible linear block; use `timeout` as safety belt |
| **Temporal split imbalance** at 5% | Low | `REPEATABLE(42)` seed ensures same split ratios; verify `TRAIN/` proportions match |
| **CatBoost overfitting** with depth 6 | Low | `early_stopping_rounds=30` still applies; test loss monitored |

## 7. Recommended Rollout

```
Phase 1: Apply hotfix (change 4 constants, run 5% sample)
          Expected: ~1.5 h total
Phase 2: If over budget, drop to 3% sample
Phase 3: If under budget, try 10% with aggressive parameter cuts
```

## 8. Quick Feasibility Hotfix

Apply before running full notebooks — change 4 lines:

```python
# FE Cell 2
SAMPLE_PERCENT = 5 if DEVELOPMENT_MODE else 100

# FE Cell 7, dev branch
base_feat_sql += " LIMIT 250000"                # was LIMIT 50000

# FE Cell 4, add DuckDB memory guard
con.execute("PRAGMA memory_limit='8GB'")        # add after view creation
con.execute("PRAGMA threads=4")                 # add after view creation

# Modeling Cell 42 (CatBoost Optuna) – reduce search
study.optimize(objective, n_trials=5, timeout=600)  # was n_trials=10
```

This alone cuts total runtime by ~40% vs. running unchanged at 5%.
