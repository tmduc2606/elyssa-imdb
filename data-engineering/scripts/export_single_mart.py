import subprocess, sys, os

table = sys.argv[1]
out_dir = "/opt/airflow/data-engineering/scripts/"
out_path = os.path.join(out_dir, f"{table}.parquet")
csv_path = os.path.join("/tmp", f"{table}.csv")

print(f"Exporting {table} to CSV via psql...")
env = os.environ.copy()
env["PGPASSWORD"] = "elyssa_pg_2026"
rc = subprocess.run([
    "psql", "-h", "postgres", "-U", "elyssa", "-d", "elyssa_warehouse",
    "-c", f"\\COPY gold_gold.\"{table}\" TO '{csv_path}' WITH (FORMAT CSV, HEADER)"
], capture_output=True, text=True, env=env)
if rc.returncode != 0:
    print(f"psql stderr: {rc.stderr}")
    sys.exit(1)
print(f"CSV exported. Converting to Parquet...")

import duckdb
con = duckdb.connect(':memory:')
con.execute(f"COPY (SELECT * FROM read_csv_auto('{csv_path}', header=true)) TO '{out_path}' (FORMAT PARQUET, COMPRESSION SNAPPY)")
r = con.execute(f"SELECT count(*) FROM read_csv_auto('{csv_path}', header=true)").fetchone()[0]
con.close()

os.remove(csv_path)
print(f"{table}: {r:,} rows -> {out_path}")
