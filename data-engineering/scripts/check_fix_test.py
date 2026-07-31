import duckdb, sys
sys.path.insert(0, "/opt/etl/data-engineering")
from bronze.s3_config import configure_s3
c = duckdb.connect(":memory:")
configure_s3(c)
for t in ["title.basics", "title.akas"]:
    n = c.execute(
        f"SELECT count(*) FROM read_csv('s3://imdb-source/{t}.tsv.gz', delim='\\t', header=true, all_varchar=true, null_padding=true, ignore_errors=true, quote='', escape='')"
    ).fetchone()[0]
    print(f"FIXED write_cfg {t}: {n:,}")
