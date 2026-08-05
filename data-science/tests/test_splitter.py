import pandas as pd
from src.data.splitter import (
    temporal_split,
    TRAIN_YEAR_MAX,
    VAL_YEAR_MIN,
    VAL_YEAR_MAX,
    TEST_YEAR_MIN,
)


def test_temporal_split_no_leakage():
    df = pd.DataFrame({"start_year": [2010, 2015, 2019, 2022]})
    train, val, test = temporal_split(df)
    assert df.loc[train, "start_year"].max() <= TRAIN_YEAR_MAX
    assert df.loc[val, "start_year"].min() >= VAL_YEAR_MIN
    assert df.loc[test, "start_year"].min() >= TEST_YEAR_MIN


def test_temporal_split_no_overlap():
    df = pd.DataFrame({"start_year": list(range(2000, 2025))})
    train, val, test = temporal_split(df)
    assert not (train & val).any()
    assert not (train & test).any()
    assert not (val & test).any()


def test_temporal_split_coverage():
    df = pd.DataFrame({"start_year": list(range(2000, 2025))})
    train, val, test = temporal_split(df)
    combined = train | val | test
    assert combined.all()


def test_temporal_split_custom_thresholds():
    df = pd.DataFrame({"start_year": [2010, 2015, 2019, 2022]})
    train, val, test = temporal_split(
        df, train_max=2010, val_min=2011, val_max=2018, test_min=2019
    )
    assert df.loc[train, "start_year"].max() == 2010
    assert df.loc[test, "start_year"].min() == 2019


def test_temporal_split_empty_result():
    df = pd.DataFrame({"start_year": [2025]})
    train, val, test = temporal_split(df)
    assert train.sum() == 0
    assert val.sum() == 0
    assert test.sum() == 1


def test_temporal_split_frozen_constants():
    assert TRAIN_YEAR_MAX == 2014
    assert VAL_YEAR_MIN == 2015
    assert VAL_YEAR_MAX == 2018
    assert TEST_YEAR_MIN == 2019
