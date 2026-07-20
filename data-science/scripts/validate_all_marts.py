import duckdb
import os

con = duckdb.connect()
MARTS_DIR = 'C:/Users/Admin/Documents/GitHub/elyssa-imdb/data-science/marts'

expected = {
    'dim_title': {
        'cols': ['tconst', 'title_type', 'primary_title', 'original_title', 'is_adult', 'start_year', 'end_year', 'runtime_minutes', 'genre_list', 'director_names', 'writer_names', 'average_rating', 'num_votes', 'popularity_segment', 'rating_bucket', 'parent_tconst', 'series_title', 'season_number', 'episode_number', 'region_list', 'language_list', 'aka_count'],
        'min_rows': 12600000
    },
    'dim_person': {
        'cols': ['nconst', 'primary_name', 'birth_year', 'death_year', 'age_at_death', 'generation', 'profession_list', 'known_for_titles'],
        'min_rows': 15400000
    },
    'fact_title_principal': {
        'cols': ['title_key', 'name_key', 'character_name', 'ordering', 'category', 'job', 'batch_id', 'ingested_at'],
        'min_rows': 100000000
    },
    'fact_performance': {
        'cols': ['tconst', 'ordering', 'nconst', 'category', 'job', 'character_name', 'batch_id', 'ingested_at'],
        'min_rows': 100000000
    },
    'fact_episode': {
        'cols': ['episode_key', 'series_key', 'season_number', 'episode_number', 'series_title', 'series_start_year', 'series_type', 'batch_id', 'ingested_at'],
        'min_rows': 9700000
    },
    'fact_title_rating': {
        'cols': ['title_key', 'snapshot_date', 'average_rating', 'num_votes', 'batch_id', 'ingested_at'],
        'min_rows': 1600000
    }
}

total_pass = 0
total_fail = 0

for mart, spec in expected.items():
    path = f'{MARTS_DIR}/{mart}.parquet'
    print(f'\n{"="*60}')
    print(f'{mart}.parquet')
    print(f'{"="*60}')
    
    # Get columns from parquet
    cols = con.execute(f"SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet('{path}'))").fetchall()
    actual_cols = [c[0] for c in cols]
    expected_cols = spec['cols']
    
    # Column count check
    col_match = actual_cols == expected_cols
    if col_match:
        print(f'  Columns: {len(actual_cols)} [PASS]')
        total_pass += 1
    else:
        print(f'  Columns: {len(actual_cols)} (expected {len(expected_cols)}) [FAIL]')
        missing = [c for c in expected_cols if c not in actual_cols]
        extra = [c for c in actual_cols if c not in expected_cols]
        if missing:
            print(f'    MISSING: {missing}')
        if extra:
            print(f'    EXTRA: {extra}')
        total_fail += 1
    
    # Row count check
    cnt = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]
    row_ok = cnt >= spec['min_rows']
    if row_ok:
        print(f'  Rows: {cnt:,} (min {spec["min_rows"]:,}) [PASS]')
        total_pass += 1
    else:
        print(f'  Rows: {cnt:,} (min {spec["min_rows"]:,}) [FAIL]')
        total_fail += 1
    
    # Null rates
    print(f'  Null rates:')
    for c in expected_cols:
        nulls = con.execute(f"SELECT COUNT(*) FROM read_parquet('{path}') WHERE \"{c}\" IS NULL").fetchone()[0]
        pct = (nulls / cnt * 100) if cnt > 0 else 0
        flag = ' [WARN]' if pct > 90 else ''
        print(f'    {c}: {pct:.1f}%{flag}')
    
    # File size
    size = os.path.getsize(path)
    print(f'  Size: {size/1024/1024:.1f} MB')

print(f'\n{"="*60}')
print(f'SUMMARY: {total_pass} PASS, {total_fail} FAIL')
print(f'{"="*60}')

con.close()
