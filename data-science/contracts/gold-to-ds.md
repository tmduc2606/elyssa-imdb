# Gold-to-DataScience Contract

## Overview

This contract defines the **input interface** between the Data Engineering
module (Gold layer) and the Data Science module. Data Science consumes
frozen Parquet snapshots — never live database connections.

**Owner:** Data Engineering
**Consumer:** Data Science
**Format:** Parquet (Snappy compression)
**Location:** `s3://gold-exports/` (production) or `data-science/marts/` (local)

---

## Schema Guarantee

### dim_title

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| title_id | string | No | tconst — alphanumeric unique identifier |
| primary_title | string | No | Most popular title |
| title_type | string | No | movie, short, tvseries, tvepisode, video, etc. |
| is_adult | boolean | No | 0: non-adult, 1: adult |
| start_year | int | Yes | Release year (YYYY) |
| end_year | int | Yes | TV series end year, null for others |
| runtime_minutes | float | Yes | Primary runtime in minutes |
| genres | string | Yes | Comma-separated genre list |
| genre_list | array[string] | Yes | Parsed genre array |
| average_rating | float | Yes | Weighted average rating |
| num_votes | int | Yes | Number of votes |
| director_names | string | Yes | Comma-separated director names |
| writer_names | string | Yes | Comma-separated writer names |
| num_episodes | int | Yes | Episode count for TV series |
| primary_name | string | Yes | Primary person name |

### dim_person

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| nconst | string | No | Alphanumeric unique person identifier |
| primary_name | string | No | Most common credited name |
| birth_year | int | Yes | Birth year (YYYY) |
| death_year | int | Yes | Death year, null if alive |
| primary_profession | string | Yes | Comma-separated top-3 professions |
| known_for_titles | string | Yes | Comma-separated tconsts |

### fact_title_rating

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| title_id | string | No | tconst reference |
| average_rating | float | Yes | Weighted average |
| num_votes | int | Yes | Vote count |

### fact_title_principal

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| title_id | string | No | tconst reference |
| nconst | string | No | Person reference |
| ordering | int | No | Billing order |
| category | string | No | actor, director, writer, etc. |
| job | string | Yes | Specific job title |
| characters | string | Yes | Character name(s) |

### fact_performance

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| title_id | string | No | tconst reference |
| nconst | string | No | Person reference |
| category | string | No | Credit category |

### fact_episode

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| episode_id | string | No | Episode tconst |
| parent_id | string | No | Series tconst |
| season_number | int | Yes | Season number |
| episode_number | int | Yes | Episode number |

---

## Quality Guarantees

1. **No duplicate `title_id`** in `dim_title`
2. **Referential integrity:** All `fact_title_rating.title_id` exist in `dim_title`
3. **Null handling:** `\N` values from IMDb source replaced with SQL `NULL`
4. **Genre normalization:** `genres` field is comma-separated, whitespace-trimmed
5. **Runtime filter:** `runtime_minutes > 0` for movies (non-null)
6. **Rating range:** `average_rating` between 1.0 and 10.0
7. **Vote count:** `num_votes >= 0`

---

## Development Mode Sampling

When `DEVELOPMENT_MODE = True`:

```sql
-- Apply at DuckDB query level, NOT after DataFrame load
FROM dim_title TABLESAMPLE SYSTEM (5 PERCENT) REPEATABLE (42)
```

Materialized as temporary tables at connection time:
- `dim_title_sm`, `fact_performance_sm`, `fact_episode_sm`, `dim_person_sm`

Views overridden to point at sampled tables for downstream transparency.

---

## Temporal Split Constants (Frozen)

```
TRAIN_YEAR_MAX = 2014
VAL_YEAR_MIN   = 2015
VAL_YEAR_MAX   = 2018
TEST_YEAR_MIN  = 2019
```

These constants are **identical** across all three notebooks (FE, Modeling,
Analytics). Any change requires updating all three simultaneously.

---

## Export Procedure

```bash
# From data-engineering Gold layer
duckdb gold.db -c "COPY (SELECT * FROM dim_title) TO 'dim_title.parquet' (FORMAT PARQUET, COMPRESSION SNAPPY);"
aws s3 cp dim_title.parquet s3://gold-exports/full/dim_title.parquet
```

For development samples:
```bash
duckdb gold.db -c "COPY (SELECT * FROM dim_title TABLESAMPLE SYSTEM (5) REPEATABLE (42)) TO 'dim_title_sm.parquet' (FORMAT PARQUET, COMPRESSION SNAPPY);"
```
