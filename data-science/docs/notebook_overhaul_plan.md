# Elyssa IMDb | Notebook Overhaul — Cumulative Hotfixes & Improvements Plan

**Date:** 2026-07-19
**Scope:** All 4 Phase 2 Duke's Manual notebooks (EDA → FE → Modeling → Analytics)
**Source:** AGENTS.md, 4 skill SKILL.md files, gold-to-ds.md, ds-to-web.md, assessment_report.md
**Evaluator:** DS Agent (deep audit of every notebook cell)
**Status:** DRAFT — Awaiting approval before implementation

---

## Executive Summary

The existing 4-notebook pipeline has strong Duke's aesthetic and solid temporal split discipline, but carries critical defects that block production readiness. This plan addresses **6 critical, 11 high, 9 medium, and 8 low** issues across all notebooks, organized into 5 phases of work.

### Severity Distribution

| Severity | Count | Examples |
|----------|-------|---------|
| **Critical** | 6 | Target leakage proxies, broken inference, missing artifacts, dimension mismatch |
| **High** | 11 | safe_minmax unused, no write_html, variable shadowing, no gate enforcement |
| **Medium** | 9 | Dead code, monolithic cells, missing exists() guards, schema mismatch |
| **Low** | 8 | Type hints, naming consistency, dead imports, CUDA seed |

### Estimated Effort

| Phase | Effort | Description |
|-------|--------|-------------|
| Phase A — Critical Fixes | 4–6 hours | Leaked features, broken inference, missing artifacts |
| Phase B — High Priority | 6–8 hours | Architecture cleanup, consistency, gate enforcement |
| Phase C — Medium Priority | 4–6 hours | Code quality, dead code, error handling |
| Phase D — Low Priority | 2–3 hours | Type hints, naming, imports |
| Phase E — Validation | 2–3 hours | Full re-run, pytest, quality gates |
| **Total** | **18–26 hours** | |

---

## Phase A — Critical Fixes (4–6 hours)

### A.1 Remove Rating Leakage Proxies (FE + Modeling + Analytics)

**Problem:** Features `avg_genre_year_rating`, `avg_genre_year_votes`, `avg_genre_year_popularity` are derived from the same `average_rating` column that is the regression target. This causes Ridge RMSE ≈ 2.6e-6 and CatBoost RMSE ≈ 0.005 — both are meaningless.

| Notebook | Location | Action |
|----------|----------|--------|
| FE notebook | Cell 5 (SQL), Cell 11 (numeric_cols) | Remove `avg_genre_year_rating`, `avg_genre_year_votes`, `avg_genre_year_popularity` from the SQL CTE and from `numeric_cols` |
| FE notebook | Cell 11, line 1208 | Also remove `genre_cnt` (never created by SQL — silently dropped) |
| Modeling notebook | All cells using `numeric_cols` | Verify feature vector excludes these columns |
| Analytics notebook | Cell 6, Cell 8 | Re-evaluate metrics after fix — RMSE should be > 0.5 (realistic) |

**Expected outcome:** Rating RMSE rises to realistic range (0.5–1.5 on 1.0–10.0 scale). CatBoost should still beat Ridge after Optuna tuning.

**Validation:** After fix, Ridge RMSE should be > 0.5, CatBoost RMSE should be < 0.55.

---

### A.2 Fix Feature Dimension Mismatch (FE)

**Problem:** `ds-to-web.md` specifies 30 tabular + 768 text = 798 dims. Actual output is 28 tabular + 768 text = 796 dims. The `genre_cnt` column is listed in `numeric_cols` but never created by SQL.

**Options:**
1. **Create `genre_cnt` column** in SQL CTE: `CARDINALITY(genre_list) AS genre_cnt`
2. **Create `is_adult` column** if missing (one-hot already handled)
3. **Update contract** to 28 tabular + 768 = 796

**Recommendation:** Option 1 — create `genre_cnt` in the SQL. It's a valid feature (count of genres per title) and the contract already expects 798 dims.

**Files:** FE notebook Cell 5 (SQL), Cell 11 (numeric_cols)

---

### A.3 Produce `scaler.joblib` as Standalone Artifact (FE)

**Problem:** `ds-to-web.md` lists `scaler.joblib` as a required artifact. It's never produced — the StandardScaler is embedded inside the ColumnTransformer preprocessor.

