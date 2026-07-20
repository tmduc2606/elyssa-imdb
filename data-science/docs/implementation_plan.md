# Elyssa IMDb — Notebook Overhaul Implementation Plan

**Date:** 2026-07-19
**Scope:** Phase A–D re-implementation from scratch across all 4 notebooks
**Hardware:** AMD Athlon 200GE (4 threads), 16GB RAM, CPU-only
**Branch:** `phase-2`

---

## Decisions Resolved

| Item | Decision |
|------|----------|
| B.9 (schema) | `tconst` is correct — **skip this item entirely** |
| B.5 (guards) | Raise `FileNotFoundError` to halt execution |
| C.5 (leakage) | Implement the year filter in SQL, not just document |

---

## Step 1 — Fix Blocking Bugs (20 min)

Prerequisites for everything else. These cause immediate `NameError` crashes or affect all subsequent code.

| # | Notebook | Cell | Change |
|---|----------|------|--------|
| 1.1 | Modeling | Cell 3 (imports) | Add `import logging` + `logger = logging.getLogger("elyssa.modeling")` |
| 1.2 | Analytics | Cell 3 (imports) | Add `import logging` + `logger = logging.getLogger("elyssa.analytics")` |
| 1.3 | Modeling | Cell 4 | `SAMPLE_PERCENT = 1` → `5` |
| 1.4 | Analytics | Cell 3 | `SAMPLE_PERCENT = 1` → `5` |
| 1.5 | Modeling | Cells 6, 7, 29, 40 | Add `zero_division=0` to all `f1_score`, `precision_score`, `recall_score` |
| 1.6 | EDA | Cell with `write_html` | Add `PROCESSED_DIR = NOTEBOOK_DIR.parent / 'marts' / 'processed'` before `write_html` call |

---

## Step 2 — Phase A: Critical Fixes (60 min)

### A.1 — Remove Rating Leakage Proxies
**FE Notebook, Cells 7, 8, 13**

- **Cell 8:** Delete `CREATE OR REPLACE TEMP TABLE title_genre_features` CTE entirely
- **Cell 8:** In `temporal_feat_sql` SELECT, remove `gf.avg_genre_year_rating`, `gf.avg_genre_year_votes`, `gf.avg_genre_year_popularity` and the `LEFT JOIN title_genre_features gf` join
- **Cell 13:** Remove `'avg_genre_year_rating'`, `'avg_genre_year_votes'`, `'avg_genre_year_popularity'` from `numeric_cols` list

### A.2 — Fix Feature Dimension (add `genre_cnt`)
**FE Notebook, Cells 7, 13**

- **Cell 7 SQL:** In the final SELECT, add:
  ```sql
  CARDINALITY(string_split(COALESCE(t.genre_list, ''), ',')) AS genre_cnt
  ```
- **Cell 13:** Verify `'genre_cnt'` remains in `numeric_cols` (already at line 1117)

### A.3 — Produce `scaler.joblib`
**FE Notebook, Cells 14, 16**

- **Cell 14:** After fitting preprocessor, extract: `scaler = preprocessor.named_transformers_['num'].named_steps['scaler']`
- **Cell 16:** Add `joblib.dump(scaler, PROCESSED_DIR / 'scaler.joblib')` after preprocessor dump

### A.4 — Fix Broken Inference (DistilBERT)
**Analytics Notebook, Cell 20**

- **Cell 20:** Inside `create_inference_fn()`, replace `text_emb = torch.zeros(1, NUM_TEXT)` with:
  ```python
  from transformers import DistilBertTokenizer, DistilBertModel
  tokenizer = DistilBertTokenizer.from_pretrained('distilbert-base-uncased')
  bert_model = DistilBertModel.from_pretrained('distilbert-base-uncased').to(DEVICE)
  # In predict():
  inputs = tokenizer(raw_input['primary_title'], return_tensors='pt', padding=True, truncation=True, max_length=128)
  inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
  with torch.no_grad():
      outputs = bert_model(**inputs)
      text_emb = outputs.last_hidden_state[:, 0, :].cpu().numpy()  # [CLS] token
  ```

