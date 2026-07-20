import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.metrics import f1_score
from pathlib import Path
import joblib
import logging

logger = logging.getLogger(__name__)


def train_dummy_classifier(X_train: np.ndarray, y_train: np.ndarray, strategy: str = "uniform") -> DummyClassifier:
    model = DummyClassifier(strategy=strategy, random_state=42)
    model.fit(X_train, y_train)
    return model


def train_logistic_regression(X_train: np.ndarray, y_train: np.ndarray, max_iter: int = 1000) -> LogisticRegression:
    model = OneVsRestClassifier(LogisticRegression(max_iter=max_iter, solver="liblinear"))
    model.fit(X_train, y_train)
    return model


def save_baseline_model(model, path: Path, name: str):
    joblib.dump(model, path / f"{name}.pkl")
    logger.info(f"Saved baseline model: {name}.pkl")