**Fix:** After fitting the preprocessor in Cell 12, extract and save the StandardScaler:
```python
scaler = preprocessor.named_transformers_['num'].named_steps['scaler']
joblib.dump(scaler, PROCESSED_DIR / 'scaler.joblib')
```

**Files:** FE notebook Cell 12 (after preprocessor fit), verification cell

---

### A.4 Fix Broken Inference Pipeline (Analytics)

**Problem:** `predict_genre()` in Analytics Cell 20 creates zero tensors for text embeddings (`torch.zeros(1, NUM_TEXT)`). The latency benchmark measures a non-functional path.

**Fix:** Replace zero embeddings with actual DistilBERT inference:
```python
from transformers import DistilBertTokenizer, DistilBertModel

tokenizer = DistilBertTokenizer.from_pretrained('distilbert-base-uncased')
text_model = DistilBertModel.from_pretrained('distilbert-base-uncased')

def get_text_embedding(title: str) -> np.ndarray:
    inputs = tokenizer(title, return_tensors="pt", truncation=True, max_length=128)
    with torch.no_grad():
        outputs = text_model(**inputs)
    return outputs.last_hidden_state[:, 0, :].squeeze().numpy()
```

**Files:** Analytics notebook Cell 20

---

### A.5 Add Quality Gate Enforcement Before Model Promotion (Analytics)

**Problem:** Models are promoted to MLflow Staging based solely on latency (< 100ms). Genre F1 = 0.33 (fails DS.4 threshold of 0.60) is promoted anyway.

**Fix:** Add gate assertions before promotion:
```python
from src.evaluation.gates import QualityGateEvaluator

evaluator = QualityGateEvaluator()
results = evaluator.evaluate({
    "test_rmse": catboost_rmse,
    "test_macro_f1": gmu_f1,
    "naming_compliant": True,
    "all_artifacts_present": True,
})
if not evaluator.all_passed(results):
    raise ValueError(f"Quality gates failed: {[k for k,v in results.items() if not v['pass']]}")
```

**Files:** Analytics notebook Cell 20 (before promotion block)

---

### A.6 Fix Cold-Start Evaluation (Modeling + Analytics)

**Problem:** Only 2 cold-start test users in dev mode. All cold-start metrics = 0.0. Evaluation is statistically insignificant.

**Fix:** 
1. Document that cold-start evaluation requires full dataset (not 5% sample)
2. In dev mode, use a proxy: evaluate on users with ≤ 3 interactions from the training set
3. Add a gate: skip cold-start promotion if test users < 30

**Files:** Modeling notebook Cell 52, Analytics notebook Cell 5

---

## Phase B — High Priority (6–8 hours)

### B.1 Call `safe_minmax()` (FE + Modeling)

**Problem:** `safe_minmax()` is defined in FE Cell 2 but never called. AGENTS.md golden rule: "Always use `safe_minmax()`."

**Fix:** Apply `safe_minmax()` to the final feature matrices after scaling:
```python
X_train = safe_minmax(X_train)
X_val = safe_minmax(X_val)
X_test = safe_minmax(X_test)
```

**Files:** FE notebook Cell 21 (after assembly), Modeling notebook (if re-scaling)

---

### B.2 Replace `plt.show()` with `write_html()` (All Notebooks)

**Problem:** AGENTS.md golden rule: "Always use `write_html()` not `fig.show()`." All 4 notebooks use `plt.show()` (45 instances in EDA alone).

**Fix:** Create a shared utility:
```python
def save_fig(fig, name, dir_path):
    fig.savefig(dir_path / f"{name}.png", dpi=150, bbox_inches="tight")
    fig.savefig(dir_path / f"{name}.html")  # via plotly if available
    plt.close(fig)
```

Replace `plt.show()` → `save_fig(fig, name, FIGURES_DIR)` across all notebooks.

**Files:** All 4 notebooks

---

### B.3 Consolidate Variable Names (Modeling)

**Problem:** `X_train`, `y_train` etc. are overwritten 4 times across cells (genre, rating, genre again, rating again). This is fragile.

**Fix:** Use task-specific names:
- `X_train_genre`, `X_val_genre`, `X_test_genre`
- `X_train_rating`, `X_val_rating`, `X_test_rating`
- `y_train_genre`, `y_val_genre`, `y_test_genre`
- `y_train_rating`, `y_val_rating`, `y_test_rating`

