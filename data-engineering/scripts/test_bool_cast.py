import psycopg2
pg = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = pg.cursor()

# Test 1: implicit cast from VARCHAR to BOOLEAN in INSERT...SELECT
cur.execute("CREATE TEMP TABLE test_bool_stg (val VARCHAR)")
cur.execute("INSERT INTO test_bool_stg VALUES ('t'), ('f'), ('0'), ('1')")
cur.execute("CREATE TEMP TABLE test_bool_in (val BOOLEAN)")
try:
    cur.execute("INSERT INTO test_bool_in SELECT val FROM test_bool_stg")
    cur.execute("SELECT * FROM test_bool_in")
    print("TEST 1 - Implicit VARCHAR->BOOLEAN: SUCCESS", cur.fetchall())
except Exception as e:
    print("TEST 1 - Implicit VARCHAR->BOOLEAN: FAILED:", e)

pg.rollback()

# Test 2: explicit cast
cur.execute("INSERT INTO test_bool_in SELECT val::BOOLEAN FROM test_bool_stg")
cur.execute("SELECT * FROM test_bool_in")
print("TEST 2 - Explicit CAST: SUCCESS", cur.fetchall())

pg.rollback()

# Test 3: COPY FROM CSV with t/f
import io
cur.execute("CREATE TEMP TABLE test_bool_in3 (val BOOLEAN)")
data = "val\nt\nf\n0\n1\n"
cur.copy_expert("COPY test_bool_in3 FROM STDIN WITH (FORMAT CSV, HEADER true)", io.StringIO(data))
cur.execute("SELECT * FROM test_bool_in3")
print("TEST 3 - COPY CSV t/f: SUCCESS", cur.fetchall())

pg.rollback()

# Test 4: COPY FROM with explicit column (staging table)
cur.execute("CREATE TEMP TABLE test_bool_stg2 (val VARCHAR)")
data = "is_adult\nt\nf\n0\n1\n"
cur.copy_expert("COPY test_bool_stg2 (val) FROM STDIN WITH (FORMAT CSV, HEADER true, DELIMITER '|', NULL '')", io.StringIO(data))
cur.execute("SELECT * FROM test_bool_stg2")
print("TEST 4 - COPY to VARCHAR staging: SUCCESS", cur.fetchall())

pg.rollback()
cur.close()
pg.close()
