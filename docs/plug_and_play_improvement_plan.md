# Elyssa Plug-and-Play Experience Improvement — Codename: Elyssa

**Date:** 2026-07-22  
**Status:** Planning / Roadmap  
**Scope:** Cross-module QA alignment, revamped sequential execution architecture, unified README hierarchy, QA catalog template.

---

## Table of Contents

1. [Cross-Module QA Alignment](#1-cross-module-qa-alignment)
2. [Revamped Execution Architecture](#2-revamped-execution-architecture)
3. [Unified README Hierarchy](#3-unified-readme-hierarchy)
4. [QA Catalog Structure](#4-qa-catalog-structure)

---

## 1. Cross-Module QA Alignment

### 1.1 Module Deliverable Inventory

| Module | Location | Key Deliverables | Weight (Proposal) |
|--------|----------|-----------------|-------------------|
| Data Engineering (DE) | `data-engineering/` | Bronze→Silver→Gold pipeline, Airflow DAG, dbt marts, 6 Parquet exports to `data-science/marts/` | 50% |
| Data Science (DS) | `data-science/` | 4 notebooks (EDA, FE, Modeling, Analytics), MLflow models (GMU genre, CatBoost rating), inference artifacts, `ds-to-web.md` contract | 20% |
| Web Application (Web) | `web-application/` | FastAPI+GraphQL API, React SPA, auth, watchlist, model inference serving | 10% |
| MLOps | `mlops/` | Docker Compose, monitoring (Prometheus/Grafana), retraining DAGs, runbooks, Terraform | 10% (embedded) |

### 1.2 Contract Consistency Check

#### Flow: DE → DS (gold-to-ds.md)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| 6 Gold Parquet exports delivered | ✅ | `data-science/marts/full/` has all 6 files |
| Snappy compression | ✅ | Defined in contract §Format |
| Consistent column names | ✅ | Schemas match between gold_schema.md and gold-to-ds.md |
| `genre_list` as comma-separated, trimmed | ✅ | `dim_title.genre_list` is `STRING_AGG` in dbt |
| `runtime_minutes > 0` for movies | ⚠️ **Gap** | Only a `warn` dbt test — no hard filter in Parquet export |
| `average_rating` 1.0–10.0 | ✅ | dbt `accepted_range` test error-severity passes |
| Temporal split constants identical | ✅ | Single source in `gold-to-ds.md` |
| Development sampling via TABLESAMPLE 5% | ✅ | Documented in contract |

**Gap G1:** `runtime_minutes > 0` for movies is **not enforced** at export time — only warned in dbt. Movies with null/zero runtime flow into DS notebooks, causing division-by-zero or silent skips downstream.

**Severity:** MEDIUM  
**Fix:** Add a DuckDB filter to the Parquet export script (`data-engineering/scripts/gold_export.py`):
```python
# data-engineering/scripts/gold_export.py
import duckdb

con = duckdb.connect()
con.execute("""
  COPY (
    SELECT * FROM dim_title
    WHERE NOT (title_type = 'movie' AND (runtime_minutes IS NULL OR runtime_minutes <= 0))
  ) TO 'dim_title.parquet' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")
```

---

#### Flow: DE → Web (gold-to-api.md)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| 6 Gold marts available for API | ✅ | Loaded via DuckDB in `web-application/api/app/graphql/` |
| Schema stability | ✅ | Contracts frozen, column mapping defined |
| `genre_list` as `genres` array | ⚠️ **Inconsistency** | Gold stores as comma-separated TEXT; API expects array |
| Parquet location | ⚠️ **Gap** | API reads from `data-science/marts/processed/` — but DE exports to `data-science/marts/full/` |

**Gap G2:** Path mismatch. DE writes to `marts/full/` and `marts/dev/` (sampled). Web application reads from `marts/processed/`. These are **not the same directory**. A user who runs only DE + Web will hit missing file errors.

**Severity:** HIGH  
**Fix:** Standardise export paths. Add an explicit symlink or config-based path resolution:

```yaml
# data-science/config/settings.yaml
marts:
  full: "marts/full/"
  dev: "marts/dev/"
  processed: "marts/processed/"   # DS writes processed artifacts here
```

Root `docker-compose.yml:186` already maps `./data-science/marts/processed:/data/marts/processed:ro`. Update DE export scripts to write to `marts/processed/` as well, or change the compose volume mount to `./data-science/marts/` and resolve subdirectories at the app level.

---

#### Flow: DS → Web (ds-to-web.md)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| MLflow registered models | ⚠️ **Gap** | MLflow server not in root `docker-compose.yml`; only in `mlops/docker-compose.yml` |
| Inference artifacts in `processed/` | ✅ | Listed in contract with paths |
| `feature_columns.json` | ✅ | Required artifact |
| RMSE <= 0.55 | ✅ | Enforced by `src/evaluation/gates.py` |
| Macro F1 > 0.60 | ✅ | Enforced by `src/evaluation/gates.py` |

**Gap G3:** MLflow server is **not part of the root Docker Compose** (`docker-compose.yml`). A user starting from the root README will have no MLflow endpoint. The Web Application's `ModelService` expects MLflow at `http://localhost:5000`, but that container only exists under `mlops/docker-compose.yml`.

**Severity:** HIGH  
**Fix:** Either:
- (a) Add MLflow to root `docker-compose.yml` as a standard service, or
- (b) Have `ModelService` fall back to local artifact loading (read `.pt`, `.cbm`, `feature_columns.json` from disk) without MLflow.
   ```python
   # web-application/api/app/models/inference.py
   class ModelService:
       def __init__(self, artifacts_path: str = "/data/marts/processed"):
           self.artifacts_path = artifacts_path
           self.models = {}
           self._load_local()

       def _load_local(self):
           import torch, catboost, json, joblib
           self.feature_schema = json.load(open(f"{self.artifacts_path}/feature_columns.json"))
           self.gmu = torch.load(f"{self.artifacts_path}/gmu_genre_best.pt", map_location="cpu")
           self.catboost = catboost.CatBoostRegressor()
           self.catboost.load_model(f"{self.artifacts_path}/catboost_rating_model.cbm")
   ```

---

#### Flow: Web API → Frontend (api-to-frontend.md)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| REST endpoints for titles | ✅ | `GET /api/v1/titles`, `/titles/{id}` |
| REST endpoints for persons | ✅ | `GET /api/v1/persons/{id}`, `/persons/{id}/credits` |
| POST /predict/genre and /predict/rating | ✅ | Endpoints exist |
| GraphQL homepage, titleDetail, personDetail | ✅ | Resolvers exist |
| JWT auth (register, login, refresh) | ✅ | Auth routes implemented |
| Error format `{ error: { code, message, details } }` | ⚠️ **Gap** | Only some endpoints return this format; check test coverage |
| Rate limiting (200/min, 429 response) | ⚠️ **Gap** | Rate limiter exists in `cache/` but is it wired to all endpoints? |

**Gap G4:** Rate limiting and standardised error format not verified across **all** endpoints. The contract declares these but the Web Application README `< 4.0` test coverage may not cover integration-level contract validation.

---

#### DS Internal: Pipeline Orchestration Broken

| Requirement | Status | Evidence |
|-------------|--------|----------|
| `scripts/run_pipeline.py` executes 4 stages (EDA, FE, Modeling, Analytics) | ❌ **All stubs** | Each stage function contains only `logger.info()` + connection setup — no actual pipeline logic |
| `src/config.py` wired into pipeline | ❌ **Not used** | Config loaded but never passed to any stage |
| User can run `python scripts/run_pipeline.py --stage all` | ❌ **No-op** | Script exits with "success" after logging 4 messages. Zero work done. |

**Gap G10:** The DS `run_pipeline.py` is the entry point advertised in `README.md`, but all 4 stage functions are empty stubs. A user following the DS README gets a false sense of completion. The actual pipeline logic lives inside the 4 notebooks (`phase_2_duke_manual_*.ipynb`), which must be run manually.

**Severity:** HIGH  
**Fix:** Implement proper stage execution. Each stage should either:
- (a) Execute the corresponding notebook via `papermill` or `nbconvert`, or
- (b) Call the underlying `src/` module functions directly.

```python
# Option (a): Papermill-based execution
import papermill as pm

def run_stage_eda(config: dict):
    pm.execute_notebook(
        "notebooks/phase_2_duke_manual_eda.ipynb",
        "notebooks/executed/phase_2_duke_manual_eda.ipynb",
        parameters=dict(CONFIG_PATH=config["path"])
    )

# Option (b): Direct module call (preferred — avoids notebook dependency)
from src.data.loader import GoldDataLoader
from src.features.builder import FeatureBuilder
def run_stage_features(config: dict):
    loader = GoldDataLoader(marts_dir=config["paths"]["marts_dir"])
    builder = FeatureBuilder(loader)
    builder.build_all(output_dir=config["paths"]["processed_dir"])
```

The recommended approach is (b) — extract core logic from notebooks into `src/` modules and call them from the pipeline script. This makes the pipeline script the single entry point and relegates notebooks to exploratory/visualization only.

---

#### DS Internal: Inference Pipeline Produces Garbage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Text embedding uses DistilBERT for 768-dim feature vector | ❌ **Zero tensor** | `src/inference/pipeline.py:85` uses `torch.zeros(1, 768)` instead of actual embeddings |
| Preprocessor pipeline applied to input features | ❌ **Ignored** | `build_feature_vector()` manually constructs tabular vectors, bypassing the fitted `ColumnTransformer` in `preprocessor.joblib` |
| Inference matches training pipeline | ❌ **Different paths** | Training uses `src/features/tabular.py` preprocessor; inference uses ad-hoc vector construction |

**Gap G11:** The inference pipeline in `src/inference/pipeline.py` has two critical flaws:
1. `predict_genre()` and `predict_rating()` both substitute `torch.zeros(1, num_text_features=768)` for the actual DistilBERT text embedding. All predictions receive a zero vector instead of real text features.
2. `build_feature_vector()` manually constructs the tabular vector with a for-loop over `feature_columns.json` instead of using the fitted `ColumnTransformer` that was saved as `preprocessor.joblib`. This means one-hot encoding, scaling, and any fitted transformations from training are **not applied** during inference.

**Severity:** HIGH (any prediction made via the Web API is based on incorrect feature vectors)  
**Fix:**

```python
# src/inference/pipeline.py — fixed predict functions
import json
import torch
import numpy as np
from joblib import load

class ModelService:
    def __init__(self, artifacts_path: str = "/data/marts/processed"):
        self.artifacts_path = artifacts_path
        self.feature_schema = json.load(open(f"{artifacts_path}/feature_columns.json"))
        self.preprocessor = load(f"{artifacts_path}/preprocessor.joblib")
        self.scaler = load(f"{artifacts_path}/scaler.joblib")
        self.gmu = torch.load(f"{artifacts_path}/gmu_genre_best.pt", map_location="cpu")
        self.catboost = CatBoostRegressor()
        self.catboost.load_model(f"{artifacts_path}/catboost_rating_model.cbm")

    def _get_text_embedding(self, title_text: str) -> np.ndarray:
        """Generate 768-dim DistilBERT embedding for input text."""
        from transformers import DistilBertTokenizer, DistilBertModel
        tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
        model = DistilBertModel.from_pretrained("distilbert-base-uncased")
        inputs = tokenizer(title_text, return_tensors="pt", truncation=True, max_length=128, padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
        return outputs.last_hidden_state.mean(dim=1).squeeze().numpy()

    def predict_genre(self, raw_input: dict, title_text: str = "") -> dict:
        tab_cols = self.feature_schema["tabular_features"]
        # Build raw DataFrame for preprocessor
        import pandas as pd
        row = {}
        for col in tab_cols:
            val = raw_input.get(col, 0)
            if col.startswith("title_type_"):
                val = 1.0 if raw_input.get("title_type", "") == col.split("_", 2)[-1] else 0.0
            row[col] = val
        df = pd.DataFrame([row])
        # Apply fitted preprocessor + scaler
        tab_features = self.scaler.transform(self.preprocessor.transform(df))
        # Get text embedding
        text_emb = self._get_text_embedding(title_text)
        # Combine
        feature_vector = np.concatenate([tab_features[0], text_emb])
        # Run through GMU model...
        # ...
```

---

#### DS Internal: Runtime Bug in Evaluation Module

| Requirement | Status | Evidence |
|-------------|--------|----------|
| `sample_efficiency_curve()` in `src/evaluation/temporal.py` | ❌ **NameError** | Calls `mean_squared_error()` without importing it from sklearn |

**Gap G12:** Line 41 of `src/evaluation/temporal.py` calls `mean_squared_error(y_true, y_pred)` but `from sklearn.metrics import mean_squared_error` is never added to the imports. This will crash at runtime if `sample_efficiency_curve()` is called.

**Severity:** HIGH (blocks analytics evaluation)  
**Fix:**

```python
# src/evaluation/temporal.py — line 3
from sklearn.metrics import mean_squared_error
```

---

#### Flow: DE → Parquet Export (Gold Export — Missing Automation)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Automated export of 6 Gold marts to Parquet | ❌ **Missing** | DAG ends at `freshness_check >> end` — no export task exists (see `imdb_pipeline_dag.py:203`) |
| Export script exists | ✅ | `data-engineering/scripts/export_marts.py` |
| Script writes to correct target path | ❌ **Wrong path** | Hardcoded to `/opt/airflow/data-engineering/scripts/` (inside container) instead of `data-science/marts/full/` |
| Script handles credentials securely | ❌ **Hardcoded password** | `elyssa_pg_2026` in plain text in `export_marts.py` |
| Export exposed via Makefile | ❌ **Missing** | No `make export` target |
| DS-side export script | ✅ | `data-science/scripts/export_marts.py` (reads from local DuckDB, not PostgreSQL) |

**Gap G9:** The Gold → Parquet export is **entirely manual**. After the 5.5-hour pipeline finishes, a human must `docker exec` into the container and run `export_marts.py` — which writes to the **wrong directory** with hardcoded credentials.

**Severity:** HIGH  
**Fix — three-part:**

**(a) Add `gold_export` task to Airflow DAG** after `freshness_check`:

```python
# data-engineering/orchestration/operators/gold_export_operator.py
import duckdb
from airflow.models import BaseOperator
from pathlib import Path

class GoldExportOperator(BaseOperator):
    def __init__(self, pg_host="postgres", pg_port=5432, pg_db="elyssa_warehouse",
                 pg_user="elyssa", pg_password="elyssa_pg_2026",
                 output_dir="/opt/airflow/output/gold/",
                 **kwargs):
        super().__init__(**kwargs)
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_db = pg_db
        self.pg_user = pg_user
        self.pg_password = pg_password
        self.output_dir = output_dir

    def execute(self, context):
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(':memory:')
        conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
        dsn = f"host={self.pg_host} port={self.pg_port} dbname={self.pg_db} user={self.pg_user} password={self.pg_password}"
        conn.execute(f"ATTACH '{dsn}' AS pg (TYPE POSTGRES, SCHEMA 'gold_gold');")
        tables = ['dim_person','dim_title','fact_episode','fact_performance','fact_title_principal','fact_title_rating']
        for t in tables:
            path = Path(self.output_dir) / f"{t}.parquet"
            conn.execute(f'COPY (SELECT * FROM pg.gold_gold."{t}") TO \'{path}\' (FORMAT PARQUET, COMPRESSION SNAPPY)')
            r = conn.execute(f'SELECT count(*) FROM pg.gold_gold."{t}"').fetchone()[0]
            self.log.info(f"Exported {t}: {r:,} rows -> {path}")
        conn.close()
```

Add to DAG (`imdb_pipeline_dag.py:194`):
```python
from operators.gold_export_operator import GoldExportOperator

gold_export = GoldExportOperator(
    task_id="gold_export",
    output_dir="/opt/airflow/output/gold/",
)

# Replace the old terminal edge:
# gold_dbt_test >> dq_checks >> freshness_check >> end
# With:
gold_dbt_test >> dq_checks >> freshness_check >> gold_export >> end
```

**(b) Symlink inside container so host can access exports:**

The Docker Compose already mounts `./data-engineering:/opt/airflow/data-engineering:rw`. Add a second mount for exports:

```yaml
# docker-compose.yml — airflow volumes section
volumes:
  - ./data-science/marts:/opt/airflow/output/gold:rw   # NEW
```

Or, simpler: write exports directly to `data-engineering/` so they appear on the host:
```python
# In gold_export_operator.py
output_dir = "/opt/airflow/data-engineering/scripts/exports/"
```
Then add a Makefile target that copies them to `data-science/marts/full/`:
```makefile
.PHONY: export
export:
	docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/export_marts.py
	robocopy data-engineering/scripts/exports/ data-science/marts/full/ *.parquet /MOVE
```

**Best approach:** Write directly to `/opt/airflow/output/gold/` (dedicated volume mount target) and mount `./data-science/marts/full/` to that path in docker-compose. This way exports appear immediately in the DS-expected location:

```yaml
# docker-compose.yml — airflow service
volumes:
  - ./data-science/marts/full:/opt/airflow/output/gold:rw
```

**(c) Remove hardcoded credentials** — read from environment variable `POSTGRES_PASSWORD` or Airflow connection:
```python
import os
pg_password = os.environ.get("GOLD_EXPORT_PG_PASSWORD", "")
# Or use Airflow's Connection.get_connection_from_secrets(...)
```

**Severity:** MEDIUM  
**Fix:** Add contract conformance tests:
```python
# web-application/api/tests/test_contract.py
def test_error_format_on_404():
    response = client.get("/api/v1/titles/nonexistent")
    assert response.status_code == 404
    assert "error" in response.json()
    assert "code" in response.json()["error"]
    assert "message" in response.json()["error"]
```

---

### 1.3 Integration Gaps Summary

| ID | Gap | Modules | Severity | Suggested Hotfix |
|----|-----|---------|----------|-----------------|
| **G1** | `runtime_minutes > 0` not enforced on movie export | DE → DS | MEDIUM | Add WHERE filter to gold_export.py |
| **G2** | Path mismatch: `marts/full/` vs `marts/processed/` | DE → Web | **HIGH** | Standardise paths; update compose volume mount |
| **G3** | MLflow server absent from root docker-compose | DS → Web | **HIGH** | Add MLflow to root compose OR implement disk-based fallback |
| **G4** | Rate limiting / error format not verified across all endpoints | Web internal | MEDIUM | Add contract conformance tests |
| **G5** | No pre-packaged sample dataset | All | **HIGH** | See §2.4 Pre-packaged Artifacts |
| **G6** | No single-command "full pipeline" script | All | MEDIUM | See §2.2 Execute Script |
| **G7** | DE `README.md` missing entirely | DE | LOW | Create `data-engineering/README.md` |
| **G8** | DS `README.md` references wrong contract name (`ds-to-swe.md` not `ds-to-web.md`) | DS | LOW | Update reference in DS README |
| **G9** | Gold→Parquet export not automated; wrong output path; hardcoded credentials | DE → DS/Web | **HIGH** | Add `gold_export` DAG task; fix path to `marts/full/`; credentials via env var; add `Makefile` target |
| **G10** | DS `run_pipeline.py` — all 4 stage functions are stubs (only `logger.info()`), pipeline does nothing | DS internal | **HIGH** | Implement actual stage logic or wire notebook execution; stub causes false-positive "success" |
| **G11** | DS inference pipeline uses `torch.zeros()` as text embedding instead of real DistilBERT; ignores fitted preprocessor | DS → Web | **HIGH** | Replace zero-tensor with actual text embedding call; apply `ColumnTransformer` from `preprocessor.joblib` |
| **G12** | `src/evaluation/temporal.py:41` uses `mean_squared_error` without importing it — `NameError` at runtime | DS internal | **HIGH** | Add `from sklearn.metrics import mean_squared_error` to `temporal.py` |
| **G13** | DE has dual parallel code paths: PySpark scripts (bronze/ingest_imdb.py, silver/transform.py) vs DuckDB Airflow operators — will diverge | DE internal | MEDIUM | Remove PySpark path or align with DuckDB; document which is canonical |
| **G14** | DE DQ checks defined in two places that diverge: `dq/config.yaml` vs `dq/run_checks.py` embedded defaults | DE internal | MEDIUM | Consolidate into single source of truth (`config.yaml`); load from file in runner |
| **G15** | No CI/CD workflows — `.github/` is empty | All | MEDIUM | Create GitHub Actions workflows for lint, test, build per module |
| **G16** | Hardcoded credentials `elyssa_pg_2026` in docker-compose.yml, all scripts, configs, docs — no `.env` usage anywhere | All | MEDIUM | Migrate to `.env` file; reference via `${POSTGRES_PASSWORD}` in compose; never hardcode |
| **G17** | DS runtime artifacts committed to Git: `imdb_gold.db`, `mlflow.db`, `catboost_info/`, `mlruns/` | DS | LOW | Add `data-science/.gitignore`; remove tracked artifacts from Git history |

### 1.4 Missing Integration Points

1. **Gold refresh → Web hot-reload**: When DE re-exports Parquet, the Web API (DuckDB in-memory) is not notified. The API must be restarted or have a `/admin/reload` endpoint. Currently **no mechanism** exists.
   - **Severity:** LOW (acceptable for dev; prod needs a reload hook)
   - **Fix:** Add `POST /admin/reload-cache` endpoint or poll file mtime.

2. **DS artifact versioning → Web consumption**: DS writes model files to `processed/` in-place. If the user runs DS twice, old model files are overwritten. The Web API loads them once at startup. No version pinning.
   - **Severity:** MEDIUM
   - **Fix:** Add version suffixes or subdirectories (`processed/v1/`, `processed/v2/`) and have Web load the latest via symlink.

3. **Airflow DAG completion → DS notebook trigger**: After Airflow finishes the DE pipeline, there is no automated trigger to start DS notebooks. User must manually run `python scripts/run_pipeline.py --stage all`.
   - **Severity:** LOW (acceptable for sequential execution plan — see §2)
   - **Fix:** Add a `Makefile` target that chains the three phases.

4. **Export script not wired into any automation path**: `data-engineering/scripts/export_marts.py` exists but is orphaned — not called by Airflow, not exposed by Makefile, not scheduled. The hardcoded output path `/opt/airflow/data-engineering/scripts/` conflicts with where DS and Web expect the Parquet files (`data-science/marts/full/`).
   - **Severity:** HIGH (blocks DE→DS handoff after pipeline completion)
   - **Fix:** Add `gold_export` DAG task (see G9 fix above); add `make export` target; fix output path to `data-science/marts/full/`.

5. **DS `run_pipeline.py` is a no-op**: The DS pipeline entry point (`python scripts/run_pipeline.py --stage all`) does nothing. New users who follow the DS README will believe the pipeline ran successfully but get zero outputs.
   - **Severity:** HIGH (complete failure of the advertised user workflow)
   - **Fix:** Implement actual stage logic (see G10 fix) — call `src/` modules directly or execute notebooks via papermill.

6. **DS inference produces garbage predictions**: `src/inference/pipeline.py` uses `torch.zeros()` for text embeddings and bypasses the fitted preprocessor. Web API predictions are based on incorrect feature vectors.
   - **Severity:** HIGH (all ML predictions served by the Web API are invalid)
   - **Fix:** Integrate real DistilBERT embedding call; apply `preprocessor.joblib` `ColumnTransformer` (see G11 fix).

7. **PySpark vs DuckDB dual code paths**: `bronze/ingest_imdb.py` and `silver/transform.py`/`upsert.py`/`scd2_transform.py` are PySpark-based. The Airflow operators (`bronze_operator.py`, `silver_operator.py`) are DuckDB-based. Two parallel implementations that will diverge.
   - **Severity:** MEDIUM (maintainers confused; changes must be made in two places)
   - **Fix:** Remove PySpark scripts and document DuckDB as canonical path; OR remove DuckDB operators and use PySpark as canonical. Add a comment in each non-canonical file pointing to the canonical file.

8. **Duplicate DQ check definitions**: `dq/config.yaml` defines 6 checks with thresholds. `dq/run_checks.py` has its own `DEFAULT_CHECKS` list (same structure but potentially different values). If a user edits `config.yaml`, the change may not take effect.
   - **Severity:** MEDIUM (silent inconsistency in quality checks)
   - **Fix:** Remove embedded defaults from `run_checks.py`; always load from `config.yaml`.

9. **No CI/CD workflows**: `.github/` directory is empty. No automated linting, testing, or building.
   - **Severity:** MEDIUM (no guardrails against regressions)
   - **Fix:** Create `.github/workflows/ci.yml` with lint + test + build across all modules. Reference the patterns described in `mlops/docs/implementation-plan.md` §2.1.

10. **Hardcoded credentials everywhere**: `elyssa_pg_2026`, `elyssa_s3_2026`, `elyssa_neo_2026` hardcoded in `docker-compose.yml`, all scripts, config files, and documentation. No `.env` file in use (only `docker/.env.example` exists).
    - **Severity:** MEDIUM (security risk if committed to public repo; tedious to change passwords)
    - **Fix:** Create `.env` file with all secrets; reference as `${POSTGRES_PASSWORD}` in compose; update scripts to read from `os.environ` with `.env` fallback.

11. **No batch_id or manifest tracking for exports**: The export script dumps Parquet files without a manifest file or batch_id marker. DS/Web have no way to know which export generation they are consuming.
   - **Severity:** LOW
   - **Fix:** Write a `_MANIFEST.json` alongside the Parquet files:
     ```json
     {
       "batch_id": "20260722_153000",
       "exported_at": "2026-07-22T15:30:00Z",
       "tables": ["dim_title", "dim_person", "fact_episode", "fact_performance", "fact_title_principal", "fact_title_rating"],
       "row_counts": { "dim_title": 12609928, "dim_person": 15448149, ... }
     }
     ```

---

## 2. Revamped Execution Architecture

### 2.1 Hardware Constraints Acknowledged

| Resource | Value | Impact |
|----------|-------|--------|
| CPU | AMD Athlon 200GE (2 cores, 4 threads) | No parallel pipeline stages; containers compete for cores |
| RAM | 16 GB | Docker Desktop overhead (~3 GB) leaves ~13 GB for workloads; PostgreSQL wants 2 GB shm |
| GPU | None | PyTorch runs CPU-only; CatBoost benefits (CPU-native) |
| Disk | ~20 GB free | Full IMDb TSVs (~10 GB) + Parquet (~5 GB) + Docker images (~6 GB) |

**Design principle:** Everything runs **sequentially**, not concurrently. Pipeline stages are separated by checkpoints so the user can pause and resume.

### 2.2 Sequential Pipeline Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 0: Smoke Test (30 min)                                                 │
│   Pre-packaged sample dataset → quick all-module validation                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ PHASE 1: Data Engineering — Full Ingestion (~5.5-6 hours)                    │
│   ├── Docker up & source download (30 min)                                   │
│   ├── Bronze ingestion (47 min)                                              │
│   ├── Silver ETL (3h 39min)                                                  │
│   ├── Gold dbt run + test (70 min)                                           │
│   ├── Gold export (15 min) ← NEW automated DAG task                          │
│   │   └── DuckDB postgres_scanner → 6 Snappy Parquet files                   │
│   │   └── Writes to /opt/airflow/output/gold/ (mounted to marts/full/)       │
│   │   └── Writes _MANIFEST.json with batch_id + row counts                   │
│   CHECKPOINT: data-science/marts/full/*.parquet (+ _MANIFEST.json)           │
├─────────────────────────────────────────────────────────────────────────────┤
│ PHASE 2: Data Science — ML Pipeline (~3-4 hours)                             │
│   ├── EDA notebook (30 min)                                                  │
│   ├── Feature engineering (45 min)                                           │
│   ├── Modeling — GMU + CatBoost (90 min)                                     │
│   ├── Analytics & verification (30 min)                                      │
│   └── Artifact export to marts/processed/ (5 min)                            │
│   CHECKPOINT: data-science/marts/processed/*.{pt,cbm,json,joblib,npy,parquet}│
├─────────────────────────────────────────────────────────────────────────────┤
│ PHASE 3: Web Application — Start & Verify (~15 min)                          │
│   ├── Start API server                                                        │
│   ├── Start React dev server                                                  │
│   ├── Run contract conformance tests                                         │
│   └── Open browser → verify homepage, search, predictions                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ PHASE 4: MLOps — Optional Infrastructure (~30 min)                           │
│   ├── Start MLflow, Prometheus, Grafana                                       │
│   ├── Verify model registry                                                    │
│   └── Verify monitoring dashboards                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Multi-Day Runbook

**Day 1 — Data Engineering (5-6 hours)**

```powershell
# === PHASE 1: DE Pipeline ===
# Step 1: Docker infrastructure
Write-Host "=== Step 1: Docker up ===" -ForegroundColor Cyan
docker builder prune -f
docker compose up -d --build
docker compose ps
# Verify: all 5 containers healthy (postgres, neo4j, rustfs, airflow, duckdb)

# Step 2: Download source data (if not already downloaded)
Write-Host "=== Step 2: Download IMDb data ===" -ForegroundColor Cyan
$files = @("title.basics","title.akas","title.ratings","title.episode","title.crew","title.principals","name.basics")
$dest = "data-engineering/duke/gate0/source"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
foreach ($f in $files) {
    $url = "https://datasets.imdbws.com/$f.tsv.gz"
    $out = "$dest/$f.tsv.gz"
    if (-not (Test-Path $out)) {
        Write-Host "Downloading $f ..."
        Invoke-WebRequest -Uri $url -OutFile $out
    }
}

# Step 3: Unpause & trigger Airflow DAG
Write-Host "=== Step 3: Trigger DE pipeline ===" -ForegroundColor Cyan
$pw = docker exec elyssa-airflow python3 -c "import json; d=json.load(open('/opt/airflow/simple_auth_manager_passwords.json.generated')); print(list(d.values())[0])"
docker exec elyssa-airflow airflow dags unpause imdb_pipeline -y
docker exec elyssa-airflow airflow dags trigger imdb_pipeline

# Monitor progress
Write-Host "Monitoring (this takes ~5-6 hours total)..." -ForegroundColor Yellow
Write-Host "  Watch: docker compose logs -f airflow"
Write-Host "  Check: docker exec elyssa-airflow airflow dags list-runs imdb_pipeline"

# === PAUSE POINT ===
# After all DAG tasks complete (including the new gold_export task), verify output:
Write-Host "=== Step 4: Verify DE output ===" -ForegroundColor Cyan

# 4a: Check Gold tables in PostgreSQL
docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "SELECT table_name, n_live_tup FROM pg_stat_user_tables WHERE schemaname='gold' ORDER BY table_name;"
# Expect: dim_title ~12.6M, dim_person ~15.4M, fact_title_principal ~100M, etc.

# 4b: Verify Parquet exports landed in the correct directory
Write-Host "=== Step 4b: Verify Parquet exports ===" -ForegroundColor Cyan
Get-ChildItem data-science/marts/full/*.parquet | Select-Object Name, Length
# Expect: 6 .parquet files + _MANIFEST.json
# dim_title.parquet (~642 MB), dim_person.parquet (~688 MB),
# fact_title_principal.parquet (~1.88 GB), fact_performance.parquet (~1.88 GB),
# fact_episode.parquet (~108 MB), fact_title_rating.parquet (~15.5 MB)

# 4c: Check manifest
Write-Host "=== Step 4c: Export manifest ===" -ForegroundColor Cyan
Get-Content data-science/marts/full/_MANIFEST.json | python -c "import sys,json; m=json.load(sys.stdin); print(f'Batch: {m[\"batch_id\"]}'); [print(f'  {t}: {r:,} rows') for t,r in m['row_counts'].items()]"

# 4d: If the gold_export task did not run (e.g. older pipeline), export manually:
Write-Host "  Alternative: manual export via Makefile target" -ForegroundColor Yellow
Write-Host "  make export"
# This runs: docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/export_marts.py
```

**Day 2 — Data Science (3-4 hours)**

```powershell
# === PHASE 2: DS Pipeline ===
# Prerequisite: Phase 1 completed, Parquet files in data-science/marts/full/

Write-Host "=== Phase 2: Data Science Pipeline ===" -ForegroundColor Cyan
cd data-science

# Activate venv (create if not exists)
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt --quiet

# Step 1: Run full DS pipeline
Write-Host "=== Step 1: Run full ML pipeline ===" -ForegroundColor Cyan
python scripts/run_pipeline.py --stage all

# Step 2: Validate contracts
Write-Host "=== Step 2: Validate DS→Web contract ===" -ForegroundColor Cyan
python scripts/validate_contracts.py

# Step 3: Generate model cards
Write-Host "=== Step 3: Generate model cards ===" -ForegroundColor Cyan
python scripts/generate_model_cards.py

# === PAUSE POINT ===
Write-Host "=== Verify artifacts ===" -ForegroundColor Cyan
Get-ChildItem marts/processed/ -Name
# Expect: feature_columns.json, gmu_genre_best.pt, catboost_rating_model.cbm,
#         preprocessor.joblib, scaler.joblib, genre_list_mlb.joblib, model_inventory.json, ...
```

**Day 3 — Web Application (15 min)**

```powershell
# === PHASE 3: Web Application ===
# Prerequisite: Phase 2 completed, artifacts in marts/processed/

Write-Host "=== Phase 3: Web Application ===" -ForegroundColor Cyan

# Step 1: Start API backend
cd web-application/api
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt --quiet

# Start API in background
Start-Process powershell -ArgumentList "-NoExit -Command .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000"

# Step 2: Start Frontend
cd ../client
npm install --silent
Start-Process powershell -ArgumentList "-NoExit -Command npm run dev"

# Step 3: Verify health
Start-Sleep -Seconds 5
curl http://localhost:8000/health
curl http://localhost:5173

# Step 4: Run API tests
cd ../api
python -m pytest tests/ -q

# Step 5: Open browser
Start-Process "http://localhost:5173"
```

### 2.4 Pre-Packaged Artifacts for Smoke Tests

To enable a **30-minute smoke test** without downloading the full IMDb dataset, the repository should ship pre-packaged sample data:

```
data-science/
├── marts/
│   ├── sample/                         ← NEW: pre-packaged sample for smoke test
│   │   ├── dim_title.parquet           (50K rows)
│   │   ├── dim_person.parquet          (50K rows)
│   │   ├── fact_title_principal.parquet (100K rows)
│   │   ├── fact_performance.parquet    (100K rows)
│   │   ├── fact_episode.parquet        (50K rows)
│   │   └── fact_title_rating.parquet   (50K rows)
│   ├── sample_processed/               ← NEW: pre-trained models for sample
│   │   ├── feature_columns.json
│   │   ├── gmu_genre_best.pt
│   │   ├── catboost_rating_model.cbm
│   │   ├── preprocessor.joblib
│   │   ├── scaler.joblib
│   │   ├── genre_list_mlb.joblib
│   │   └── model_inventory.json
│   ├── full/                           (generated by DE pipeline)
│   └── processed/                      (generated by DS pipeline)
```

**Generation script** (`scripts/generate_sample_data.py`):
```python
"""Generate sample Parquet + pre-trained models for smoke testing."""
import duckdb
import torch
import catboost
import numpy as np
import pandas as pd
from pathlib import Path
from joblib import dump

SAMPLE_DIR = Path("marts/sample")
SAMPLE_PROCESSED_DIR = Path("marts/sample_processed")
SAMPLE_SIZE = 50_000

def extract_sample(source_dir: Path):
    con = duckdb.connect()
    for mart in ["dim_title", "dim_person", "fact_title_principal",
                  "fact_performance", "fact_episode", "fact_title_rating"]:
        src = source_dir / f"{mart}.parquet"
        if src.exists():
            con.execute(f"""
                COPY (
                  SELECT * FROM '{src}'
                  USING SAMPLE {SAMPLE_SIZE} ROWS
                ) TO '{SAMPLE_DIR / src.name}' (FORMAT PARQUET, COMPRESSION SNAPPY)
            """)
            print(f"  ✓ {mart}: {SAMPLE_SIZE} rows")
```

**Smoke test runbook** (`SMOKE_TEST.md`):
```markdown
# Quick Smoke Test (30 minutes)

Verify the entire Elyssa stack works end-to-end without downloading IMDb.

## Prerequisites
- Docker Desktop
- Python 3.12+
- Node.js 20+

## Steps

```powershell
# 1. Symlink sample data as full data
New-Item -ItemType Junction -Path data-science\marts\full -Target data-science\marts\sample
New-Item -ItemType Junction -Path data-science\marts\processed -Target data-science\marts\sample_processed

# 2. Start API + Frontend (see Phase 3 above)
```

## What gets verified
- Gold Parquet loads in DuckDB
- GraphQL queries return results
- REST endpoints respond
- ML models load and predict
- Frontend renders homepage
```
```

### 2.5 Checkpoint Strategy

| Phase | Checkpoint | Format | Size | Resume |
|-------|-----------|--------|------|--------|
| After DE | `marts/full/*.parquet` | Snappy Parquet | ~5.1 GB | Skip Docker DE; go straight to DS |
| After DS | `marts/processed/*` | Mixed (`.pt`, `.cbm`, `.joblib`, `.json`, `.npy`) | ~200 MB | Skip DS; start Web |
| After Web | Server running on :8000 + :5173 | — | — | Smoke test only |

**Pseudo-code for checkpoint resume detection:**
```python
# scripts/detect_checkpoint.py
from pathlib import Path

def get_pipeline_state():
    state = {"de_complete": False, "ds_complete": False}
    full_dir = Path("data-science/marts/full")
    processed_dir = Path("data-science/marts/processed")
    required_full = ["dim_title.parquet", "dim_person.parquet", "fact_title_principal.parquet"]
    required_processed = ["gmu_genre_best.pt", "catboost_rating_model.cbm", "feature_columns.json"]

    if all((full_dir / f).exists() for f in required_full):
        state["de_complete"] = True
    if all((processed_dir / f).exists() for f in required_processed):
        state["ds_complete"] = True
    return state
```

---

## 3. Unified README Hierarchy

### 3.1 Root `README.md` — Proposed Structure

```markdown
# Codename: Elyssa — IMDb Intelligence Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

End-to-end IMDb analytics platform: Bronze→Silver→Gold data pipeline → ML models → Web application.

## What's New (July 2026)

- ✅ **Phase 1:** Data Engineering — Bronze→Silver→Gold pipeline processing ~210M source rows
- ✅ **Phase 2:** Data Science — Multi-modal ML (GMU genre classification, CatBoost rating regression)
- ✅ **Phase 3-4:** Web Application — FastAPI+GraphQL API + React SPA with auth, search, predictions
- 🚧 **Phase 6:** MLOps — MLflow, Prometheus/Grafana, retraining DAGs, Terraform

## Quick Start

### Smoke Test (30 min)
```powershell
# Verify all modules with pre-packaged sample data
docs\SMOKE_TEST.md
```

### Full Pipeline (3 days, sequential)
| Day | Phase | Duration | What You Get |
|-----|-------|----------|-------------|
| 1 | Data Engineering | ~5-6 hours | Gold Parquet marts (6 tables) |
| 2 | Data Science | ~3-4 hours | Trained models (GMU, CatBoost) + inference artifacts |
| 3 | Web Application | ~15 min | API + Frontend serving data and predictions |

See [RUNBOOK.md](docs/RUNBOOK.md) for the complete step-by-step guide.

## Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores (AMD Athlon 200GE) | 4+ cores |
| RAM | 16 GB | 32 GB |
| Disk | 20 GB free | 50 GB SSD |
| Docker | 24+ with compose plugin | 24+ |

## Features

- **Medallion Pipeline:** DuckDB → PostgreSQL+TimescaleDB → dbt star-schema
- **SCD2 Tracking:** Slowly Changing Dimension Type 2 for title/person history
- **ML Models:** Genre classification (GMU, macro F1 > 0.60), Rating regression (CatBoost, RMSE ≤ 0.55)
- **Web Application:** GraphQL + REST API, React SPA with dark mode, search, predictions
- **Monitoring:** Prometheus + Grafana dashboards, structured logging, alerting
- **Containerised:** Docker Compose for local dev, Terraform for cloud deployment

## Performance

| Pipeline Stage | Duration (Full IMDb) |
|----------------|---------------------|
| Bronze Ingestion | ~47 min |
| Silver ETL | ~3h 39min |
| Gold dbt Run + Test | ~70 min |
| **DE Total** | **~5h 36min** |
| DS EDA → Modeling → Analytics | ~3-4 hours |
| Web API startup | ~30s |

> **Note:** Sequential execution on reference hardware (AMD Athlon 200GE, 16 GB RAM).
> Running all containers concurrently may degrade performance. See [docs/execution_architecture.md](docs/execution_architecture.md) for the recommended runbook.

## Module READMEs

| Module | Description | README |
|--------|-------------|--------|
| Data Engineering | Bronze→Silver→Gold pipeline, Airflow DAG, dbt marts | [data-engineering/README.md](data-engineering/README.md) |
| Data Science | ML notebooks, model training, inference artifacts | [data-science/README.md](data-science/README.md) |
| Web Application | FastAPI + GraphQL API, React SPA | [web-application/README.md](web-application/README.md) |
| MLOps | MLflow, monitoring, retraining, IaC | [mlops/README.md](mlops/README.md) |

## Repository Structure

```
elyssa-imdb/
├── data-engineering/     # Bronze→Silver→Gold pipeline
├── data-science/         # ML pipelines & artifacts
├── web-application/      # API gateway + React frontend
├── mlops/                # MLOps infrastructure
├── docker/               # Shared Dockerfiles
├── docs/                 # Project documentation
├── docker-compose.yml    # Root Docker Compose
├── Makefile              # Build targets
└── LICENSE               # MIT License
```

## Cross-Module Contracts

```
DE (Gold Parquet) ──gold-to-ds.md──▶ DS (notebooks)
DE (Gold Parquet) ─gold-to-api.md──▶ Web (API)
DS (MLflow) ────────ds-to-web.md──▶ Web (API)
Web (API) ─────api-to-frontend.md──▶ Frontend (React)
```

## License

MIT License — see [LICENSE](LICENSE).
```

### 3.2 Module-Level README Outlines

#### `data-engineering/README.md` (NEW — currently missing)

```markdown
# Elyssa Data Engineering — Bronze→Silver→Gold Pipeline

## Overview
Medallion architecture processing IMDb .tsv.gz into queryable star-schema marts.

## Pipeline Stages
1. **Bronze** — DuckDB ingestion → Raw Parquet
2. **Silver** — PySpark ETL → PostgreSQL 3NF/BCNF (14 tables, SCD2)
3. **Gold** — dbt → Star-schema (6 tables, 4 views)

## Prerequisites
- Docker 24+ (docker compose plugin)
- 20 GB free disk
- 16 GB RAM

## Quick Start
```powershell
docker builder prune -f && docker compose up -d --build
```

## Key Files

| File | Description |
|------|-------------|
| `bronze/` | DuckDB ingestion scripts |
| `silver/` | PySpark ETL transforms + SCD2 |
| `gold/` | dbt models (staging, intermediate, marts) |
| `orchestration/dags/` | Airflow DAG definition |
| `orchestration/operators/` | Custom Airflow operators |
| `dq/` | Data quality check runner |
| `docs/` | Schema dictionary, architecture, tests |

## Output
- `data-science/marts/full/*.parquet` (6 Gold marts)

## Data Quality
See [docs/data_quality_tests.md](docs/data_quality_tests.md).

## Contracts
- [gold-to-ds.md](../data-science/contracts/gold-to-ds.md) — DE → DS
- [gold-to-api.md](../web-application/contracts/gold-to-api.md) — DE → Web

## Tests
```powershell
pytest bronze/tests/ -v
cd gold && dbt test
```
```

#### `data-science/README.md` (update existing)

```markdown
# Elyssa Data Science — ML Pipelines

(Keep existing structure; add:)

## Pipeline Usage

```bash
# Full pipeline (after DE marts are available)
python scripts/run_pipeline.py --stage all

# Checkpoint resume
python scripts/run_pipeline.py --stage features   # skip EDA if already done
```

## Artifact Verification

```bash
python scripts/validate_contracts.py
```

## Quick Smoke Test

```powershell
# Use pre-packaged sample data
New-Item -ItemType Junction -Path marts\full -Target marts\sample
python scripts/run_pipeline.py --stage all --sample
```

## Required Outputs

| Artifact | Path | Consumer |
|----------|------|----------|
| GMU model | `marts/processed/gmu_genre_best.pt` | Web API |
| CatBoost model | `marts/processed/catboost_rating_model.cbm` | Web API |
| Feature schema | `marts/processed/feature_columns.json` | Web API |
| Preprocessor | `marts/processed/preprocessor.joblib` | Web API |

## Upstream Dependency

Gold Parquet marts from `data-engineering/` at `marts/full/`.

## Downstream Consumer

Web Application API at `web-application/` reads from `marts/processed/`.
```

#### `web-application/README.md` (update existing)

(Keep existing comprehensive structure; add sections for:)

```markdown
## Prerequisites Check

Before starting the API, verify upstream artifacts exist:

```powershell
if (-not (Test-Path "../data-science/marts/processed/feature_columns.json")) {
    Write-Error "DS artifacts missing — run data-science pipeline first"
    exit 1
}
if (-not (Test-Path "../data-science/marts/full/dim_title.parquet")) {
    Write-Error "Gold marts missing — run data-engineering pipeline first"
    exit 1
}
```

## Contract Conformance

```bash
pytest tests/test_contract.py -v    # verifies api-to-frontend.md compliance
```

## Graceful Degradation

The API handles missing models gracefully:
- Models absent → `/predict/genre` returns `{"error": "Model unavailable"}`
- Gold marts absent → `/graphql` returns `{"data": null, "errors": [...]}`
```

#### `mlops/README.md` (keep existing; extend with:)

```markdown
## Wiring to Other Modules

| Module | Integration Point | Port | Status |
|--------|------------------|------|--------|
| Data Engineering | Airflow DAG monitoring | Prometheus :9090 | ✅ |
| Data Science | MLflow model registry | MLflow :5000 | ✅ |
| Web Application | API metrics, Grafana dashboards | Grafana :3000 | ✅ |

## Quick Start with Sample Data

```bash
# Ensure MLflow can see DS artifacts
docker compose -f mlops/docker-compose.yml up -d
```
```

---

## 4. QA Catalog Structure

### 4.1 QA Catalog Template

The template below is designed to be reused across all pipeline runs. It can be executed as a Python script (automated) or followed as a manual checklist.

**File:** `docs/qa_catalog_template.md`

```markdown
# QA Catalog: Elyssa End-to-End Pipeline Validation

**Run Date:** {{DATE}}
**Run ID:** {{RUN_ID}}
**Data Source:** [ ] Full IMDb / [ ] Sample / [ ] Incremental

---

## Section A: Data Engineering (Bronze→Silver→Gold)

### A.1 Infrastructure Health

| # | Check | Command | Expected | Actual | Pass/Fail |
|---|-------|---------|----------|--------|-----------|
| 1 | PostgreSQL running | `docker ps --filter name=elyssa-postgres --format "{{.Status}}"` | `healthy` | | |
| 2 | Airflow running | `docker ps --filter name=elyssa-airflow --format "{{.Status}}"` | `healthy` | | |
| 3 | RustFS running | `docker ps --filter name=elyssa-rustfs --format "{{.Status}}"` | `healthy` | | |
| 4 | DuckDB available | `docker exec elyssa-airflow duckdb -c "SELECT 1"` | `1` | | |

### A.2 Pipeline Execution

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 5 | DAG triggered successfully | Run ID returned | |
| 6 | All tasks completed without failure | All tasks = `success` | |
| 7 | Pipeline runtime within bounds | < 6 hours | |

### A.3 Bronze Layer

| # | Check | Query | Expected | Pass/Fail |
|---|-------|-------|----------|-----------|
| 8 | title.basics row count | `SELECT COUNT(*) FROM bronze.title_basics` | ~12.6M | |
| 9 | name.basics row count | `SELECT COUNT(*) FROM bronze.name_basics` | ~15.4M | |
| 10 | title.principals row count | `SELECT COUNT(*) FROM bronze.title_principals` | ~100M | |
| 11 | No zero-row tables | `SELECT table_name, row_count FROM bronze.batch_metadata` | All > 0 | |
| 12 | No quarantined corrupt files | `SELECT COUNT(*) FROM silver.quarantine` | 0 | |

### A.4 Silver Layer

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 13 | 14 tables exist | `SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='silver'` | 14 | |
| 14 | SCD2 active (is_current = TRUE) | `SELECT COUNT(*) FROM silver.title_basics WHERE is_current = TRUE` | > 0 | |
| 15 | No duplicate PKs | `SELECT COUNT(*) FROM (SELECT tconst, COUNT(*) FROM silver.title_basics GROUP BY tconst HAVING COUNT(*) > 1) AS dupes` | 0 | |
| 16 | Referential integrity (episode→title) | `SELECT COUNT(*) FROM silver.title_episode e LEFT JOIN silver.title_basics t ON e.parent_tconst = t.tconst WHERE t.tconst IS NULL` | 0 | |
| 17 | Latest batch ingested_at not stale | `SELECT MAX(ingested_at) FROM silver.batch_metadata` | < 24h from now | |

### A.5 Gold Layer

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 18 | 6 materialized tables exist | `SELECT table_name FROM information_schema.tables WHERE table_schema='gold' AND table_type='BASE TABLE'` | dim_title, dim_person, fact_title_principal, fact_performance, fact_episode, fact_title_rating |
| 19 | dim_title.tconst unique | dbt test `unique` | PASS | |
| 20 | dim_title.primary_title not null | dbt test `not_null` | PASS | |
| 21 | average_rating 0.0-10.0 | dbt test `accepted_range` | PASS | |
| 22 | dbt run + test: 0 ERROR | `dbt test` exit code | 0 | |
| 23 | Parquet export complete | `Get-ChildItem marts/full/*.parquet` | 6 files, > 0 MB each | |

---

## Section B: Data Science (Models)

### B.1 Artifact Presence

| # | Check | Path | Expected | Pass/Fail |
|---|-------|------|----------|-----------|
| 24 | Feature schema | `marts/processed/feature_columns.json` | Exists, valid JSON | |
| 25 | GMU model | `marts/processed/gmu_genre_best.pt` | Exists, loadable | |
| 26 | CatBoost model | `marts/processed/catboost_rating_model.cbm` | Exists, loadable | |
| 27 | Preprocessor | `marts/processed/preprocessor.joblib` | Exists, loadable | |
| 28 | MLB binarizer | `marts/processed/genre_list_mlb.joblib` | Exists, loadable | |
| 29 | Model inventory | `marts/processed/model_inventory.json` | Exists, valid JSON | |

### B.2 Quality Gates

| # | Check | Expected | Actual | Pass/Fail |
|---|-------|----------|--------|-----------|
| 30 | Rating RMSE | ≤ 0.55 | | |
| 31 | Genre Macro F1 | > 0.60 | | |
| 32 | Temporal generalisation (train-test Δ) | < 0.10 | | |
| 33 | All 18 required artifacts present | 18 files | | |
| 34 | MLflow metric naming compliant | No `@` or `+` in names | | |

---

## Section C: Web Application (API + Frontend)

### C.1 API Health

| # | Check | Command | Expected | Pass/Fail |
|---|-------|---------|----------|-----------|
| 35 | Health endpoint | `curl -s http://localhost:8000/health \| jq .status` | `"ok"` | |
| 36 | GraphQL playground | `curl -s http://localhost:8000/graphql` | 405 or HTML | |
| 37 | OpenAPI docs | `curl -s http://localhost:8000/docs` | 200 | |
| 38 | Auth register | `curl -s -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d '{"email":"test@test.com","password":"test123","display_name":"Test"}'` | 200 or 409 | |

### C.2 Data Endpoints

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 39 | GET /api/v1/titles returns data | Non-empty results | |
| 40 | GET /api/v1/titles/{id} returns detail | 200 with title data | |
| 41 | GET /api/v1/search?q=Inception returns results | Non-empty | |
| 42 | GET /api/v1/persons/{id} returns person | 200 with person data | |
| 43 | P95 API latency < 500ms | Fast response | |

### C.3 Prediction Endpoints

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 44 | POST /api/v1/predict/genre returns genres | Non-empty genres array | |
| 45 | POST /api/v1/predict/rating returns rating | Float between 1.0-10.0 | |
| 46 | GET /api/v1/models lists registered models | 2+ models | |
| 47 | Graceful degradation when model absent | `{"error": ...}` | |

### C.4 Frontend

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 48 | Homepage renders at http://localhost:5173 | 200, no console errors | |
| 49 | Browse page loads titles | Data visible | |
| 50 | Title detail page renders | All sections load | |
| 51 | Person detail page renders | Filmography visible | |
| 52 | Search returns suggestions | Dropdown appears | |
| 53 | Register/Login flow works | JWT received | |
| 54 | Dark mode toggle works | Theme switches | |

---

## Section D: Cross-Module Integration

| # | Check | Criteria | Pass/Fail |
|---|-------|----------|-----------|
| 55 | DE→DS: Gold Parquet readable by DS notebooks | `python -c "import duckdb; con=duckdb.connect(); con.execute(\"SELECT COUNT(*) FROM 'marts/full/dim_title.parquet'\").fetchone()"` | |
| 56 | DE→Web: Gold marts queryable by API | curl graphql homepage query | |
| 57 | DS→Web: Models loadable by ModelService | `python -c "from app.models.inference import ModelService; m=ModelService('/data/marts/processed'); print('OK')"` | |
| 58 | Web→Frontend: API response matches contract | `pytest tests/test_contract.py -v` | |

---

## Summary

| Section | Total Checks | Pass | Fail | Skipped | Pass % |
|---------|-------------|------|------|---------|--------|
| A. Data Engineering | 23 | | | | |
| B. Data Science | 11 | | | | |
| C. Web Application | 20 | | | | |
| D. Cross-Module | 4 | | | | |
| **Total** | **58** | | | | |

**Sign-off:**

| Role | Name | Date |
|------|------|------|
| QA Engineer | | |
| DE Lead | | |
| DS Lead | | |
| Web Lead | | |
| MLOps Lead | | |
```

### 4.2 Automated QA Script

**File:** `scripts/run_qa_catalog.py`

```python
#!/usr/bin/env python3
"""
Automated QA catalog runner. Executes all 58 checks and outputs JUnit XML + HTML report.
Usage:
    python scripts/run_qa_catalog.py                     # Full run
    python scripts/run_qa_catalog.py --section A          # DE only
    python scripts/run_qa_catalog.py --report qa_report.json  # Save report
"""

import json, subprocess, sys, time
from datetime import datetime
from pathlib import Path

CHECKS = {
    "A1": {"desc": "PostgreSQL running", "cmd": "docker ps --filter name=elyssa-postgres --format '{{.Status}}'", "expected": "healthy"},
    "A2": {"desc": "Airflow running", "cmd": "docker ps --filter name=elyssa-airflow --format '{{.Status}}'", "expected": "healthy"},
    # ... (all 58 checks from the template)
}

def run_check(check_id: str, check: dict) -> dict:
    try:
        result = subprocess.run(check["cmd"], shell=True, capture_output=True, text=True, timeout=30)
        actual = result.stdout.strip()
        passed = actual == check["expected"] if isinstance(check["expected"], str) else actual in check["expected"]
        return {"id": check_id, "desc": check["desc"], "passed": passed, "actual": actual, "expected": check["expected"]}
    except Exception as e:
        return {"id": check_id, "desc": check["desc"], "passed": False, "actual": str(e), "expected": check["expected"]}

def main(sections: list = None):
    report = {
        "run_id": f"elyssa-qa-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": []
    }
    for cid, c in CHECKS.items():
        if sections and not any(cid.startswith(s) for s in sections):
            continue
        report["checks"].append(run_check(cid, c))
    passed = sum(1 for c in report["checks"] if c["passed"])
    total = len(report["checks"])
    report["summary"] = {"passed": passed, "failed": total - passed, "total": total, "pass_pct": round(passed/total*100, 1) if total else 0}
    print(json.dumps(report, indent=2))
    return report

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", help="Run specific section (A, B, C, D)")
    parser.add_argument("--report", help="Output JSON report path")
    args = parser.parse_args()
    sections = [f"{args.section.upper()}"] if args.section else None
    report = main(sections)
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2))
        print(f"Report saved to {args.report}")
```

### 4.3 Reusable QA Template Directory Structure

```
docs/
├── qa_catalog_template.md        # <-- This template (human-readable)
├── qa_catalog_template.html      # (generated from script)
├── qa_reports/                   # (gitignored) historical QA runs
│   ├── 2026-07-22_full_imdb.json
│   └── 2026-07-22_sample.json
└── scripts/
    └── run_qa_catalog.py         # <-- Automated runner
```

---

## Appendix A: File Manifest of Proposed New/Modified Files

| File | Action | Purpose |
|------|--------|---------|
| `docs/plug_and_play_improvement_plan.md` | **CREATE** | This document |
| `docs/SMOKE_TEST.md` | **CREATE** | 30-minute smoke test runbook |
| `docs/RUNBOOK.md` | **CREATE** | Full 3-day step-by-step runbook |
| `docs/qa_catalog_template.md` | **CREATE** | QA checklist template |
| `docs/scripts/run_qa_catalog.py` | **CREATE** | Automated QA script |
| `data-engineering/README.md` | **CREATE** | DE module README (missing) |
| `data-engineering/scripts/gold_export.py` | **CREATE/MODIFY** | Enforce runtime_minutes > 0 filter |
| `data-engineering/orchestration/operators/gold_export_operator.py` | **CREATE** | Airflow task: DuckDB postgres_scanner → Snappy Parquet to `marts/full/` |
| `data-engineering/orchestration/dags/imdb_pipeline_dag.py` | **MODIFY** | Add `gold_export >> end` after `freshness_check` |
| `data-engineering/scripts/export_marts.py` | **MODIFY** | Fix output path to `/opt/airflow/output/gold/`; remove hardcoded password; add `_MANIFEST.json` |
| `data-science/marts/full/_MANIFEST.json` | **CREATE** | Export manifest with batch_id, row counts, timestamps (written by export operator) |
| `data-science/marts/sample/*.parquet` | **CREATE** | Sample data for smoke tests |
| `data-science/marts/sample_processed/*` | **CREATE** | Pre-trained sample models |
| `data-science/scripts/generate_sample_data.py` | **CREATE** | Sample data generator |
| `data-science/README.md` | **MODIFY** | Add checkpoint + sample data sections |
| `web-application/README.md` | **MODIFY** | Add prerequisite checks + contract conformance |
| `web-application/api/app/models/inference.py` | **MODIFY** | Add disk-based fallback (no MLflow); replace zero-tensor with real text embedding; apply `preprocessor.joblib` |
| `web-application/api/tests/test_contract.py` | **CREATE** | Contract conformance tests |
| `mlops/README.md` | **MODIFY** | Add module wiring table |
| `docker-compose.yml` | **MODIFY** | Add MLflow service OR document absence; add `./data-science/marts/full:/opt/airflow/output/gold:rw` volume mount for airflow service; migrate hardcoded credentials to `.env` |
| `./.env` | **CREATE** | Central environment file with all secrets (gitignored) |
| `./.env.example` | **CREATE** | Document all required env vars (tracked) |
| `AGENTS.md` (root) | **CREATE** | Root-level agent orchestration entry point |
| `data-science/scripts/run_pipeline.py` | **MODIFY** | Replace stub stage functions with actual execution (call `src/` modules or papermill notebooks) |
| `data-science/src/inference/pipeline.py` | **MODIFY** | Replace `torch.zeros()` with real DistilBERT embedding; use `preprocessor.joblib` `ColumnTransformer` |
| `data-science/src/evaluation/temporal.py` | **MODIFY** | Add `from sklearn.metrics import mean_squared_error` import |
| `data-science/src/models/rating/xgboost.py` | **CREATE** | XGBoost regressor module (referenced but missing) |
| `data-science/src/models/genre/xgboost.py` | **CREATE** | XGBoost classifier module (referenced but missing) |
| `data-science/src/evaluation/shap.py` | **CREATE** | SHAP explainability module (required by DS.6 quality gate) |
| `data-science/src/evaluation/ablation.py` | **CREATE** | Ablation study module (required by DS.7 quality gate) |
| `data-science/.gitignore` | **CREATE** | Exclude `*.db`, `*.db.wal`, `mlruns/`, `catboost_info/` from Git |
| `data-engineering/dq/config.yaml` | **MODIFY** | Single source of truth for DQ checks (remove embedded defaults from `run_checks.py`) |
| `data-engineering/dq/run_checks.py` | **MODIFY** | Always load checks from `config.yaml`; remove `DEFAULT_CHECKS` |
| `.github/workflows/ci.yml` | **CREATE** | CI workflow for lint + test + build across DE, DS, Web |
| `.github/workflows/cd.yml` | **CREATE** | CD workflow for Docker builds and push |

## Appendix B: Priority Gating

| Priority | Item | Effort | Impact | Depends On |
|----------|------|--------|--------|------------|
| P0 | G2: Fix path mismatch `full/` vs `processed/` | 1h | **HIGH** — blocks DE→Web integration | — |
| P0 | G3: Add MLflow or disk fallback for ModelService | 2h | **HIGH** — blocks DS→Web integration | — |
| P0 | **G9: Automate Gold→Parquet export** (DAG task, fix path, secure creds) | 3h | **HIGH** — blocks DE→DS handoff; export currently manual + wrong directory | — |
| P0 | **G10: Fix DS `run_pipeline.py` stubs** — implement actual stage execution | 4h | **HIGH** — DS pipeline entry point is completely non-functional | G2 |
| P0 | **G11: Fix DS inference pipeline** — replace zero-tensor, apply preprocessor | 3h | **HIGH** — all Web API ML predictions are garbage | G3 |
| P0 | **G12: Fix `temporal.py` NameError** — add missing import | 5min | **HIGH** — blocks analytics evaluation at runtime | — |
| P0 | G5: Pre-packaged sample dataset | 4h | **HIGH** — enables smoke test without full download | — |
| P1 | G1: Enforce `runtime_minutes > 0` on export | 30min | MEDIUM — prevents silent DS errors | — |
| P1 | G4: Contract conformance tests | 3h | MEDIUM — ensures API contract compliance | — |
| P1 | Root README rewrite | 3h | MEDIUM — improves onboarding | — |
| P2 | DE README creation | 1h | LOW — missing documentation | — |
| P2 | G8: Fix ds-to-swe.md → ds-to-web.md reference | 15min | LOW — documentation accuracy | — |
| P2 | QA catalog creation | 4h | MEDIUM — reusable validation framework | All P0 |
| P2 | Automated QA script | 3h | MEDIUM — enables CI integration | QA catalog |
