import psycopg2
pg = psycopg2.connect(host="postgres", port=5432, user="elyssa", password="elyssa_pg_2026", dbname="elyssa_warehouse")
c = pg.cursor()
c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'silver' ORDER BY table_name")
for row in c.fetchall():
    print(row[0])
pg.close()
