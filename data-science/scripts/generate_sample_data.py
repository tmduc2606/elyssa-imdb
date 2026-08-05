"""Generate sample Parquet + pre-trained models for smoke testing."""
import duckdb
from pathlib import Path

SAMPLE_DIR = Path("marts/sample")
SAMPLE_PROCESSED_DIR = Path("marts/sample_processed")
FULL_DIR = Path("marts/gold")
PROCESSED_DIR = Path("marts/processed")
SAMPLE_SIZE = 50_000


def extract_sample():
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    for mart in [
        "dim_title", "dim_person", "fact_title_principal",
        "fact_performance", "fact_episode", "fact_title_rating",
    ]:
        src = FULL_DIR / f"{mart}.parquet"
        dst = SAMPLE_DIR / f"{mart}.parquet"
        if src.exists():
            con.execute(f"""
                COPY (
                  SELECT * FROM '{src}'
                  USING SAMPLE {SAMPLE_SIZE} ROWS
                ) TO '{dst}' (FORMAT PARQUET, COMPRESSION SNAPPY)
            """)
            row_count = con.execute(f"SELECT count(*) FROM '{dst}'").fetchone()[0]
            print(f"  Created {mart}: {row_count:,} rows")

    con.close()
    print(f"Sample data created in {SAMPLE_DIR}")


def copy_processed_artifacts():
    """Copy DS artifacts from processed/ to sample_processed/ for smoke testing."""
    SAMPLE_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    artifacts = [
        "feature_columns.json",
        "genre_list_mlb.joblib",
        "preprocessor.joblib",
        "scaler.joblib",
        "gmu_genre_best.pt",
        "catboost_rating_model.cbm",
        "model_inventory.json",
    ]
    for name in artifacts:
        src = PROCESSED_DIR / name
        if src.exists():
            dst = SAMPLE_PROCESSED_DIR / name
            data = src.read_bytes()
            dst.write_bytes(data)
            print(f"  Copied {name} ({len(data):,} bytes)")
    print(f"Processed artifacts copied to {SAMPLE_PROCESSED_DIR}")


def main():
    print("=== Generating smoke test sample data ===")
    extract_sample()
    copy_processed_artifacts()
    print("Done")


if __name__ == "__main__":
    main()
