# DE Pipeline Specialized Assessment Results
_Generated: 2026-07-22T22:04:02.790931_

**Total checks: 56 | PASS: 40 | WARN: 6 | FAIL: 5 | SKIP: 0**

| Category | Check | Value | Status | Note |
|----------|-------|-------|--------|------|
| Bronze Ingestion | Source exists + readable: title_basics | 213.2 MB, 12,609,928 rows | OK |  |
| Bronze Ingestion | Source exists + readable: name_basics | 291.6 MB, 15,448,238 rows | OK |  |
| Bronze Ingestion | Source exists + readable: title_ratings | 8.1 MB, 1,689,394 rows | OK |  |
| Bronze Ingestion | Source exists + readable: title_principals | 735.9 MB, 100,243,363 rows | OK |  |
| Bronze Ingestion | Source exists + readable: title_episode | 51.4 MB, 9,743,274 rows | OK |  |
| Bronze Ingestion | Source exists + readable: title_crew | 78.3 MB, 12,611,414 rows | OK |  |
| Bronze Ingestion | Source exists + readable: title_akas | 480.8 MB, 58,178,050 rows | OK |  |
| Bronze Schema | Bronze view created: bronze_title_basics | 12,609,928 rows | OK |  |
| Bronze Schema | Bronze view created: bronze_name_basics | 15,448,238 rows | OK |  |
| Bronze Schema | Bronze view created: bronze_title_ratings | 1,689,394 rows | OK |  |
| Bronze Schema | Bronze view created: bronze_title_principals | 100,243,363 rows | OK |  |
| Bronze Schema | Bronze view created: bronze_title_episode | 9,743,274 rows | OK |  |
| Bronze Schema | Bronze view created: bronze_title_crew | 12,611,414 rows | OK |  |
| Gold Intrinsic Quality | Duplicate PK (tconst) in dim_title | 0 | OK |  |
| Gold Intrinsic Quality | Duplicate PK (nconst) in dim_person | 0 | OK |  |
| Gold Intrinsic Quality | PK uniqueness: fact_title_principal(tconst, ordering) | Binder Error: Referenced column "tconst" not found in FROM clause!
Candidate bin | FAIL |  |
| Gold Intrinsic Quality | Duplicate PK (title_key, snapshot_date) in fact_title_rating | 0 | OK |  |
| Gold Intrinsic Quality | Duplicate PK (series_key, season_number, episode_number) in fact_episode | 1978824 | FAIL |  |
| Gold Intrinsic Quality | Duplicate PK (tconst, nconst, category) in fact_performance | 1905885 | FAIL |  |
| Gold Intrinsic Quality | Invalid tconst format in dim_title | 0 | OK |  |
| Gold Intrinsic Quality | Invalid nconst format in dim_person | 0 | OK |  |
| Gold Intrinsic Quality | is_adult domain (0/1) | 0 | OK |  |
| Gold Intrinsic Quality | Runtime domain (>0 and <=100000) | 6 | WARN |  |
| Gold Intrinsic Quality | Rating domain [0,10] | 0 | OK |  |
| Gold Intrinsic Quality | Start year range [1880,2030] | 38 | WARN |  |
| Gold Null Rates | Null rate: dim_title.average_rating | 86.6% | INFO | Expected for sparse IMDb fields (ratings, votes, runtime) |
| Gold Null Rates | Null rate: dim_title.num_votes | 86.6% | INFO | Expected for sparse IMDb fields (ratings, votes, runtime) |
| Gold Null Rates | Null rate: dim_title.runtime_minutes | 64.1% | INFO | Expected for sparse IMDb fields (ratings, votes, runtime) |
| Gold Null Rates | Null rate: dim_title.genre_list | 4.27% | OK | Expected for sparse IMDb fields (ratings, votes, runtime) |
| Gold Null Rates | Null rate: dim_person.birth_year | 95.62% | INFO | Expected for sparse IMDb fields (ratings, votes, runtime) |
| Gold Null Rates | Null rate: dim_person.death_year | 98.32% | INFO | Expected for sparse IMDb fields (ratings, votes, runtime) |
| Gold Referential Integrity | fact_episode.series_key orphan (not a TV series) | 323065 | WARN | FK enforcement missing in Silver; quarantine should catch |
| Gold Referential Integrity | fact_performance.tconst orphan | 0 | OK |  |
| Gold Referential Integrity | fact_performance.nconst orphan | 7649 | FAIL |  |
| ETL Correctness (Bronze vs Gold) | Row count: bronze_title_basics(12,609,928) vs dim_title(12,609,928) | Bronze=12,609,928, Gold=12,609,928, delta=0 | OK |  |
| ETL Correctness (Bronze vs Gold) | Row count: bronze_name_basics(15,448,238) vs dim_person(15,448,149) | Bronze=15,448,238, Gold=15,448,149, delta=89 | WARN |  |
| ETL Correctness (Bronze vs Gold) | Distinct tconst: bronze vs dim_title | Bronze=12,609,928, Gold=12,609,928, delta=0 | OK |  |
| ETL Correctness (Bronze vs Gold) | Distinct nconst: bronze vs dim_person | Bronze=15,448,238, Gold=15,448,149, delta=89 | WARN |  |
| ETL Correctness (Bronze vs Gold) | dim_title tconst missing from bronze | 0 | OK |  |
| Fitness for Use | Minimum row count: dim_title (>1,000,000) | 12,609,928 | OK |  |
| Fitness for Use | Minimum row count: dim_person (>500,000) | 15,448,149 | OK |  |
| Fitness for Use | Minimum row count: fact_performance (>5,000,000) | 100,243,369 | OK |  |
| Fitness for Use | Minimum row count: fact_episode (>1,000,000) | 9,743,274 | OK |  |
| Fitness for Use | Max start_year in dim_title | 2115 | OK | Current year: 2026 |
| Fitness for Use | Genre distribution query time | 1.953s | OK |  |
| Fitness for Use | Actor co-occurrence query time | 30.544s | FAIL | Advisor #3 flagged 27s in prior benchmark; this measures current DuckDB-over-Parquet |
| Pipeline Governance | Gold export size: dim_title | 638.96 MB | OK |  |
| Pipeline Governance | Gold export size: dim_person | 642.56 MB | OK |  |
| Pipeline Governance | Gold export size: fact_title_rating | 12.31 MB | OK |  |
| Pipeline Governance | Gold export size: fact_performance | 1758.6 MB | OK |  |
| Pipeline Governance | Gold export size: fact_episode | 114.94 MB | OK |  |
| Pipeline Governance | Gold export size: fact_title_principal | 1758.35 MB | OK |  |
| Pipeline Governance | Total Gold export size | 4925.7 MB | OK |  |
| Pipeline Governance | Gold export manifest present | not found | WARN |  |
| Pipeline Governance | dim_title schema completeness | 22 columns | OK |  |
| Pipeline Governance | dim_title analytical columns (genre_list, director_names) | genre_list=VARCHAR, director_names=True | OK |  |