**Files:** Modeling notebook (all data-loading cells)

---

### B.4 Merge MLflow Experiments (Modeling)

**Problem:** 9 separate MLflow experiments for 3 pillars is excessive. Experiment naming is inconsistent.

**Fix:** Consolidate to 3 experiments:
- `elyssa_genre_classification` (runs: internal_baselines, external_baselines, enhanced)
- `elyssa_rating_regression` (runs: internal_baselines, external_baselines, enhanced)
- `elyssa_recommender` (runs: internal_baselines, external_baselines, enhanced)

**Files:** Modeling notebook (all MLflow cells)

---

### B.5 Add `exists()` Guards Before All Artifact Loads (All Notebooks)

**Problem:** Most `joblib.load()` and `np.load()` calls don't check if the file exists first. AGENTS.md: "Always check `exists()` before loading optional artifacts."

**Fix:**
```python
artifact_path = PROCESSED_DIR / "preprocessor.joblib"
if artifact_path.exists():
    preprocessor = joblib.load(artifact_path)
else:
    raise FileNotFoundError(f"Required artifact missing: {artifact_path}")
```

**Files:** All 4 notebooks

---

### B.6 Add Structured Logging (All Notebooks)

**Problem:** All 4 notebooks use `print()` (100+ instances). No `logging` module configured. AGENTS.md requires production-grade code.

**Fix:** Add to each notebook's setup cell:
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("elyssa.{notebook_name}")
```

Replace `print()` → `logger.info()` / `logger.warning()`.

**Files:** All 4 notebooks

---

### B.7 Fix BiLSTM GloVe Loading (Modeling)

**Problem:** BiLSTM Cell 24 falls back to random embeddings because GloVe file not found at `~/.keras/datasets/glove.6B.100d.txt`. Model achieves F1 = 0.011 (worse than dummy).

**Fix:**
1. Download GloVe to a project-local path
2. Or use `torch.nn.Embedding` with pretrained weights from a verified path
3. Or document that BiLSTM requires GloVe and skip it if unavailable

**Files:** Modeling notebook Cell 24

---

### B.8 Add SHAP + Ablation to Analytics (Analytics)

**Problem:** DS.6 (SHAP) and DS.7 (ablation) are mandatory quality gates with zero implementation in Analytics. They exist in Modeling but not in the Analytics evaluation pipeline.

**Fix:** Import and call the SHAP/ablation functions from Modeling:
```python
from src.evaluation.metrics import compute_shap, run_ablation
```

Or add inline SHAP analysis for the stacked ensemble models.

**Files:** Analytics notebook (new cells after Phase 5)

---

### B.9 Fix Schema Mismatch (Analytics)

**Problem:** Cell 5 SQL uses `f.tconst`, `d.tconst` but `gold-to-ds.md` defines `fact_performance.title_id`. If Gold layer enforces the contract, this breaks.

**Fix:** Verify the actual Parquet column names. If they're `tconst`, update the contract. If they're `title_id`, fix the SQL.

**Files:** Analytics notebook Cell 5, contracts/gold-to-ds.md

---

### B.10 Add Type Hints to All Functions (All Notebooks)

**Problem:** No function has type hints. Reduces IDE support and documentation.

**Fix:** Add type annotations to all function signatures:
```python
def evaluate_multilabel(y_true: np.ndarray, y_pred: np.ndarray, threshold: float = 0.5) -> dict:
def reg_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
def safe_minmax(x: np.ndarray, axis: int = 0) -> np.ndarray:
```

**Files:** All 4 notebooks

---

### B.11 Fix Rating Model Registry Promotion (Analytics)

**Problem:** Only the genre model is promoted to MLflow registry. Rating and recommender models are orphaned.

**Fix:** Add rating and recommender model registration:
```python
mlflow.register_model(catboost_run_uri, "Elyssa_Rating_CatBoost")
mlflow.register_model(svd_run_uri, "Elyssa_Recommender_SVD")
```

**Files:** Analytics notebook Cell 20

---

## Phase C — Medium Priority (4–6 hours)

### C.1 Split Monolithic Cells

| Notebook | Cell | Lines | Action |
|----------|------|-------|--------|
| FE | Cell 6 | ~210 | Split into 4–5 cells (one per temp table + join) |
| FE | Cell 9 | ~80 | Split full-mode and dev-mode loading |
| Analytics | Cell 20 | ~210 | Split into: serialization, inference, latency, registry, export |

---

### C.2 Remove Dead Code

| Notebook | Cell | Issue | Action |
|----------|------|-------|--------|
| FE | Cell 2 | `import matplotlib.pyplot as plt` (unused) | Remove |
| FE | Cell 2 | `import seaborn as sns` (unused) | Remove |
| FE | Cell 19 | Duplicate `to_list()` definition | Remove duplicate |
| FE | Cell 21 | Redundant `preprocessor = joblib.load(...)` | Remove (already in memory) |
| FE | Cell 5 | `archive_footage_count`, `archive_sound_count` computed but not selected | Remove from CTE |
| Modeling | Cell 1 | `surprise_train_test_split`, `surprise_split` (unused) | Remove |
| Modeling | Cell 35 | `train_mask = ...` (Ellipsis literal, dead code path) | Remove or implement |
| Analytics | Cell 1 | `torch.nn`, `torch.optim`, `DataLoader`, `TensorDataset` (unused) | Remove |
| Analytics | Cell 1 | `xgboost`, `SVD`, `cosine_similarity`, `StandardScaler` (unused) | Remove |
| Analytics | Cell 9 | `feature_std` overwritten by `std_dev` | Remove dead variable |

---

### C.3 Close DuckDB Connections

| Notebook | Cell | Issue |
|----------|------|-------|
| FE | Cell 4 | `con = duckdb.connect(...)` — never closed |
| Analytics | Cell 1 | `con = duckdb.connect(...)` — never closed |

**Fix:** Add `try/finally` or context manager:
```python
con = duckdb.connect(':memory:')
try:
    # ... work ...
