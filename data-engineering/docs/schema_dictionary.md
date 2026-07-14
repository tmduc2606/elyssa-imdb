# Elyssa-IMDb — Schema Dictionary

## Silver Layer Tables

### title_basics
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| title_key | INTEGER (serial) | NO | Surrogate key from `silver.title_key_seq` |
| tconst | VARCHAR(20) | NO | IMDb unique identifier |
| title_type | VARCHAR(50) | NO | Type (movie, tvSeries, tvEpisode, etc.) |
| primary_title | TEXT | NO | Primary title |
| original_title | TEXT | NO | Original title (non-English) |
| is_adult | BOOLEAN | NO | Adult content flag |
| start_year | SMALLINT | YES | Release year (or series start) |
| end_year | SMALLINT | YES | Series end year |
| runtime_minutes | INTEGER | YES | Runtime in minutes |
| valid_from | TIMESTAMPTZ | NO | SCD2 validity start |
| valid_to | TIMESTAMPTZ | YES | SCD2 validity end |
| is_current | BOOLEAN | NO | SCD2 current flag |
| batch_id | VARCHAR(20) | YES | Bronze ingestion batch |
| ingested_at | TIMESTAMPTZ | NO | Ingestion timestamp |

### name_basics
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| name_key | INTEGER (serial) | NO | Surrogate key from `silver.name_key_seq` |
| nconst | VARCHAR(20) | NO | IMDb unique person identifier |
| primary_name | TEXT | NO | Primary name |
| birth_year | SMALLINT | YES | Birth year |
| death_year | SMALLINT | YES | Death year |
| valid_from | TIMESTAMPTZ | NO | SCD2 validity start |
| valid_to | TIMESTAMPTZ | YES | SCD2 validity end |
| is_current | BOOLEAN | NO | SCD2 current flag |
| batch_id | VARCHAR(20) | YES | Bronze ingestion batch |
| ingested_at | TIMESTAMPTZ | NO | Ingestion timestamp |

### title_rating (TimescaleDB hypertable)
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| tconst | VARCHAR(20) | NO | Title identifier (PK) |
| average_rating | NUMERIC(3,1) | NO | Weighted average (0.0–10.0) |
| num_votes | INTEGER | NO | Vote count |
| snapshot_date | DATE | NO | Rating snapshot date (hypertable partition key) |
| batch_id | VARCHAR(20) | YES | Ingestion batch |
| ingested_at | TIMESTAMPTZ | NO | Ingestion timestamp |

### title_episode
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| tconst | VARCHAR(20) | NO | Episode identifier (PK) |
| parent_tconst | VARCHAR(20) | NO | Parent series identifier |
| season_number | INTEGER | YES | Season number |
| episode_number | INTEGER | YES | Episode number |
| batch_id | VARCHAR(20) | YES | Ingestion batch |
| ingested_at | TIMESTAMPTZ | NO | Ingestion timestamp |

### title_akas
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| title_id | VARCHAR(20) | NO | Title identifier (PK part 1) |
| ordering | INTEGER | NO | Ordering (PK part 2) |
| title | TEXT | NO | Alternative title |
| region | VARCHAR(10) | YES | Region code |
| language | VARCHAR(50) | YES | Language code |
| is_original_title | BOOLEAN | NO | Original title flag |
| batch_id | VARCHAR(20) | YES | Ingestion batch |
| ingested_at | TIMESTAMPTZ | NO | Ingestion timestamp |

### title_director
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| tconst | VARCHAR(20) | NO | Title identifier (PK part 1) |
| ordering | SMALLINT | NO | Ordering (PK part 2) |
| nconst | VARCHAR(20) | NO | Director identifier |
| batch_id | VARCHAR(20) | YES | Ingestion batch |

### title_writer
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| tconst | VARCHAR(20) | NO | Title identifier (PK part 1) |
| ordering | SMALLINT | NO | Ordering (PK part 2) |
| nconst | VARCHAR(20) | NO | Writer identifier |
| batch_id | VARCHAR(20) | YES | Ingestion batch |

### title_principal
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| tconst | VARCHAR(20) | NO | Title identifier (PK part 1) |
| ordering | SMALLINT | NO | Ordering (PK part 2) |
| nconst | VARCHAR(20) | NO | Person identifier |
| category | VARCHAR(50) | NO | Category (actor, director, etc.) |
| job | TEXT | YES | Specific job |
| batch_id | VARCHAR(20) | YES | Ingestion batch |
| ingested_at | TIMESTAMPTZ | NO | Ingestion timestamp |

### title_principal_char
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| tconst | VARCHAR(20) | NO | Title identifier (PK part 1) |
| ordering | SMALLINT | NO | Ordering (PK part 2) |
| character_name | TEXT | NO | Character name (PK part 3) |

### title_genre
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| tconst | VARCHAR(20) | NO | Title identifier (PK part 1) |
| genre | VARCHAR(50) | NO | Genre (PK part 2) |

### name_profession
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| nconst | VARCHAR(20) | NO | Person identifier (PK part 1) |
| profession_order | SMALLINT | NO | Order 1–3 (PK part 2) |
| profession | VARCHAR(100) | NO | Profession name |

### name_known_for_title
| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| nconst | VARCHAR(20) | NO | Person identifier (PK part 1) |
| known_for_order | SMALLINT | NO | Order 1–4 (PK part 2) |
| tconst | VARCHAR(20) | NO | Title identifier |

### Governance Tables
- `data_quality_log` — DQ check results (check_name, metric_value, passed, logged_at)
- `quarantine` — Rejected records (table_name, error_message, raw_record JSONB)
- `graph_sync_status` — Neo4j sync tracking (sync_name, last_sync_ts, rows_synced)

## Gold Layer Models

| Model | Type | Grain | Schema |
|-------|------|-------|--------|
| stg_title_basics | view (staging) | tconst | gold_stg |
| stg_name_basics | view (staging) | nconst | gold_stg |
| stg_title_ratings | view (staging) | tconst, snapshot_date | gold_stg |
| stg_title_episode | view (staging) | tconst | gold_stg |
| int_title_details | view (intermediate) | tconst | gold_int |
| int_person_details | view (intermediate) | nconst | gold_int |
| dim_title | table (mart) | tconst | gold |
| dim_person | table (mart) | nconst | gold |
| fact_title_rating | table (mart) | title_key, snapshot_date | gold |
| fact_title_principal | table (mart) | title_key, name_key, character_key | gold |
| fact_episode | table (mart) | episode_key, series_key | gold |
