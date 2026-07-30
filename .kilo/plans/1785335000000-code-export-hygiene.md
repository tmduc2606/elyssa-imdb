# Plan: Code & Export Hygiene — Phase 2 Production Data Science

## Goal

Re-organise the four DS notebooks and their outputs to meet production-grade standards: uniform imports, reusable variables, centralised exports, relocated classes, and a clean `marts/` structure. No changes to logic or results.

---

## Current State Summary

### `data-science/src/` (already exists and is well-structured)
- `models/genre/` — baselines, bilstm, **gmu.py** (has `GatedMultimodalUnit`), xgboost
- `models/rating/` — baselines, catboost_regressor, xgboost
- `models/recommender/` — **hybrid.py** (has hybrid functions), **ncf_model.py** (has `NCF`), svd_model
- `features/`, `evaluation/`, `inference/`, `registry/`, `utils/`

### Classes defined inline in notebooks (should be moved to `src/`)
| Class | Notebook | Line (raw JSON) | Target |
|-------|----------|-----------------|--------|
| `ItemAverageRecommender` | modeling | ~589 | `src/models/recommender/item_avg.py` |
| `CosineRecommender` | modeling | ~610 | `src/models/recommender/cosine.py` |
| `NCF` | modeling | ~1344 | Already in `src/models/recommender/ncf_model.py` |
| `GatedMultimodalUnit` | modeling | ~1549 | Already in `src/models/genre/gmu.py` |
| `GatedMultimodalUnit` | analytics | ~1166 | Replace with import from `src/models/genre/gmu.py` |

### Current export locations (scattered)
| Artifact type | Current location | Target location |
|---------------|------------------|-----------------|
| EDA figures | `marts/processed/eda_cell*.png` | `figures/eda/` |
| Modeling figures | `marts/processed/modeling_cell*.png` | `figures/modeling/` |
| Analytics figures | `marts/processed/analytics_cell*.png`, `qerror_*.png` | `figures/analytics/` |
| Models (.pt, .pkl, .cbm, .keras) | `marts/processed/` | `notebooks/models/{genre,rating,recommender}/` |
| Feature artifacts (.parquet, .npy, .joblib) | `marts/processed/` | `notebooks/models/{genre,rating,recommender}/` |
| Baselines (.json) | `marts/processed/` | `notebooks/models/{genre,rating,recommender}/` |
| Gold Parquet | `marts/full/` | `marts/gold/` (rename) |

---

## Execution Steps

### Step 1: Directory Restructuring

#### 1.1 Create new directories
```
data-science/
├── figures/
│   ├── eda/
│   ├── feature_engineering/
│   ├── modeling/
│   └── analytics/
└── notebooks/
    └── models/
        ├── genre/
        ├── rating/
        └── recommender/
```

#### 1.2 Move existing figures
- Move all files from `data-science/figures/*.png` → `data-science/figures/eda/`
- Move all `marts/processed/eda_cell*.png` → `data-science/figures/eda/`
- Move all `marts/processed/modeling_cell*.png` → `data-science/figures/modeling/`
- Move all `marts/processed/analytics_cell*.png`, `qerror_*.png`, `sample_efficiency_*.png`, `radar_chart.html` → `data-science/figures/analytics/`
- Remove empty `marts/processed/figures/` if it exists

#### 1.3 Rename Gold layer
- Rename `marts/full/` → `marts/gold/`
- Update all notebook references from `marts/full/` to `marts/gold/`

#### 1.4 Move model/feature artifacts
- Move `marts/processed/*.pt` → `notebooks/models/genre/` or `notebooks/models/recommender/`
- Move `marts/processed/*.pkl` → `notebooks/models/{genre,rating,recommender}/`
- Move `marts/processed/*.cbm` → `notebooks/models/rating/`
- Move `marts/processed/*.keras` → `notebooks/models/genre/`
- Move `marts/processed/*.joblib` → `notebooks/models/{genre,rating,recommender}/`
- Move `marts/processed/*.parquet` (features, splits) → `notebooks/models/{genre,rating,recommender}/`
- Move `marts/processed/*.npy` → `notebooks/models/{genre,rating,recommender}/`
- Move `marts/processed/*.json` (baselines, inventory, feature_columns) → `notebooks/models/{genre,rating,recommender}/`
- Keep `marts/processed/ensemble_models/` → move to `notebooks/models/ensemble/`

