import pytest
from pathlib import Path
from src.data.loader import GoldDataLoader


def test_gold_data_loader_init():
    loader = GoldDataLoader(
        marts_dir=Path("."),
        development_mode=True,
        sample_percent=5,
    )
    assert loader.development_mode
    assert loader.sample_percent == 5
    assert loader.random_seed == 42
    assert loader.con is None


def test_gold_data_loader_close_no_connection():
    loader = GoldDataLoader(Path("."))
    loader.close()


def test_query_to_df_no_connection():
    loader = GoldDataLoader(Path("."))
    with pytest.raises(AttributeError):
        loader.query_to_df("SELECT 1")


def test_gold_data_loader_development_mode_default():
    loader = GoldDataLoader(Path("."))
    assert loader.development_mode
    assert loader.sample_percent == 5


def test_gold_data_loader_production_mode():
    loader = GoldDataLoader(
        marts_dir=Path("."),
        development_mode=False,
    )
    assert not loader.development_mode


def test_gold_data_loader_custom_seed():
    loader = GoldDataLoader(
        marts_dir=Path("."),
        development_mode=True,
        sample_percent=10,
        random_seed=123,
    )
    assert loader.sample_percent == 10
    assert loader.random_seed == 123
