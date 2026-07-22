"""Ablation study for model modality combinations."""
import numpy as np
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


def run_ablation(
    X_tab: np.ndarray, X_text: np.ndarray, y: np.ndarray,
    train_idx: np.ndarray, val_idx: np.ndarray,
    model_fn,
    modalities: Optional[List[Tuple[bool, bool]]] = None,
) -> Dict[str, float]:
    if modalities is None:
        modalities = [(True, True), (True, False), (False, True)]
    results = {}
    for use_tab, use_text in modalities:
        label = f"tab={use_tab}_text={use_text}"
        X = []
        if use_tab:
            X.append(X_tab)
        if use_text:
            X.append(X_text)
        if not X:
            continue
        X_combined = np.concatenate(X, axis=1)
        X_tr, X_va = X_combined[train_idx], X_combined[val_idx]
        y_tr, y_va = y[train_idx], y[val_idx]
        model = model_fn(X_tr, y_tr)
        from sklearn.metrics import mean_squared_error
        pred = model.predict(X_va) if hasattr(model, "predict") else model
        score = float(np.sqrt(mean_squared_error(y_va, pred)))
        results[label] = score
        logger.info(f"Ablation {label}: score={score:.4f}")
    return results
