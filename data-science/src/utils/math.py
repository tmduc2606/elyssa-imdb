import numpy as np


def safe_minmax(x: np.ndarray, axis: int = 0) -> np.ndarray:
    mins = np.min(x, axis=axis, keepdims=True)
    maxs = np.max(x, axis=axis, keepdims=True)
    ranges = maxs - mins
    ranges[ranges == 0] = 1.0
    return (x - mins) / ranges
