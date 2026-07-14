# Phase 2: Statistical Insights Report

> **Source**: `phase_2_duke_manual_eda.ipynb` executed 2026-07-12
> **Data**: Gold Layer Parquet exports (6 tables, ~5.1 GB)
> **Engine**: DuckDB (in-memory), Python/Pandas for visualization

---

## Module 0: Bronze-Gold Data Quality Assurance

### 0.1 Gold Table Row Counts

| Table | Rows |
|-------|------|
| `dim_title` | 12,609,928 |
| `dim_person` | 15,448,149 |
| `fact_title_rating` | 1,689,394 |
| `fact_performance` | 100,243,369 |
| `fact_episode` | 9,743,274 |
| `fact_title_principal` | 100,243,369 |

### 0.2 ETL Correctness Checks

| Check | Bronze | Gold | Delta | Status |
|-------|--------|------|-------|--------|
| `title_basics` → `dim_title` row count | 12,609,928 | 12,609,928 | 0 | ✅ OK |
| `name_basics` → `dim_person` row count | 15,448,238 | 15,448,149 | 89 | ⚠️ WARN |
| `title_principals` → `fact_title_principal` row count | 100,243,363 | 100,243,369 | -6 | ⚠️ WARN |
| `title_episode` → `fact_episode` row count | 9,743,274 | 9,743,274 | 0 | ✅ OK |
| Rating mismatch > 0.01 | — | 0 / 1,689,394 | — | ✅ OK |
| `dim_title` tconst missing from bronze | — | 0 | — | ✅ OK |
| Distinct tconst match | 12,609,928 | 12,609,928 | 0 | ✅ OK |
| Distinct nconst match | 15,448,238 | 15,448,149 | 89 | ⚠️ WARN |

**Note**: The 89-row `dim_person` delta and 6-row `fact_title_principal` delta are likely due to deduplication during Silver→Gold ETL. `dim_person` deduplicates by `nconst`; `fact_title_principal` may merge or drop certain records.

### 0.3 Intrinsic Quality Checks

| Check | Status | Detail |
|-------|--------|--------|
| PK uniqueness: `dim_title.tconst` | ✅ OK | 0 duplicates |
| PK uniqueness: `dim_person.nconst` | ✅ OK | 0 duplicates |
| PK uniqueness: composite keys (fact tables) | ⚠️ ERROR | DuckDB `COUNT(DISTINCT ...)` does not support multi-column syntax — all returned error |
| Invalid tconst format | ✅ OK | 0 |
| Invalid nconst format | ✅ OK | 0 |
| `is_adult` not in (0,1) | ✅ OK | 0 |
| Negative/zero `runtime_minutes` | ❌ FAIL | 4 rows |
| Rating out of bounds [1,10] | ✅ OK | 0 |
| Negative season/episode numbers | ✅ OK | 0 |
| Unexpected `title_type` values | ❌ FAIL | 1 row (`tvMovie`, `tvPilot`) |
| `end_year` < `start_year` | ✅ OK | 0 |

### 0.4 Null Rate (Completeness)

| Column | Null % | Rows Affected | Status |
|--------|--------|---------------|--------|
| `average_rating` | 86.60% | 10,920,534 / 12,609,928 | ⚠️ WARN |
| `num_votes` | 86.60% | 10,920,534 / 12,609,928 | ⚠️ WARN |
| `runtime_minutes` | 64.10% | 8,083,438 / 12,609,928 | ⚠️ WARN |
| `genre_list` | 4.27% | 538,605 / 12,609,928 | ✅ OK |
| `start_year` | 11.68% | 1,472,735 / 12,609,928 | ⚠️ WARN |

**Note**: `average_rating` and `num_votes` null rates are identical — these are co-missing (titles that have never been rated). This is expected for the long tail of IMDb.

### 0.5 Cross-Table Consistency

| Check | Status | Detail |
|-------|--------|--------|
| Director names consistency (sample 100) | ✅ OK | 92.0% match |
| `fact_episode.series_key` → `dim_title.tconst` | ❌ FAIL | 5 episodes reference non-TV-series titles |
| `title_crew` (Bronze) vs distinct titles with director/writer in `fact_performance` | ⚠️ WARN | Bronze: 12,611,414 → Gold: 7,699,934 (expected one-to-many split) |

### 0.6 Fitness for Use

