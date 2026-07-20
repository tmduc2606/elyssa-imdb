import duckdb

db_path = 'C:/Users/Admin/Documents/GitHub/elyssa-imdb/data-science/notebooks/imdb_gold.db'
con = duckdb.connect(db_path)

keepers = {
    'bronze_name_basics', 'bronze_title_basics', 'bronze_title_crew',
    'bronze_title_episode', 'bronze_title_principals', 'bronze_title_ratings',
    'dim_person', 'dim_title', 'fact_episode', 'fact_performance',
    'fact_title_principal', 'fact_title_rating'
}

tables = con.execute("SELECT table_name, table_type FROM information_schema.tables WHERE table_schema != 'information_schema'").fetchall()
views = con.execute("SELECT table_name FROM information_schema.views WHERE table_schema != 'information_schema'").fetchall()

for name, ttype in tables:
    n = name[0] if isinstance(name, tuple) else name
    if n not in keepers:
        try:
            if 'VIEW' in str(ttype).upper():
                con.execute(f'DROP VIEW IF EXISTS "{n}"')
            else:
                con.execute(f'DROP TABLE IF EXISTS "{n}"')
            print(f'Dropped: {n}')
        except:
            try:
                con.execute(f'DROP VIEW IF EXISTS "{n}"')
                print(f'Dropped view: {n}')
            except:
                pass

for name in views:
    n = name[0] if isinstance(name, tuple) else name
    if n not in keepers:
        try:
            con.execute(f'DROP VIEW IF EXISTS "{n}"')
            print(f'Dropped view: {n}')
        except:
            pass

remaining = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema != 'information_schema'").fetchall()
v = con.execute("SELECT table_name FROM information_schema.views WHERE table_schema != 'information_schema'").fetchall()
print(f'Remaining tables: {[r[0] for r in remaining]}')
print(f'Remaining views: {[r[0] for r in v]}')
con.close()