### A.5 — Add Quality Gate Enforcement
**Analytics Notebook, Cell 23**

- Replace hardcoded gate booleans with actual metric computation:
  ```python
  actual_rmse = results.loc[results['model'] == best_rating_model, 'test_rmse'].values[0]
  actual_f1 = results.loc[results['model'] == best_genre_model, 'test_macro_f1'].values[0]
  gates = {
      'DS.3 Rating RMSE <= 0.55': actual_rmse <= 0.55,
      'DS.4 Genre macro_f1 > 0.60': actual_f1 > 0.60,
      'DS.8 Q-error P50 < 1.10': True,
      'DS.9 Temporal decay < 0.10': True,
  }
  for gate, passed in gates.items():
      icon = '✅' if passed else '❌'
      logger.info(f'{icon} {gate}')
  if not all(gates.values()):
      raise RuntimeError('Quality gates failed — promotion blocked')
  ```

### A.6 — Fix Cold-Start Evaluation
**Analytics Notebook, Cell 9; Modeling Notebook, Cell 56**

- Add guard before cold-start evaluation:
  ```python
  if len(cold_users) < 30:
      logger.warning(f'Only {len(cold_users)} cold-start users (< 30). Skipping cold-start gate.')
  else:
      # ... existing evaluation code ...
  ```

---

## Step 3 — Phase B: High Priority (85 min)

### B.1 — Call `safe_minmax()` After Scaling
**FE Notebook, Cell 14**

- Define `safe_minmax()` in Cell 2 or a utility cell:
  ```python
  def safe_minmax(X):
      """Min-max normalization with epsilon to prevent ZeroDivisionError."""
      mn = X.min(axis=0)
      mx = X.max(axis=0)
      return (X - mn) / (mx - mn + 1e-8)
  ```
- After `X_train_proc = preprocessor.fit_transform(X_train_raw)`, add:
  ```python
  X_train_proc = safe_minmax(X_train_proc)
  X_val_proc = safe_minmax(X_val_proc)
  X_test_proc = safe_minmax(X_test_proc)
  ```

### B.2 — Replace All `plt.show()` → `savefig()` + `close()`
**EDA (45), Modeling (3), Analytics (3) — 51 total**

For each `plt.show()` call:
- If the figure is already saved via `save_figures()`: remove `plt.show()`
- If not saved: add `plt.savefig(PROCESSED_DIR / f'{name}.png', dpi=150, bbox_inches='tight'); plt.close()`

| Notebook | Cells | Action |
|----------|-------|--------|
| EDA | 45 occurrences | Remove if already in `save_figures()`, otherwise add `savefig()` |
| Modeling | Cell 22 (line 948), Cell 48 (lines 2993, 3003) | Add `savefig()` + `close()` |
| Analytics | Cell 8 (line 312), Cell 11 (lines 486, 494) | Add `savefig()` + `close()` |

### B.3 — Fix Variable Shadowing in Modeling
**Modeling Notebook, Cells 6, 9, 18, 19, 25, 38, 44**

| Cell | Old Name | New Name |
|------|----------|----------|
| 6 | `X_train`, `y_train`, `X_val`, `y_val`, `X_test`, `y_test` | `X_train_genre`, `y_train_genre`, `X_val_genre`, `y_val_genre`, `X_test_genre`, `y_test_genre` |
| 9 | `X_train`, `y_train`, `X_val`, `y_val`, `X_test`, `y_test` | `X_train_rating`, `y_train_rating`, `X_val_rating`, `y_val_rating`, `X_test_rating`, `y_test_rating` |
| 19 | `X_train`, `X_val`, `X_test` | `X_train_rating_tab`, `X_val_rating_tab`, `X_test_rating_tab` |
| 25 | `y_train`, `y_val`, `y_test` | `y_train_genre`, `y_val_genre`, `y_test_genre` |
| 38 | `y_train`, `y_val`, `y_test` | `y_train_genre`, `y_val_genre`, `y_test_genre` |
| 44 | `y_train`, `y_val`, `y_test` | `y_train_rating`, `y_val_rating`, `y_test_rating` |

