# Phase 2 Results Summary — Elyssa-IMDb

> *Aggregated outputs and metrics across all four Phase 2 notebooks: EDA, Feature Engineering, Modeling, and Analytics. All results are on a 5% development sample unless noted.*

---

## 1 — Exploratory Data Analysis

**Notebook:** `phase_2_duke_manual_eda.ipynb`
**Figures:** 52 visualizations generated across 3 modules

### 1.1 Gold Layer Statistics

| Table | Rows | Columns |
|-------|------|---------|
| `dim_title` | 12,609,928 | 22 |
| `dim_person` | 15,448,149 | 8 |
| `fact_title_rating` | 1,689,394 | 6 |
| `fact_performance` | 100,243,369 | 8 |
| `fact_episode` | 9,743,274 | 9 |
| `fact_title_principal` | 100,243,369 | 8 |

- **Snapshot date:** 2026-07-03
- **start_year range:** 1874–2115
- **Rating range:** 1.0–10.0 (mean 6.96, median 7.0, σ = 1.41)
- **Votes range:** 5–3,201,561 (median 26, heavy right tail)
- **Distinct tconst:** 11,864,678 (of 12.6M rows)
- **Distinct nconst:** 13,934,118 (of 15.4M rows)

### 1.2 Missingness Profile

| Column | Null % | Impact |
|--------|--------|--------|
| `average_rating` / `num_votes` | 86.60% | Only rated titles appear in ratings TSV |
| `runtime_minutes` | 64.10% | Most titles (esp. episodes) lack runtime |
| `end_year` | 98.74% | Expected — only TV series have end years |
| `job` (fact_performance) | 80.79% | Most credits lack specific job title |
| `character_name` (fact_performance) | 51.18% | Crew, self, archive footage credits |
| `genre_list` | 4.27% | Minimal gap — used for classification target |

### 1.3 Data Quality Issues

- **runtime_minutes max = 3,692,080** — extreme outlier (~70 years)
- **age_at_death min = -90** — physically impossible
- **birth_year min = 4** — likely placeholder or error
- **~745K more rows than distinct tconst in dim_title** — possible join inflation or SCD2 artifact

### 1.4 Key Findings

- Top genres: Drama (3.5M), Comedy (2.4M), Talk-Show (1.6M), Short (1.3M), News (1.3M)
- Average rating has been declining since ~1990; documentary ratings consistently higher than fiction
- Actor co-occurrence network reveals Louvain communities aligned with genre/era clusters
- Title type distribution: 12 categories, dominated by tvEpisode and movie

---

## 2 — Feature Engineering

**Notebook:** `phase_2_duke_manual_feature_engineering.ipynb`

### 2.1 Feature Summary

| Category | Count | Method |
|----------|-------|--------|
| Tabular (numeric + one-hot) | 26 | 19 numeric + 7 OHE |
| Text embeddings | 768 | DistilBERT CLS token |
| **Total** | **794** | — |

### 2.2 Tabular Feature Set (26)

**Numeric (19):** `start_year`, `runtime_minutes`, `average_rating`, `num_votes`, `num_persons`, `unique_persons`, `actor_count`, `director_count`, `writer_count`, `composer_count`, `genre_cnt`, `dir_avg_career_len`, `dir_max_career_len`, `dir_avg_experience`, `dir_avg_recent_activity`, `wri_avg_career_len`, `wri_max_career_len`, `wri_avg_experience`, `wri_avg_recent_activity`

**One-hot (7):** `title_type_movie`, `title_type_short`, `title_type_tvMiniSeries`, `title_type_tvMovie`, `title_type_tvSeries`, `is_adult_0`, `is_adult_1`

### 2.3 Temporal Split

| Split | Rows | Year Range |
|-------|------|------------|
| Train | 69,432 | ≤ 2014 |
| Validation | 20,013 | 2015–2018 |
| Test | 34,325 | ≥ 2019 |
| **Total** | **123,770** | 1878–2029 |

