"""Generate deterministic CI test fixtures from local Gold marts.

Produces a small, committed subset of Gold parquet (tests/fixtures/gold)
plus the DS contract artifacts (tests/fixtures/processed) so that CI jobs
(API Gateway tests, DS CI verify-artifacts/validate-contracts) can run
without the gitignored runtime marts.

Usage (from data-science/):  python scripts/generate_ci_fixtures.py
"""
import shutil
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
GOLD_DIR = ROOT / "marts" / "gold"
PROCESSED_DIR = ROOT / "marts" / "processed"
MODELS_DIR = ROOT / "notebooks" / "models"
FIXTURE_DIR = ROOT / "tests" / "fixtures"
FIXTURE_GOLD = FIXTURE_DIR / "gold"
FIXTURE_PROCESSED = FIXTURE_DIR / "processed"

MARTS = [
    "dim_title",
    "dim_person",
    "fact_title_principal",
    "fact_performance",
    "fact_episode",
    "fact_title_rating",
]

FORCED_TCONSTS = ["tt28262612", "tt0133093", "tt0076759"]
FORCED_NCONSTS = ["nm0000108", "nm0000206"]
SEED = 42
SAMPLE_ROWS = 800
MAX_ROWS = 3000


def subset_dim_title(con: duckdb.DuckDBPyConnection) -> list[str]:
    src = GOLD_DIR / "dim_title.parquet"
    forced_ids = "'" + "','".join(FORCED_TCONSTS) + "'"
    exact = con.execute(f"""
        SELECT * FROM '{src}' WHERE tconst IN ({forced_ids})
    """).df()
    matches = con.execute(f"""
        SELECT * FROM '{src}'
        WHERE tconst NOT IN ({forced_ids})
          AND (primary_title ILIKE '%matrix%'
               OR primary_title ILIKE '%star%'
               OR genre_list LIKE '%Action%')
        ORDER BY tconst
        LIMIT {MAX_ROWS}
    """).df()
    sample = con.execute(f"""
        SELECT * FROM '{src}'
        WHERE tconst NOT IN ({forced_ids})
          AND primary_title NOT ILIKE '%matrix%'
          AND primary_title NOT ILIKE '%star%'
          AND genre_list NOT LIKE '%Action%'
        USING SAMPLE ({SAMPLE_ROWS} ROWS) REPEATABLE ({SEED})
        ORDER BY tconst
        LIMIT 500
    """).df()
    df = pd.concat([exact, matches, sample], ignore_index=True).drop_duplicates("tconst")
    out = FIXTURE_GOLD / "dim_title.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"  dim_title: {len(df)} rows -> {out.name}")
    return list(df["tconst"])


def subset_mart(con: duckdb.DuckDBPyConnection, mart: str, tconsts: list[str],
                column: str = "tconst", extra_ids: list[str] | None = None) -> int:
    src = GOLD_DIR / f"{mart}.parquet"
    if not src.exists():
        return 0
    ids = "'" + "','".join(tconsts) + "'"
    exact = con.execute(f"""
        SELECT * FROM '{src}' WHERE {column} IN ({ids})
    """).df()
    frames = [exact]
    if extra_ids:
        eids = "'" + "','".join(extra_ids) + "'"
        if mart == "fact_title_principal":
            extra = f"name_key IN ({eids})"
        elif mart == "fact_performance":
            extra = f"nconst IN ({eids})"
        else:
            extra = ""
        if extra:
            extra_df = con.execute(f"SELECT * FROM '{src}' WHERE {extra}").df()
            frames.append(extra_df)
    seen = pd.concat(frames, ignore_index=True)
    rest = con.execute(f"""
        SELECT * FROM '{src}'
        WHERE {column} IN ({ids})
        LIMIT {MAX_ROWS}
    """).df()
    df = pd.concat([seen, rest], ignore_index=True).drop_duplicates()
    out = FIXTURE_GOLD / f"{mart}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"  {mart}: {len(df)} rows -> {out.name}")
    return len(df)


