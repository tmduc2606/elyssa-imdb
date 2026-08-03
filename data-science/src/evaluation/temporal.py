import pandas as pd
import numpy as np
from typing import List, Dict
import logging
from sklearn.metrics import mean_squared_error

logger = logging.getLogger(__name__)


def compute_temporal_decay(inventory: List[dict]) -> pd.DataFrame:
    results = []
    for entry in inventory:
        val_metric = entry.get("metrics", {}).get("val_macro_f1") or entry.get("metrics", {}).get("val_rmse")
        test_metric = entry.get("metrics", {}).get("test_macro_f1") or entry.get("metrics", {}).get("test_rmse")
        if val_metric is not None and test_metric is not None:
            delta = test_metric - val_metric
            results.append({
                "name": entry["name"],
                "val": val_metric,
                "test": test_metric,
                "delta": delta,
            })
    df = pd.DataFrame(results)
    logger.info(f"Temporal decay computed for {len(results)} models")
    return df


def sample_efficiency_curve(
    X_train: np.ndarray, y_train: np.ndarray,
    X_test: np.ndarray, y_test: np.ndarray,
    model_fn, fracs: List[float] = None, random_seed: int = 42,
) -> Dict[str, List[float]]:
    if fracs is None:
        fracs = [0.2, 0.5, 0.8, 1.0]
    rng = np.random.RandomState(random_seed)
    scores = []
    for frac in fracs:
        n = int(frac * len(X_train))
        idx = rng.choice(len(X_train), n, replace=False)
        model = model_fn(X_train[idx], y_train[idx])
        pred = model.predict(X_test)
        scores.append(float(np.sqrt(mean_squared_error(y_test, pred))))
    return {"fracs": fracs, "scores": scores}


def build_split_masks(
    df: pd.DataFrame,
    train_year_max: int,
    val_year_min: int,
    val_year_max: int,
    test_year_min: int,
) -> tuple:
    """Build boolean train/val/test masks from ``start_year`` (DS.1).

    The four constants must match the frozen temporal split contract
    (TRAIN <= train_year_max, VAL [val_year_min, val_year_max], TEST >= test_year_min).
    """
    years = df["start_year"]
    train_mask = years <= train_year_max
    val_mask = (years >= val_year_min) & (years <= val_year_max)
    test_mask = years >= test_year_min
    return train_mask, val_mask, test_mask
