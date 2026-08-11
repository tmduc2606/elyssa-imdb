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

Schemas below match the dbt Gold models in `data-engineering/gold/models/marts/`
(verified against `data-science/scripts/validate_contracts.py`).

### dim_title

Source: `marts/dim_title.sql` (22 columns)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| tconst | string | No | Alphanumeric unique title identifier |
| title_type | string | No | movie, short, tvseries, tvepisode, video, etc. |
| primary_title | string | No | Most popular title |
| original_title | string | Yes | Original non-English title |
| is_adult | boolean | No | 0: non-adult, 1: adult |
| start_year | int | Yes | Release year (YYYY) |
| end_year | int | Yes | TV series end year, null for others |
| runtime_minutes | int | Yes | Primary runtime in minutes |
| genre_list | string | Yes | Comma-separated, whitespace-trimmed genre list |
| director_names | string | Yes | Comma-separated director names (billing order) |
| writer_names | string | Yes | Comma-separated writer names (billing order) |
| average_rating | float | Yes | Weighted average rating |
| num_votes | int | Yes | Number of votes |
| popularity_segment | string | Yes | high/medium/low/unknown (CASE on num_votes) |
| rating_bucket | string | Yes | excellent/good/average/unrated (CASE on average_rating) |
| parent_tconst | string | Yes | Series tconst for episodes, null otherwise |
| series_title | string | Yes | Primary title of parent series |
| season_number | int | Yes | Episode season number |
| episode_number | int | Yes | Episode number within season |
| region_list | string | Yes | Comma-separated aka regions (title_akas) |
| language_list | string | Yes | Comma-separated aka languages (title_akas) |
| aka_count | int | Yes | Number of alternate titles (title_akas) |

### dim_person

Source: `marts/dim_person.sql` (9 columns)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| nconst | string | No | Alphanumeric unique person identifier |
| primary_name | string | No | Most common credited name |
| birth_year | int | Yes | Birth year (YYYY) |
| death_year | int | Yes | Death year, null if alive |
| age_at_death | int | Yes | Computed `death_year - birth_year` |
| generation | string | Yes | Gen Alpha/Gen Z/Millennial/Gen X/Boomer/Silent-Greatest (CASE on birth_year) |
| profession_list | string | Yes | Comma-separated top-3 professions |
| known_for_titles | string | Yes | Comma-separated **primary titles** (not tconsts) |
| known_for_ids | string | Yes | Comma-separated **tconsts** of known-for titles |

### fact_title_rating

Source: `marts/fact_title_rating.sql` (6 columns). Grain: `(title_key, snapshot_date)`.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| title_key | string | No | Unique title identifier (was `tconst`) |
| snapshot_date | date | No | Snapshot date of rating |
| average_rating | float | Yes | Weighted average |
| num_votes | int | Yes | Vote count |
| batch_id | string | Yes | Ingestion batch identifier |
| ingested_at | timestamp | Yes | Ingestion timestamp |

### fact_title_principal

Source: `marts/fact_title_principal.sql` (8 columns). Unique key: `(title_key, ordering)`.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| title_key | string | No | Unique title identifier (was `tconst`) |
| name_key | string | No | Person reference (was `nconst`) |
| ordering | int | No | Billing order |
| category | string | No | actor, director, writer, etc. |
| job | string | Yes | Specific job title |
| character_name | string | Yes | Aggregated character name(s) (was `characters`) |
| batch_id | string | Yes | Ingestion batch identifier |
| ingested_at | timestamp | Yes | Ingestion timestamp |

### fact_performance

Source: `marts/fact_performance.sql` (8 columns). **No unique key** — the join to
`title_principal_char` expands 1 principal into N rows (one per character).

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| tconst | string | No | Unique title identifier |
| ordering | int | No | Billing order |
| nconst | string | No | Person reference |
| category | string | No | Credit category |
| job | string | Yes | Specific job title |
| character_name | string | Yes | Character name |
| batch_id | string | Yes | Ingestion batch identifier |
| ingested_at | timestamp | Yes | Ingestion timestamp |

### fact_episode

Source: `marts/episodic_content/fact_episode.sql` (9 columns)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| episode_key | string | No | Episode tconst (was `episode_id`) |
| series_key | string | No | Series tconst (was `parent_id`) |
| season_number | int | Yes | Season number |
| episode_number | int | Yes | Episode number |
| series_title | string | Yes | Series primary title |
| series_start_year | int | Yes | Series start year |
| series_type | string | Yes | Series title type |
| batch_id | string | Yes | Ingestion batch identifier |
| ingested_at | timestamp | Yes | Ingestion timestamp |

> **Not exported:** `agg_actor_cooccurrence` (19 GB) is deliberately excluded
> from the DS contract — see `data-engineering/docs/export_guide.md`.

---

## Quality Guarantees

1. **No duplicate `tconst`** in `dim_title`
2. **Referential integrity:** `fact_title_rating.title_key` and `fact_title_principal.title_key` exist in `dim_title`
3. **Null handling:** `\N` values from IMDb source replaced with SQL `NULL`
4. **Genre normalization:** `genre_list` is a comma-separated string, whitespace-trimmed (not an array)
5. **Runtime filter:** `runtime_minutes > 0` for movies (non-null)
6. **Rating range:** `average_rating` between 1.0 and 10.0
7. **Vote count:** `num_votes >= 0`
8. **Performance grain:** `fact_performance` may contain duplicate `(tconst, ordering)` rows (row-expanding character join) — deduplicate downstream when a unique key is required
9. **Known-for titles:** `dim_person.known_for_titles` stores comma-separated title names, not tconsts; the matching `dim_person.known_for_ids` stores the comma-separated tconsts in the same order

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