def subset_person(con: duckdb.DuckDBPyConnection, tconsts: list[str] | None = None) -> None:
    src = GOLD_DIR / "dim_person.parquet"
    forced = "'" + "','".join(FORCED_NCONSTS) + "'"
    extra_people: list[str] = []
    if tconsts:
        forced_t = "'" + "','".join(FORCED_TCONSTS) + "'"
        rows = con.execute(f"""
            SELECT DISTINCT name_key FROM '{GOLD_DIR / 'fact_title_principal.parquet'}'
            WHERE title_key IN ({forced_t})
        """).fetchall()
        extra_people = [r[0] for r in rows if r[0]]
    exact = con.execute(f"""
        SELECT * FROM '{src}'
        WHERE nconst IN ({forced})
    """).df()
    referenced: list[str] = []
    if extra_people:
        ids = "'" + "','".join(extra_people) + "'"
        referenced = [r[0] for r in con.execute(f"""
            SELECT DISTINCT nconst FROM '{src}' WHERE nconst IN ({ids})
        """).fetchall()]
    frames = [exact]
    if referenced:
        rids = "'" + "','".join(referenced) + "'"
        frames.append(con.execute(
            f"SELECT * FROM '{src}' WHERE nconst IN ({rids})").df())
    match = con.execute(f"""
        SELECT * FROM '{src}'
        WHERE primary_name ILIKE '%keanu%'
    """).df()
    frames.append(match)
    sample = con.execute(f"""
        SELECT * FROM '{src}'
        USING SAMPLE ({SAMPLE_ROWS} ROWS) REPEATABLE ({SEED})
        ORDER BY nconst
        LIMIT 500
    """).df()
    df = pd.concat(frames + [sample], ignore_index=True).drop_duplicates("nconst")
    out = FIXTURE_GOLD / "dim_person.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"  dim_person: {len(df)} rows -> {out.name}")


def copy_processed_artifacts() -> None:
    sources = {
        "feature_columns.json": MODELS_DIR / "shared" / "feature_columns.json",
        "model_inventory.json": MODELS_DIR / "shared" / "model_inventory.json",
        "preprocessor.joblib": MODELS_DIR / "shared" / "preprocessor.joblib",
        "genre_list_mlb.joblib": MODELS_DIR / "shared" / "genre_list_mlb.joblib",
        "scaler.joblib": MODELS_DIR / "shared" / "scaler.joblib",
        "gmu_genre_best.pt": MODELS_DIR / "genre" / "gmu_genre_best.pt",
        "catboost_rating_model.cbm": MODELS_DIR / "rating" / "catboost_rating_model.cbm",
    }
    FIXTURE_PROCESSED.mkdir(parents=True, exist_ok=True)
    for name, src in sources.items():
        if src.exists():
            dst = FIXTURE_PROCESSED / name
            shutil.copy2(src, dst)
            print(f"  {name} ({dst.stat().st_size:,} bytes)")
        else:
            print(f"  SKIP {name}: not found at {src}")


def main() -> None:
    if not GOLD_DIR.exists():
        print(f"ERROR: Gold marts not found at {GOLD_DIR}. Run the DE pipeline first.")
        sys.exit(1)

    print("=== Generating CI fixtures ===")
    con = duckdb.connect()
    try:
        tconsts = subset_dim_title(con)
        print(f"  Selected {len(tconsts)} titles (seed={SEED})")
        subset_person(con, tconsts)
        subset_mart(con, "fact_title_principal", tconsts, column="title_key",
                    extra_ids=FORCED_NCONSTS)
        subset_mart(con, "fact_performance", tconsts, extra_ids=FORCED_NCONSTS)
        subset_mart(con, "fact_episode", tconsts, column="series_key")
        subset_mart(con, "fact_title_rating", tconsts, column="title_key")
        print("  Copying DS contract artifacts...")
        copy_processed_artifacts()
    finally:
        con.close()
    print(f"Done. Fixtures written to {FIXTURE_DIR}")


if __name__ == "__main__":
    main()
