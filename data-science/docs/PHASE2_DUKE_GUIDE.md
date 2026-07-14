# Phase 2: Duke's Manual Data Science – Codename: Elyssa

## Gold Layer Mart Export & Data Split Strategy

Source document: `Duke's Manual Data Science - Codename_ Elyssa.docx`

---

## Export Destination: RustFS S3 (`s3://gold-exports/`)

All gold tables exported as **Parquet** via DuckDB `COPY TO` + `aws s3 cp`.

```
s3://gold-exports/
├── full/                           # EDA — 100% data
│   ├── dim_title.parquet
│   ├── dim_person.parquet
│   ├── fact_title_rating.parquet
│   ├── fact_title_principal.parquet
│   ├── fact_performance.parquet
│   └── fact_episode.parquet
├── rating_regression/              # CatBoost — time-based split
│   ├── train.parquet               # pre-2015  (70%)
│   ├── val.parquet                 # 2015-2018 (15%)
│   └── test.parquet                # post-2018 (15%)
├── genre_classification/           # GMU — stratified by genre
│   ├── train.parquet               # (70%)
│   ├── val.parquet                 # (15%)
│   └── test.parquet                # (15%)
├── recommender/                    # Hybrid — time + cold-start
│   ├── train.parquet               # (60%)
│   ├── val.parquet                 # (20%)
│   └── test.parquet                # (20%)
└── network_analysis/               # SNA (Module 2)
    ├── actor_cooccurrence.parquet
    ├── director_genre_affinity.parquet
    └── writer_director_pairs.parquet
```

---

## Split Strategy Per ML Task

| Task | Split Method | Ratio | Rationale |
|------|-------------|-------|-----------|
| **Rating Regression** | Time-based (`start_year`) | 70/15/15 | pre-2015 train, 2015-2018 val, post-2018 test. Prevents temporal leakage. |
| **Genre Classification** | Stratified by genre | 70/15/15 | Handles label imbalance (Drama has 5x more titles than Documentary). Preserves rare-genre representation. |
| **Hybrid Recommender** | Time-based + cold-start | 60/20/20 | 20% test reserved for cold-start evaluation (users/titles unseen in train). |
| **Sentiment Analysis** | External dataset | N/A | Requires IMDb review text — not in current gold marts. Needs separate source. |

---

## Memory Budget (16GB RAM Hardware)

| Table | Rows | Parquet (disk) | Pandas (in-memory) | Risk |
|-------|------|---------------|-------------------|------|
| `dim_title` | 2.2M | ~150MB | ~600MB | Low |
| `dim_person` | 14.7M | ~250MB | ~1GB | Low |
| `fact_title_rating` | ~2M | ~80MB | ~300MB | Low |
| `fact_performance` | ~15M | ~400MB | ~1.5GB | Medium |
| `fact_episode` | ~6M | ~200MB | ~800MB | Medium |
| `fact_title_principal` | 83M | ~1.5GB | ~6-8GB | **High** |

### Recommended Memory-Safe Workflow

1. **DuckDB for EDA** — pushdown queries, never load full tables
2. **Polars for feature engineering** — lazy evaluation, out-of-core
3. **Load one split at a time** for ML training (train → val → test)
4. **Sample 10% for scatter plots** — enough for pattern visibility at 16GB
5. **Aggregate before loading** — GROUP BY in DuckDB, then load result

---

## Part A: EDA — Modules & Data Sources

### Module 1: Movies & TV Shows
**Tables:** `dim_title`, `fact_title_rating`, `fact_episode`
- Genre distribution and rating dynamics
- Temporal trends in ratings and production volume
- Runtime analysis (optimal runtime, trends by decade)
- Episode-level analysis for TV series

### Module 2: Principals, Crews & Persons
**Tables:** `dim_person`, `fact_performance`, `fact_title_principal`, `dim_title`
- Director influence analysis (productivity vs. quality)
- Actor collaboration networks (co-occurrence graphs)
- Writer and crew analysis (writer-director partnerships)
- Career trajectories and longevity

### Module 3: Miscellaneous
**Table:** `dim_title` (enriched with AKAS data)
- Documentary film analysis
- International distribution and regional patterns
- Title type comparisons
- Industry economics and success factors
- Adult content analysis (isAdult flag)

---

## Part B: Predictive Modeling

| Model | Architecture | Data Sources | Evaluation |
|-------|-------------|--------------|------------|
| **Genre Classification** | Gated Multimodal Unit (GMU) + KG embeddings | `dim_title` + external plot text | Macro-F1, ablation studies |
| **Rating Regression** | CatBoost + temporal features | `dim_title`, `fact_title_rating` | RMSE <= 0.55, time-based CV |
| **Sentiment Analysis** | Multiple Instance Learning (MIL) | External review dataset | EDU-level explanations |
| **Hybrid Recommender** | SVD + NCF + BERT content | `fact_title_principal`, `dim_title`, `dim_person` | Cold-start precision, <100ms latency |

### Baseline References
- haritanair/IMDB-Sentiment-Analysis (TF-IDF, LR, RF, SVM, LSTM, CNN, GRU)
- Priyanka-S2021/Movie-Rating-Prediction-DataScience-Project (XGBoost + SHAP)
- ParitKansal/IMDb-Movie-Classification (Word2Vec + BiLSTM)
- apraneeth20/Movie-Recommendation-System (content + collaborative + BERT + NCF + SVD)

---

## Part C: Analytic Efficiency & Deployment

- **C.1** Gold-Layer Evaluation Protocol (temporal partitions, multi-dimension metrics)
- **C.2** Performance Stress & Robustness Hardening
- **C.3** Hyperparameter Optimisation (Bayesian search + MLflow)
- **C.4** Production Handoff — Gold-Layer Gate (immutable barrier)
- **C.5** Aesthetic & Citation Grounding (every claim anchored to peer-reviewed reference)

---

## Tech Stack

| Category | Tools |
|----------|-------|
| Core ML | PyTorch, TensorFlow, Scikit-learn, XGBoost, CatBoost |
| Data | Pandas, Polars, DuckDB |
| Graph | PyTorch Geometric, DGL |
| Experiment | MLflow (tracking + registry) |
| Export | DuckDB COPY TO Parquet → RustFS S3 |
| Notebook | Jupyter Lab |

---

## Network Analysis Exports (Pre-computed Edge Lists)

| File | Schema | Purpose |
|------|--------|---------|
| `actor_cooccurrence.parquet` | (actor_a, actor_b, title_count, avg_rating) | Actor collaboration graph |
| `director_genre_affinity.parquet` | (nconst, genre, title_count, avg_rating) | Director-genre matrix |
| `writer_director_pairs.parquet` | (writer_nconst, director_nconst, collab_count, avg_rating) | Writer-director partnerships |
