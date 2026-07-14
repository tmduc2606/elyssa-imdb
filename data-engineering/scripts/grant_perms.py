import psycopg2
conn = psycopg2.connect("host=postgres port=5432 user=elyssa password='***' dbname=elyssa_warehouse")
conn.autocommit = True
cur = conn.cursor()
# Grant permissions (idempotent)
cur.execute("GRANT USAGE ON SCHEMA silver TO elyssa")
cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA silver TO elyssa")
# Test: can we see the tables?
cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname = 'silver'")
print(f"Silver tables visible: {cur.fetchone()[0]}")
conn.close()
print("Done")
