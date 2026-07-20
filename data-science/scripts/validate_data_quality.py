import duckdb

con = duckdb.connect()
MARTS_DIR = 'C:/Users/Admin/Documents/GitHub/elyssa-imdb/data-science/marts'

# Check batch_id in fact tables
for mart in ['fact_title_principal', 'fact_performance', 'fact_episode', 'fact_title_rating']:
    path = f'{MARTS_DIR}/{mart}.parquet'
    batch_vals = con.execute(f"SELECT batch_id, COUNT(*) as cnt FROM read_parquet('{path}') GROUP BY batch_id LIMIT 5").fetchall()
    print(f"{mart}.parquet batch_id:")
    for r in batch_vals:
        print(f"  '{r[0]}': {r[1]:,}")

# Check region_list data quality
print("\ndim_title.parquet region_list stats:")
path = f'{MARTS_DIR}/dim_title.parquet'
total = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]
nonnull = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}') WHERE region_list IS NOT NULL").fetchone()[0]
print(f"  Total: {total:,}")
print(f"  With regions: {nonnull:,} ({nonnull/total*100:.1f}%)")

# Sample of titles with regions
print("\nSample titles with regions:")
samples = con.execute(f"""
SELECT tconst, primary_title, region_list, language_list, aka_count
FROM read_parquet('{path}')
WHERE region_list IS NOT NULL
LIMIT 5
""").fetchall()
for r in samples:
    print(f"  {r}")

# Sample of titles without regions
print("\nSample titles without regions:")
samples = con.execute(f"""
SELECT tconst, primary_title, region_list, language_list, aka_count
FROM read_parquet('{path}')
WHERE region_list IS NULL
LIMIT 5
""").fetchall()
for r in samples:
    print(f"  {r}")

con.close()
