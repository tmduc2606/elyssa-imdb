# Blueprint: Real-Time Database Ingestion for Elyssa-IMDb Pipeline

**Date:** 2026-06-26
**Status:** ✅ APPROVED — Phase 2A In Progress
**Author:** DE Agent

---

## Approved Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary source | **PostgreSQL** (Silver) | Already deployed, schemas defined, connections configured |
| Incremental strategy | **Watermark-based** | Requires `ingested_at` column — all Silver tables have it |
| Benchmark scope | **All 7 tables** | Full baseline for throughput comparison |
| DuckDB runtime | **Inside Docker** | Avoids storing large `.db` files on host; DuckDB runs as ephemeral service |
| Phase order | **Sequential**: 2A → 2B → 2C → 2D → 2E | Each phase builds on the previous |

---

## 1. Source Evaluation

### 1.1 Current State

| Source | Format | Size | Location | Status |
|--------|--------|------|----------|--------|
| IMDb TSV dumps | `.tsv.gz` | 9.14 GB raw | `duke/gate0/source/` | ✅ Ingested (Bronze) |
| IMDb Parquet | `.parquet` | 2.49 GB | `duke/gate0/bronze/` | ✅ Converted |
| DuckDB audit | `.db` | 3.69 GB | `duke/gate0/notebooks/` | ⚠️ Empty skeleton |

### 1.2 Candidate Database Sources

| Source Type | Use Case | Latency | Complexity |
|-------------|----------|---------|------------|
| **PostgreSQL (Silver)** | Already deployed, 14 tables | Real-time | Low — connection exists |
| **DuckDB** | Analytical queries on Parquet | Near-real-time | Medium — new driver needed |
| **SQLite** | Local embedded DB | Real-time | Low — stdlib built-in |
| **IMDb API** | Live ratings/updates | ~24h delay | High — rate limits, parsing |
| **Kafka/CDC** | Stream ingestion | Real-time | High — new infrastructure |

### 1.3 Recommendation

**Primary:** PostgreSQL (Silver) as the operational store — already deployed, schemas defined, connections configured.

**Secondary:** DuckDB as the analytical query engine — reads Parquet natively, SQL-compatible, lightweight.

**Future:** Kafka/CDC for true real-time streaming from IMDb daily dumps.

---

## 2. Architecture Blueprint

### 2.1 Current Flow

```
IMDb TSV.gz → [PySpark Bronze] → Parquet → [PySpark Silver] → PostgreSQL → [dbt Gold] → Marts
```

### 2.2 Proposed Flow (Database-Ingested)

```
                    ┌─────────────────────────────────────────────────┐
                    │              DATABASE INGESTION LAYER            │
                    │                                                  │
                    │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
                    │  │PostgreSQL│  │  DuckDB   │  │  SQLite  │      │
                    │  │ (Silver) │  │ (Analytic)│  │ (Local)  │      │
                    │  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
                    │       │             │             │              │
                    │       └─────────────┼─────────────┘              │
                    │                     ▼                            │
                    │         ┌───────────────────────┐               │
                    │         │   Database Reader      │               │
                    │         │   (psycopg2/duckdb)    │               │
                    │         └───────────┬───────────┘               │
                    │                     ▼                            │
                    │         ┌───────────────────────┐               │
                    │         │   Schema Validator     │               │
                    │         │   (type coercion)      │               │
                    │         └───────────┬───────────┘               │
                    │                     ▼                            │
                    │         ┌───────────────────────┐               │
                    │         │   Bronze Writer        │               │
                    │         │   (Parquet + metadata) │               │
                    │         └───────────┬───────────┘               │
                    └─────────────────────┼───────────────────────────┘
                                          ▼
                    ┌─────────────────────────────────────────────────┐
                    │              EXISTING PIPELINE                    │
                    │                                                  │
                    │  Bronze → Silver → Gold → Neo4j → DQ            │
                    └─────────────────────────────────────────────────┘
```

