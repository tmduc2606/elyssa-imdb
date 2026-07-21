"""Generate baseline feature statistics for drift detection.

Computes per-feature histograms from current Gold marts and saves
to feature_statistics.joblib for the drift_detection Airflow DAG.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from joblib import dump


TAB_FEATURES = [
    "start_year", "runtime_minutes", "average_rating", "num_votes",
    "num_persons", "actor_count", "director_count", "writer_count",
    "genre_cnt", "unique_persons",
]

NUM_BINS = 20


def compute_statistics(parquet_dir: str) -> dict:
    """Compute feature histograms from dim_title.parquet."""
    import pandas as pd

    parquet_path = Path(parquet_dir) / "dim_title.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"dim_title.parquet not found in {parquet_dir}")

    available_cols = [c for c in TAB_FEATURES]
    df = pd.read_parquet(parquet_path, columns=available_cols)

    stats = {"columns": available_cols, "probs": {}, "counts": {}}
    for col in available_cols:
        values = df[col].dropna().values.astype(np.float64)
        if len(values) == 0:
            hist = np.ones(NUM_BINS) / NUM_BINS
        else:
            hist, _ = np.histogram(values, bins=NUM_BINS, density=True)
            hist = hist + 1e-10
            hist = hist / hist.sum()
        stats["probs"][col] = hist
        stats["counts"][col] = len(values)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Generate feature statistics baseline")
    parser.add_argument("--input", required=True, help="Directory containing dim_title.parquet")
    parser.add_argument("--output", required=True, help="Output path for feature_statistics.joblib")
    args = parser.parse_args()

    stats = compute_statistics(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dump(stats, output_path)
    print(f"Feature statistics saved to {output_path}")
    print(f"  Features: {len(stats['columns'])}")
    for col in stats["columns"]:
        print(f"  {col}: {stats['counts'][col]:,} non-null values")


if __name__ == "__main__":
    main()
