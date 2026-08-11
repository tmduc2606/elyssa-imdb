import numpy as np
from pathlib import Path
from src.features.builder import FeatureBuilder


def test_no_rating_leakage(sample_data):
    builder = FeatureBuilder(Path("."))
    rating_features = builder.get_rating_features(
        ["start_year", "runtime_minutes", "average_rating", "num_votes",
         "rating_bucket", "avg_rating_genre_year", "avg_votes_genre_year"]
    )
    assert "average_rating" not in rating_features
    assert "num_votes" not in rating_features
    assert "rating_bucket" not in rating_features
    assert "avg_rating_genre_year" not in rating_features
    assert "avg_votes_genre_year" not in rating_features
    assert "start_year" in rating_features
    assert "runtime_minutes" in rating_features


def test_feature_matrix_shape(sample_data):
    builder = FeatureBuilder(Path("."))
    result = builder.build_genre_matrix(
        sample_data["X_tab"], sample_data["X_text"], sample_data["y_genre"]
    )
    assert result["X"].shape == (100, 785)
    assert result["y"].shape == (100, 28)


def test_rating_matrix_excludes_leakage(sample_data):
    builder = FeatureBuilder(Path("."))
    result = builder.build_rating_matrix(
        sample_data["X_tab"], sample_data["X_text"], sample_data["y_rating"]
    )
    assert result["X"].shape == (100, 785)
    assert result["y"].shape == (100,)


def test_rating_matrix_with_exclude_cols(sample_data):
    builder = FeatureBuilder(Path("."))
    exclude = [0, 1]
    result = builder.build_rating_matrix(
        sample_data["X_tab"], sample_data["X_text"],
        sample_data["y_rating"], exclude_cols=exclude,
    )
    assert result["X"].shape == (100, 783)


def test_rating_excluded_constant():
    assert "average_rating" in FeatureBuilder.RATING_EXCLUDED
    assert "num_votes" in FeatureBuilder.RATING_EXCLUDED
    assert "rating_bucket" in FeatureBuilder.RATING_EXCLUDED
    assert "avg_rating_genre_year" in FeatureBuilder.RATING_EXCLUDED
    assert "avg_votes_genre_year" in FeatureBuilder.RATING_EXCLUDED
    assert len(FeatureBuilder.RATING_EXCLUDED) == 5


def test_load_preprocessors_no_error(processed_dir):
    builder = FeatureBuilder(processed_dir)
    builder.load_preprocessors()


def test_safe_minmax_zero_range():
    from src.utils.math import safe_minmax
    x = np.ones((10, 3)) * 5.0
    result = safe_minmax(x, axis=0)
    assert np.allclose(result, 0.0)
    assert result.shape == (10, 3)
    assert not np.any(np.isnan(result))


def test_safe_minmax_normal():
    from src.utils.math import safe_minmax
    x = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    result = safe_minmax(x, axis=0)
    assert np.allclose(result[0], [0.0, 0.0])
    assert np.allclose(result[1], [1.0, 1.0])