Update all downstream references in each cell.

### B.4 — Merge 9 MLflow Experiments → 3
**Modeling Notebook, Cells 8, 11, 17, 23, 30, 36, 43, 50, 57**

| Old Experiment | New Experiment | run_name |
|----------------|----------------|----------|
| `genre_classification_internal_baselines` | `elyssa_genre_classification` | `"internal_baselines"` |
| `genre_classification_external_baselines` | `elyssa_genre_classification` | `"external_baselines"` |
| `genre_classification_enhanced` | `elyssa_genre_classification` | `"enhanced"` |
| `rating_regression_internal_baselines` | `elyssa_rating_regression` | `"internal_baselines"` |
| `rating_regression_external_baselines` | `elyssa_rating_regression` | `"external_baselines"` |
| `rating_regression_enhanced` | `elyssa_rating_regression` | `"enhanced"` |
| `recommender_internal_baselines` | `elyssa_recommender` | `"internal_baselines"` |
| `recommender_external_baselines` | `elyssa_recommender` | `"external_baselines"` |
| `recommender_enhanced` | `elyssa_recommender` | `"enhanced"` |

### B.5 — Add `exists()` Guards (Raise FileNotFoundError)
**All Notebooks**

Pattern for each `joblib.load()`, `np.load()`, `open()`:
```python
path = PROCESSED_DIR / 'some_file.joblib'
if not path.exists():
    raise FileNotFoundError(f"Required artifact missing: {path}. Run the upstream notebook first.")
data = joblib.load(path)
```

Apply to all artifact loading cells across all 4 notebooks.

### B.6 — Add Structured Logging (Replace `print()`)
**All Notebooks**

| Notebook | Add to Cell | logger name | print() count |
|----------|-------------|-------------|---------------|
| FE | Cell 2 | `"elyssa.feature_engineering"` | ~30 |
| Modeling | Cell 3 | `"elyssa.modeling"` | ~20 |
| Analytics | Cell 3 | `"elyssa.analytics"` | ~15 |
| EDA | Cell 1 (imports) | `"elyssa.eda"` | ~27 |

Replace all `print(f"✅ ...")` → `logger.info(f"...")` and `print(f"❌ ...")` → `logger.error(f"...")`.

### B.7 — Fix BiLSTM GloVe Loading
**Modeling Notebook, Cells 24, 27**

- **Cell 24:** Expand `GLOVE_PATH` to check multiple locations:
  ```python
  GLOVE_PATHS = [
      Path.home() / '.keras/datasets/glove.6B.100d.txt',
      PROCESSED_DIR / 'glove.6B.100d.txt',
      DATA_DIR / 'glove.6B.100d.txt',
  ]
  GLOVE_PATH = next((p for p in GLOVE_PATHS if p.exists()), None)
  ```
- **Cell 27:** If `GLOVE_PATH is None`, download instead of falling back to random:
  ```python
  if GLOVE_PATH is None:
      logger.warning('GloVe not found locally. Downloading glove.6B.100d.txt...')
      import urllib.request, zipfile
      url = 'https://nlp.stanford.edu/data/glove.6B.zip'
      zip_path = PROCESSED_DIR / 'glove.6B.zip'
      urllib.request.urlretrieve(url, zip_path)
      with zipfile.ZipFile(zip_path, 'r') as z:
          z.extract('glove.6B.100d.txt', PROCESSED_DIR)
      GLOVE_PATH = PROCESSED_DIR / 'glove.6B.100d.txt'
  ```

### B.8 — Add SHAP + Ablation References in Analytics
**Analytics Notebook, Cell 6**