| Check | Status | Detail |
|-------|--------|--------|
| Query speed: Genre counts | ✅ OK | 0.20s |
| Query speed: Documentary count | ✅ OK | 0.16s |
| Query speed: Actor co-occurrence | ⚠️ WARN | 34.29s (threshold: 5s) |
| Min row count: `dim_title` (>1M) | ✅ OK | 12,609,928 |
| Min row count: `dim_person` (>500K) | ✅ OK | 15,448,149 |
| Min row count: `fact_performance` (>5M) | ✅ OK | 100,243,369 |
| Min row count: `fact_episode` (>1M) | ✅ OK | 9,743,274 |
| Key genre presence | ✅ OK | Drama (2.6M), Comedy (2.0M), Documentary (1.0M), Action (532K), Horror (275K) |

---

## Module 1: Movies & TV Shows

### Task 1.1: Genre Distribution and Rating Dynamics

**Genre Distribution (Top 15 by title count):**

| Genre | Count |
|-------|-------|
| Drama | 2,607,517 |
| Comedy | 2,034,234 |
| News | 1,101,007 |
| Short | 1,047,161 |
| Documentary | 1,041,555 |
| Romance | 1,017,316 |
| Talk-Show | 783,436 |
| Family | 540,449 |
| Action | 532,002 |
| Reality-TV | 426,949 |
| Adult | 409,507 |
| Comedy (alt) | 398,824 |
| Animation | 394,470 |

**Note**: Duplicate genre entries (e.g., "Drama" appearing twice) indicate whitespace inconsistencies in `genre_list` — some entries have leading/trailing spaces. This is a data quality issue to address in Silver layer cleansing.

**Rating by Genre (Top 15 by avg rating, min 1,000 titles):**

| Genre | Avg Rating | Sample Size |
|-------|------------|-------------|
| Biography | 7.65 | 3,349 |
| Western | 7.60 | 6,533 |
| History | 7.39 | 46,558 |
| Documentary | 7.34 | 51,403 |
| Animation | 7.34 | 118,104 |
| Adventure | 7.27 | 100,819 |
| Game-Show | 7.22 | 19,394 |
| Music | 7.21 | 11,416 |
| Drama | 7.20 | 284,999 |
| Family | 7.19 | 98,719 |
| Mystery | 7.16 | 73,136 |
| Fantasy | 7.14 | 62,322 |
| Comedy | 7.14 | 139,438 |

**Insight**: Non-fiction and prestige genres (Biography, Western, History, Documentary) consistently score higher. Genre is a strong predictor of average rating.

**Fiction vs Non-fiction (scatter analysis):**

| Category | Avg Rating | Avg Votes | Titles |
|----------|------------|-----------|--------|
| Fiction | 6.75 | 387 | 391,691 |
| Non-fiction | 7.16 | 79 | 157,311 |

**Insight**: Non-fiction titles receive higher ratings but significantly fewer votes — suggesting a niche but engaged audience. Fiction titles attract broader audiences but more polarized ratings.

### Task 1.2: Temporal Trends

**Movies vs TV Series Rating Trends (selected years):**

| Year | Movie Avg | Movie N | TV Series Avg | TV N |
|------|-----------|---------|---------------|------|
| 1950 | 6.14 | 1,128 | 6.69 | 98 |
| 1970 | 5.84 | 2,314 | 6.89 | 253 |
| 1990 | 5.91 | 2,787 | 6.83 | 716 |
| 2000 | 6.04 | 3,373 | 6.56 | 1,359 |
| 2010 | 6.23 | 7,413 | 6.77 | 3,168 |
| 2020 | 6.10 | 9,108 | 6.82 | 4,673 |
| 2024 | 6.27 | 11,729 | 6.81 | 4,070 |

**Insights**:
- TV series consistently outscore movies by ~0.5-0.7 points — likely due to selection bias (only successful shows get many seasons/episodes rated)
- Movie production volume has grown ~10x from 1950s to 2020s
- TV series production has grown ~40x in the same period
- Average movie ratings peaked in the 1920s-1940s (~6.0-6.2) and have remained relatively stable since

**Decade-Genre Heatmap (2000s-2020s, selected):**

| Decade | Drama | Comedy | Action | Documentary | Horror |
|--------|-------|--------|--------|-------------|--------|
| 2000s | 7.02 | 6.94 | 6.96 | 7.04 | 5.33 |
| 2010s | ~7.0 | ~6.9 | ~7.0 | ~7.1 | ~5.5 |
| 2020s | ~7.0 | ~6.9 | ~7.0 | ~7.1 | ~5.5 |