#### 1.5 Clean `marts/`
- After moving artifacts, `marts/processed/` should be empty → delete it
- `marts/processed_archived/` → delete entirely (or keep if user wants to preserve, but the plan says remove stale files)
- `marts/` should contain only: `bronze/`, `silver/`, `gold/`

---

### Step 2: Class Relocation to `src/`

#### 2.1 Create new src modules
- **`src/models/recommender/item_avg.py`** — move `ItemAverageRecommender` class from modeling notebook
- **`src/models/recommender/cosine.py`** — move `CosineRecommender` class from modeling notebook

#### 2.2 Update `src/models/__init__.py` and subpackage `__init__.py` files
- Export the new classes so notebooks can import them cleanly

#### 2.3 Replace inline definitions in notebooks
- **modeling.ipynb:** Remove inline `ItemAverageRecommender`, `CosineRecommender`, `NCF`, `GatedMultimodalUnit`. Replace with:
  ```python
  from elyssa.src.models.recommender.item_avg import ItemAverageRecommender
  from elyssa.src.models.recommender.cosine import CosineRecommender
  from elyssa.src.models.recommender.ncf_model import NCF
  from elyssa.src.models.genre.gmu import GatedMultimodalUnit
  ```
- **analytics.ipynb:** Remove inline `GatedMultimodalUnit`. Replace with import from `src/models/genre/gmu.py`.

---

### Step 3: Notebook Import Consolidation

#### 3.1 First code cell of each notebook
Move ALL `import` and `from ... import` statements to the very first code cell. Ensure:
- No duplicate imports across cells
- No unused imports
- Consistent import style (standard lib → third-party → local)

#### 3.2 Shared constants
Extract common constants to a shared location or ensure they're defined identically in each notebook's first cell:
- `DEVELOPMENT_MODE`, `SAMPLE_PERCENT`, `TRAIN_YEAR_MAX`, `VAL_YEAR_MIN`, `VAL_YEAR_MAX`, `TEST_YEAR_MIN`, `RANDOM_SEED`
- `DATA_DIR`, `PROCESSED_DIR`, `FIGURES_DIR`, `MODELS_DIR`

#### 3.3 New path constants (add to first cell of each notebook)
```python
from pathlib import Path
NOTEBOOK_DIR = Path.cwd()
DATA_DIR = (NOTEBOOK_DIR.parent / "marts").resolve()
PROCESSED_DIR = DATA_DIR / "processed"  # legacy, may be unused after cleanup
MODELS_DIR = (NOTEBOOK_DIR.parent / "notebooks" / "models").resolve()
FIGURES_DIR = (NOTEBOOK_DIR.parent / "figures").resolve()
GOLD_DIR = DATA_DIR / "gold"
```

---

### Step 4: Figure Export Overhaul

#### 4.1 Update `save_figures()` in EDA notebook
The EDA notebook already has a `save_figures()` function at the end. Update it to:
```python
def save_figures(plot_dict: dict, folder: str = "figures", formats: list = None) -> None:
    if formats is None:
        formats = ["png"]
    root = Path.cwd().resolve().parent
    target_folder = root / "figures" / "eda"  # hardcoded per notebook
    target_folder.mkdir(parents=True, exist_ok=True)
    ...
```

#### 4.2 Update inline `plt.savefig()` calls in all notebooks
- **EDA notebook:** Replace `PROCESSED_DIR / 'eda_cellXX.png'` → `FIGURES_DIR / 'eda' / 'eda_cellXX.png'`
- **Modeling notebook:** Replace `PROCESSED_DIR / 'modeling_cellXX.png'` → `FIGURES_DIR / 'modeling' / 'modeling_cellXX.png'`
- **Analytics notebook:** Replace `PROCESSED_DIR / 'analytics_cellX.png'`, `qerror_*.png` → `FIGURES_DIR / 'analytics' / ...`