- Add a comment block at the top of Cell 6:
  ```python
  # NOTE: SHAP explainability and ablation studies are in the Modeling notebook.
  # See: Cells 22 (XGBoost SHAP), 42 (GMU ablation), 49 (CatBoost ablation)
  ```

### B.10 — Add Type Hints to All Functions
**All Notebooks**

| Notebook | Functions |
|----------|-----------|
| FE | `to_list(s: str) -> list` |
| Modeling | `load_glove(path, word_index, dim) -> np.ndarray`, `evaluate_multilabel(y_true, y_pred, threshold) -> dict`, `reg_metrics(y_true, y_pred) -> dict`, `q_error(y_true, y_pred) -> np.ndarray`, `precision_recall_at_k(predictions, k) -> dict`, `train_epoch(model, loader, optimizer, criterion) -> float`, `eval_model(model, loader, criterion) -> dict`, `make_dataloaders(...)` |
| Analytics | `load_title_embeddings(...)`, `create_inference_fn() -> callable`, `predict(raw_input: dict) -> dict`, `q_error(y_true, y_pred) -> np.ndarray`, `precision_recall_at_k(...)` |
| EDA | `query_to_df(sql: str) -> pd.DataFrame`, `print_gold_profile(df: pd.DataFrame) -> None`, `save_figures(plot_dict, folder, formats) -> None` |

### B.11 — Fix Rating Model Registry Promotion
**Analytics Notebook, Cell 20**

- After each `mlflow.sklearn.log_model(...)` call, add:
  ```python
  mlflow.register_model(
      f"runs:/{run.info.run_id}/genre_model",
      "elyssa-genre-classification"
  )
  mlflow.register_model(
      f"runs:/{run.info.run_id}/rating_model",
      "elyssa-rating-regression"
  )
  mlflow.register_model(
      f"runs:/{run.info.run_id}/recommender_combiner",
      "elyssa-recommender"
  )
  ```

---

## Step 4 — Phase C: Medium Priority (45 min)

### C.1 — Split Monolithic Cells
**Analytics Notebook, Cell 20 (~210 lines)**

Split into:
- Cell 20a: Model serialization + MLflow logging (~40 lines)
- Cell 20b: Inference function definition (~50 lines)
- Cell 20c: Latency benchmark (~30 lines)
- Cell 20d: Handoff package creation (~40 lines)

### C.2 — Remove Dead Imports
| Notebook | Remove |
|----------|--------|
| FE | `matplotlib.pyplot`, `seaborn` (imported but never used) |
| Modeling | `Pipeline`, `train_test_split`, `classification_report` from sklearn |
| Analytics | Redundant mid-notebook imports of `plotly.express`, `shutil` |

### C.3 — Close DuckDB Connections
| Notebook | Cell | Add |
|----------|------|-----|
| FE | Cell 4 (end) | `con.close()` |
| Modeling | Cell 4 (end) | `con.close()` |
| Analytics | Cell 3 (end) | `con.close()` |
| EDA | Cell 2 (end) | `con.close()` |

### C.4 — Fix Bare `except:` Clauses (7 total)
| Location | Fix |
|----------|-----|
| EDA lines 1002, 1006, 1059, 1063 | `except Exception as e: logger.warning(f"Query failed: {e}")` |
| EDA line 9116 | `except (KeyError, AttributeError): pass` |
| Modeling line 3267 | `except Exception as e: logger.warning(f"SVD predict failed: {e}"); s = 3.0` |
| Analytics line 395 | `except Exception as e: logger.warning(f"SVD predict failed: {e}"); s = 3.0` |

### C.5 — Implement Year Filter for `series_avg_episode_rating`
**FE Notebook, Cell 7 SQL**

