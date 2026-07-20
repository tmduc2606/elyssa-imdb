import numpy as np
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import RidgeCV
from pathlib import Path
import joblib
import logging

logger = logging.getLogger(__name__)


def train_dummy_regressor(y_train: np.ndarray, strategy: str = "mean") -> DummyRegressor:
    model = DummyRegressor(strategy=strategy)
    model.fit(np.zeros((len(y_train), 1)), y_train)
    return model


def train_ridge(X_train: np.ndarray, y_train: np.ndarray, alphas: list = None) -> RidgeCV:
    if alphas is None:
        alphas = [1, 10, 100]
    model = RidgeCV(alphas=alphas)
    model.fit(X_train, y_train)
    logger.info(f"Ridge best alpha: {model.alpha_}")
    return model


def save_baseline_model(model, path: Path, name: str):
    joblib.dump(model, path / f"{name}.pkl")
    logger.info(f"Saved baseline model: {name}.pkl")