#### 4.3 Remove old export paths
- Ensure no `plt.savefig(PROCESSED_DIR / ...)` calls remain
- Ensure no figures are written to `marts/processed/`

---

### Step 5: Model & Feature Storage Relocation

#### 5.1 Update `MODELS_DIR` in each notebook
Add to first cell:
```python
MODELS_DIR = (NOTEBOOK_DIR.parent / "notebooks" / "models").resolve()
MODELS_DIR.mkdir(parents=True, exist_ok=True)
```

#### 5.2 Update model/artifact save paths
Replace all `PROCESSED_DIR / 'filename'` with the appropriate `MODELS_DIR / 'pillar' / 'filename'`:
- Genre models → `MODELS_DIR / 'genre' / ...`
- Rating models → `MODELS_DIR / 'rating' / ...`
- Recommender models → `MODELS_DIR / 'recommender' / ...`
- Shared/ensemble → `MODELS_DIR / 'ensemble' / ...`

#### 5.3 Update model/artifact load paths
Replace all `PROCESSED_DIR / 'filename'` load calls with the new paths.

#### 5.4 Files to update per notebook

**Feature engineering notebook:**
- `base_features.parquet` → `MODELS_DIR / 'genre' / 'base_features.parquet'` (or shared)
- `merged_features.parquet` → `MODELS_DIR / 'shared' / 'merged_features.parquet'`
- `preprocessor.joblib` → `MODELS_DIR / 'shared' / 'preprocessor.joblib'`
- `scaler.joblib` → `MODELS_DIR / 'shared' / 'scaler.joblib'`
- `*_mlb.joblib` → `MODELS_DIR / 'shared' / ...`
- `temporal_split.parquet` → `MODELS_DIR / 'shared' / 'temporal_split.parquet'`
- `split_indices.parquet` → `MODELS_DIR / 'shared' / 'split_indices.parquet'`

**Modeling notebook:**
- `gmu_genre_best.pt` → `MODELS_DIR / 'genre' / 'gmu_genre_best.pt'`
- `bilstm_model.keras` → `MODELS_DIR / 'genre' / 'bilstm_model.keras'`
- `catboost_rating_model.cbm` → `MODELS_DIR / 'rating' / 'catboost_rating_model.cbm'`
- `item_avg_recommender.pkl` → `MODELS_DIR / 'recommender' / 'item_avg_recommender.pkl'`
- `content_cosine_recommender.pkl` → `MODELS_DIR / 'recommender' / 'content_cosine_recommender.pkl'`
- `svd_model.pkl` → `MODELS_DIR / 'recommender' / 'svd_model.pkl'`
- `ncf_model.pt` → `MODELS_DIR / 'recommender' / 'ncf_model.pt'`
- `svd_hybrid.pkl`, `hybrid_lr.pkl` → `MODELS_DIR / 'recommender' / ...`
- `dummy_classifier.pkl`, `logistic_regression.pkl` → `MODELS_DIR / 'genre' / ...`
- `dummy_regressor.pkl`, `ridge_regression.pkl` → `MODELS_DIR / 'rating' / ...`
- `*_baseline.json` → `MODELS_DIR / '{genre,rating,recommender}' / ...`
- `feature_columns.json` → `MODELS_DIR / 'shared' / 'feature_columns.json'`

**Analytics notebook:**
- `model_inventory.json` → `MODELS_DIR / 'shared' / 'model_inventory.json'`
- `stacking_meta_*.pkl` → `MODELS_DIR / '{genre,rating}' / ...`
- All model loading paths updated accordingly

---

### Step 6: Marts Folder Cleanup

#### 6.1 Rename Gold layer
```bash
git mv data-science/marts/full data-science/marts/gold
```
Update all notebook references from `marts/full/` to `marts/gold/`.

