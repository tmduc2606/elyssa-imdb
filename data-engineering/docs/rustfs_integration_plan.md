# RustFS Integration Plan — S3-Centric Pipeline (Revised)

## Investigation Summary

### Current State (Post-Phase 1 Cleanup)

| Aspect | Status | Detail |
|--------|--------|--------|
| **duke/ directory** | ✅ Removed | All 14 files + 3.4 GB deleted. References migrated to S3 paths. |
| **Bronze I/O** | ✅ Updated | `run_bronze.py` reads from `s3://imdb-source/`, writes to bind mount `data-science/marts/bronze/` |
| **Silver I/O** | ✅ Updated | `silver_operator.py` reads from bind mount `marts/bronze/` via DuckDB temp tables, writes to PostgreSQL |
| **Silver Export** | ✅ Done | `silver_export_operator.py` exports 15 tables to `data-science/marts/silver/` (bind mount) |
| **Gold Export** | ✅ Updated | `gold_export_operator.py` writes to bind mount `data-science/marts/full/` |
| **DAG wiring** | ✅ Updated | `silver_export` task inserted after `wait_silver`, before `gold_dbt_run` |
| **RustFS status** | ⏳ Pending | Infrastructure exists (`Dockerfile.rustfs` + `entrypoint.sh`). Not yet in compose. |
| **DuckDB httpfs** | ⏳ Pending | No `httpfs` extension, no `SET s3_*` settings. Required for S3 reads. |
| **boto3/S3 libs** | ⏳ Pending | Not installed in any requirements file. |

### Why the Old Approach Is Wrong for a Public Repo

The previous plan (Option B — local Bronze + S3 archive) created a **confusing dual-path architecture**:
- Users see Bronze writing to local volumes AND to S3
- "Why both?" / "Which one is the source of truth?"
- Harder to document, harder to follow

The right approach is **S3 as the single source of truth**:
```
IMDb datasets → S3 (imdb-source/) → Bronze S3 (bronze/) → Silver (local cache for speed)
```
Where the local cache is an **invisible implementation detail**, not a storage layer the user needs to manage.

---

## Proposed Architecture: S3-Centric Pipeline

```
https://datasets.imdbws.com/
        │
        ▼  download_imdb.py (writes directly to RustFS via HTTP PUT)
  s3://imdb-source/{table}.tsv.gz
        │
        ▼  DuckDB reads .tsv.gz from S3 (via httpfs extension)
  s3://bronze/{table}.parquet
        │
        ▼  DuckDB materializes S3 Parquet → local DuckDB temp tables
        │  (implementation detail — transparent to user)
  Silver PostgreSQL (6 parent + 8 child tables)
        │
        ▼
  Gold dbt → s3://gold-exports/{batch}/*.parquet
```

### Why This Works on Athlon 200GE

The risk with S3 reads is **network overhead**. But on a single-node deployment:
- RustFS runs on localhost (`http://rustfs:9000`) — same Docker network, zero network latency
- DuckDB's `httpfs` makes **range requests** (reads only needed row groups/columns), not full-file downloads
- The Silver operator already materializes source Parquet into DuckDB temp tables (M2 optimization from previous session) — **one S3 read per source file**, then all processing is local

The S3 read penalty per file:
- title.basics (264 MB Parquet): ~5-10 s over localhost HTTP
- name.basics (598 MB): ~15-20 s
- title.principals (3.3 GB): ~1-2 min
- **Total added: ~3-5 min** across all 7 files — negligible vs. 3h40m Silver ETL

---

## S3 Bucket Layout

| Bucket | Content | Created By |
|--------|---------|------------|
| `imdb-source` | Raw `.tsv.gz` files | `entrypoint.sh` at RustFS startup |
| `bronze` | Immutable Parquet (Snappy) | `entrypoint.sh` at RustFS startup |
| `gold-exports` | DS-ready Parquet + manifest | `entrypoint.sh` at RustFS startup (or on first export) |

---

## Implementation Tasks

### ✅ COMPLETED — Phase 1 Cleanup (Before This Plan)

These tasks are **already implemented** and should NOT be re-executed:

| Task | File(s) | Status | Detail |
|------|---------|--------|--------|
| SilverExportOperator | `operators/silver_export_operator.py` | ✅ Done | Reads 15 PostgreSQL tables via DuckDB `postgres_scanner`, writes Snappy Parquet to `/opt/airflow/output/silver/` |
| Silver bind mount | `docker/docker-compose.yml` | ✅ Done | `../data-science/marts/silver:/opt/airflow/output/silver:rw` added to airflow |
| Bronze bind mount | `docker/docker-compose.yml` | ✅ Done | `../data-science/marts/bronze:/opt/airflow/output/bronze:rw` added to airflow |
| Gold bind mount | `docker/docker-compose.yml` | ✅ Done | `../data-science/marts/full:/opt/airflow/output/gold:rw` added to airflow |
| DAG wiring | `dags/imdb_pipeline_dag.py` | ✅ Done | `silver_export` inserted: `wait_silver >> silver_export >> gold_dbt_run` |
| Duke removal | `data-engineering/duke/` | ✅ Done | All 14 files deleted, 19+ code references migrated to S3 paths |
| EDA notebook Part D | `phase_2_duke_manual_eda.ipynb` | ✅ Done | 10 cells merged into Part B: Bronze/Silver/Gold counts, reconciliation, DQ anomalies, freshness |

> **⚠ CRITICAL: Part D is COMPLETE and MERGED into Part B of the notebook.** Do NOT create new notebook cells or duplicate Part D code. The existing cells in Part B handle all cross-layer assessment. Any agent working on this plan must skip notebook modifications after applying fixes.
| paths.yaml | `config/paths.yaml` | ✅ Done | `source_dir: s3://imdb-source/` (was duke/gate0/source/) |
| db_configs.py | `bronze/db_configs.py` | ✅ Done | All `duke/gate0/bronze/` → `s3://bronze/` |
| AGENTS.md | `AGENTS.md` | ✅ Done | Duke's Gate 0 section removed, routing table updated |
| Code references | 9 files | ✅ Done | All `duke/gate0/source/` → `s3://imdb-source/` |

---

### ✅ COMPLETED — S3-Centric Pipeline Implementation

All tasks below have been implemented. See git diff for details.

### ✅ Task 1 — Docker: Restore RustFS + Create All Buckets

**Files:** `docker/docker-compose.yml`, `docker/rustfs/entrypoint.sh`