### 2.3 Component Design

#### A. Database Reader (`bronze/db_reader.py`)

```python
class DatabaseReader:
    """Unified interface for reading from multiple database sources."""
    
    def __init__(self, source_type: str, connection_config: dict):
        self.source_type = source_type  # "postgresql", "duckdb", "sqlite"
        self.config = connection_config
    
    def read_table(self, table_name: str, batch_size: int = 10000) -> DataFrame:
        """Read table from source database with batched iteration."""
        pass
    
    def read_query(self, query: str) -> DataFrame:
        """Execute custom query and return results."""
        pass
    
    def get_schema(self, table_name: str) -> dict:
        """Infer schema from source table."""
        pass
    
    def get_row_count(self, table_name: str) -> int:
        """Get approximate row count for partitioning."""
        pass
```

#### B. Connection Configs (`bronze/db_configs.py`)

```python
DB_CONFIGS = {
    "postgresql_silver": {
        "type": "postgresql",
        "host": "postgres",
        "port": 5432,
        "database": "elyssa_warehouse",
        "user": "elyssa",
        "password": "elyssa_pg_2026",
        "schema": "silver",
    },
    "duckdb_analytics": {
        "type": "duckdb",
        "read_only": True,
    },
    "sqlite_local": {
        "type": "sqlite",
        "path": "data-engineering/local/imdb_local.db",
    },
}
```

#### C. Schema Mapping (`bronze/db_schema_map.py`)

```python
# Maps source DB columns → Bronze columns (snake_case → camelCase)
SOURCE_MAPPINGS = {
    "postgresql_silver": {
        "title_basics": {
            "source_table": "silver.title_basics",
            "column_map": {
                "tconst": "tconst",
                "title_type": "titleType",
                "primary_title": "primaryTitle",
            },
            "null_marker": None,  # PostgreSQL uses actual NULLs
        },
    },
}
```

---

## 3. Integration Points

### 3.1 Bronze Layer Changes

| File | Change | Purpose |
|------|--------|---------|
| `bronze/db_configs.py` | **NEW** | Database connection configs + source table definitions |
| `bronze/db_reader.py` | **NEW** | Unified database reader (PostgreSQL) |
| `bronze/db_schema_map.py` | **NEW** | DB snake_case → Bronze camelCase mapping |
| `bronze/ingest_imdb.py` | Add `--source db` flag (future) | Switch from TSV to DB ingestion |

### 3.2 Silver Layer Changes

| File | Change | Purpose |
|------|--------|---------|
| `silver/transform.py` | No change needed | DB-native NULLs are already NULL |

### 3.3 Orchestration Changes

| File | Change | Purpose |
|------|--------|---------|
| `orchestration/dags/imdb_pipeline_dag.py` | Add `db_ingest` sensor (Phase 2D) | Trigger on DB availability |
| `orchestration/operators/db_operator.py` | **NEW** (Phase 2D) | Database ingestion operator |

### 3.4 Docker Changes

| File | Change | Purpose |
|------|--------|---------|
| `docker/docker-compose.yml` | Add `duckdb` service (Phase 2B) | Ephemeral DuckDB for analytics |
| `docker/Dockerfile.airflow` | No change needed | psycopg2 already installed |

---

## 4. Benchmark Strategy

### 4.1 Benchmark Dimensions

| Dimension | Metrics | Target |
|-----------|---------|--------|
| **Throughput** | rows/sec, MB/sec | >10K rows/sec |
| **Latency** | time-to-Bronze, time-to-Silver | <30s per table |
| **Memory** | Peak RSS, GC pressure | <2GB peak |
| **Incremental** | Delta detection, CDC lag | <5min |
| **Schema Inference** | Metadata overhead | <1s per table |

### 4.2 Benchmark Scenarios (Phase 2E)