#### 6.2 Remove stale directories
```bash
rm -rf data-science/marts/processed
rm -rf data-science/marts/processed_archived
```

#### 6.3 Final `marts/` structure
```
data-science/marts/
├── bronze/        (populated by pipeline, may be empty initially)
├── silver/        (populated by pipeline, may be empty initially)
├── gold/          (bind mount from Airflow export)
│   ├── dim_title.parquet
│   ├── dim_person.parquet
│   ├── fact_episode.parquet
│   ├── fact_performance.parquet
│   ├── fact_title_principal.parquet
│   ├── fact_title_rating.parquet
│   └── _MANIFEST.json
```

---

### Step 7: General Hygiene

#### 7.1 Remove dead code and commented-out blocks
- Scan all notebooks for `# TODO`, `# FIXME`, `# DEBUG`, commented-out code blocks
- Remove or fix them

#### 7.2 Fix typos
- Scan for common typos in variable names, string literals, comments

#### 7.3 Ensure single definition of variables
- Check that `DATA_DIR`, `PROCESSED_DIR`, `con`, `views`, `sample_clause`, `DEVELOPMENT_MODE`, etc. are defined exactly once per notebook
- Remove duplicate definitions

#### 7.4 Validate all paths
- After restructuring, every `Path(...)` reference in all notebooks must resolve correctly
- No broken references to `marts/processed/` or `marts/full/`

---

### Step 8: Validation

#### 8.1 Static validation (no notebook execution)
- Parse all four notebooks and verify:
  - No `PROCESSED_DIR` references remain for output paths
  - No `marts/full/` references remain
  - No `marts/processed/` references remain for output
  - All `plt.savefig()` calls point to `FIGURES_DIR / '{subfolder}'`
  - All `joblib.dump()` / `torch.save()` / `.to_parquet()` calls point to `MODELS_DIR`
  - All imports of `ItemAverageRecommender`, `CosineRecommender`, `NCF`, `GatedMultimodalUnit` come from `src/`
  - First cell of each notebook contains all imports

#### 8.2 File system validation
- Verify target directories exist
- Verify no stale files remain in old locations
- Verify `marts/` contains only `bronze/`, `silver/`, `gold/`

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Notebook execution fails after path changes | Implementation agent should update ALL path references atomically per notebook |
| `src/models/` imports fail due to missing `__init__.py` exports | Update all `__init__.py` files in `src/models/` and subpackages |
| `processed_archived/` contains needed files | Confirm with user; if yes, move to `notebooks/models/archived/` before deletion |
| Analytics notebook GMU import fails | Ensure `src/models/genre/gmu.py` is compatible; the src version is more general and should work |

---

## Open Questions (resolved)

1. **`marts/full/` → `marts/gold/`** — User confirmed: rename
2. **Analytics GMU class** — User confirmed: use src version with import
3. **Silver fallback scope** — Row counts only (from previous task)

---

## Files Changed (summary)

### New files to create
- `src/models/recommender/item_avg.py`
- `src/models/recommender/cosine.py`
- (Update existing `__init__.py` files)

### Notebooks to modify
- `phase_2_duke_manual_eda.ipynb`
- `phase_2_duke_manual_feature_engineering.ipynb`
- `phase_2_duke_manual_modeling.ipynb`
- `phase_2_duke_manual_analytics.ipynb`

### Directories to rename/move/delete
- `marts/full/` → `marts/gold/`
- `marts/processed/` → delete after moving contents
- `marts/processed_archived/` → delete
- Create `figures/{eda,feature_engineering,modeling,analytics}/`
- Create `notebooks/models/{genre,rating,recommender,ensemble,shared}/`

### Files to move
- All `marts/processed/*` → `notebooks/models/**`
- All `figures/*.png` → `figures/eda/`
- All `marts/processed/eda_cell*.png` → `figures/eda/`
- All `marts/processed/modeling_cell*.png` → `figures/modeling/`
- All `marts/processed/analytics_cell*.png`, `qerror_*.png`, etc. → `figures/analytics/`
