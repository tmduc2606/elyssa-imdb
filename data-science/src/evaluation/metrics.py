import numpy as np
from sklearn.metrics import (
    f1_score, precision_score, recall_score, accuracy_score,
    hamming_loss, mean_squared_error, mean_absolute_error, r2_score,
)
from typing import Dict


def evaluate_multilabel(y_true: np.ndarray, y_pred_probs: np.ndarray, threshold: float = 0.5) -> Dict[str, float]:
    return evaluate_multilabel_detailed(y_true, y_pred_probs, dataset_name="", threshold=threshold)


def evaluate_multilabel_detailed(
    y_true: np.ndarray,
    y_pred_probs: np.ndarray,
    dataset_name: str = "",
    threshold: float = 0.5,
) -> Dict[str, float]:
    """Full multi-label metric set with a ``{dataset_name}_`` key prefix.

    Notebook-compatible contract (plan §4.12): returns the same keys the
    FE/Modeling notebooks persisted (``{name}_macro_f1``, ``{name}_micro_f1``,
    ``{name}_macro_precision``, ``{name}_macro_recall``, ``{name}_hamming_loss``,
    ``{name}_subset_accuracy``). ``dataset_name=''`` yields unprefixed keys.
    """
    y_pred = (y_pred_probs > threshold).astype(int)
    prefix = f"{dataset_name}_" if dataset_name else ""
    return {
        f"{prefix}macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        f"{prefix}micro_f1": f1_score(y_true, y_pred, average="micro", zero_division=0),
        f"{prefix}macro_precision": precision_score(y_true, y_pred, average="macro", zero_division=0),
        f"{prefix}macro_recall": recall_score(y_true, y_pred, average="macro", zero_division=0),
        f"{prefix}hamming_loss": hamming_loss(y_true, y_pred),
        f"{prefix}subset_accuracy": accuracy_score(y_true, y_pred),
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
