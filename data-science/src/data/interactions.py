"""Recommender interaction-table builder + persistence (plan §4.4).

Builds the user→item interaction table from the Gold layer
(``fact_performance ⋈ dim_title``) with **consistent dev sampling**:
both fact tables are sampled with the same ``REPEATABLE(seed)`` so the
recommender pillar matches the FE sampling contract instead of joining a
5% ``fact_performance`` sample against a 100% ``dim_title`` view.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import duckdb
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

INTERACTION_FILES = {
    "parquet": "interactions.parquet",
    "user_index": "user_index.parquet",
    "item_index": "item_index.parquet",
}


def build_interactions(
    con: duckdb.DuckDBPyConnection,
    sample_percent: int = 5,
    random_seed: int = 42,
    views: Optional[Dict[str, Path]] = None,
) -> pd.DataFrame:
    """Query user→item interactions (user_id, item_id, rating, year).

    Applies ``TABLESAMPLE SYSTEM`` to both ``fact_performance`` and
    ``dim_title`` with the same ``REPEATABLE(seed)`` in dev mode so the
    join is internally consistent (no 5%-vs-100% mismatch).
    """
    sample_clause_fp = (
        f"TABLESAMPLE SYSTEM ({sample_percent} PERCENT) REPEATABLE ({random_seed})"
        if sample_percent < 100
        else ""
    )
    sample_clause_dt = sample_clause_fp

    sql = f"""
        SELECT
            f.nconst AS user_id,
            f.tconst AS item_id,
            d.average_rating AS rating,
            d.start_year AS year
        FROM fact_performance f {sample_clause_fp}
        JOIN dim_title d {sample_clause_dt} ON f.tconst = d.tconst
        WHERE f.category IN ('actor', 'actress', 'director')
          AND d.average_rating IS NOT NULL
          AND d.start_year IS NOT NULL
    """
    df = con.execute(sql).df()
    logger.info(f"Interaction dataset: {df.shape[0]} rows")
    return df


def persist_interactions(
    df_inter: pd.DataFrame,
    user2idx: Dict[str, int],
    item2idx: Dict[str, int],
    models_dir: Path,
) -> None:
    """Persist the interaction table + id→idx maps for the Analytics notebook.

    Files (under ``models/shared/``): ``interactions.parquet``,
    ``user_index.parquet``, ``item_index.parquet``.
    """
    shared = Path(models_dir) / "shared"
    shared.mkdir(parents=True, exist_ok=True)

    cols = ["user_id", "item_id", "rating", "year", "user_idx", "item_idx"]
    out_df = df_inter[cols].copy()
    out_df.to_parquet(shared / INTERACTION_FILES["parquet"], index=False)

    pd.DataFrame({"user_id": list(user2idx.keys()), "user_idx": list(user2idx.values())}).to_parquet(
        shared / INTERACTION_FILES["user_index"], index=False
    )
    pd.DataFrame({"item_id": list(item2idx.keys()), "item_idx": list(item2idx.values())}).to_parquet(
        shared / INTERACTION_FILES["item_index"], index=False
    )
    logger.info(f"Persisted interactions.parquet ({len(out_df):,} rows) + id-index maps to {shared}")


def load_interactions(
    models_dir: Path,
    user2idx: Optional[Dict[str, int]] = None,
    item2idx: Optional[Dict[str, int]] = None,
) -> Tuple[pd.DataFrame, Dict[str, int], Dict[str, int]]:
    """Load persisted interactions + maps; returns (df_inter, user2idx, item2idx).

    The returned DataFrame already carries ``user_idx`` / ``item_idx`` columns.
    Raises ``FileNotFoundError`` with run-order guidance if artifacts are missing.
    """
    shared = Path(models_dir) / "shared"
    inter_path = shared / INTERACTION_FILES["parquet"]
    user_path = shared / INTERACTION_FILES["user_index"]
    item_path = shared / INTERACTION_FILES["item_index"]

    missing = [p for p in (inter_path, user_path, item_path) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"Interaction artifacts missing: {[p.name for p in missing]}. "
            "Run the Modeling notebook first (Cell 30 persists them)."
        )

    df = pd.read_parquet(inter_path)
    if user2idx is None:
        user2idx = dict(
            zip(pd.read_parquet(user_path)["user_id"], pd.read_parquet(user_path)["user_idx"])
        )
    if item2idx is None:
        item2idx = dict(
            zip(pd.read_parquet(item_path)["item_id"], pd.read_parquet(item_path)["item_idx"])
        )
    logger.info(f"Loaded persisted interactions: {len(df):,} rows")
    return df, user2idx, item2idx


def interaction_summary(df_inter: pd.DataFrame) -> Tuple[int, int]:
    """Return (num_users, num_items) for a loaded interaction table."""
    n_users = int(df_inter["user_idx"].nunique())
    n_items = int(df_inter["item_idx"].nunique())
    return n_users, n_items


def user_embeddings_from_interactions(
    df_inter: pd.DataFrame,
    item_emb_dict: Dict[int, np.ndarray],
    rating_threshold: float = 7.0,
    global_item_emb: Optional[np.ndarray] = None,
) -> Dict[int, np.ndarray]:
    """Content-based user profile: mean embedding of high-rated items in train.

    Users without high-rated items fall back to the global item embedding.
    """
    user_embs: Dict[int, np.ndarray] = {}
    high = df_inter[df_inter["rating"] >= rating_threshold]
    for user, group in high.groupby("user_idx"):
        embs = [item_emb_dict[i] for i in group["item_idx"] if i in item_emb_dict]
        if embs:
            user_embs[user] = np.mean(embs, axis=0)

    if global_item_emb is None:
        candidates = [e for e in item_emb_dict.values() if e is not None]
        global_item_emb = np.mean(candidates, axis=0) if candidates else None

    for user in df_inter["user_idx"].unique():
        user_embs.setdefault(user, global_item_emb)
    return user_embs