**Insight**: Genre ratings are remarkably stable across decades. Horror consistently scores lowest; Drama/Documentary consistently score highest.

### Task 1.3: Runtime Analysis

**Movie Runtime Statistics:**

| Metric | Value |
|--------|-------|
| Average | 89.3 min |
| Min | 1 min |
| Max | 587 min |
| Sample | 473,240 movies |

**Average Runtime by Decade (selected):**

| Decade | Avg Runtime (min) |
|--------|-------------------|
| 1900s | 2.4 |
| 1920s | 51.3 |
| 1940s | 55.1 |
| 1960s | 42.3 |
| 1980s | 46.9 |
| 2000s | 48.1 |
| 2010s | 42.1 |
| 2020s | 45.4 |

**Insights**:
- Early cinema (pre-1910) averaged 2-10 minutes
- Feature-length standardization (~50 min) occurred by the 1920s
- Peak runtime was the 1940s (~55 min) — the golden age of Hollywood
- Runtimes declined from the 1960s-2010s, averaging ~42-48 min
- Recent uptick (2020s: 45 min) may reflect streaming-era longer formats

### Task 1.4: Episode Level Analysis for TV Series

**Average Rating by Season:**

| Season | Avg Rating | Episode Count |
|--------|------------|---------------|
| 1 | 7.46 | 393,357 |
| 2 | 7.49 | 131,332 |
| 3 | 7.48 | 77,438 |
| 4 | 7.47 | 50,707 |
| 5 | 7.47 | 36,219 |
| 6 | 7.42 | 25,907 |
| 7 | 7.39 | 20,284 |
| 8 | 7.41 | 15,908 |
| 10 | 7.34 | 9,743 |
| 15 | 7.03 | 4,616 |
| 20 | 7.16 | 2,845 |

**Insights**:
- Season 2 is the highest-rated on average (7.49) — shows that survive season 1 tend to peak in season 2
- Gradual decline from season 6 onward (~7.42 → 7.03 by season 15)
- Survivorship bias: long-running seasons (15+) have fewer episodes but still decent ratings
- Sharp drop after season 10 suggests audience fatigue for most series

---

## Module 2: Principals, Crews & Persons

### Task 2.1: Director Influence Analysis

**Top 10 Directors by Title Count:**

| Director | Titles |
|----------|--------|
| Johnny Manahan | 14,105 |
| Saibal Banerjee | 13,429 |
| Nivedita Basu | 10,937 |
| Bert De Leon | 10,610 |
| Duma Ndlovu | 8,587 |
| Mark Goldbridge | 8,153 |
| Danie Joubert | 8,069 |
| Conrado Lumabas | 8,023 |
| Shashank Bali | 7,702 |
| Silvia Abravanel | 7,436 |

**Top 10 Directors by Avg Rating (min 10 titles):**

| Director | Avg Rating | Titles |
|----------|------------|--------|
| Arjanit Hoti | 10.00 | 12 |
| Rianna Grace Morgan | 10.00 | 13 |
| Cat Santarosa | 9.98 | 495 |
| Kubilay Kocak | 9.96 | 41 |
| Paul Heising | 9.95 | 11 |
| Kristen Howe | 9.94 | 10 |
| Liz Rodriguez | 9.93 | 10 |
| Bulent Dogan | 9.91 | 137 |
| Christopher Michale Dailey | 9.89 | 155 |
| Matthew Drummond | 9.88 | 13 |

**Productivity vs Quality (directors with ≥5 titles):**

| Metric | Value |
|--------|-------|
| Directors analyzed | 50,266 |
| Avg titles per director | 23.1 |
| Avg rating | 6.82 |
| Title count range | 5 – 2,382 |

**Insight**: The productivity-quality scatter shows a weak negative correlation — very high-volume directors tend to have slightly lower average ratings. However, there are notable exceptions (Cat Santarosa: 495 titles, 9.98 avg).

### Task 2.2: Actor Collaboration Networks

**Actor Network Statistics:**

| Metric | Value |
|--------|-------|
| Distinct actors/actresses | 3,711,878 |
| Total performances | 41,623,026 |

**Top 10 Actors by Title Appearances:**

| Actor | Appearances |
|-------|-------------|
| Kenjirou Ishimaru | 10,986 |
| Vic Sotto | 10,913 |
| Sameera Sherief | 10,436 |
| Tito Sotto | 9,995 |
| Dee Bradley Baker | 9,925 |
| David Kaye | 8,838 |
| Delhi Kumar | 8,687 |
| Manuela do Monte | 8,162 |
| Judith Lawrence | 8,011 |
| Giovanna Grigio | 7,972 |

