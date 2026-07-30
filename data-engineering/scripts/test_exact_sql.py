import duckdb, sys
sys.path.insert(0, "/opt/airflow/data-engineering")
from bronze.s3_config import configure_s3
conn = duckdb.connect(":memory:")
configure_s3(conn)

source_url = "s3://imdb-source/title.basics.tsv.gz"
table = "title.basics"

schema_def = {
    "tconst": "VARCHAR", "titleType": "VARCHAR", "primaryTitle": "VARCHAR",
    "originalTitle": "VARCHAR", "isAdult": "VARCHAR", "startYear": "VARCHAR",
    "endYear": "VARCHAR", "runtimeMinutes": "VARCHAR", "genres": "VARCHAR",
}

cols_str = ", ".join(f"'{k}': '{v}'" for k, v in schema_def.items())

# Test 1: simplest possible - no subquery, no columns, no quote
sql1 = "CREATE TEMP TABLE t1 AS SELECT * FROM read_csv('s3://imdb-source/title.basics.tsv.gz', delim='\t', header=true, all_varchar=true, ignore_errors=true)"
try:
    conn.execute(sql1)
    print("[OK] t1: no subquery, all_varchar")
except Exception as e:
    print(f"[FAIL] t1: {e}")

# Test 2: with columns (no subquery)
sql2 = f"CREATE TEMP TABLE t2 AS SELECT * FROM read_csv('{source_url}', columns={{{cols_str}}}, delim='\t', header=true, null_padding=true, ignore_errors=true)"
try:
    conn.execute(sql2)
    print("[OK] t2: with columns, no subquery")
except Exception as e:
    print(f"[FAIL] t2: {e}")

# Test 3: with columns and with quote=''
sql3 = f"CREATE TEMP TABLE t3 AS SELECT * FROM read_csv('{source_url}', columns={{{cols_str}}}, delim='\t', header=true, null_padding=true, ignore_errors=true, quote='', escape='')"
try:
    conn.execute(sql3)
    print("[OK] t3: with columns, quote=''")
except Exception as e:
    print(f"[FAIL] t3: {e}")

# Test 4: no columns, quote='', in subquery
sql4 = "CREATE TEMP TABLE t4 AS SELECT * FROM (SELECT * FROM read_csv('s3://imdb-source/title.basics.tsv.gz', delim='\t', header=true, all_varchar=true, ignore_errors=true, quote='', escape=''))"
try:
    conn.execute(sql4)
    print("[OK] t4: subquery, no columns")
except Exception as e:
    print(f"[FAIL] t4: {e}")

# Test 5: with columns AND subquery
sql5 = f"CREATE TEMP TABLE t5 AS SELECT * FROM (SELECT * FROM read_csv('{source_url}', columns={{{cols_str}}}, delim='\t', header=true, null_padding=true, ignore_errors=true, quote='', escape=''))"
try:
    conn.execute(sql5)
    print("[OK] t5: columns + subquery")
except Exception as e:
    print(f"[FAIL] t5: {e}")

# Test 6: SELECT with extra cols in subquery
sql6 = f"CREATE TEMP TABLE t6 AS SELECT *, 'test' AS extra FROM (SELECT * FROM read_csv('{source_url}', columns={{{cols_str}}}, delim='\t', header=true, null_padding=true, ignore_errors=true, quote='', escape=''))"
try:
    conn.execute(sql6)
    print("[OK] t6: extra cols + subquery")
except Exception as e:
    print(f"[FAIL] t6: {e}")

# Test 7: the exact bronze SQL
base_sql = (
    f"SELECT *, '{source_url}' AS _source_file, 'test' AS _source_table "
    f"FROM (SELECT * FROM read_csv('{source_url}', columns={{{cols_str}}}, delim='\t', header=true, null_padding=true, ignore_errors=true, quote='', escape=''))"
)
sql7 = f"CREATE TEMP TABLE t7 AS {base_sql}"
try:
    conn.execute(sql7)
    print("[OK] t7: exact bronze SQL")
except Exception as e:
    print(f"[FAIL] t7: {e}")
