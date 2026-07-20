import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

RATING_THRESHOLD = 7.0


def compute_user_embeddings(
    train_df: pd.DataFrame,
    item_emb_dict: Dict[int, np.ndarray],
    rating_threshold: float = RATING_THRESHOLD,
) -> Tuple[Dict[int, np.ndarray], np.ndarray]:
    user_embeddings = {}
    for user, group in train_df[train_df["rating"] >= rating_threshold].groupby("user_idx"):
        item_embeds = [
            item_emb_dict[i] for i in group["item_idx"]
            if i in item_emb_dict
        ]
        if item_embeds:
            user_embeddings[user] = np.mean(item_embeds, axis=0)

    all_embeds = np.array([item_emb_dict[i] for i in item_emb_dict])
    global_item_emb = np.mean(all_embeds, axis=0) if len(all_embeds) > 0 else np.zeros(768)

    return user_embeddings, global_item_emb


def fill_missing_users(
    user_embeddings: Dict[int, np.ndarray],
    user_ids: np.ndarray,
    global_item_emb: np.ndarray,
) -> Dict[int, np.ndarray]:
    for u in user_ids:
        if u not in user_embeddings:
            user_embeddings[u] = global_item_emb
    return user_embeddings


def compute_scores(
    df: pd.DataFrame,
    svd_model,
    user_embeddings: Dict[int, np.ndarray],
    item_emb_dict: Dict[int, np.ndarray],
    global_item_emb: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    svd_scores = []
    content_scores = []
    for _, row in df.iterrows():
        u, i = int(row["user_idx"]), int(row["item_idx"])
        try:
            s = svd_model.predict(u, i).est
        except Exception:
            s = 3.0
        svd_scores.append(s)

        u_emb = user_embeddings.get(u, global_item_emb)
        i_emb = item_emb_dict.get(i, global_item_emb)
        sim = cosine_similarity([u_emb], [i_emb])[0][0]
        content_scores.append(sim)

    return np.array(svd_scores), np.array(content_scores)


def train_hybrid(
    val_df: pd.DataFrame,
    svd_scores_val: np.ndarray,
    cont_scores_val: np.ndarray,
    threshold: float = RATING_THRESHOLD,
    random_seed: int = 42,
) -> Tuple[LogisticRegression, StandardScaler]:
    y_val_bin = (val_df["rating"].values >= threshold).astype(int)

    scaler = StandardScaler()
    X_val = np.column_stack([svd_scores_val, cont_scores_val])
    X_val_scaled = scaler.fit_transform(X_val)

    lr = LogisticRegression(random_state=random_seed)
    lr.fit(X_val_scaled, y_val_bin)

    logger.info(f"Hybrid LR trained: val set size={len(val_df)}")
    return lr, scaler


def predict_hybrid(
    lr: LogisticRegression,
    scaler: StandardScaler,
    svd_scores: np.ndarray,
    cont_scores: np.ndarray,
) -> np.ndarray:
    X = np.column_stack([svd_scores, cont_scores])
    X_scaled = scaler.transform(X)
    return lr.predict_proba(X_scaled)[:, 1]


def precision_recall_at_k(df: pd.DataFrame, scores: np.ndarray, k: int = 10, threshold: float = RATING_THRESHOLD):
    df = df.copy()
    df["score"] = scores
    precisions = []
    recalls = []
    for user, group in df.groupby("user_idx"):
        topk = group.nlargest(k, "score")
        true_pos = topk["rating"] >= threshold
        relevant = (group["rating"] >= threshold).sum()
        prec = true_pos.sum() / k if k > 0 else 0
        rec = true_pos.sum() / relevant if relevant > 0 else 0
        precisions.append(prec)
        recalls.append(rec)
    return float(np.mean(precisions)), float(np.mean(recalls))
