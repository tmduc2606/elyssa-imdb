import pandas as pd
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

TRAIN_YEAR_MAX = 2014
VAL_YEAR_MIN = 2015
VAL_YEAR_MAX = 2018
TEST_YEAR_MIN = 2019


def temporal_split(
    df: pd.DataFrame,
    year_col: str = "start_year",
    train_max: int = TRAIN_YEAR_MAX,
    val_min: int = VAL_YEAR_MIN,
    val_max: int = VAL_YEAR_MAX,
    test_min: int = TEST_YEAR_MIN,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    train_mask = df[year_col] <= train_max
    val_mask = (df[year_col] >= val_min) & (df[year_col] <= val_max)
    test_mask = df[year_col] >= test_min

    logger.info(
        f"Temporal split: train={train_mask.sum():,}, "
        f"val={val_mask.sum():,}, test={test_mask.sum():,}"
    )

    return train_mask, val_mask, test_mask