finally:
    con.close()
```

---

### C.4 Fix Bare `except:` Clauses

| Notebook | Cell | Line |
|----------|------|------|
| EDA | Cell 8, 9, 59 | Bare `except:` |
| Modeling | Cell 50 | Bare `except:` |
| Analytics | Cell 5 | Bare `except:` |

**Fix:** Replace with `except Exception as e:` + `logger.warning(str(e))`

---

### C.5 Handle Sharded Embeddings in Verification (FE)

**Problem:** Verification cell assumes `title_embeddings.npy` exists. Full mode writes `shard_*.npy` files.

**Fix:**
```python
embeddings_file = PROCESSED_DIR / "title_embeddings.npy"
shard_files = list(PROCESSED_DIR.glob("title_embeddings_shard_*.npy"))
if embeddings_file.exists():
    status["title_embeddings"] = "OK (monolithic)"
elif shard_files:
    status["title_embeddings"] = f"OK ({len(shard_files)} shards)"
else:
    status["title_embeddings"] = "MISSING"
```

---

### C.6 Document `series_avg_episode_rating` Leakage Risk (FE)

**Problem:** `series_avg_episode_rating` is a proxy for the target (episode ratings come from the same `average_rating` column).

**Fix:** Add a warning comment and consider excluding from rating regression:
```python
# WARNING: series_avg_episode_rating is a temporal aggregation of episode ratings,
# which share the same underlying source as the rating target.
# Consider excluding for rating regression tasks.
```

---

### C.7 Fix CUDA Seed (All Notebooks with PyTorch)

**Problem:** `torch.manual_seed(RANDOM_SEED)` is set but `torch.cuda.manual_seed_all(RANDOM_SEED)` is missing.

**Fix:** Add after `torch.manual_seed()`:
```python
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(RANDOM_SEED)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
```

---

### C.8 Fix `SAMPLE_PERCENT` Inconsistency (Analytics)

**Problem:** Analytics notebook sets `SAMPLE_PERCENT = 1` when `DEVELOPMENT_MODE = True`, but AGENTS.md says `SAMPLE_PERCENT = 5`.

**Fix:** Change to `SAMPLE_PERCENT = 5` to match the other 3 notebooks and AGENTS.md.

---

### C.9 Add Zero-Division Guards (All Notebooks)

**Problem:** `f1_score`, `precision_score`, `recall_score` called without `zero_division=0`, producing warnings.

**Fix:** Add `zero_division=0` to all metric calls:
```python
f1_score(y_true, y_pred, average='macro', zero_division=0)
```

---

## Phase D — Low Priority (2–3 hours)

### D.1 Fix Dead `safe_minmax()` Redefinition (Analytics)

Analytics Cell 13 redefines `safe_minmax()` inline. Should import from `src/utils/math.py`.

---

### D.2 Fix BiLSTM Save Format (Modeling)

Cell 27 saves Keras model as `.h5` (legacy format). Use `.keras` format instead.

---

### D.3 Add MLflow Model Signatures (Analytics)

Log model signatures with `mlflow.models.ModelSignature` for proper inference-time validation.

---

### D.4 Fix `fig.show()` in EDA Cell 59

Replace with `write_html()`.

---

### D.5 Consolidate `to_list()` Definitions (FE)

Remove duplicate in Cell 19; keep single definition in Cell 13.

---

### D.6 Fix Inconsistent Naming

| Pattern | Current | Fix |
|---------|---------|-----|
| Split info | `split_info`, `split_source`, `split_indices` | Consolidate to `temporal_split` |
| Feature df | `df_features`, `df_merged`, `df_base` | Use `df_features` consistently |
| Baseline citation | `BASELINE_CITATION` overwritten 4 times | Use per-section constants |

---

### D.7 Remove Redundant MLB Reload (FE)

Cell 19 reloads `genre_list_mlb.joblib` from disk when it's already in memory from Cell 13.

---

### D.8 Add Verification Cells (Modeling + Analytics)

Both notebooks lack a final verification cell per AGENTS.md requirement.

---

## Phase E — Validation (2–3 hours)

### E.1 Full Pipeline Re-run

```bash
python scripts/run_pipeline.py --stage all
```

### E.2 Pytest Execution

```bash
cd data-science
pytest tests/ -v --tb=short
```

### E.3 Quality Gate Verification

| Gate | Metric | Threshold | Expected After Fixes |
|------|--------|-----------|---------------------|
| DS.1 | Temporal split integrity | No future leakage | ✅ PASS (unchanged) |
| DS.2 | Baseline comparison | Beat DummyClassifier | ⚠️ Depends on genre model |
| DS.3 | Rating RMSE | ≤ 0.55 | ✅ After A.1 fix |
| DS.4 | Genre macro_f1 | > 0.60 | ❌ Still failing (5% sample limitation) |
| DS.5 | MLflow metric naming | Regex compliant | ✅ PASS (unchanged) |
| DS.6 | SHAP explainability | Required | ✅ After B.8 |
| DS.7 | Ablation study | Required | ✅ After B.8 |
| DS.8 | Q-error profiling | P50 < 1.10 | ✅ After A.1 fix |
| DS.9 | Temporal generalization | Δ < 0.10 | ⚠️ Depends on model |
| DS.10 | Model artifacts exist | All present | ✅ After A.3 |
| DS.11 | Inference pipeline | Functional | ✅ After A.4 |
| DS.12 | Duke's aesthetic | Applied | ✅ PASS (unchanged) |

### E.4 Contract Validation

```bash
python scripts/validate_contracts.py
```

### E.5 Known Limitation

**DS.4 (Genre F1 > 0.60) will likely still fail** at 5% dev sample. This is a data limitation, not a code limitation. The 0.60 threshold requires the full dataset or at least 20% sample. Document this as a known limitation with recommendation to re-evaluate at full scale.

---

## Architecture Considerations

### Current: 4 Monolithic Notebooks

```
EDA (114 cells) → FE (22 cells) → Modeling (58 cells) → Analytics (22 cells)
```

### Recommended: Hybrid Approach (Phase 3 already created modules)

The Phase 3 `src/` package already provides modular Python code. The notebooks should become **thin orchestrators** that import from `src/`:

```python
# notebooks/02_feature_engineering.ipynb (thin wrapper)
import sys
sys.path.insert(0, '..')
from src.data.loader import GoldDataLoader
from src.features.builder import FeatureBuilder
from src.features.tabular import build_tabular_features
from src.features.text import compute_text_embeddings
from src.utils.verification import verify_artifacts

