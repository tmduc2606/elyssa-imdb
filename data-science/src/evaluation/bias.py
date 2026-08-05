import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def genre_label_distribution(y_train_genre: np.ndarray, mlb_classes: np.ndarray) -> pd.DataFrame:
    genre_counts = y_train_genre.sum(axis=0)
    df = pd.DataFrame({"genre": mlb_classes, "count": genre_counts})
    df = df.sort_values("count", ascending=False)
    return df


def split_year_ranges(base_df: pd.DataFrame, split_df: pd.DataFrame) -> pd.DataFrame:
    merged = base_df.merge(split_df[["tconst", "split"]], on="tconst", how="left")
    results = []
    for split_name in merged["split"].unique():
        years = merged[merged["split"] == split_name]["start_year"]
        results.append({
            "split": split_name,
            "min_year": int(years.min()),
            "max_year": int(years.max()),
            "median_year": float(years.median()),
            "count": len(years),
        })
    return pd.DataFrame(results)