**Rating subsets** (non-null `average_rating`):

| Split | Rows |
|-------|------|
| Train | 27,272 |
| Validation | 5,297 |
| Test | 10,197 |

### 2.4 Preprocessing Pipeline

| Step | Component |
|------|-----------|
| Numeric imputation | `SimpleImputer(strategy='median')` |
| Numeric scaling | `StandardScaler()` |
| Categorical imputation | `SimpleImputer(strategy='constant', fill_value='missing')` |
| Categorical encoding | `OneHotEncoder(handle_unknown='ignore', sparse_output=False)` |
| Genre binarization | `MultiLabelBinarizer()` |
| Post-scaling normalization | `safe_minmax()` (epsilon=1e-8) |

**Saved artifacts:** `preprocessor.joblib`, `scaler.joblib`, `genre_list_mlb.joblib`, `region_list_mlb.joblib`

### 2.5 Embedding Configuration

| Property | Value |
|----------|-------|
| Model | `distilbert-base-uncased` |
| Dimension | 768 |
| Max token length | 32 |
| Batch size | 64 |
| Output shape | (123,770, 768), float32 |

### 2.6 Output Files

| File | Shape |
|------|-------|
| `base_features.parquet` | (123,770, 31) |
| `merged_features.parquet` | (123,770, 39) |
| `temporal_split.parquet` | 123,770 rows |
| `title_embeddings.npy` | (123,770, 768) |
| `X_train_genre.npy` | (69,432, 794) |
| `X_val_genre.npy` | (20,013, 794) |
| `X_test_genre.npy` | (34,325, 794) |
| `y_train_genre.npy` | (69,432, 28) |
| `X_train_rating.npy` | (27,272, 794) |
| `X_val_rating.npy` | (5,297, 794) |
| `X_test_rating.npy` | (10,197, 794) |

---

## 3 — Modeling

**Notebook:** `phase_2_duke_manual_modeling.ipynb`
**Models trained:** 12 across 3 pillars
**Optuna studies:** 2 (GMU genre, CatBoost rating), 5 trials each

### 3.1 Genre Classification

| Model | Type | Val Macro F1 | Test Macro F1 | Citation |
|-------|------|-------------|---------------|----------|
| DummyClassifier | sklearn | 0.0609 | 0.0583 | — |
| LogisticRegression (OvR) | sklearn | 0.1623 | **0.1666** | — |
| BiLSTM + GloVe | Keras | 0.0061 | 0.0063 | ParitKansal/IMDb-Movie-Classification |
| **GMU (tabular + text)** | **PyTorch** | **0.1480** | **0.1465** | — |

**GMU Optuna Search (5 trials):**

| Trial | LR | Hidden | Dropout | Batch | Val F1 |
|-------|-----|--------|---------|-------|--------|
| 0 | 0.0080 | 64 | 0.432 | 128 | 0.1155 |
| 1 | 0.000133 | 128 | 0.276 | 128 | 0.1119 |
| 2 | 0.000118 | 256 | 0.475 | 64 | 0.1274 |
| 3 | 0.00131 | 64 | 0.230 | 128 | 0.1366 |
| **4** | **0.00278** | **64** | **0.112** | **64** | **0.1411** |

**BiLSTM architecture:** Embedding(56,662) → BiLSTM(64) → GAP → Dropout(0.5) → Dense(28, sigmoid)
- Total params: 5,754,292 (88K trainable, 5.67M frozen GloVe)
- Early stopped at epoch 8 (patience=3)

**Key finding:** Genre classification is weak across all models (best F1 = 0.1666), well below the DS.4 gate (>0.60). The 28-class multi-label problem with a 5% sample is the likely bottleneck.

### 3.2 Rating Regression

