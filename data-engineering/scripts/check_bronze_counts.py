import duckdb
c = duckdb.connect(":memory:")
for t in ["title.basics", "title.akas", "title.principals", "name.basics", "title.episode", "title.ratings", "title.crew"]:
    try:
        n = c.execute(f"SELECT count(*) FROM read_parquet('/opt/airflow/output/bronze/{t}.parquet')").fetchone()[0]
        print(f"LOCAL {t}: {n:,}")
    except Exception as e:
        print(f"LOCAL {t}: ERROR {str(e).splitlines()[0]}")