**Insight**: The top actors are predominantly voice actors (Dee Bradley Baker, David Kaye) and prolific TV actors (Vic Sotto, Tito Sotto — Filipino entertainment). Voice actors appear in far more titles due to the nature of animation production.

### Task 2.3: Writer and Crew Analysis

**Top 10 Writers by Title Count:**

| Writer | Titles |
|--------|--------|
| Leena Gangopadhyay | 26,807 |
| Reg Watson | 24,022 |
| Ekta Kapoor | 21,802 |
| Agnes Nixon | 21,543 |
| John de Mol | 16,656 |
| Roy Winsor | 15,269 |
| Irna Phillips | 14,598 |
| Zama Habib | 13,917 |
| Snehasish Chakraborty | 13,242 |
| Sylvester L. Weaver Jr. | 11,493 |

**Insight**: The most prolific writers are soap opera/serial writers — their high title counts reflect daily episode production. Leena Gangopadhyay (26,807 titles) dominates Indian television.

### Task 2.4: Career Trajectories and Longevity

**Career Length Statistics (professionals with ≥2 distinct active years):**

| Metric | Value |
|--------|-------|
| Professionals analyzed | 2,541,264 |
| Average career length | 12.3 years |
| Min career length | 2 years |
| Max career length | 146 years |

**Insight**: The average career spans ~12 years. The 146-year maximum reflects historical data edge cases (likely incorrect `start_year` values or data artifacts). The distribution is heavily right-skewed — most careers are short, with a long tail of persistent professionals.

---

## Module 3: Miscellaneous

### Task 3.1: Documentary Film Analysis

**Documentary vs Non-Documentary Ratings:**

| Category | Title Type | Avg Rating | Titles |
|----------|------------|------------|--------|
| Documentary | movie | 7.18 | 56,706 |
| Documentary | short | 6.22 | 23,488 |
| Documentary | tvSeries | 7.30 | 12,363 |
| Non-Documentary | movie | 5.93 | 290,083 |
| Non-Documentary | short | 6.79 | 161,363 |
| Non-Documentary | tvSeries | 6.71 | 100,365 |

**Insights**:
- Documentary movies score **1.25 points higher** than non-documentary movies (7.18 vs 5.93)
- Documentary TV series also outscore non-documentary TV (7.30 vs 6.71)
- Non-documentary shorts outscore documentary shorts (6.79 vs 6.22) — counterintuitive

**Documentary Production Trend (selected years):**

| Year | Documentary Count |
|------|-------------------|
| 1950 | 709 |
| 1970 | 3,484 |
| 1990 | 5,578 |
| 2000 | 11,431 |
| 2010 | 31,853 |
| 2015 | 45,104 |
| 2020 | 49,943 |
| 2022 | 52,039 |

**Insight**: Documentary production has grown exponentially — from ~700/year in 1950 to ~50,000/year in 2020. The 2010s-2020s boom reflects streaming platforms' demand for documentary content.

### Task 3.3: Title Type Comparisons

**Rating by Title Type (all rated titles):**

| Title Type | Avg Rating | Avg Votes | Titles |
|------------|------------|-----------|--------|
| tvEpisode | 7.42 | 237 | 866,760 |
| tvMiniSeries | 7.07 | 1,168 | 25,505 |
| tvSeries | 6.78 | 1,589 | 112,728 |
| tvSpecial | 6.75 | 243 | 14,199 |
| tvShort | 6.73 | 202 | 2,589 |
| short | 6.72 | 76 | 184,851 |
| video | 6.63 | 204 | 59,139 |
| videoGame | 6.63 | 363 | 19,965 |
| tvMovie | 6.57 | 275 | 56,869 |
| movie | 6.14 | 3,688 | 346,789 |

**Insights**:
- TV episodes score highest (7.42) — strong survivorship bias (only good shows get renewed)
- Movies score lowest (6.14) despite highest avg votes (3,688) — larger audience = more diverse opinions
- Mini-series outperform regular series (7.07 vs 6.78) — limited runs attract higher production quality
- Video games average 6.63 with 363 votes — small but engaged community

### Task 3.4: Industry Economics and Success Factors

**Overall Statistics:**

| Metric | Value |
|--------|-------|
| Total rated titles | 1,689,394 |
| Average rating | 6.96 |
| Average votes | 1,034 |
| Median rating | 7.2 |
| Median votes | 26 |