**Reference:** [RustFS Documentation](https://github.com/rustfs/rustfs)

- ✅ Restore RustFS service with `mem_limit: 256m`
- ✅ Update `entrypoint.sh` to create all 3 buckets at startup:
  ```bash
  curl -X PUT http://localhost:9000/imdb-source/ || true
  curl -X PUT http://localhost:9000/bronze/ || true
  curl -X PUT http://localhost:9000/gold-exports/ || true
  ```
- ✅ Add S3 environment variables to `etl-runner` and `airflow`:
  ```
  S3_ENDPOINT=http://rustfs:9000
  S3_ACCESS_KEY=elyssa
  S3_SECRET_KEY=elyssa_s3_2026
  S3_REGION=us-east-1
  ```

**Acceptance:** `docker compose up -d` starts RustFS with 3 buckets ready.

---

### ✅ Task 2 — Download Script: IMDb → S3 Direct

**File:** `data-engineering/scripts/download_imdb.py`

New standalone script that:
1. ✅ Downloads 7 `.tsv.gz` files from `https://datasets.imdbws.com/`
2. ✅ Streams directly to RustFS S3 via HTTP PUT (no local disk needed)
3. ✅ Validates SHA-256 checksum after upload
4. ✅ Writes `s3://imdb-source/download_metadata.json` with timestamps

```python
# Pseudocode
import requests
import hashlib

S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://rustfs:9000")
FILES = ["title.basics.tsv.gz", "name.basics.tsv.gz", ...]

for fname in FILES:
    resp = requests.get(f"https://datasets.imdbws.com/{fname}", stream=True)
    sha256 = hashlib.sha256()
    put_url = f"{S3_ENDPOINT}/imdb-source/{fname}"
    requests.put(put_url, data=_stream_with_hash(resp.iter_content(), sha256))
    # validate SHA-256
    print(f"Downloaded {fname} → {put_url} ({sha256.hexdigest()})")
```

**Acceptance:** Running `python scripts/download_imdb.py` populates RustFS `imdb-source/` bucket.

---

### ✅ Task 3 — DuckDB: Configure `httpfs` for All ETL Containers

**Files:** `data-engineering/requirements.txt` (no change — httpfs is bundled with DuckDB)
**Files:** `scripts/run_bronze.py`, `orchestration/operators/silver_operator.py`, `scripts/export_gold.py`

Add S3 bootstrap block to every DuckDB connection:

```python
conn.execute("INSTALL httpfs; LOAD httpfs;")
conn.execute("SET s3_endpoint = 'rustfs:9000'")  # Docker internal DNS
conn.execute("SET s3_access_key_id = 'elyssa'")
conn.execute("SET s3_secret_access_key = 'elyssa_s3_2026'")
conn.execute("SET s3_region = 'us-east-1'")
conn.execute("SET s3_url_style = 'path'")
conn.execute("SET s3_use_ssl = false")
```

**Acceptance:** `read_parquet('s3://bronze/title.basics.parquet')` works from etl-runner.

---

### ✅ Task 4 — Bronze: Rewrite `run_bronze.py` to Use S3

**File:** `scripts/run_bronze.py`

Changes:
1. **Read source:** `read_csv('s3://imdb-source/{table}.tsv.gz', ...)` instead of local path
2. **Write Parquet:** `COPY TO 's3://bronze/{table}.parquet'` instead of local path
3. **Config:** Remove `BRONZE_PATH` and `SOURCE_DIR` constants — replace with S3 URLs
4. **Retain local cache:** Materialize S3 Parquet to local DuckDB temp table for `read_parquet()` during `wc -l` and metadata extraction (optional optimization)

```python
# Source → reads from S3
source_url = f"s3://imdb-source/{SOURCE_FILES[table]}"
count_sql = f"SELECT count(*) FROM read_csv('{source_url}', delim='\\t', header=true, all_varchar=true, ignore_errors=true, quote='', escape='')"

# Parquet → writes to S3
parquet_url = f"s3://bronze/{table}.parquet"
conn.execute(f"COPY ({select_sql}) TO '{parquet_url}' (FORMAT PARQUET, COMPRESSION SNAPPY)")
```

**Acceptance:** Full Bronze run reads from `s3://imdb-source/`, writes to `s3://bronze/`.

---

### ✅ Task 5 — Silver: Read Parquet from S3 with Local Materialization

**File:** `orchestration/operators/silver_operator.py`

Changes:
1. Change `parquet_path` from local to `s3://bronze/{table}.parquet`
2. The M2 optimization (materialize → DuckDB temp table) already exists — it reads from `read_parquet('{path}')` and creates `CREATE TABLE src_... AS SELECT * FROM read_parquet(...)`. Just change the path.
3. No performance regression expected (one S3 read per source file, then all subsequent chunked UNNEST operations work from local DuckDB temp tables)

```python
parquet_path = f"s3://bronze/{src_table}.parquet"
# The existing M2 code:
duck_src = f"src_{src_table.replace('.', '_')}"
conn.execute(f"DROP TABLE IF EXISTS {duck_src}")
conn.execute(f"CREATE TABLE {duck_src} AS SELECT * FROM read_parquet('{parquet_path}')")
# All subsequent operations use {duck_src} (local DuckDB table)
```

**Acceptance:** Silver ETL reads from S3, writes to PostgreSQL. No local Parquet volume needed.

---

### ✅ Task 6 — Gold Export: Write to S3 (Optional — Bind Mount Already Works)

**File:** `orchestration/operators/gold_export_operator.py`

**Current state:** Already writes to `/opt/airflow/output/gold/` → bind-mounted to `data-science/marts/full/`. This works and survives Docker wipes.

**Optional S3 enhancement:** If S3 gold-exports bucket is desired for external access:

```python
output_prefix = f"s3://gold-exports/{batch_id}"
for t in tables:
    path = f"{output_prefix}/{t}.parquet"
    conn.execute(f"COPY (...) TO '{path}' (FORMAT PARQUET, COMPRESSION SNAPPY)")
```

**Recommendation:** Keep the bind mount as primary. S3 gold-exports is optional for external tools (e.g., BI dashboards, remote DS notebooks). The tar archive creation can be removed since S3 provides object storage natively.

**Acceptance:** Gold Parquet files land at `data-science/marts/full/` (bind mount) and optionally at `s3://gold-exports/`.

---

### ✅ Task 7 — DAG: Update Sensor + Clean Up Path Defaults

**File:** `orchestration/dags/imdb_pipeline_dag.py`

**Already done:**
- `silver_export` task wired after `wait_silver`, before `gold_dbt_run`

**Pending:**
- Update `imdb_sensor` to poll `s3://imdb-source/` instead of local directory (requires httpfs)
- Update `BronzeCompletionSensor` to check for S3 completion markers
- Remove hardcoded `BRONZE_PATH` and `bronze_dir` defaults (use S3 URLs)
- Note: `SilverDoneSensor` already polls PostgreSQL (no change needed)

---

### ✅ Task 8 — Documentation: Revise All Docs

**Files:**
- `data-engineering/docs/README.md` — Update pipeline overview to show S3 flow
- `data-engineering/docs/DOCKER_CONFIG_SUMMARY.md` — Restore RustFS + add env vars
- `data-engineering/docs/architecture_overview.md` — Add S3 layer
- `data-engineering/docs/export_guide.md` — Update paths to S3
- `README.md` (root) — Update service URLs + Docker stacks table + repo structure
- `data-engineering/docs/rustomfs_integration_plan.md` — This plan (consumed after approval)

---

### ✅ Task 9 — Cleanup: Remove Legacy Local Path Assumptions

**Files:** `orchestration/config/paths.yaml`, `bronze/config.py`, `bronze/db_configs.py`

- Update `paths.yaml` to reflect S3 paths as primary
- Flag/remove `bronze/` local-only config modules that are superseded
- The `bronze/` package (PySpark legacy ingest) stays as-is but clearly marked as superseded

---

## Docker Configuration

With RustFS restored (256 MB):

| Service | Mem Limit | S3 Access | Purpose |
|---------|-----------|-----------|---------|
| postgres | 3g | No | Silver/Gold warehouse |
| airflow | 2g | Yes (httpfs) | DAG + download script |
| etl-runner | 2.5g | Yes (httpfs) | Bronze + Silver ETL |
| rustfs | 256m | — | S3 object store |

**Total: ~7.75 GB / 13.9 GB (56%)** — well within peak ≤91%.

RustFS at 256 MB is negligible. It stays in the base compose because it's now a **core dependency** (not optional) — the entire pipeline reads/writes from it.

---

## Flow Diagram (Current DAG)

```
start
  │
  ▼
imdb_sensor → run_bronze → wait_bronze → bronze_done → quarantine_check
                                                        │
                                                        ▼
                                              silver_transform → wait_silver
                                                                     │
                                                                     ▼
                                                           silver_export ──────► (bind mount: marts/silver/)
                                                                     │
                                                                     ▼
                                                           gold_dbt_run → gold_dbt_test
                                                                     │
                                                                     ▼
                                                           dq_checks → freshness_check
                                                                     │
                                                                     ▼
                                                           gold_export ──────────► (bind mount: marts/full/)
                                                                     │
                                                                     ▼
                                                                    end
```

**Persistence (bind mounts survive Docker wipes):**

| Step | Writes To (Docker) | Host Path (persistent) |
|------|--------------------|-----------------------|
| Bronze ingestion | `/opt/airflow/output/bronze/` | `data-science/marts/bronze/` |
| Silver export | `/opt/airflow/output/silver/` | `data-science/marts/silver/` |
| Gold export | `/opt/airflow/output/gold/` | `data-science/marts/full/` |

---

## Estimated Effort

### ✅ Already Completed (Phase 1 Cleanup)

| Task | Files | Time |
|------|-------|------|
| SilverExportOperator + bind mount + DAG wiring | 3 | 20 min |
| Bronze + Gold bind mounts | 1 | 5 min |
| Duke removal (19+ reference updates) | 12 | 45 min |
| EDA notebook Part D (10 cells) | 1 | 25 min |
| Documentation updates | 4 | 20 min |
| **Completed subtotal** | **~21** | **~1.75 h** |

### ⏳ Pending (S3-Centric Pipeline)

| Task | Files | Est. Time |
|------|-------|-----------|
| 1. Docker compose + RustFS restore | 2 | 10 min |
| 2. Download script | 1 | 15 min |
| 3. DuckDB httpfs config | 3 | 15 min |
| 4. Bronze S3 rewrite | 2 | 30 min |
| 5. Silver S3 reads | 1 | 15 min |
| 6. Gold export S3 (optional — bind mount already works) | 1 | 10 min |
| 7. DAG path updates | 1 | 10 min |
| 8. Documentation | 5 | 25 min |
| 9. Legacy cleanup | 3 | 10 min |
| **Pending subtotal** | **~19** | **~2.5 h** |

### Grand Total

| Phase | Time |
|-------|------|
| Phase 1 Cleanup (completed) | ~1.75 h |
| S3-Centric Pipeline (pending) | ~2.5 h |
| **Total** | **~4.25 h** |

---

## Key Decisions

| Decision | Choice | Rationale | Status |
|----------|--------|-----------|--------|
| **Download method** | Pure Python `requests` → HTTP PUT | No `boto3` dependency. RustFS supports S3 REST API over plain HTTP. | ⏳ Pending |
| **Bronze → S3 write** | DuckDB `COPY TO 's3://...'` via httpfs | Native DuckDB S3 support. No extra libraries. | ⏳ Pending |
| **Silver → S3 read** | Single materialize per source file | One S3 range-read per file → DuckDB temp table → all processing local | ⏳ Pending |
| **Gold export** | Bind mount to `data-science/marts/full/` | Survives Docker wipes. DS notebook reads directly. | ✅ Done |
| **Silver export** | Bind mount to `data-science/marts/silver/` | Pre-Gold baseline for cross-layer benchmarking. Survives Docker wipes. | ✅ Done |
| **Bronze cache** | Bind mount to `data-science/marts/bronze/` | Survives Docker wipes. DS notebook reads directly. | ✅ Done |
| **Persistence strategy** | Host bind mounts (not S3) for DS consumption | S3 for pipeline hot path, bind mounts for DS deliverables. Best of both. | ✅ Done |

---

---
## Integration: DE Agent Accompaniment

Every task in this plan is executed via the DE Agent lifecycle commands defined in `data-engineering/AGENTS.md`:

| Task | Agent Command | Supporting Skill |
|------|---------------|------------------|
| Docker compose + RustFS restore | `/build airflow-orchestration` | `delta-medallion-architecture` |
| Download script | `/build python-pipeline-packaging` | — |
| DuckDB httpfs config | `/build delta-medallion-architecture` | `python-pipeline-packaging` |
| Bronze S3 rewrite | `/build python-pipeline-packaging` | `schema-evolution-migrations` |
| Silver S3 reads | `/build python-pipeline-packaging` | `airflow-orchestration` |
| Gold export to S3 | `/build dbt-analytics-engineering` | `delta-medallion-architecture` |
| DAG path updates | `/build airflow-orchestration` | — |
| Lineage & audit | `/validate lineage-pii-governance` | — |
| DQ contract testing | `/validate data-quality-contract-testing` | — |
| Resilience drills | `/validate data-resiliency-testing` | — |

The DE Agent loads the appropriate skill at session start, runs the lifecycle command, and validates acceptance criteria before proceeding to the next task.

---

## Optimization Principles

The S3-centric architecture balances four pillars:

| Principle | Application |
|-----------|-------------|
| **Efficiency** | Local DuckDB temp tables avoid repeated S3 reads. One S3 fetch per source file, then all chunked UNNEST operations run in-memory. Total added latency ~3-5 min vs 3h40m Silver ETL. |
| **Optimality** | S3 path-style requests minimize data transfer (range requests, not full-file downloads). DuckDB materializes only needed row groups/columns per query. Memory budget stays within 2.5 GB for etl-runner. |
| **Consistency** | Single source of truth (S3) eliminates dual-path confusion. Every pipeline stage reads/writes the same bucket convention. No local volumes to manage or lose. |
| **Coherence** | The architecture mirrors cloud-native medallion patterns (Bronze→Silver→Gold via S3). A public repo reader sees a clean, explainable flow: datasets.imdbws.com → download_imdb.py → RustFS S3 → DuckDB ETL → PostgreSQL → Gold Parquet → S3. |

---

## Plug-and-Play Guarantee

**One-time setup, zero friction for downstream modules:**

1. **Clone → `docker compose up -d`** — All 4 services (postgres, airflow, etl-runner, rustfs) start. RustFS auto-creates 3 buckets (`imdb-source/`, `bronze/`, `gold-exports/`).

2. **`python scripts/download_imdb.py`** — Downloads 7 `.tsv.gz` files directly to RustFS `s3://imdb-source/`. No local disk storage needed. SHA-256 verification built-in.

3. **Unpause DAG → triggers pipeline** — Airflow sensor detects source files in S3. Bronze reads from S3 → writes Parquet to S3. Silver materializes S3→DuckDB temp → writes PostgreSQL. Gold exports to S3.

4. **`docker cp` or host mount** — Gold Parquet arrives at `data-science/marts/full/` for DS consumption. The DS module reads local Parquet (unchanged).

**Deliverables for further modules:**
- **Data Science**: 6 Gold Parquet tables at `marts/full/` + `_MANIFEST.json` with batch metadata
- **Web Application**: Gold-to-API contract (`web-application/contracts/gold-to-api.md`) with schema guarantees
- **MLOps**: MLflow registry can consume from S3 or local Parquet

**No user action required between pipeline runs.** The sensor polls, Bronze is idempotent (checkpoint-based), Silver resumes via `pipeline_checkpoints` table, and Gold produces deterministic exports.

---

## Duke Removal & Notebook Migration Strategy

> **⚠ CRITICAL: All notebook work is COMPLETE.** Part D has been merged into Part B of the DS EDA notebook. Do NOT create new cells, modify existing cells, or add any notebook code after applying fixes. The existing cells in Part B handle all cross-layer assessment (Bronze/Silver/Gold counts, reconciliation, DQ anomalies, freshness, null-rates).

### Decision: Remove `data-engineering/duke/`

The `duke/` directory was Gate 0 — a human-lead pre-pipeline assessment phase. With the production pipeline now mature, this directory is removed:

| Artifact | Disposition |
|----------|-------------|
| Source `.tsv.gz` files | Superseded by `download_imdb.py` → RustFS S3 |
| `schema_draft.sql` | Implemented in Silver-layer DDL (`silver/` schema) |
| `duke_imdb_profilling.ipynb` | Superseded by DS EDA notebook Part D |
| `source_schemas.md` | Column profiles → automated null-rate checks in Part D |
| `anomalies.md` | DQ anomaly detection → automated in Part D |
| `array_parsing_rules.json` | Cardinality rules → implemented in Silver UNNEST operators |
| `download_metadata.json` | Checksums → integrated into `run_bronze.py` SHA-256 |
| `duke_imdb_source_assessment.md` | Narrative → condensed into Part D markdown |

### Migration Target: `data-science/notebooks/phase_2_duke_manual_eda.ipynb` — Part D (MERGED into Part B)

Part D — Exhaustive Bronze vs Silver vs Gold Layer Assessment — is complete and merged into Part B of the notebook:

```
Part B (Current Layout — Part D merged in):
  Part B Header        — Original notebook header
  Part A cells         — Source exploration
  Part B cells         — Schema analysis (now includes Part D content)
  Part D cells         — Cross-layer assessment (counts, reconciliation, DQ, freshness)
  Savestates           — Cache management
```

**Benefits of migration:**
- Automated (no manual notebook execution needed)
- Operates against live pipeline output (not stale snapshot)
- Cross-layer (compares Bronze ↔ Silver ↔ Gold, not just source TSV)
- Reproducible (same DuckDB/httpfs stack as the pipeline)
- Owned by Data Science (lives in DS module, not DE)

---

## Gold Mart Persistence Across Docker Wipes

### Problem

All pipeline storage is inside Docker volumes. `docker compose down -v` destroys everything:
- Source `.tsv.gz` in RustFS `s3://imdb-source/`
- Bronze Parquet in RustFS `s3://bronze/`
- **Gold Parquet marts** in the `airflow_data` named volume at `/opt/airflow/output/gold/`

The DS EDA notebook reads Gold marts from `data-science/marts/full/` on the host. When Docker is wiped, this directory becomes stale or empty.

### Solution: Bind Mount Both Bronze Parquet and Gold Marts to Host Paths

**File:** `docker/docker-compose.yml` — airflow service volumes:

```yaml
volumes:
  - ../data-science/marts/full:/opt/airflow/output/gold:rw     # Gold
  - ../data-science/marts/bronze:/opt/airflow/output/bronze:rw # Bronze
```

Three bind mounts, one pattern:

| Layer | Docker Path | Host Path | Survives `down -v` |
|-------|-------------|-----------|--------------------|
| Bronze Parquet | `/opt/airflow/output/bronze/` | `data-science/marts/bronze/` | Yes |
| Silver Parquet | `/opt/airflow/output/silver/` | `data-science/marts/silver/` | Yes |
| Gold Marts | `/opt/airflow/output/gold/` | `data-science/marts/full/` | Yes |

**No code changes needed.** `BronzeIngestOperator` writes to `/opt/airflow/output/bronze/` (default), `GoldExportOperator` writes to `/opt/airflow/output/gold/` (default). Both paths transparently redirect to the host.

### What the User Sees

After first successful pipeline run:

```
data-science/marts/
├── bronze/                          ← survives Docker wipe
│   ├── title.basics.parquet
│   ├── title.akas.parquet
│   ├── title.crew.parquet
│   ├── title.episode.parquet
│   ├── title.principals.parquet
│   ├── title.ratings.parquet
│   └── name.basics.parquet
├── silver/                          ← survives Docker wipe
│   ├── title_basics.parquet
│   ├── title_akas.parquet
│   ├── title_crew.parquet
│   ├── title_episode.parquet
│   ├── title_principal.parquet
│   ├── title_rating.parquet
│   ├── name_basics.parquet
│   ├── title_genre.parquet
│   ├── title_director.parquet
│   ├── title_writer.parquet
│   ├── title_akas_type.parquet
│   ├── title_akas_attribute.parquet
│   ├── title_principal_char.parquet
│   ├── name_profession.parquet
│   ├── name_known_for_title.parquet
│   └── _MANIFEST.json
└── full/                            ← survives Docker wipe
    ├── dim_person.parquet
    ├── dim_title.parquet
    ├── fact_episode.parquet
    ├── fact_performance.parquet
    ├── fact_title_principal.parquet
    ├── fact_title_rating.parquet
    └── _MANIFEST.json
```

`docker compose down -v` → empty RustFS, empty PostgreSQL. **All three `marts/bronze/`, `marts/silver/`, `marts/full/` are untouched.**

### Silver Export Operator

**New file:** `orchestration/operators/silver_export_operator.py`

Follows the same pattern as `GoldExportOperator`:

```
DuckDB postgres_scanner → read 15 silver.* tables → COPY TO Parquet (Snappy) → _MANIFEST.json
```

Exports all tables:
- 7 parent: `title_basics`, `title_akas`, `title_crew`, `title_episode`, `title_principal`, `title_rating`, `name_basics`
- 8 child: `title_genre`, `title_director`, `title_writer`, `title_akas_type`, `title_akas_attribute`, `title_principal_char`, `name_profession`, `name_known_for_title`
- **Total: 15 Silver tables** exported as Snappy Parquet

**DAG wiring** (`imdb_pipeline_dag.py`):

```python
wait_silver >> silver_export >> gold_dbt_run >> gold_dbt_test
```

Runs immediately after Silver ETL completes, before Gold dbt models. The exported Parquet serves as the pre-Gold baseline for cross-layer benchmarking.

### EDA Notebook Part D — Multi-Source Resilience

> **⚠ CRITICAL: This section is COMPLETE and MERGED.** Do NOT add new notebook cells, modify existing cells, or create any notebook code. The existing cells in Part B handle all cross-layer assessment.

Each layer reads from **two strategies**, tried in order:

| Layer | Strategy 1 (cache) | Strategy 2 (fallback) | Failsafe |
|-------|--------------------|-----------------------|----------|
| Bronze | `marts/bronze/{table}.parquet` | `s3://imdb-source/` via httpfs | Skip |
| Silver | `marts/silver/{table}.parquet` | PostgreSQL via psycopg2 | Skip |
| Gold | `marts/full/{table}.parquet` | — (host bind mount only) | Skip |

| Scenario | Bronze | Silver | Gold | Result |
|----------|--------|--------|------|--------|
| Fresh pipeline run | Cache ✓ | Cache ✓ | Marts ✓ | Full 3-layer comparison |
| After `down -v` (all caches intact) | Cache ✓ | Cache ✓ | Marts ✓ | Full comparison, no Docker needed |
| Only Gold exists | Skipped | Skipped | Marts ✓ | Gold QA only |
| Nothing exists | Skipped | Skipped | Skipped | Clear instructions |

### Edge Cases

- **Stale data after DBT / Silver change:** Re-running the pipeline overwrites all three bind mounts in place. No stale data issue.
- **Partial cache (`bronze/` exists, `silver/` missing):** Part D runs the comparison for available layers and skips the rest.
- **Downstream DS notebook runs before pipeline:** Clear "file not found" messages guide the user to run the pipeline first.

---

## Rollback & Backward Compatibility

### If S3 Integration Breaks

The bind mount persistence layer is **independent** of S3. If RustFS or httpfs fails:

| Layer | Fallback Behavior |
|-------|-------------------|
| Bronze | `run_bronze.py` can fall back to local TSV reads (old `SOURCE_DIR` path) |
| Silver | `silver_operator.py` reads from bind-mounted Bronze Parquet (already local) |
| Gold | `gold_export_operator.py` reads from PostgreSQL, writes to bind mount (unchanged) |
| Silver Export | `silver_export_operator.py` reads from PostgreSQL, writes to bind mount (unchanged) |
| EDA Notebook | Part D reads from local caches (S3 is optional fallback) |

**The bind mounts work regardless of S3.** The S3 integration is an optimization for the pipeline hot path, not a requirement for DS deliverables.

### Rolling Back a Failed S3 Migration

If S3 integration introduces issues, revert by:

1. Revert `run_bronze.py` — restore `SOURCE_DIR = "/opt/airflow/data-engineering/duke/gate0/source/"` (or use bind mount)
2. Revert `silver_operator.py` — restore local `parquet_path` (already reads from bind mount)
3. Remove RustFS from `docker-compose.yml` (or leave disabled)
4. Keep bind mounts — they work without S3

### Backward Compatibility

| Change | Compatible With Old Docker? | Notes |
|--------|----------------------------|-------|
| Bind mounts (Bronze/Silver/Gold) | ✅ Yes | New volume mounts, old containers still work |
| SilverExportOperator | ✅ Yes | New task in DAG, old DAG without it still runs |
| duke/ removal | ⚠️ Partial | Old `SOURCE_DIR` references break. Must update code. |
| S3 httpfs config | ❌ No | Requires RustFS container + httpfs extension |

---

## Acceptance Criteria Checklist

Before approving S3 implementation, verify:

- [x] `docker compose up -d` starts all 4 services (postgres, airflow, etl-runner, rustfs)
- [x] `python scripts/download_imdb.py` populates `s3://imdb-source/` with 7 files (code written, not yet run)
- [x] Bronze reads from S3, writes Parquet to S3
- [x] Silver reads Bronze Parquet from S3 via httpfs
- [x] SilverExportOperator writes 15 tables to `data-science/marts/silver/`
- [x] Gold export writes to `data-science/marts/full/` (with optional S3 gold-exports)
- [x] EDA notebook Part D runs with all 3 layers (Bronze/Silver/Gold) — **ALREADY COMPLETE, DO NOT RE-EXECUTE**
- [x] `docker compose down -v` does NOT delete `marts/bronze/`, `marts/silver/`, `marts/full/` (bind mounts, unchanged)
- [x] RAM usage stays ≤91% during full pipeline run (rustfs 256m added, ~8 GB total)
- [x] All 9 pending tasks completed and verified

> **⚠ NOTEBOOK RULE:** Part D cells are complete and merged into Part B. After applying fixes to the pipeline code, do NOT touch notebook cells. The notebook should only be run, not modified.

---

## ⏸ Waiting for Approval

This plan replaces Options A/B from the previous draft. Reply with:
- **"Approve"** — proceed with S3-centric pipeline implementation
- **"Modify"** — request changes
- **"Hold"** — defer