| Scenario | Source | Tables | Rows | Purpose |
|----------|--------|--------|------|---------|
| **Full Load** | PostgreSQL | 7 | All | Baseline throughput |
| **Incremental** | PostgreSQL | 1 | 1M | Delta detection |
| **DuckDB Query** | DuckDB (Docker) | 1 | 1M | Analytical read speed |
| **Schema Inference** | PostgreSQL | 7 | 0 | Metadata overhead |

---

## 5. Implementation Phases

### Phase 2A: Database Reader Foundation ✅ (In Progress)

- [x] Create `bronze/db_configs.py` with PostgreSQL connection configs
- [x] Create `bronze/db_reader.py` with PostgreSQL support (batched reads, schema inference, metadata)
- [x] Create `bronze/db_schema_map.py` with snake_case → camelCase mappings for all 7 tables
- [ ] Unit tests for database reader (with mocked connections)
- [ ] Integration test with PostgreSQL (Docker)

### Phase 2B: DuckDB Integration (Next)

- [ ] Add DuckDB driver to `requirements.txt`
- [ ] Extend `DatabaseReader` for DuckDB
- [ ] Add `duckdb` service to Docker compose (ephemeral, no volume)
- [ ] DuckDB can read Parquet directly — test this path
- [ ] Benchmark DuckDB vs PostgreSQL read speeds

### Phase 2C: Incremental Ingestion

- [ ] Add watermark-based delta detection (`read_incremental`)
- [ ] Create `bronze/watermark.py` for watermark tracking
- [ ] Implement Bronze watermark table
- [ ] Test incremental vs full load performance

### Phase 2D: Orchestration Integration

- [ ] Create `orchestration/operators/db_operator.py`
- [ ] Update DAG with database ingestion sensor
- [ ] Add database health checks
- [ ] End-to-end integration test

### Phase 2E: Benchmarking & Documentation

- [ ] Implement `scripts/db_benchmark.py`
- [ ] Run full benchmark suite (all 7 tables)
- [ ] Generate performance report
- [ ] Update architecture documentation

---

## 6. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| PostgreSQL connection pool exhaustion | High | Connection pooling, retry logic |
| DuckDB file locking (concurrent writes) | Medium | Read-only mode for analytics (Docker ephemeral) |
| Schema drift between source and target | Medium | Schema validation on read |
| Memory pressure from large table reads | High | Batched iteration with 50K row batches |
| Network latency (Docker internal) | Low | Use Docker network, not localhost |

---

## 7. Implementation Details

### Phase 2A Files

```
data-engineering/bronze/
├── __init__.py
├── config.py                    # Existing TSV config
├── db_configs.py                # NEW: PostgreSQL connection + source table defs
├── db_reader.py                 # NEW: PostgreSQL reader with PySpark output
├── db_schema_map.py             # NEW: Column name mapping
├── ingest_imdb.py               # Existing TSV ingestion
├── tests/
│   ├── __init__.py
│   ├── test_db_reader.py        # NEW: DB reader tests (mocked)
│   ├── test_ingestion.py        # Existing TSV tests
│   └── test_bronze_comprehensive.py
```

### PostgreSQL Column Mapping

| Silver (snake_case) | Bronze (camelCase) |
|---------------------|-------------------|
| `tconst` | `tconst` |
| `title_type` | `titleType` |
| `primary_title` | `primaryTitle` |
| `original_title` | `originalTitle` |
| `is_adult` | `isAdult` |
| `start_year` | `startYear` |
| `end_year` | `endYear` |
| `runtime_minutes` | `runtimeMinutes` |
| `average_rating` | `averageRating` |
| `num_votes` | `numVotes` |
| `snapshot_date` | `snapshotDate` |
| `primary_name` | `primaryName` |
| `birth_year` | `birthYear` |
| `death_year` | `deathYear` |
| `is_original_title` | `isOriginalTitle` |
| `title_id` | `titleId` |
| `parent_tconst` | `parentTconst` |
| `season_number` | `seasonNumber` |
| `episode_number` | `episodeNumber` |

---

*This blueprint is a living document. Updated as phases are completed.*