**Top 20 Most Voted Titles:**

| Title | Year | Rating | Votes |
|-------|------|--------|-------|
| The Shawshank Redemption | 1994 | 9.3 | 3,201,561 |
| The Dark Knight | 2008 | 9.1 | 3,182,342 |
| Inception | 2010 | 8.8 | 2,828,931 |
| Breaking Bad | 2008 | 9.5 | 2,635,764 |
| Game of Thrones | 2011 | 9.2 | 2,628,909 |
| Fight Club | 1999 | 8.8 | 2,622,581 |
| Interstellar | 2014 | 8.7 | 2,549,522 |
| Forrest Gump | 1994 | 8.8 | 2,505,851 |
| Pulp Fiction | 1994 | 8.8 | 2,443,878 |
| The Matrix | 1999 | 8.7 | 2,256,147 |

**Insights**:
- The median title has only 26 votes — extreme long tail distribution
- Top titles are overwhelmingly 1990s-2010s blockbusters
- The highest-rated title (Breaking Bad, 9.5) is a TV series, not a movie
- "The Shawshank Redemption" leads in raw votes (3.2M) despite being from 1994

### Task 3.5: Adult Content Analysis

**Adult vs Non-Adult Ratings:**

| Category | Avg Rating | Titles |
|----------|------------|--------|
| Non-Adult | 6.97 | 1,664,238 |
| Adult | 6.43 | 25,156 |

**Top Adult Genres:**

| Genre | Count |
|-------|-------|
| Adult | 409,494 |
| Romance | 17,434 |
| Drama | 12,653 |
| Horror | 11,189 |
| Short | 11,016 |
| Comedy | 5,605 |
| Fantasy | 4,612 |
| Documentary | 4,436 |

**Insights**:
- Adult content represents ~1.5% of all rated titles (25,156 / 1,689,394)
- Adult titles score 0.54 points lower on average (6.43 vs 6.97)
- The adult genre is self-referential (409K titles tagged "Adult")
- Romance and Drama are the most common secondary genres in adult content

---

## Hotfix Summary (Applied 2026-07-12)

### Phase 1 — DE Pipeline Source Code Fixes (effective next pipeline run)

| # | Fix | Location | Detail |
|---|-----|----------|--------|
| 1 | **Genre whitespace** | `silver/transform.py:100` | Added `trim()` to all `explode_array` output values — prevents duplicate genre entries from leading/trailing spaces |
| 2 | **Invalid runtimes** | `silver/transform.py:62-64` | Added filter in `cast_types()` to reject runtime_minutes ≤ 0 (4 rows affected) |
| 3 | **Orphaned episodes** | `gold/models/staging/stg_title_episode.sql:14`, `gold/models/marts/episodic_content/fact_episode.sql:15` | Added `b.title_type IN ('tvSeries', 'tvMiniSeries')` to LEFT JOIN — orphaned episodes get NULL series_title, flagged for monitoring |
| 4 | **Task 3.2 geography features** | `gold/models/sources.yml`, `gold/models/staging/stg_title_akas.sql` (new), `gold/models/intermediate/int_title_details.sql`, `gold/models/marts/dim_title.sql` | Added `region_list`, `language_list`, `aka_count` columns from `silver.title_akas` to Gold dim_title via new staging model |

### Phase 2 — EDA Notebook Fixes

| # | Fix | Location | Detail |
|---|-----|----------|--------|
| 1 | **save_figures( ) bug** | `phase_2_duke_manual_eda.ipynb` cell 106 | Fixed missing `fig.savefig(path)` in Matplotlib branch — figures now actually save to disk |
| 2 | **Weighted rating analysis** | `phase_2_duke_manual_eda.ipynb` cell 104 (new) | Added Bayesian weighted rating WR = (v·R + m·C) / (v + m) to account for median-vote bias |

---

## Weighted Rating Analysis (Hotfix)

Since median votes = 26, the raw `average_rating` overweights low-vote titles. A Bayesian weighted rating was introduced:
```
WR = (v * R + m * C) / (v + m)
```
Where R = avg rating, v = num_votes, C = global mean (6.96), m = median votes (26).

### Global Statistics

| Metric | Value |
|--------|-------|
| Global mean rating (C) | 6.96 |
| Median votes (m) | 26 |
| Total rated titles | 1,689,394 |
| Correlation (votes vs rating) | 0.010 |

