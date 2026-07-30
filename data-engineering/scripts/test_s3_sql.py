import duckdb, sys
sys.path.insert(0, "/opt/airflow/data-engineering")
from bronze.s3_config import configure_s3
conn = duckdb.connect(":memory:")
configure_s3(conn)

tests = [
    ("simple count", "SELECT count(*) FROM read_csv('s3://imdb-source/title.basics.tsv.gz', delim='\t', header=true, all_varchar=true, ignore_errors=true)"),
    ("with columns", "SELECT * FROM read_csv('s3://imdb-source/title.basics.tsv.gz', columns={'tconst': 'VARCHAR', 'titleType': 'VARCHAR'}, delim='\t', header=true, null_padding=true, ignore_errors=true, quote='', escape='') LIMIT 1"),
    ("nested subquery", "SELECT count(*) FROM (SELECT * FROM read_csv('s3://imdb-source/title.basics.tsv.gz', delim='\t', header=true, all_varchar=true, ignore_errors=true))"),
    ("temp table", "CREATE TEMP TABLE test AS SELECT * FROM read_csv('s3://imdb-source/title.basics.tsv.gz', delim='\t', header=true, all_varchar=true, ignore_errors=true)"),
]

for name, sql in tests:
    try:
        r = conn.execute(sql).fetchone()
        print(f"[OK] {name}: {r}")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
