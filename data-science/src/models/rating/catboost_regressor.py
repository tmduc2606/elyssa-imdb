import numpy as np
import catboost as cb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def objective_catboost(
    trial,
    X_train: np.ndarray,
    y_train: np.ndarray,
    random_seed: int = 42,
    n_splits: int = 2,
) -> float:
    params = {
        "iterations": trial.suggest_int("iterations", 200, 400),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "depth": trial.suggest_int("depth", 4, 6),
        "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 0.1, 10),
        "bagging_temperature": trial.suggest_float("bagging_temperature", 0.1, 1.0),
        "random_strength": trial.suggest_float("random_strength", 0.1, 10),
        "random_seed": random_seed,
        "verbose": 0,
    }

    tscv = TimeSeriesSplit(n_splits=n_splits)
    rmse_scores = []
    for train_idx, val_idx in tscv.split(X_train):
        X_tr, X_va = X_train[train_idx], X_train[val_idx]
        y_tr, y_va = y_train[train_idx], y_train[val_idx]
        model = cb.CatBoostRegressor(**params)
        model.fit(X_tr, y_tr, eval_set=(X_va, y_va), early_stopping_rounds=30, verbose=False)
        pred = model.predict(X_va)
        rmse = np.sqrt(mean_squared_error(y_va, pred))
        rmse_scores.append(rmse)

    return float(np.mean(rmse_scores))


def train_catboost(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: Optional[np.ndarray] = None,
    y_val: Optional[np.ndarray] = None,
    best_params: Optional[dict] = None,
    random_seed: int = 42,
) -> Tuple[cb.CatBoostRegressor, dict]:
    if best_params is None:
        best_params = {
            "iterations": 300,
            "learning_rate": 0.1,
            "depth": 6,
            "l2_leaf_reg": 3.0,
            "bagging_temperature": 0.5,
            "random_strength": 1.0,
        }

    params = {**best_params, "random_seed": random_seed, "verbose": 100}
    model = cb.CatBoostRegressor(**params)

    eval_set = (X_val, y_val) if X_val is not None and y_val is not None else None
    model.fit(
        X_train, y_train,
        eval_set=eval_set,
        early_stopping_rounds=50,
    )

    metrics = {}
    if eval_set:
        val_pred = model.predict(X_val)
        metrics["val_rmse"] = float(np.sqrt(mean_squared_error(y_val, val_pred)))

    return model, metrics


def train_eval_subset(
    X_train: np.ndarray, y_train: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
    X_test: np.ndarray, y_test: np.ndarray,
    feature_indices: np.ndarray,
    best_params: dict,
    random_seed: int = 42,
) -> float:
    X_tr = X_train[:, feature_indices]
    X_va = X_val[:, feature_indices]
    X_te = X_test[:, feature_indices]

    model = cb.CatBoostRegressor(**best_params, random_seed=random_seed, verbose=0)
    model.fit(X_tr, y_train, eval_set=(X_va, y_val), early_stopping_rounds=30, verbose=False)
    pred = model.predict(X_te)
    rmse = np.sqrt(mean_squared_error(y_test, pred))
    logger.info(f"Ablation [{feature_indices}]: Test RMSE = {rmse:.4f}")
    return float(rmse)
