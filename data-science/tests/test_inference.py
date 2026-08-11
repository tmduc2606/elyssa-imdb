import numpy as np
import pandas as pd
from pathlib import Path


def _fitted_preprocessor():
    from src.features.tabular import build_preprocessor

    df = pd.DataFrame({
        "start_year": [2000, 2005, 2010],
        "runtime_minutes": [90, 120, 150],
        "title_type": ["movie", "tvSeries", "short"],
        "is_adult": [0, 0, 1],
    })
    numeric_cols = ["start_year", "runtime_minutes"]
    categorical_cols = ["title_type", "is_adult"]
    preprocessor = build_preprocessor(numeric_cols, categorical_cols)
    preprocessor.fit(df[numeric_cols + categorical_cols])
    return preprocessor


def _models_dict(preprocessor):
    tabular = ["start_year", "runtime_minutes",
               "title_type_movie", "title_type_tvSeries", "title_type_short",
               "is_adult_0", "is_adult_1"]
    text = ["text_emb_0", "text_emb_1"]
    return {
        "feature_info": {"tabular_features": tabular, "text_features": text},
        "preprocessor": preprocessor,
        "scaler": None,
        "num_tab": len(tabular),
        "num_text": len(text),
    }


def test_build_feature_vector_no_leakage():
    from src.inference.pipeline import build_feature_vector

    models = _models_dict(_fitted_preprocessor())
    vec = build_feature_vector({
        "start_year": 2010,
        "runtime_minutes": 148,
        "title_type": "movie",
        "is_adult": 0,
    }, models)
    assert vec.shape == (9,)
    leaked = build_feature_vector({
        "start_year": 2010,
        "runtime_minutes": 148,
        "title_type": "movie",
        "is_adult": 0,
        "average_rating": 10.0,
        "num_votes": 1_000_000,
        "rating_bucket": "excellent",
    }, models)
    assert np.allclose(vec, leaked), "rating-pillar inputs leaked into feature vector"


def test_build_feature_vector_onehot_encoding():
    from src.inference.pipeline import build_feature_vector

    models = _models_dict(_fitted_preprocessor())
    vec = build_feature_vector({
        "start_year": 2005,
        "runtime_minutes": 100,
        "title_type": "tvSeries",
        "is_adult": 1,
    }, models)
    tab = vec[: models["num_tab"]]
    assert tab[2] == 0.0
    assert tab[3] == 0.0
    assert tab[4] == 1.0
    assert tab[5] == 0.0
    assert tab[6] == 1.0
    assert np.all(vec[models["num_tab"]:] == 0.0), "text embeddings must be zero without title_text"


def test_build_feature_vector_missing_cols():
    from src.inference.pipeline import build_feature_vector

    models = _models_dict(_fitted_preprocessor())
    vec = build_feature_vector({"start_year": 2005}, models)
    assert vec.shape == (9,)
    assert np.isfinite(vec).all(), "missing features must be imputed, not NaN"


def test_build_feature_vector_rejects_no_schema():
    from src.inference.pipeline import build_feature_vector

    models = {
        "feature_info": None,
        "preprocessor": None,
        "scaler": None,
        "num_tab": 0,
        "num_text": 0,
    }
    try:
        build_feature_vector({"start_year": 2010}, models)
        raise AssertionError("expected failure with missing preprocessor")
    except (AttributeError, TypeError):
        pass


def test_predict_genre_schema():
    from src.inference.pipeline import predict_genre, load_inference_models
    from pathlib import Path

    processed = Path(__file__).parent.parent / "marts" / "processed"
    if not (processed / "gmu_genre_best.pt").exists():
        return

    models = load_inference_models(processed)
    result = predict_genre({
        "runtime_minutes": 148,
        "start_year": 2010,
        "is_adult": 0,
        "title_type": "movie",
    }, models)
    assert "genres" in result
    assert isinstance(result["genres"], list)


def test_predict_rating_range():
    from src.inference.pipeline import predict_rating, load_inference_models

    processed = Path(__file__).parent.parent / "marts" / "processed"
    if not (processed / "catboost_rating_model.cbm").exists():
        return

    models = load_inference_models(processed)
    result = predict_rating({
        "runtime_minutes": 148,
        "start_year": 2010,
        "is_adult": 0,
        "title_type": "movie",
    }, models)
    assert "predicted_rating" in result
    assert 1.0 <= result["predicted_rating"] <= 10.0