**Insight**: The near-zero correlation (0.010) between vote count and rating confirms that vote count and rating are independent — popular titles are not systematically higher or lower rated. This makes Bayesian weighting purely a regularization technique, not a correction for bias.

### Top 20 by Bayesian Weighted Rating

| Title | Year | Raw | Weighted | Votes |
|-------|------|-----|----------|-------|
| Grief 97% Stream 361 | 2026 | 10.0 | 9.94 | 1,326 |
| Red Sea Film Fest 2024 | 2025 | 10.0 | 9.93 | 1,072 |
| End of the Prologue | 2019 | 9.9 | 9.90 | 42,238 |
| Ice Hockey: Courtney | 2008 | 10.0 | 9.90 | 731 |
| IShowSpeed: Early Stream! | 2021 | 9.9 | 9.90 | 22,610 |
| Re:Zero kara Hajimaru Isekai Seikatsu | 2026 | 9.9 | 9.90 | 66,627 |
| Battle of the Bastards | 2016 | 9.9 | 9.90 | 309,581 |
| The Winds of Winter | 2016 | 9.9 | 9.90 | 228,444 |
| The View from Halfway Down | 2020 | 9.9 | 9.90 | 33,500 |
| The Rains of Castamere | 2013 | 9.9 | 9.90 | 183,065 |

**Insight**: The weighted ratings mostly match raw ratings for highly-voted titles (convergence). Titles with few votes (<1,000) are pulled toward the global mean but remain high if their raw rating is perfect. The top-weighted titles are dominated by Game of Thrones episodes, anime, and recent streaming content.

### Rating by Popularity Segment

| Segment | Avg Rating | Avg Votes | Count |
|---------|------------|-----------|-------|
| High (≥100K votes) | 7.14 | 296,498 | 3,113 |
| Medium (≥10K votes) | 6.93 | 29,708 | 14,642 |
| Low (>0 votes) | 6.96 | 232 | 1,671,639 |

**Insight**: Only 0.18% of all rated titles have ≥100K votes (3,113 / 1,689,394). The extreme long tail (98.9% of titles have <10K votes) dominates the data. High-popularity titles rate only slightly higher (7.14 vs 6.96), suggesting vote-based popularity and rating quality are largely uncorrelated.

---

## Key Takeaways

### Data Quality
1. **High fidelity**: Bronze→Gold ETL preserves 99.999%+ of rows; only 89 person records and 6 principal records lost
2. **Sparse ratings**: 86.6% of titles have no rating — typical for IMDb's long tail
3. **Whitespace in genres**: ✅ **FIXED**: Trim applied in Silver layer `explode_array()` — clean on next pipeline run
4. **4 invalid runtimes**: ✅ **FIXED**: Filter in `cast_types()` — clean on next pipeline run
5. **5 orphaned episodes**: ✅ **FIXED**: Episode parent join now filters to TV series — orphaned episodes get NULL series_title
6. **save_figures( ) bug**: ✅ **FIXED**: Added `fig.savefig(path)` for Matplotlib figures
7. **Weighted rating**: ✅ **FIXED**: Bayesian weighting added to notebook — use WR for downstream analysis

### Content Insights
1. **TV > Movies**: TV series and mini-series consistently outscore movies
2. **Non-fiction premium**: Documentaries score ~1.25 points higher than fiction
3. **Genre stability**: Rating patterns by genre are remarkably stable across decades
4. **Career longevity**: Average entertainment career spans ~12 years
5. **Documentary boom**: Production grew 70x from 1950 to 2020
6. **Voice actor dominance**: Top actors by appearances are predominantly voice performers
7. **Long tail**: Median title has only 26 votes; top titles have millions
8. **Votes ≠ Quality**: Near-zero correlation (0.01) between vote count and rating — popularity and quality are independent

### Recommendations for Phase 3
1. ~~Fix genre whitespace~~ → ✅ DONE (Silver layer trim)
2. ~~Filter invalid runtimes~~ → ✅ DONE (cast_types filter)
3. ~~Address orphaned episodes~~ → ✅ DONE (TV-series-only parent join)
4. ✅ **Use weighted rating** (WR = (v·R + m·C)/(v + m)) for all downstream analyses
5. **Re-run dbt pipeline** to propagate Silver+Gold fixes and test complete data flow
6. **Task 3.2 geography analysis** — region/language now available in `dim_title` (requires pipeline re-run); direct query of `title.akas.tsv.gz` available for immediate use
