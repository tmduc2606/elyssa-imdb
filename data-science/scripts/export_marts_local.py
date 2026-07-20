import duckdb, os, sys
from pathlib import Path

out_dir = Path(__file__).resolve().parents[1] / "marts"
out_dir.mkdir(parents=True, exist_ok=True)

conn = duckdb.connect(':memory:')
conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
conn.execute("ATTACH 'host=localhost port=54321 dbname=elyssa_warehouse user=elyssa password=elyssa_pg_2026' AS pg (TYPE POSTGRES, SCHEMA 'gold_gold');")

tables = ['dim_person','dim_title','fact_episode','fact_performance','fact_title_principal','fact_title_rating']
for t in tables:
    path = os.path.join(str(out_dir), f"{t}.parquet")
    print(f"Exporting {t}...")
    conn.execute(f'COPY (SELECT * FROM pg.gold_gold."{t}") TO \'{path}\' (FORMAT PARQUET, COMPRESSION SNAPPY);')
    r = conn.execute(f'SELECT count(*) FROM pg.gold_gold."{t}"').fetchone()[0]
    print(f"  {t}: {r:,} rows -> {path}")

conn.close()
print("Done")
