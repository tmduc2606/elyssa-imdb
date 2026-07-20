from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, MultiLabelBinarizer
from sklearn.compose import ColumnTransformer
import pandas as pd
import numpy as np
from pathlib import Path
import joblib
from typing import Tuple, Dict
import logging

logger = logging.getLogger(__name__)

RATING_FEATURE_COLS = [
    "start_year", "runtime_minutes",
    "num_persons", "unique_persons",
    "actor_count", "actress_count",
    "director_count", "writer_count", "producer_count", "composer_count",
    "editor_count", "cinematographer_count", "self_count",
    "series_episode_count", "series_avg_episode_rating",
    "min_season", "max_season",
    "genre_cnt",
    "avg_genre_year_rating", "avg_genre_year_votes", "avg_genre_year_popularity",
    "dir_avg_career_len", "dir_max_career_len", "dir_avg_experience", "dir_avg_recent_activity",
    "wri_avg_career_len", "wri_max_career_len", "wri_avg_experience", "wri_avg_recent_activity",
]


def build_preprocessor(numeric_cols: list, categorical_cols: list) -> ColumnTransformer:
    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer(
        transformers=[
        ("num", numeric_transformer, numeric_cols),
        ("cat", categorical_transformer, categorical_cols),
    ])


def fit_transform_features(
    preprocessor: ColumnTransformer,
    df: pd.DataFrame,
    numeric_cols: list,
    categorical_cols: list,
    train_mask: pd.Series,
) -> np.ndarray:
    X_train_raw = df.loc[train_mask, numeric_cols + categorical_cols]
    preprocessor.fit(X_train_raw)
    return preprocessor.transform(df[numeric_cols + categorical_cols])


def to_list(series: pd.Series):
    return series.fillna("").apply(
        lambda x: [item.strip() for item in x.split(",") if item.strip()]
        if isinstance(x, str) else []
    )


def binarize_multilabel(
    df: pd.DataFrame,
    col: str,
    train_mask: pd.Series,
    val_mask: pd.Series,
    test_mask: pd.Series,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, MultiLabelBinarizer]:
    lists_train = to_list(df.loc[train_mask, col])
    lists_val = to_list(df.loc[val_mask, col])
    lists_test = to_list(df.loc[test_mask, col])
    mlb = MultiLabelBinarizer()
    y_train = mlb.fit_transform(lists_train)
    y_val = mlb.transform(lists_val)
    y_test = mlb.transform(lists_test)
    return y_train, y_val, y_test, mlb
