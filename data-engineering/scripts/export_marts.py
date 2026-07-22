import duckdb, sys, os, json
from datetime import datetime, timezone
from pathlib import Path

out_dir = os.environ.get("GOLD_EXPORT_DIR", "/opt/airflow/output/gold/")
pg_host = os.environ.get("GOLD_EXPORT_PG_HOST", "postgres")
pg_port = os.environ.get("GOLD_EXPORT_PG_PORT", "5432")
pg_db = os.environ.get("GOLD_EXPORT_PG_DB", "elyssa_warehouse")
pg_user = os.environ.get("GOLD_EXPORT_PG_USER", "elyssa")
pg_password = os.environ.get("GOLD_EXPORT_PG_PASSWORD", "")

if not pg_password:
    print("FATAL: GOLD_EXPORT_PG_PASSWORD environment variable is required", file=sys.stderr)
    sys.exit(1)

Path(out_dir).mkdir(parents=True, exist_ok=True)
conn = duckdb.connect(':memory:')
conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
dsn = f"host={pg_host} port={pg_port} dbname={pg_db} user={pg_user} password={pg_password}"
conn.execute(f"ATTACH '{dsn}' AS pg (TYPE POSTGRES, SCHEMA 'gold_gold');")

tables = ['dim_person', 'dim_title', 'fact_episode', 'fact_performance', 'fact_title_principal', 'fact_title_rating']
row_counts = {}
for t in tables:
    path = os.path.join(out_dir, f"{t}.parquet")
    if t == 'dim_title':
        conn.execute(f"""
            COPY (
                SELECT * FROM pg.gold_gold."{t}"
                WHERE NOT (title_type = 'movie' AND (runtime_minutes IS NULL OR runtime_minutes <= 0))
            ) TO '{path}' (FORMAT PARQUET, COMPRESSION SNAPPY)
        """)
    else:
        conn.execute(f'COPY (SELECT * FROM pg.gold_gold."{t}") TO \'{path}\' (FORMAT PARQUET, COMPRESSION SNAPPY)')
    r = conn.execute(f'SELECT count(*) FROM pg.gold_gold."{t}"').fetchone()[0]
    row_counts[t] = r
    print(f"Exported {t}: {r:,} rows -> {path}")

manifest = {
    "batch_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
    "exported_at": datetime.now(timezone.utc).isoformat(),
    "tables": tables,
    "row_counts": row_counts,
}
manifest_path = os.path.join(out_dir, "_MANIFEST.json")
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)
print(f"Manifest written to {manifest_path}")

conn.close()
print("Done")
