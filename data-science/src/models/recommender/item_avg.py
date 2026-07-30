import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ItemAverageRecommender:
    def __init__(self, global_mean: float):
        self.global_mean = global_mean

    def predict(self, X: Optional[np.ndarray] = None) -> np.ndarray:
        if X is None:
            return np.array([self.global_mean])
        return np.full(len(X) if hasattr(X, '__len__') else 1, self.global_mean)
