"""XGBoost regressor for rating prediction."""
import numpy as np
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False
    logger.warning("XGBoost not installed; using CatBoost as fallback")


def train_xgboost(
    X_train: np.ndarray, y_train: np.ndarray,
    X_val: Optional[np.ndarray] = None, y_val: Optional[np.ndarray] = None,
    params: Optional[dict] = None,
) -> Tuple[Optional[object], dict]:
    if not XGB_AVAILABLE:
        return None, {"error": "XGBoost not installed"}
    if params is None:
        params = {"n_estimators": 300, "max_depth": 6, "learning_rate": 0.1, "random_state": 42}
    model = xgb.XGBRegressor(**params)
    eval_set = [(X_val, y_val)] if X_val is not None and y_val is not None else None
    model.fit(X_train, y_train, eval_set=eval_set, verbose=False)
    metrics = {}
    if eval_set:
        from sklearn.metrics import mean_squared_error
        pred = model.predict(X_val)
        metrics["val_rmse"] = float(np.sqrt(mean_squared_error(y_val, pred)))
    return model, metrics
