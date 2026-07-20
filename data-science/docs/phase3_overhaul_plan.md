# Elyssa IMDb | Phase 3 — Official Data Science Overhaul Plan

**Date:** 2026-07-19
**Source:** `assessment_report.md` — Phase 2 findings and gaps
**Target:** Production-grade, pipeline-orchestrated, testable ML system
**Hardware:** AMD Athlon 200GE (4 threads), 16GB RAM, CPU-only

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Phase 0 — Critical Fixes (Week 1)](#2-phase-0--critical-fixes)
3. [Phase 1 — Modular Refactoring (Weeks 2–3)](#3-phase-1--modular-refactoring)
4. [Phase 2 — Pipeline Orchestration (Weeks 4–5)](#4-phase-2--pipeline-orchestration)
5. [Phase 3 — Testing & Validation (Week 6)](#5-phase-3--testing--validation)
6. [Phase 4 — MLOps & Registry (Week 7)](#6-phase-4--mlops--registry)
7. [Phase 5 — Documentation & Handoff (Week 8)](#7-phase-5--documentation--handoff)
8. [Directory Structure](#8-directory-structure)
9. [Config Management](#9-config-management)
10. [Quality Gates Enforcement](#10-quality-gates-enforcement)
11. [Risk Register](#11-risk-register)

---

## 1. Architecture Overview

### Current State (Phase 2)

```
Notebooks (monolithic)
├── EDA (114 cells, 52 figs)
├── Feature Engineering (24 cells, 56 artifacts)
├── Modeling (62 cells, 14 models)
└── Analytics (22 cells, registry)

Issues:
- Target leakage in rating features
- No importable Python modules
- No tests
- No config management
- Hardcoded paths per notebook
- Mixed artifact locations
```

### Target State (Phase 3)

```
data-science/
├── config/
│   ├── settings.yaml              # Central config (splits, paths, constants)
│   └── environments.yaml          # Dev/staging/prod profiles
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py              # DuckDB connection, Parquet loading
│   │   ├── splitter.py            # Temporal split logic
│   │   └── sampler.py             # TABLESAMPLE helpers
│   ├── features/
│   │   ├── __init__.py
│   │   ├── tabular.py             # Numeric/categorical encoding
│   │   ├── text.py                # DistilBERT embeddings
│   │   ├── builder.py             # Feature matrix assembly
│   │   └── schema.py              # FeatureColumns.json management
│   ├── models/
│   │   ├── __init__.py
│   │   ├── genre/
│   │   │   ├── gmu.py             # Gated Multimodal Unit
│   │   │   ├── bilstm.py          # BiLSTM baseline
│   │   │   └── baselines.py       # Dummy, LogReg
│   │   ├── rating/
│   │   │   ├── catboost_regressor.py
│   │   │   └── baselines.py       # Dummy, Ridge
│   │   └── recommender/
│   │       ├── svd_model.py
│   │       ├── ncf_model.py
│   │       └── hybrid.py
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── metrics.py             # All metric computations
│   │   ├── qerror.py              # Q-error profiling
│   │   ├── temporal.py            # Decay analysis
│   │   └── bias.py                # Bias audit
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── pipeline.py            # predict_genre(), predict_rating()
│   │   └── feature_builder.py     # Raw input → feature vector
│   └── utils/
│       ├── __init__.py
│       ├── mlflow_utils.py        # MLflow try/except wrapper
│       ├── visualization.py       # save_figures(), write_html()
│       └── logging.py             # Structured logging setup
├── notebooks/
│   ├── 01_eda.ipynb               # Thin EDA notebook (calls src/data/)
│   ├── 02_feature_engineering.ipynb
│   ├── 03_modeling.ipynb
│   └── 04_analytics.ipynb
├── tests/
│   ├── __init__.py
│   ├── test_data_loader.py
│   ├── test_splitter.py
│   ├── test_features.py
│   ├── test_models.py
│   ├── test_inference.py
│   └── conftest.py                # Shared fixtures
├── scripts/
│   ├── run_pipeline.py            # End-to-end orchestrator
│   ├── export_marts.py            # Gold → Parquet export
│   └── validate_contracts.py      # Schema validation
├── contracts/
│   ├── gold-to-ds.md
│   └── ds-to-web.md
├── marts/                         # Parquet snapshots (frozen)
├── figures/
├── docs/
└── requirements.txt
```

---

## 2. Phase 0 — Critical Fixes (Week 1)

### 2.1 Fix Target Leakage in Rating Regression

**Problem:** `average_rating` and `num_votes` are included as input features while also being prediction targets.

**Fix:**

```python
# src/features/tabular.py

# BEFORE (Phase 2 — LEAKED):
numeric_cols = [
    'start_year', 'runtime_minutes', 'average_rating', 'num_votes',
    'num_persons', 'unique_persons', ...
]

# AFTER (Phase 3 — FIXED):
RATING_FEATURE_COLS = [
    'start_year', 'runtime_minutes', 'is_adult',
    'num_episodes', 'num_persons', 'unique_persons',
    'director_count', 'writer_count', 'producer_count',
    'composer_count', 'editor_count', 'cinematographer_count',
    'self_count', 'series_episode_count', 'series_avg_episode_rating',
    'min_season', 'max_season',
    # One-hot title_type columns...
]

# average_rating and num_votes used ONLY as targets, never as features
```

**Validation:** After fix, Ridge RMSE should be > 0.5 (realistic for 1.0–10.0 rating scale).

### 2.2 Add `safe_minmax()` Helper

```python
# src/utils/math.py

import numpy as np

def safe_minmax(x: np.ndarray, axis: int = 0) -> np.ndarray:
    """Min-max normalization that handles constant features (zero division)."""
    mins = np.min(x, axis=axis, keepdims=True)
    maxs = np.max(x, axis=axis, keepdims=True)
    ranges = maxs - mins
    ranges[ranges == 0] = 1.0  # Prevent division by zero
    return (x - mins) / ranges
```

### 2.3 Add Verification Cell

```python
# src/utils/verification.py

from pathlib import Path
import json

REQUIRED_ARTIFACTS = [
    "feature_columns.json",
    "preprocessor.joblib",
    "genre_list_mlb.joblib",
    "scaler.joblib",
    "X_train_genre.npy",
    "X_val_genre.npy",
    "X_test_genre.npy",
    "y_train_genre.npy",
    "y_val_genre.npy",
    "y_test_genre.npy",
    "gmu_genre_best.pt",
    "catboost_rating_model.cbm",
    "model_inventory.json",
]

def verify_artifacts(processed_dir: Path) -> dict:
    """Check all required artifacts exist and are non-empty."""
    results = {}
    for artifact in REQUIRED_ARTIFACTS:
        path = processed_dir / artifact
        results[artifact] = {
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "status": "OK" if path.exists() and path.stat().st_size > 0 else "MISSING"
        }
    
    missing = [k for k, v in results.items() if v["status"] == "MISSING"]
    if missing:
        raise FileNotFoundError(f"Missing artifacts: {missing}")
    
    return results
```

---

## 3. Phase 1 — Modular Refactoring (Weeks 2–3)

### 3.1 Extract Data Loading Module

```python
# src/data/loader.py

import duckdb
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class GoldDataLoader:
    """Load Gold-layer Parquet exports via DuckDB."""
    
    def __init__(self, marts_dir: Path, development_mode: bool = True,
                 sample_percent: int = 5):
        self.marts_dir = marts_dir
        self.development_mode = development_mode
        self.sample_percent = sample_percent
        self.con: Optional[duckdb.DuckDBPyConnection] = None
    
    def connect(self) -> duckdb.DuckDBPyConnection:
        """Create DuckDB connection and register Parquet views."""
        self.con = duckdb.connect(":memory:")
        
        tables = {
            "dim_title": "dim_title.parquet",
            "dim_person": "dim_person.parquet",
            "fact_title_rating": "fact_title_rating.parquet",
            "fact_title_principal": "fact_title_principal.parquet",
            "fact_performance": "fact_performance.parquet",
            "fact_episode": "fact_episode.parquet",
        }
        
        for view_name, parquet_file in tables.items():
            parquet_path = self.marts_dir / parquet_file
            if self.development_mode:
                self.con.execute(f"""
                    CREATE OR REPLACE VIEW {view_name} AS
                    SELECT * FROM read_parquet('{parquet_path}')
                    TABLESAMPLE SYSTEM ({self.sample_percent} PERCENT) REPEATABLE (42)
                """)
            else:
                self.con.execute(f"""
                    CREATE OR REPLACE VIEW {view_name} AS
                    SELECT * FROM read_parquet('{parquet_path}')
                """)
            
            count = self.con.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()[0]
            logger.info(f"Loaded {view_name}: {count:,} rows")
        
        return self.con
    
    def query_to_df(self, sql: str, max_rows: int = 50000):
        """Execute query with row-count safety check."""
        count_sql = f"SELECT count(*) FROM ({sql}) t"
        row_cnt = self.con.execute(count_sql).fetchone()[0]
        if row_cnt > max_rows:
            raise ValueError(
                f"Query returns {row_cnt:,} rows (limit: {max_rows:,}). "
                "Add aggregation or sampling."
            )
        return self.con.execute(sql).df()
    
    def close(self):
        if self.con:
            self.con.close()
```

### 3.2 Extract Temporal Splitter

```python
# src/data/splitter.py

import pandas as pd
import numpy as np
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

# Frozen constants — DO NOT CHANGE
TRAIN_YEAR_MAX = 2014
VAL_YEAR_MIN = 2015
VAL_YEAR_MAX = 2018
TEST_YEAR_MIN = 2019

def temporal_split(
    df: pd.DataFrame,
    year_col: str = "start_year",
    train_max: int = TRAIN_YEAR_MAX,
    val_min: int = VAL_YEAR_MIN,
    val_max: int = VAL_YEAR_MAX,
    test_min: int = TEST_YEAR_MIN,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Return boolean masks for temporal train/val/test split."""
    train_mask = df[year_col] <= train_max
    val_mask = (df[year_col] >= val_min) & (df[year_col] <= val_max)
    test_mask = df[year_col] >= test_min
    
    logger.info(
        f"Temporal split: train={train_mask.sum():,}, "
        f"val={val_mask.sum():,}, test={test_mask.sum():,}"
    )
    
    return train_mask, val_mask, test_mask
```

### 3.3 Extract Feature Builder

```python
# src/features/builder.py

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class FeatureBuilder:
    """Build feature matrices from raw Gold data."""
    
    # Features that MUST NOT be used for rating regression (target leakage)
    RATING_EXCLUDED = {"average_rating", "num_votes"}
    
    def __init__(self, processed_dir: Path):
        self.processed_dir = processed_dir
        self.preprocessor = None
        self.mlb_genre = None
        self.mlb_region = None
    
    def load_preprocessors(self):
        """Load fitted preprocessors from FE stage."""
        self.preprocessor = joblib.load(self.processed_dir / "preprocessor.joblib")
        self.mlb_genre = joblib.load(self.processed_dir / "genre_list_mlb.joblib")
        self.mlb_region = joblib.load(self.processed_dir / "region_list_mlb.joblib")
    
    def get_rating_features(self, feature_cols: list) -> list:
        """Return feature columns safe for rating regression (no leakage)."""
        return [c for c in feature_cols if c not in self.RATING_EXCLUDED]
    
    def build_genre_matrix(
        self,
        X_tab: np.ndarray,
        X_text: np.ndarray,
        y_genre: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        """Build concatenated feature matrix for genre classification."""
        X = np.concatenate([X_tab, X_text], axis=1).astype(np.float32)
        return {"X": X, "y": y_genre}
    
    def build_rating_matrix(
        self,
        X_tab: np.ndarray,
        X_text: np.ndarray,
        y_rating: np.ndarray,
        exclude_cols: list = None,
    ) -> Dict[str, np.ndarray]:
        """Build feature matrix for rating regression (leakage-safe)."""
        if exclude_cols:
            mask = ~np.isin(range(X_tab.shape[1]), exclude_cols)
            X_tab = X_tab[:, mask]
        X = np.concatenate([X_tab, X_text], axis=1).astype(np.float32)
        return {"X": X, "y": y_rating}
```

### 3.4 Extract Model Registry Wrapper

```python
# src/utils/mlflow_utils.py

import logging
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import mlflow
    import mlflow.sklearn
    import mlflow.catboost
    import mlflow.pytorch
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("MLflow not installed; experiment tracking disabled")


class MlflowWrapper:
    """Safe MLflow wrapper with try/except and no-op fallback."""
    
    def __init__(self, tracking_uri: str = "sqlite:///mlflow.db"):
        self.available = MLFLOW_AVAILABLE
        if self.available:
            mlflow.set_tracking_uri(tracking_uri)
    
    @contextmanager
    def start_run(self, experiment_name: str, run_name: str):
        """Context manager for MLflow runs."""
        if not self.available:
            logger.info(f"[MLflow disabled] Would start run: {run_name}")
            yield None
            return
        
        mlflow.set_experiment(experiment_name)
        with mlflow.start_run(run_name=run_name) as run:
            yield run
    
    def log_params(self, params: dict):
        if self.available:
            mlflow.log_params(params)
    
    def log_metrics(self, metrics: dict):
        if self.available:
            # sanitize metric names (no @ or +)
            sanitized = {
                k.replace("@", "_at_").replace("+", "_and_"): v
                for k, v in metrics.items()
            }
            mlflow.log_metrics(sanitized)
    
    def log_artifact(self, path: str):
        if self.available:
            mlflow.log_artifact(path)
```

### 3.5 Refactor Notebooks to Thin Wrappers

Each notebook becomes a thin orchestrator that imports from `src/`:

```python
# notebooks/03_modeling.ipynb (Cell 0)

import sys
sys.path.insert(0, str(Path.cwd().parent))

from src.data.loader import GoldDataLoader
from src.data.splitter import temporal_split
from src.features.builder import FeatureBuilder
from src.models.genre.gmu import GatedMultimodalUnit
from src.models.rating.catboost_regressor import train_catboost
from src.utils.mlflow_utils import MlflowWrapper
from src.utils.verification import verify_artifacts
```

---

## 4. Phase 2 — Pipeline Orchestration (Weeks 4–5)

### 4.1 Config Management

```yaml
# config/settings.yaml

project:
  name: elyssa-imdb
  version: "3.0.0"
  hardware:
    cpu_threads: 4
    ram_gb: 16
    gpu: false

paths:
  marts_dir: "../marts"
  processed_dir: "../marts/processed"
  figures_dir: "../figures"
  contracts_dir: "../contracts"

development_mode:
  enabled: true
  sample_percent: 5
  random_seed: 42

temporal_splits:
  train_year_max: 2014
  val_year_min: 2015
  val_year_max: 2018
  test_year_min: 2019

features:
  tabular_columns:
    - start_year
    - runtime_minutes
    - is_adult
    - num_episodes
    - num_persons
    - unique_persons
    - director_count
    - writer_count
    - producer_count
    - composer_count
    - editor_count
    - cinematographer_count
    - self_count
    - series_episode_count
    - series_avg_episode_rating
    - min_season
    - max_season
  text_embedding_model: "distilbert-base-uncased"
  text_embedding_dim: 768
  rating_excluded_features:
    - average_rating
    - num_votes

models:
  genre:
    gmu:
      hidden_dim: 256
      dropout: 0.3
      optuna_trials: 5
      max_epochs: 30
      patience: 5
    bilstm:
      embedding_dim: 128
      lstm_units: 64
      max_epochs: 20
  rating:
    catboost:
      optuna_trials: 5
      max_iterations: 400
      max_depth: 6
      early_stopping_rounds: 50
  recommender:
    svd_factors: 100
    ncf_embedding_dim: 64
    ncf_layers: [64, 32, 16]

evaluation:
  quality_gates:
    rating_rmse_max: 0.55
    genre_macro_f1_min: 0.60
    inference_latency_max_ms: 100
    cold_start_precision_min: 0.01

mlflow:
  tracking_uri: "sqlite:///mlflow.db"
  experiment_prefix: "elyssa_phase3"
```

### 4.2 Pipeline Orchestrator

```python
# scripts/run_pipeline.py

"""
Elyssa Phase 3 — End-to-End Pipeline Orchestrator

Usage:
    python scripts/run_pipeline.py --stage all
    python scripts/run_pipeline.py --stage features
    python scripts/run_pipeline.py --stage models --model gmu
"""

import argparse
import yaml
import logging
from pathlib import Path
from datetime import datetime

from src.data.loader import GoldDataLoader
from src.data.splitter import temporal_split
from src.features.builder import FeatureBuilder
from src.utils.verification import verify_artifacts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("pipeline.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("elyssa.pipeline")

def load_config(config_path: str = "config/settings.yaml") -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)

def run_stage_eda(config: dict):
    """Stage 1: Exploratory Data Analysis."""
    logger.info("=== Stage: EDA ===")
    # Import and run EDA notebook logic
    from notebooks.eda_runner import run_eda
    run_eda(config)

def run_stage_features(config: dict):
    """Stage 2: Feature Engineering."""
    logger.info("=== Stage: Feature Engineering ===")
    from src.data.loader import GoldDataLoader
    from src.features.tabular import build_tabular_features
    from src.features.text import compute_text_embeddings
    from src.features.builder import FeatureBuilder
    
    loader = GoldDataLoader(
        marts_dir=Path(config["paths"]["marts_dir"]),
        development_mode=config["development_mode"]["enabled"],
        sample_percent=config["development_mode"]["sample_percent"]
    )
    con = loader.connect()
    
    builder = FeatureBuilder(Path(config["paths"]["processed_dir"]))
    # ... feature construction logic
    
    loader.close()

def run_stage_models(config: dict, model_name: str = "all"):
    """Stage 3: Model Training."""
    logger.info(f"=== Stage: Models ({model_name}) ===")
    # ... model training logic

def run_stage_analytics(config: dict):
    """Stage 4: Evaluation & Registry."""
    logger.info("=== Stage: Analytics ===")
    # ... analytics logic

def main():
    parser = argparse.ArgumentParser(description="Elyssa Pipeline")
    parser.add_argument("--stage", choices=["eda", "features", "models", "analytics", "all"])
    parser.add_argument("--model", default="all", help="Specific model to train")
    parser.add_argument("--config", default="config/settings.yaml")
    args = parser.parse_args()
    
    config = load_config(args.config)
    start = datetime.now()
    logger.info(f"Pipeline started at {start}")
    
    stages = {
        "eda": run_stage_eda,
        "features": run_stage_features,
        "models": lambda c: run_stage_models(c, args.model),
        "analytics": run_stage_analytics,
    }
    
    if args.stage == "all":
        for stage_name, stage_fn in stages.items():
            stage_fn(config)
    else:
        stages[args.stage](config)
    
    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"Pipeline completed in {elapsed:.1f}s")

if __name__ == "__main__":
    main()
```

### 4.3 Contract Validation Script

```python
# scripts/validate_contracts.py

"""
Validate that model artifacts match ds-to-web.md contract.
Run after model training and before handoff to SWE.
"""

import json
from pathlib import Path

def validate_api_contract(processed_dir: Path) -> dict:
    """Verify inference artifacts match API contract."""
    required = {
        "feature_columns.json": validate_feature_schema,
        "preprocessor.joblib": validate_preprocessor,
        "genre_list_mlb.joblib": validate_mlb,
        "gmu_genre_best.pt": validate_pytorch_model,
        "catboost_rating_model.cbm": validate_catboost_model,
    }
    
    results = {}
    for artifact, validator in required.items():
        path = processed_dir / artifact
        try:
            result = validator(path)
            results[artifact] = {"status": "PASS", "details": result}
        except Exception as e:
            results[artifact] = {"status": "FAIL", "error": str(e)}
    
    return results

def validate_feature_schema(path: Path) -> dict:
    with open(path) as f:
        schema = json.load(f)
    
    assert "tabular_columns" in schema, "Missing tabular_columns"
    assert "embedding_dim" in schema, "Missing embedding_dim"
    assert "total_dim" in schema, "Missing total_dim"
    assert schema["total_dim"] == len(schema["tabular_columns"]) + schema["embedding_dim"]
    
    return {"columns": len(schema["tabular_columns"]), "dim": schema["total_dim"]}
```

---

## 5. Phase 3 — Testing & Validation (Week 6)

### 5.1 Test Structure

```python
# tests/conftest.py

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture
def processed_dir():
    return Path("data-science/marts/processed")

@pytest.fixture
def sample_data():
    """Load minimal sample data for unit tests."""
    import numpy as np
    return {
        "X_tab": np.random.randn(100, 17).astype(np.float32),
        "X_text": np.random.randn(100, 768).astype(np.float32),
        "y_genre": np.random.randint(0, 2, (100, 28)).astype(np.float32),
        "y_rating": np.random.uniform(1.0, 10.0, 100).astype(np.float32),
    }

# tests/test_splitter.py

from src.data.splitter import temporal_split, TRAIN_YEAR_MAX, VAL_YEAR_MIN
import pandas as pd
import numpy as np

def test_temporal_split_no_leakage():
    df = pd.DataFrame({"start_year": [2010, 2015, 2019, 2022]})
    train, val, test = temporal_split(df)
    
    assert df.loc[train, "start_year"].max() <= TRAIN_YEAR_MAX
    assert df.loc[val, "start_year"].min() >= VAL_YEAR_MIN
    assert df.loc[test, "start_year"].min() >= 2019

def test_temporal_split_no_overlap():
    df = pd.DataFrame({"start_year": list(range(2000, 2025))})
    train, val, test = temporal_split(df)
    
    assert not (train & val).any()
    assert not (train & test).any()
    assert not (val & test).any()

# tests/test_features.py

def test_no_rating_leakage(sample_data):
    from src.features.builder import FeatureBuilder
    from pathlib import Path
    
    builder = FeatureBuilder(Path("."))
    rating_features = builder.get_rating_features(
        ["start_year", "runtime_minutes", "average_rating", "num_votes"]
    )
    
    assert "average_rating" not in rating_features
    assert "num_votes" not in rating_features
    assert "start_year" in rating_features

def test_feature_matrix_shape(sample_data):
    from src.features.builder import FeatureBuilder
    from pathlib import Path
    
    builder = FeatureBuilder(Path("."))
    result = builder.build_genre_matrix(
        sample_data["X_tab"], sample_data["X_text"], sample_data["y_genre"]
    )
    
    assert result["X"].shape == (100, 785)  # 17 + 768
    assert result["y"].shape == (100, 28)

# tests/test_models.py

def test_gmu_forward_pass():
    from src.models.genre.gmu import GatedMultimodalUnit
    import torch
    
    model = GatedMultimodalUnit(
        tabular_dim=17, text_dim=768, hidden_dim=128, output_dim=28
    )
    
    x_tab = torch.randn(4, 17)
    x_text = torch.randn(4, 768)
    
    output = model(x_tab, x_text)
    assert output.shape == (4, 28)
    assert output.min() >= 0  # sigmoid output
    assert output.max() <= 1

def test_catboost_loadable(processed_dir):
    from catboost import CatBoostRegressor
    
    model = CatBoostRegressor()
    model.load_model(str(processed_dir / "catboost_rating_model.cbm"))
    
    # Test prediction with dummy input
    import numpy as np
    dummy = np.zeros((1, 796))
    pred = model.predict(dummy)
    assert pred.shape == (1,)
    assert 1.0 <= pred[0] <= 10.0  # Rating range

# tests/test_inference.py

def test_predict_genre_schema():
    from src.inference.pipeline import predict_genre
    
    result = predict_genre({
        "runtime_minutes": 148,
        "start_year": 2010,
        "is_adult": False,
        "title_type": "movie",
    })
    
    assert "genres" in result
    assert isinstance(result["genres"], list)
    assert all("name" in g and "confidence" in g for g in result["genres"])

def test_predict_rating_range():
    from src.inference.pipeline import predict_rating
    
    result = predict_rating({
        "runtime_minutes": 148,
        "start_year": 2010,
        "is_adult": False,
        "title_type": "movie",
    })
    
    assert "predicted_rating" in result
    assert 1.0 <= result["predicted_rating"] <= 10.0
```

### 5.2 Test Coverage Targets

| Module | Target Coverage | Priority |
|--------|----------------|----------|
| `src/data/splitter.py` | 100% | P0 |
| `src/features/builder.py` | 95% | P0 |
| `src/models/genre/gmu.py` | 90% | P1 |
| `src/models/rating/catboost_regressor.py` | 90% | P1 |
| `src/inference/pipeline.py` | 95% | P0 |
| `src/utils/mlflow_utils.py` | 85% | P2 |
| All other modules | 80% | P2 |

---

## 6. Phase 4 — MLOps & Registry (Week 7)

### 6.1 MLflow Model Registry

```python
# src/registry/model_registry.py

import mlflow
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class ModelRegistry:
    """Manage MLflow model registry with stage transitions."""
    
    STAGES = ["None", "Staging", "Production", "Archived"]
    
    def __init__(self, tracking_uri: str = "sqlite:///mlflow.db"):
        mlflow.set_tracking_uri(tracking_uri)
        self.client = mlflow.tracking.MlflowClient()
    
    def register_model(
        self,
        model_name: str,
        source_run_id: str,
        metrics: Dict[str, float],
    ) -> str:
        """Register a new model version."""
        try:
            model_version = mlflow.register_model(
                f"runs:/{source_run_id}/model",
                model_name
            )
            logger.info(f"Registered {model_name} v{model_version.version}")
            return model_version.version
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            return None
    
    def promote_to_staging(self, model_name: str, version: str) -> bool:
        """Promote model to Staging after passing quality gates."""
        try:
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage="Staging"
            )
            logger.info(f"Promoted {model_name} v{version} to Staging")
            return True
        except Exception as e:
            logger.error(f"Promotion failed: {e}")
            return False
    
    def promote_to_production(self, model_name: str, version: str) -> bool:
        """Promote model to Production after staging validation."""
        try:
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage="Production"
            )
            logger.info(f"Promoted {model_name} v{version} to Production")
            return True
        except Exception as e:
            logger.error(f"Promotion failed: {e}")
            return False
    
    def get_production_model(self, model_name: str) -> Optional[str]:
        """Get the current production model version."""
        versions = self.client.get_latest_versions(model_name, stages=["Production"])
        if versions:
            return versions[0].version
        return None
```

### 6.2 Quality Gate Enforcer

```python
# src/evaluation/gates.py

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

QUALITY_GATES = {
    "G1_rating_rmse": {"metric": "test_rmse", "threshold": 0.55, "op": "<="},
    "G2_genre_macro_f1": {"metric": "test_macro_f1", "threshold": 0.60, "op": ">"},
    "G3_temporal_generalization": {"metric": "val_test_delta", "threshold": 0.10, "op": "<"},
    "G4_mlflow_naming": {"metric": "naming_compliant", "threshold": True, "op": "=="},
    "G5_inference_latency": {"metric": "p95_latency_ms", "threshold": 100, "op": "<"},
    "G6_artifacts_exist": {"metric": "all_artifacts_present", "threshold": True, "op": "=="},
}

class QualityGateEvaluator:
    """Evaluate models against quality gates before promotion."""
    
    def evaluate(self, metrics: Dict[str, Any]) -> Dict[str, dict]:
        """Check all quality gates and return pass/fail status."""
        results = {}
        for gate_name, gate_config in QUALITY_GATES.items():
            metric_value = metrics.get(gate_config["metric"])
            threshold = gate_config["threshold"]
            op = gate_config["op"]
            
            if metric_value is None:
                results[gate_name] = {"pass": False, "reason": "Metric not found"}
                continue
            
            passed = self._compare(metric_value, threshold, op)
            results[gate_name] = {
                "pass": passed,
                "value": metric_value,
                "threshold": threshold,
                "op": op,
            }
            
            status = "PASS" if passed else "FAIL"
            logger.info(f"  {gate_name}: {metric_value} {op} {threshold} → {status}")
        
        return results
    
    def all_passed(self, results: Dict[str, dict]) -> bool:
        return all(r["pass"] for r in results.values())
    
    @staticmethod
    def _compare(value, threshold, op) -> bool:
        ops = {
            "<": lambda a, b: a < b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            ">=": lambda a, b: a >= b,
            "==": lambda a, b: a == b,
        }
        return ops[op](value, threshold)
```

---

## 7. Phase 5 — Documentation & Handoff (Week 8)

### 7.1 Documentation Standards

| Document | Owner | Location | Update Trigger |
|----------|-------|----------|----------------|
| API Contract | DS → SWE | `contracts/ds-to-web.md` | Model schema change |
| Feature Schema | DS | `marts/processed/feature_columns.json` | Feature addition/removal |
| Model Cards | DS | `docs/model_cards/{model_name}.md` | New model registration |
| Pipeline README | DS | `README.md` | Architecture change |
| Changelog | DS | `CHANGELOG.md` | Any release |

### 7.2 Model Card Template

```markdown
# Model Card: {model_name}

## Overview
- **Task:** Genre Classification / Rating Regression
- **Architecture:** GMU / CatBoost
- **Version:** {version}
- **Date:** {date}

## Training Data
- **Source:** Gold layer Parquet exports
- **Sample:** {sample_percent}% development mode
- **Temporal Split:** Train < 2015, Val 2015-2018, Test 2019+

## Performance
| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Macro F1 | {value} | > 0.60 | {pass/fail} |
| RMSE | {value} | <= 0.55 | {pass/fail} |

## Intended Use
- **Primary:** Film genre recommendation for web application
- **Secondary:** Analytical insights for content strategy

## Limitations
- Trained on IMDb English-language titles
- Cold-start performance limited for new users
- Temporal bias toward pre-2019 content

## Ethical Considerations
- No PII in training data
- Genre labels reflect IMDb categorization (may contain biases)
- Rating predictions are estimates, not guarantees
```

---

## 8. Directory Structure

```
data-science/
├── config/
│   ├── __init__.py
│   ├── settings.yaml
│   └── environments.yaml
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── splitter.py
│   │   └── sampler.py
│   ├── features/
│   │   ├── __init__.py
│   │   ├── tabular.py
│   │   ├── text.py
│   │   ├── builder.py
│   │   └── schema.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── genre/
│   │   │   ├── __init__.py
│   │   │   ├── gmu.py
│   │   │   ├── bilstm.py
│   │   │   └── baselines.py
│   │   ├── rating/
│   │   │   ├── __init__.py
│   │   │   ├── catboost_regressor.py
│   │   │   └── baselines.py
│   │   └── recommender/
│   │       ├── __init__.py
│   │       ├── svd_model.py
│   │       ├── ncf_model.py
│   │       └── hybrid.py
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── metrics.py
│   │   ├── qerror.py
│   │   ├── temporal.py
│   │   ├── bias.py
│   │   └── gates.py
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── pipeline.py
│   │   └── feature_builder.py
│   ├── registry/
│   │   ├── __init__.py
│   │   └── model_registry.py
│   └── utils/
│       ├── __init__.py
│       ├── mlflow_utils.py
│       ├── visualization.py
│       ├── logging.py
│       ├── math.py
│       └── verification.py
├── notebooks/
│   ├── 01_eda.ipynb
│   ├── 02_feature_engineering.ipynb
│   ├── 03_modeling.ipynb
│   └── 04_analytics.ipynb
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_data_loader.py
│   ├── test_splitter.py
│   ├── test_features.py
│   ├── test_models.py
│   ├── test_inference.py
│   └── test_evaluation.py
├── scripts/
│   ├── run_pipeline.py
│   ├── export_marts.py
│   ├── validate_contracts.py
│   └── generate_model_cards.py
├── contracts/
│   ├── gold-to-ds.md
│   └── ds-to-web.md
├── docs/
│   ├── assessment_report.md
│   ├── phase3_overhaul_plan.md
│   ├── model_cards/
│   └── API.md
├── marts/
├── figures/
├── requirements.txt
├── setup.py
└── README.md
```

---

## 9. Config Management

### Environment Profiles

```yaml
# config/environments.yaml

development:
  development_mode: true
  sample_percent: 5
  optuna_trials: 5
  max_epochs: 15
  log_level: DEBUG

staging:
  development_mode: false
  sample_percent: 20
  optuna_trials: 10
  max_epochs: 30
  log_level: INFO

production:
  development_mode: false
  sample_percent: 100
  optuna_trials: 20
  max_epochs: 50
  log_level: WARNING
```

### Config Loader

```python
# src/config.py

import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import List

@dataclass
class TemporalSplits:
    train_year_max: int = 2014
    val_year_min: int = 2015
    val_year_max: int = 2018
    test_year_min: int = 2019

@dataclass
class FeatureConfig:
    tabular_columns: List[str] = None
    text_embedding_dim: int = 768
    rating_excluded_features: List[str] = None

@dataclass
class ElyssaConfig:
    development_mode: bool = True
    sample_percent: int = 5
    random_seed: int = 42
    temporal_splits: TemporalSplits = None
    features: FeatureConfig = None

def load_config(config_path: str = "config/settings.yaml") -> ElyssaConfig:
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    
    return ElyssaConfig(
        development_mode=raw["development_mode"]["enabled"],
        sample_percent=raw["development_mode"]["sample_percent"],
        random_seed=raw["development_mode"]["random_seed"],
        temporal_splits=TemporalSplits(**raw["temporal_splits"]),
        features=FeatureConfig(
            tabular_columns=raw["features"]["tabular_columns"],
            text_embedding_dim=raw["features"]["text_embedding_dim"],
            rating_excluded_features=raw["features"]["rating_excluded_features"],
        ),
    )
```

---

## 10. Quality Gates Enforcement

### Gate Checklist (Phase 3)

| Gate | Metric | Threshold | Enforcement Point | Automated? |
|------|--------|-----------|-------------------|------------|
| G.1 | Rating RMSE | ≤ 0.55 | `src/evaluation/gates.py` | ✅ Yes |
| G.2 | Genre Macro F1 | > 0.60 | `src/evaluation/gates.py` | ✅ Yes |
| G.3 | Temporal Generalization | Δ < 0.10 | `src/evaluation/temporal.py` | ✅ Yes |
| G.4 | MLflow Metric Naming | Regex compliant | `src/utils/mlflow_utils.py` | ✅ Yes |
| G.5 | Inference Latency | < 100ms p95 | `tests/test_inference.py` | ✅ Yes |
| G.6 | Artifacts Exist | All required | `src/utils/verification.py` | ✅ Yes |
| G.7 | No Target Leakage | Excluded features | `tests/test_features.py` | ✅ Yes |
| G.8 | Unit Tests Pass | 100% pass rate | `pytest` | ✅ Yes |
| G.9 | Contract Validation | Schema match | `scripts/validate_contracts.py` | ✅ Yes |
| G.10 | Duke's Aesthetic | Markdown format | Manual review | ❌ No |

### CI/CD Integration

```yaml
# .github/workflows/ds-tests.yml (for future GitHub Actions)

name: Data Science Tests

on:
  push:
    branches: [main, develop]
    paths:
      - 'data-science/**'
  pull_request:
    branches: [main]
    paths:
      - 'data-science/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python 3.13
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - name: Install dependencies
        run: |
          cd data-science
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: |
          cd data-science
          pytest tests/ -v --cov=src --cov-report=xml
      - name: Validate contracts
        run: |
          cd data-science
          python scripts/validate_contracts.py
```

---

## 11. Risk Register

| Risk | Likelihood | Impact | Mitigation | Owner |
|------|-----------|--------|------------|-------|
| Target leakage persists after fix | Low | Critical | Unit test `test_no_rating_leakage` enforced in CI | DS Agent |
| CatBoost performance degrades without leaked features | Medium | High | Re-run Optuna tuning with leakage-free features; adjust depth/iterations | DS Agent |
| Embedding time exceeds 2h at 5% sample | Medium | Medium | Implement `torch.inference_mode()`; consider ONNX export | DS Agent |
| MLflow DB corruption | Low | Medium | Backup `mlflow.db` before each run; implement WAL mode | DS Agent |
| Test data insufficient for cold-start | High | Medium | Use 5% sample for dev; full data for final validation | DS Agent |
| Config drift between notebooks | Medium | High | Single `settings.yaml` source of truth; validate at pipeline start | DS Agent |
| Breaking changes in contract | Low | High | Contract validation script runs in CI; version contracts | DS Agent |
| Hardware OOM at 5% | Low | Medium | Monitor RAM; fallback to 3% sample; use `PRAGMA memory_limit` | DS Agent |

---

## Appendix A: Migration Checklist

### Week 1 — Critical Fixes
- [ ] Remove `average_rating` and `num_votes` from rating feature vector
- [ ] Implement `safe_minmax()` helper
- [ ] Add verification cell to all notebooks
- [ ] Re-run full pipeline after leakage fix
- [ ] Validate metrics against quality gates

### Weeks 2–3 — Modular Refactoring
- [ ] Create `src/` directory structure with `__init__.py` files
- [ ] Extract `GoldDataLoader` class
- [ ] Extract `temporal_split()` function
- [ ] Extract `FeatureBuilder` class
- [ ] Extract `MlflowWrapper` class
- [ ] Refactor notebooks to thin wrappers
- [ ] Create `config/settings.yaml`

### Weeks 4–5 — Pipeline Orchestration
- [ ] Implement `scripts/run_pipeline.py`
- [ ] Implement `scripts/validate_contracts.py`
- [ ] Add YAML config loading
- [ ] Add structured logging
- [ ] Add `requirements.txt` with pinned versions

### Week 6 — Testing
- [ ] Write `conftest.py` with fixtures
- [ ] Write `test_splitter.py` (100% coverage)
- [ ] Write `test_features.py` (95% coverage)
- [ ] Write `test_models.py` (90% coverage)
- [ ] Write `test_inference.py` (95% coverage)
- [ ] Run `pytest --cov` and verify targets

### Week 7 — MLOps
- [ ] Implement `ModelRegistry` class
- [ ] Implement `QualityGateEvaluator` class
- [ ] Create model card templates
- [ ] Implement stage transitions
- [ ] Validate MLflow metric naming compliance

### Week 8 — Documentation & Handoff
- [ ] Update `contracts/ds-to-web.md` with final schema
- [ ] Write API documentation
- [ ] Write pipeline README
- [ ] Generate model cards for all models
- [ ] Final integration test with SWE module

---

*Plan generated from Phase 2 assessment. All tasks traceable to gaps identified in `assessment_report.md`.*