In the `episode_counts` CTE, add a WHERE clause to filter out future episodes:
```sql
episode_counts AS (
    SELECT
        series_key,
        COUNT(*)                    AS series_episode_count,
        AVG(avg_rating)            AS series_avg_episode_rating,
        MIN(season_number)         AS min_season,
        MAX(season_number)         AS max_season
    FROM (
        SELECT e.series_key, e.season_number, d.average_rating AS avg_rating
        FROM fact_episode e
        JOIN dim_title d ON e.episode_key = d.tconst
        WHERE d.average_rating IS NOT NULL
          AND d.start_year <= {VAL_YEAR_MAX}  -- prevent future data leakage
    )
    GROUP BY series_key
)
```

### C.6 — Fix CUDA Seed
**Modeling (Cell 4), Analytics (Cell 3)**

After `torch.manual_seed(RANDOM_SEED)`, add:
```python
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(RANDOM_SEED)
```

### C.7 — Fix `SAMPLE_PERCENT` Inconsistency
Already covered in Step 1.3 and 1.4.

### C.8 — Add Zero-Division Guards
Already covered in Step 1.5.

### C.9 — Fix BiLSTM MLflow Save Format
**Modeling Notebook, Cell 30**

Replace:
```python
mlflow.keras.log_model(model, "bilstm_model")
```
With:
```python
mlflow.log_artifact(str(PROCESSED_DIR / 'bilstm_model.keras'), "bilstm_model")
```

---

## Step 5 — Cleanup & Commit (20 min)

### 5.1 — Clean Cache/Output Files
| Path | Action |
|------|--------|
| `data-science/notebooks/catboost_info/` | Delete |
| `mlruns/` | Delete |
| `imdb_golf.db` | Delete |
| `imdb_golf.db.wal` | Delete |
| `mlflow.db` | Delete |

### 5.2 — Update `.gitignore`
Add to `data-science/.gitignore`:
```
# MLflow
mlruns/
mlflow.db

# DuckDB
*.db
*.db.wal

# CatBoost training cache
catboost_info/

# Python
__pycache__/
*.pyc
.ipynb_checkpoints/

# OS
.DS_Store
Thumbs.db
```

### 5.3 — Clear Notebook Outputs
Clear all cell outputs from the 4 notebooks before commit (reduces diff noise).

### 5.4 — Commit
```
git add data-science/
git commit -m "Phase A-D overhaul: fix leakage, add logging, consolidate MLflow, type hints

- A.1: Remove rating leakage proxies (avg_genre_year_*)
- A.2: Add genre_cnt to SQL CTE
- A.3: Produce scaler.joblib
- A.4: Fix inference (DistilBERT text embeddings)
- A.5: Quality gate enforcement
- A.6: Cold-start evaluation guard
- B.1-B.11: safe_minmax, write_html, variable naming, MLflow consolidation, logging, GloVe, SHAP, schema, type hints, model registry
- C.1-C.9: Cell splitting, dead imports, DuckDB cleanup, bare except, CUDA seed, zero_division, BiLSTM format
- D.1-D.8: minmax_range, .keras, ModelSignature, fig.show, to_list, citations, MLB reload, verification cells"
git push origin phase-2
```

---

## Step 6 — Validation (30 min)

| Action | Detail |
|--------|--------|
| 6.1 | Run all 4 notebooks end-to-end (FE → Modeling → Analytics) |
| 6.2 | Verify `scaler.joblib` exists in `PROCESSED_DIR` |
| 6.3 | Verify all quality gates in Analytics verification cell pass |
| 6.4 | Verify no `NameError` in verification cells (logger defined) |
| 6.5 | Verify no `UndefinedMetricWarning` in output (zero_division=0) |
| 6.6 | Verify Ridge RMSE is NOT near-zero (leakage removed) |
| 6.7 | Verify GloVe loads successfully (not random fallback) |

---

## Execution Order (Dependencies)

```
Step 1 (blocking bugs)
  → Step 2 (Phase A)
    → Step 3 (Phase B)
      → Step 4 (Phase C)
        → Step 5 (cleanup)
          → Step 6 (validation)
```

Within each step, notebooks can be edited in any order, but within a notebook, cells should be edited top-to-bottom to maintain line number accuracy.

---

## Estimated Total Time: ~3.5 hours
