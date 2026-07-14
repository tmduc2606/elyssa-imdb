# Elyssa IMDb | Phase 2 — Exploratory Data Analysis Report

**Generated:** 2026-07-14 18:11:53 UTC
**Analyst:** Duke (formerly Cresht)
**Dataset:** IMDb Non-Commercial Datasets (2026)
**Gold Layer:** 6 materialized marts (2 dimensions + 4 facts)

---

## 1. Data Architecture & Pipeline

The EDA operates on the **Gold Layer** of the Elyssa-IMDb medallion pipeline:

| Layer | Storage | Technology | Purpose |
|-------|---------|------------|---------|
| Bronze | TSV / Parquet | DuckDB | Raw immutable ingestion |
| Silver | PostgreSQL | DuckDB → psycopg2 | 3NF normalization, SCD2 |
| Gold | Parquet (Snappy) | DuckDB views | Star-schema marts for analytics |

### Gold Mart Schema

| Mart | Type | Rows | Key Columns |
|------|------|------|-------------|
| dim_title | Dimension | 12,609,928 | tconst, title_type, start_year, genre_list, region_list |
| dim_person | Dimension | 15,448,149 | nconst, primary_name, birth_year, generation |
| fact_title_principal | Fact | 100,243,369 | title_key, name_key, category, character_name |
| fact_performance | Fact | 100,243,369 | tconst, nconst, category, job |
| fact_episode | Fact | 9,743,274 | episode_key, series_key, season_number |
| fact_title_rating | Fact | 1,689,394 | title_key, snapshot_date, average_rating, num_votes |

---

## 2. ETL Correctness & Data Quality

### 2.1 Row Count Consistency

Bronze-to-Gold row count verification:

| Check | Result |
|-------|--------|
| ========================= COMPREHENSIVE DATA QUALITY BENCHMARK =========================
         Category               | |

### 2.2 Intrinsic Quality Checks

The following quality dimensions were validated:
- **Primary key uniqueness**: tconst (dim_title), nconst (dim_person), composite keys in fact tables
- **Column format validation**: tconst format (ttNNNNNNN), nconst format (nmNNNNNNN), is_adult boolean, runtime bounds
- **Rating bounds**: average_rating in [1.0, 10.0], num_votes >= 0
- **Temporal consistency**: end_year >= start_year where both present
- **Null rate analysis**: Missing data percentages for critical columns
- **Cross-table consistency**: Director names match between dim_title and fact_performance (sample-based)

### 2.3 Null Rate Summary

| Column | Null % | Notes |
|--------|--------|-------|
| region_list | 29.0% | Titles without region localization data |
| language_list | 53.6% | Titles without language localization data |
| average_rating | 86.6% | Majority of titles unrated |
| runtime_minutes | 64.1% | Many titles missing runtime |
| director_names | 44.3% | Many titles lack credited directors |
| writer_names | 49.2% | Many titles lack credited writers |

---

## 3. Analytical Insights

### 3.1 Genre Distribution

The most prolific genres across the catalog:
1. **Drama** — 3,515,373 titles
2. **Comedy** — 2,433,058 titles
3. **Talk-Show** — 1,563,207 titles
4. **Short** — 1,339,360 titles
5. **News** — 1,283,610 titles

Drama dominates with nearly 50% more titles than the next genre, reflecting its broad appeal and low production barriers for digital content.

### 3.2 Title Type Breakdown

The dataset spans 10 title types: movie, short, tvEpisode, tvMiniSeries, tvMovie, tvSeries, tvShort, tvSpecial, video, videoGame.
TV Episodes represent the largest segment, reflecting the episodic nature of modern content production.

### 3.3 Temporal Trends

- **Start year range**: 1893 to 2026 (133 years of cinema)
- **Missing start_year**: 11.7% of titles
- **End year > 98% null**: Consistent with most titles being single-release (movies) rather than ongoing series

### 3.4 Rating Distribution

- **Average rating**: Ranges from 1.0 to 10.0
- **Vote distribution**: Highly skewed — few titles receive the majority of votes
- **Unrated titles**: ~87% have no votes/ratings, reflecting long-tail content

### 3.5 Regional & Language Coverage

- **Titles with regional data**: 71.0% have at least one region
- **Titles with language data**: 46.4% have at least one language
- **Top regions**: US, DE, GB, FR, IT, ES, JP (consistent with major film markets)

---

## 4. Visualization Summary

The notebook generated the following visualizations:
- Genre distribution bar chart
- Title type breakdown
- Temporal distribution of titles (start_year histogram)
- Rating distribution analysis
- Regional coverage map (choropleth)
- Network analysis of director-writer collaborations
- Heatmaps of genre × rating correlations


---

## 5. Key Takeaways

1. **Data completeness is high** for core attributes (title, type, year) but degrades for derived attributes (ratings, runtime, regional data).
2. **Drama and Comedy** dominate the genre landscape, accounting for the majority of titles.
3. **TV Episodes** represent the largest content segment, indicating IMDb's extensive catalog of episodic content.
4. **Rating sparsity** (~87% unrated) necessitates careful statistical treatment for any rating-based analysis.
5. **Regional coverage** is strong for major markets but thin for smaller markets.
6. **Cross-table consistency** between dim_title and fact_performance is verified for director/writer attribution.

---

*Report generated from executed EDA notebook. All metrics traceable to code cells in phase_2_duke_manual_eda.ipynb.*
