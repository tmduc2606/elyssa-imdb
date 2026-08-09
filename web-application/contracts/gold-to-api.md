# Gold-to-API Contract

## Overview

Defines the interface between the Gold layer (DE) and the Web Application API gateway. The API queries Gold marts via DuckDB over Parquet files — never reads from live databases.

**Producer:** Data Engineering (Gold layer)
**Consumer:** Web Application API
**Format:** Parquet (Snappy compression)
**Location:** `data-science/marts/gold/` (mounts as `/data/marts/gold` in containers)

---

## Query Interface

The API uses DuckDB to query Gold marts directly from Parquet files. No ETL — pure analytics queries at request time.

### Available Marts

| Mart | File | Primary Key | Description |
|------|------|-------------|-------------|
| dim_title | dim_title.parquet | title_key | Title dimension (12.6M rows) |
| dim_person | dim_person.parquet | person_key | Person dimension (15.4M rows) |
| fact_title_rating | fact_title_rating.parquet | title_key | Rating facts (1.7M rows) |
| fact_title_principal | fact_title_principal.parquet | principal_key | Principal credits (100M rows) |
| fact_performance | fact_performance.parquet | performance_key | Performance facts (100M rows) |
| fact_episode | fact_episode.parquet | episode_key | Episode hierarchy (9.7M rows) |

---

## Column Mapping (Gold → API)

| Gold Column | API Field | Notes |
|-------------|-----------|-------|
| `tconst` | `title_id` or `nconst` | Original IMDb ID |
| `title_key` | `title_key` | Surrogate key (int) |
| `person_key` | `person_key` | Surrogate key (int) |
| `primary_title` | `primaryTitle` | GraphQL naming convention |
| `start_year` | `startYear` | Release year |
| `runtime_minutes` | `runtimeMinutes` | Runtime in minutes |
| `average_rating` | `averageRating` | Weighted average rating |
| `num_votes` | `numVotes` | Vote count |
| `genre_list` | `genres` | Array of genre strings |
| `primary_name` | `primaryName` | Person name |
| `primary_profession` | `professionList` | Comma-separated professions |
| `known_for_titles` | `knownForTitles` | Title names (not IDs) |
| `character_name` | `characterName` | Character name(s) |
| `category` | `category` | Credit category (actor, director, etc.) |
| `season_number` | `seasonNumber` | TV season number |
| `episode_number` | `episodeNumber` | TV episode number |

---

## Quality Guarantees

1. **No duplicate keys** in dimension tables
2. **Referential integrity** across all fact tables
3. **Null handling:** `\N` values replaced with SQL `NULL`
4. **Schema stability:** Column renames require contract update + API version bump
5. **Frozen contracts:** No breaking changes without approval from DE + SWE leads

---

## API Response Format

All REST responses follow:
```json
{
  "data": { ... },
  "meta": { "latency_ms": 50, "cached": false }
}
```

All GraphQL responses follow standard Strawberry format with cursor-based pagination.