# Load config
from src.config import load_config
config = load_config()

# Execute pipeline
loader = GoldDataLoader(...)
con = loader.connect()
# ... call src functions ...
loader.close()
```

### Migration Priority

| Notebook | Migration Difficulty | Recommendation |
|----------|---------------------|----------------|
| EDA | Low (read-only analysis) | Keep as-is; it's a reporting notebook |
| FE | Medium (data pipeline) | Convert to thin wrapper calling `src/` |
| Modeling | High (complex training loops) | Convert to thin wrapper calling `src/` |
| Analytics | High (evaluation + registry) | Convert to thin wrapper calling `src/` |

**This migration is a separate initiative from the hotfixes above.** The hotfixes address the existing notebook code; the migration would replace notebook code with `src/` imports.

---

## Appendix: Issue Index by Notebook

### EDA Notebook

| # | Severity | Issue | Phase |
|---|----------|-------|-------|
| 1 | Medium | 5 bare `except:` clauses | C.4 |
| 2 | Medium | `fig.show()` in Cell 59 | D.4 |
| 3 | Medium | 2 `SELECT *` queries | C.2 |
| 4 | Low | 45 `plt.show()` instances | B.2 |
| 5 | Low | 27 `print()` instances | B.6 |
| 6 | Low | No `safe_query_to_df()` enforcement | C.5 (pattern) |

### FE Notebook

| # | Severity | Issue | Phase |
|---|----------|-------|-------|
| 1 | Critical | Rating leakage proxies (avg_genre_year_*) | A.1 |
| 2 | Critical | Feature dimension mismatch (796 vs 798) | A.2 |
| 3 | Critical | Missing `scaler.joblib` artifact | A.3 |
| 4 | High | `safe_minmax()` defined but never called | B.1 |
| 5 | High | Dead imports (matplotlib, seaborn) | C.2 |
| 6 | High | Duplicate `to_list()` definition | D.5 |
| 7 | Medium | Monolithic Cell 6 (~210 lines) | C.1 |
| 8 | Medium | DuckDB connection never closed | C.3 |
| 9 | Medium | Redundant preprocessor reload | D.7 |
| 10 | Medium | `genre_cnt` column missing from SQL | A.2 |
| 11 | Medium | Sharded embeddings not handled in verification | C.5 |
| 12 | Low | No type hints | B.10 |
| 13 | Low | Dead SQL columns (archive_footage_count) | C.2 |

### Modeling Notebook

| # | Severity | Issue | Phase |
|---|----------|-------|-------|
| 1 | High | Variable shadowing (X_train overwritten 4×) | B.3 |
| 2 | High | 9 MLflow experiments (should be 3) | B.4 |
| 3 | High | Missing `exists()` guards | B.5 |
| 4 | High | BiLSTM GloVe fallback to random embeddings | B.7 |
| 5 | Medium | Bare `except:` in Cell 50 | C.4 |
| 6 | Medium | No zero-division guards on F1/precision/recall | C.9 |
| 7 | Low | Unused imports (surprise_train_test_split) | C.2 |
| 8 | Low | `globals()` fallback for GMU output_dim | D.8 |
| 9 | Low | Dead code path (Cell 35 Ellipsis) | C.2 |

### Analytics Notebook

| # | Severity | Issue | Phase |
|---|----------|-------|-------|
| 1 | Critical | Broken inference (zero text embeddings) | A.4 |
| 2 | Critical | Model promotion without quality gates | A.5 |
| 3 | High | Cold-start evaluation (2 users) | A.6 |
| 4 | High | SHAP + ablation missing (DS.6, DS.7) | B.8 |
| 5 | High | Schema mismatch (tconst vs title_id) | B.9 |
| 6 | High | Rating model not registered in MLflow | B.11 |
| 7 | Medium | SAMPLE_PERCENT = 1 (should be 5) | C.8 |
| 8 | Medium | Monolithic Cell 20 (~210 lines) | C.1 |
| 9 | Medium | DuckDB connection never closed | C.3 |
| 10 | Medium | Bare `except:` in Cell 5 | C.4 |
| 11 | Low | 15+ unused imports | C.2 |
| 12 | Low | CUDA seed not set | C.7 |

---

*Plan generated from deep audit of all 4 Phase 2 notebooks against AGENTS.md, 4 skill SKILL.md files, and both contracts. All findings traceable to specific cells and line numbers.*
