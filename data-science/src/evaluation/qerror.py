import numpy as np
from typing import Dict, List


def q_error(y_true: np.ndarray, y_pred: np.ndarray, percentiles: List[int] = None) -> Dict[str, float]:
    if percentiles is None:
        percentiles = [50, 90, 95, 99]
    ratios = np.maximum(y_pred / y_true, y_true / y_pred)
    ratios = ratios[~np.isinf(ratios)]
    ratios = ratios[~np.isnan(ratios)]
    return {f"Q_error_p{p}": float(np.percentile(ratios, p)) for p in percentiles}


def add_noise(X: np.ndarray, noise_level: float, feature_std: np.ndarray) -> np.ndarray:
    noise = np.random.normal(0, noise_level * feature_std, size=X.shape)
    return X + noise
