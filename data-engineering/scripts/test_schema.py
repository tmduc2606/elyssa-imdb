import psycopg2
import sys

conn = psycopg2.connect(
    host="postgres", port=5432,
    user="elyssa", password="elyssa_pg_2026",
    dbname="elyssa_warehouse",
)
conn.autocommit = True

with open("/opt/airflow/data-engineering/silver/schema.sql", "r") as f:
    sql = f.read()

statements = [s.strip() for s in sql.split(';') if s.strip()]

for i, stmt in enumerate(statements):
    try:
        with conn.cursor() as cur:
            cur.execute(stmt)
        print(f"[OK] Statement {i+1}: {stmt[:60]}...")
    except Exception as e:
        print(f"[ERR] Statement {i+1}: {stmt[:60]}...")
        print(f"      Error: {e}")
        # Don't break - continue to see all errors

conn.close()
print("Done")
