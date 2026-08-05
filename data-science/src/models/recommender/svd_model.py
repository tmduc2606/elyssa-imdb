import pandas as pd
from surprise import SVD, Reader, Dataset
from pathlib import Path
import joblib
import logging

logger = logging.getLogger(__name__)


def train_svd(
    train_df: pd.DataFrame,
    n_factors: int = 50,
    n_epochs: int = 20,
    random_seed: int = 42,
) -> SVD:
    reader = Reader(rating_scale=(1, 10))
    train_surprise = Dataset.load_from_df(
        train_df[["user_idx", "item_idx", "rating"]], reader
    )
    trainset = train_surprise.build_full_trainset()
    model = SVD(n_factors=n_factors, n_epochs=n_epochs, biased=True, random_state=random_seed)
    model.fit(trainset)
    logger.info(f"Trained SVD: {n_factors} factors, {n_epochs} epochs")
    return model


def save_svd_model(model, path: Path, name: str = "svd_model"):
    joblib.dump(model, path / f"{name}.pkl")
    logger.info(f"Saved SVD model: {name}.pkl")