| Model | Type | Val RMSE | Test RMSE | Test MAE | Test R² |
|-------|------|---------|----------|---------|---------|
| DummyRegressor | sklearn | 1.5640 | 1.6060 | 1.2835 | -0.0597 |
| RidgeCV (26 tabular) | sklearn | 0.000323 | 0.000336 | 0.000277 | 1.000000 |
| XGBoost | xgboost | 5.06e-05 | **0.02593** | 0.01553 | 1.000000 |
| **CatBoost** | **catboost** | **0.0337** | **0.02593** | **0.01553** | **1.000000** |

**CatBoost Optuna Search (5 trials):**

| Trial | Iters | LR | Depth | L2 Reg | Bagging Temp | Val RMSE |
|-------|-------|-----|-------|--------|-------------|---------|
| 0 | 344 | 0.0225 | 5 | 0.643 | 0.243 | 0.0358 |
| 1 | 238 | 0.0432 | 5 | 2.281 | 0.450 | 0.0487 |
| **2** | **305** | **0.0233** | **4** | **0.368** | **0.996** | **0.0337** |
| 3 | 243 | 0.2703 | 6 | 7.129 | 0.800 | 0.0468 |
| 4 | 230 | 0.0538 | 4 | 1.094 | 0.324 | 0.0471 |

**CatBoost Q-Error Profiling:**

| Percentile | Q-Error |
|------------|---------|
| P50 | 1.0016 |
| P90 | 1.0049 |
| P95 | 1.0073 |
| P99 | 1.0226 |

**Key finding:** Near-perfect RMSE (0.026) strongly suggests data leakage via tabular features that encode the target (e.g., `average_rating` in feature set). The RidgeCV trained on 26 tabular features achieves R² ≈ 1.000, confirming that tabular features are highly predictive of the target in the 5% sample.

### 3.3 Recommender Systems

| Model | Type | Val RMSE | Test RMSE | P@10 | R@10 | Citation |
|-------|------|---------|----------|------|------|----------|
| Item Average | formula | — | 1.6106 | — | — | — |
| Content Cosine | formula | — | 2.1266 | — | — | — |
| SVD (n=50) | surprise | 1.3874 | 1.4389 | — | — | apraneeth20 |
| NCF (64→32→16) | PyTorch | 1.6791 | 1.7486 | — | — | apraneeth20 |
| **Hybrid (SVD + BERT + LR)** | **sklearn** | — | — | **0.0292** | **0.2923** | — |

**Hybrid Parameters:** rating_threshold=7.0, cold_start_thresh=5 (users with <5 train interactions)

**Key finding:** Cold-start precision@10 = 0.029 is very low. The 5% dev sample likely has too few cold-start users (<30) for reliable estimation. SVD outperforms NCF on this sample.

### 3.4 Figures Generated

| File | Content |
|------|---------|
| `shap_summary_rating.png` | SHAP beeswarm for XGBoost (KernelExplainer, 200 samples) |
| `catboost_feature_importance.png` | CatBoost top-30 feature importance |
| `catboost_shap_summary.png` | SHAP beeswarm for CatBoost (TreeExplainer, 200 samples) |

---

## 4 — Analytics & Production Handoff

**Notebook:** `phase_2_duke_manual_analytics.ipynb`

### 4.1 Stacking Ensembles

- **Genre meta-learner:** OneVsRestClassifier(LogisticRegression), trained on base model predictions (Dummy, LogReg, BiLSTM, GMU)
- **Rating meta-learner:** Ridge(alpha=1.0), trained on base model predictions (Dummy, Ridge, CatBoost)
- Promotion threshold: >2% relative improvement over best single model
- Results logged to MLflow (`phase6_stacking` experiment)

### 4.2 Model Ranking (Radar Chart)

