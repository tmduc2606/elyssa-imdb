import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


def build_raw_feature_vector(
    row: pd.Series,
    numeric_cols: list,
    categorical_cols: list,
) -> pd.DataFrame:
    data = {}
    for col in numeric_cols:
        val = row.get(col, np.nan)
        if col not in row:
            val = np.nan
        data[col] = val
    for col in categorical_cols:
        val = row.get(col, "missing")
        data[col] = val
    return pd.DataFrame([data])


def transform_single(
    preprocessor: ColumnTransformer,
    row: pd.Series,
    numeric_cols: list,
    categorical_cols: list,
) -> np.ndarray:
    raw_df = build_raw_feature_vector(row, numeric_cols, categorical_cols)
    return preprocessor.transform(raw_df)
