import duckdb, psycopg2

conn = duckdb.connect(':memory:')
conn.execute("SET threads = 2")

tsv_path = 's3://imdb-source/title.ratings.tsv.gz'
row_count = conn.execute(
    "SELECT COUNT(*) FROM read_csv(?, sep='\t', header=true, all_varchar=true)",
    [tsv_path]
).fetchone()[0]
print(f'Rows in source: {row_count}')

csv_path = '/tmp/tr.csv'
nm = chr(92) + 'N'
query = (
    "COPY ("
    "SELECT tconst, NULLIF(averageRating, '" + nm + "') as averageRating, "
    "NULLIF(numVotes, '" + nm + "') as numVotes "
    "FROM read_csv(?, sep='\t', header=true, all_varchar=true)"
    ") TO '" + csv_path + "' (FORMAT CSV, HEADER true, DELIMITER '|')"
)
conn.execute(query, [tsv_path])

with open(csv_path) as f:
    for i, line in enumerate(f):
        if i < 3:
            print(f'CSV {i}: {line.strip()[:100]}')

pg = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
pg.autocommit = False
cur = pg.cursor()
cur.execute('TRUNCATE silver.title_rating CASCADE')
with open(csv_path) as f:
    cur.copy_expert(
        "COPY silver.title_rating (tconst, average_rating, num_votes) FROM STDIN "
        "WITH (FORMAT CSV, HEADER true, DELIMITER '|', NULL '')",
        f
    )
pg.commit()
cnt = cur.execute('SELECT count(*) FROM silver.title_rating').fetchone()[0]
print(f'After COPY: {cnt} rows in silver.title_rating')
pg.close()
print('DONE')