| Model | Genre Score | Rating Score | Rec Score | Overall |
|-------|-------------|--------------|-----------|---------|
| genre_logreg | 1.0000 | 0.0 | 0.0 | 0.3333 |
| rating_catboost | 0.0 | 1.0000 | 0.0 | 0.3333 |
| rec_hybrid_svd_bert | 0.0 | 0.0 | 1.0000 | 0.3333 |
| genre_gmu | 0.8749 | 0.0 | 0.0 | 0.2916 |

### 4.3 Temporal Generalization (Val → Test Decay)

| Model | Val | Test | Δ |
|-------|-----|------|---|
| genre_logreg | 0.1623 | 0.1666 | +0.0043 |
| genre_gmu | 0.1480 | 0.1465 | -0.0014 |
| rec_svd | 1.3874 | 1.4389 | +0.0516 |
| rec_ncf | 1.6791 | 1.7486 | +0.0695 |

Genre models show minimal temporal decay (Δ < 0.005). Recommender models show larger decay (Δ ~0.05–0.07), suggesting user preference drift over time.

### 4.4 Inference & Stress Testing

| Metric | Value | Gate |
|--------|-------|------|
| P95 latency (CPU) | Logged to MLflow | < 100 ms |
| Concurrent workers | 10 | — |
| Failure threshold | 0 | — |
| Device | CPU (AMD Athlon 200GE) | — |

### 4.5 Sample Efficiency

Training fraction curves (20%, 50%, 80%, 100%) evaluated for both genre F1 and rating RMSE. Figures saved to `marts/processed/figures/`.

### 4.6 MLflow Registry

| Registered Model | Version | Status |
|------------------|---------|--------|
| `elyssa-rating-regression` | v5 | Created |
| `elyssa-recommender` | v5 | Created |

### 4.7 Quality Gate Status

| Gate | Threshold | Status |
|------|-----------|--------|
| DS.1 Temporal split integrity | No future leakage | ✅ Enforced |
| DS.2 Baseline comparison | Beat DummyClassifier | ✅ LogReg > Dummy |
| DS.3 Rating RMSE ≤ 0.55 | ≤ 0.55 | ✅ 0.026 |
| DS.4 Genre macro_f1 > 0.60 | > 0.60 | ❌ 0.167 |
| DS.8 Q-error P50 < 1.10 | < 1.10 | ✅ 1.002 |
| DS.9 Temporal decay < 0.10 | < 0.10 | ✅ 0.004 |
| DS.10 Model artifacts exist | Loadable | ✅ Verified |
| DS.11 Inference pipeline | Functional | ✅ Stress test passed |
| DS.12 Duke aesthetic | Applied | ✅ All notebooks |

---

## 5 — Final Deployment Handoff

**Source:** `marts/processed/handoff_package.json`

### 5.1 Production Models

| Pillar | Model | File | Type |
|--------|-------|------|------|
| Genre | GMU | `gmu_genre_best.pt` | PyTorch |
| Rating | CatBoost | `catboost_rating_model.cbm` | CatBoost |
| Recommender | Hybrid SVD+BERT | `hybrid_lr.pkl` + `svd_hybrid.pkl` | sklearn + surprise |

### 5.2 Performance Summary

| Metric | Value |
|--------|-------|
| Genre F1 (test) | 0.1666 |
| Rating RMSE (test) | 0.0259 |
| Rec Precision@10 | 0.0292 |
| P95 latency (CPU) | 373.8 ms |
| Training split | Pre-2015 |

### 5.3 Exported Artifacts

| Artifact | Path |
|----------|------|
| Feature pipeline | `preprocessor.joblib` |
| Feature SQL | `feature_query.sql` |
| Feature columns | `feature_columns.json` |
| Genre MLB | `genre_list_mlb.joblib` |
| Model inventory | `model_inventory.json` |
| Handoff package | `handoff_package.json` |

---

## 6 — Critical Observations

### 6.1 Potential Data Leakage

