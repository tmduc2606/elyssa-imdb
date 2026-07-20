import pytest
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def processed_dir():
    return Path(__file__).parent.parent / "marts" / "processed"


@pytest.fixture
def sample_data():
    return {
        "X_tab": np.random.randn(100, 17).astype(np.float32),
        "X_text": np.random.randn(100, 768).astype(np.float32),
        "y_genre": np.random.randint(0, 2, (100, 28)).astype(np.float32),
        "y_rating": np.random.uniform(1.0, 10.0, 100).astype(np.float32),
    }


@pytest.fixture
def sample_df():
    import pandas as pd
    return pd.DataFrame({
        "start_year": [2010, 2015, 2019, 2022, 2005],
        "runtime_minutes": [120, 90, 150, 100, 80],
        "average_rating": [7.5, 8.0, 6.5, 9.0, 7.0],
        "num_votes": [1000, 5000, 200, 10000, 800],
        "title_type": ["movie", "tvSeries", "movie", "tvMovie", "short"],
        "is_adult": [0, 0, 0, 1, 0],
    })
