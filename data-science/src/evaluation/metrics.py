import numpy as np
from sklearn.metrics import (
    f1_score, precision_score, recall_score, accuracy_score,
    hamming_loss, mean_squared_error, mean_absolute_error, r2_score,
)
from typing import Dict


def evaluate_multilabel(y_true: np.ndarray, y_pred_probs: np.ndarray, threshold: float = 0.5) -> Dict[str, float]:
    y_pred = (y_pred_probs > threshold).astype(int)
    return {
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
        "micro_f1": f1_score(y_true, y_pred, average="micro"),
        "macro_precision": precision_score(y_true, y_pred, average="macro"),
        "macro_recall": recall_score(y_true, y_pred, average="macro"),
        "hamming_loss": hamming_loss(y_true, y_pred),
        "subset_accuracy": accuracy_score(y_true, y_pred),
    }


def reg_metrics(y_true: np.ndarray, y_pred: np.ndarray, prefix: str = "test") -> Dict[str, float]:
    return {
        f"{prefix}_rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        f"{prefix}_mae": float(mean_absolute_error(y_true, y_pred)),
        f"{prefix}_r2": float(r2_score(y_true, y_pred)),
    }


def precision_recall_at_k(df, scores, k: int = 10, threshold: float = 7.0):
    df = df.copy()
    df["score"] = scores
    precisions = []
    recalls = []
    for user, group in df.groupby("user_idx"):
        topk = group.nlargest(k, "score")
        true_pos = topk["rating"] >= threshold
        relevant = (group["rating"] >= threshold).sum()
        prec = float(true_pos.sum()) / k if k > 0 else 0.0
        rec = float(true_pos.sum()) / relevant if relevant > 0 else 0.0
        precisions.append(prec)
        recalls.append(rec)
    return float(np.mean(precisions)), float(np.mean(recalls))