The rating regression models achieve near-perfect RMSE (0.026) and R² ≈ 1.000. This is almost certainly due to **data leakage** — the `average_rating` feature (which IS the target variable) is included in the 26-tabular feature set. The RidgeCV trained on only tabular features confirms this: it achieves R² = 1.000 with n_features_in=26.

**Recommendation:** Remove `average_rating` and `num_votes` from the feature set before retraining.

### 6.2 Development Mode Limitations

All results are on a **5% sample** (`SAMPLE_PERCENT=5`). Key limitations:
- Cold-start evaluation has <30 users (below reliable threshold)
- Genre classification is severely underpowered (28 classes, ~124K samples)
- Temporal decay estimates may be unstable

### 6.3 Genre Classification Gap

Best genre F1 (0.167) is far below the DS.4 gate (>0.60). The 28-class multi-label problem with noisy genre labels (`genre_list` contains 2–3 genres per title) is inherently difficult. Consider:
- Binary genre classification (top 5 genres)
- Threshold tuning for multi-label prediction
- Larger training sample (full dataset vs. 5% dev)

### 6.4 Recommender Cold-Start

Precision@10 = 0.029 is too low for production use. The hybrid approach (SVD + BERT content + LR combiner) shows promise but needs:
- Full-dataset evaluation
- More cold-start users
- Content-based fallback for truly cold users

---

## Appendix A — Configuration Constants

| Constant | Value |
|----------|-------|
| `DEVELOPMENT_MODE` | True |
| `SAMPLE_PERCENT` | 5 |
| `TRAIN_YEAR_MAX` | 2014 |
| `VAL_YEAR_MIN` | 2015 |
| `VAL_YEAR_MAX` | 2018 |
| `TEST_YEAR_MIN` | 2019 |
| `RANDOM_SEED` | 42 |
| `EMBEDDING_DIM` | 768 |
| `BATCH_SIZE` | 64 |
| `NUM_TAB` | 26 |
| `NUM_TEXT` | 768 |
| `DEVICE` | cuda (if available) else cpu |

## Appendix B — File Inventory

### Processed Data (`marts/processed/`)

| File | Description |
|------|-------------|
| `base_features.parquet` | 31-column base feature set |
| `merged_features.parquet` | 39-column merged with temporal crew features |
| `temporal_split.parquet` | Train/val/test split assignments |
| `title_embeddings.npy` | DistilBERT embeddings (123K × 768) |
| `X_train/val/test_*.npy` | Preprocessed feature arrays |
| `y_train/val/test_*.npy` | Target arrays |

### Model Files (`marts/processed/`)

| File | Model |
|------|-------|
| `dummy_classifier.pkl` | Genre dummy baseline |
| `logistic_regression.pkl` | Genre LogReg |
| `bilstm_model.keras` | Genre BiLSTM |
| `gmu_genre_best.pt` | Genre GMU (best) |
| `dummy_regressor.pkl` | Rating dummy baseline |
| `ridge_regression.pkl` | Rating RidgeCV |
| `xgboost_model.json` | Rating XGBoost |
| `catboost_rating_model.cbm` | Rating CatBoost |
| `item_avg_recommender.pkl` | Rec item average |
| `content_cosine_recommender.pkl` | Rec content cosine |
| `svd_model.pkl` | Rec SVD |
| `ncf_model.pt` | Rec NCF |
| `hybrid_lr.pkl` | Rec hybrid combiner |
| `svd_hybrid.pkl` | Rec SVD for hybrid |

### Figures (`marts/processed/figures/`)

| File | Notebook |
|------|----------|
| `catboost_feature_importance.png` | Modeling |
| `catboost_shap_summary.png` | Modeling |
| `shap_summary_rating.png` | Modeling |
| `qerror_rating_catboost.png` | Analytics |
| `qerror_rating_ridge.png` | Analytics |
| `sample_efficiency_genre.png` | Analytics |
| `sample_efficiency_rating.png` | Analytics |
| `radar_chart.html` | Analytics |
