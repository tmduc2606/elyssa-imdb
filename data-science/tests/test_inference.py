import numpy as np
from pathlib import Path



def test_build_feature_vector_no_leakage():
    dummy_features = [
        "start_year", "runtime_minutes", "title_type_movie",
        "title_type_tvSeries", "is_adult_0", "is_adult_1",
        "num_persons", "unique_persons",
    ]
    raw = {
        "start_year": 2010,
        "runtime_minutes": 148,
        "title_type": "movie",
        "is_adult": 0,
    }
    num_tab = len(dummy_features)
    tab_vec = np.zeros(num_tab, dtype=np.float32)
    for i, col in enumerate(dummy_features):
        if col in raw:
            tab_vec[i] = float(raw[col])
        elif col.startswith("title_type_"):
            expected = col.split("_", 2)[-1]
            tab_vec[i] = 1.0 if raw.get("title_type", "") == expected else 0.0
        elif col.startswith("is_adult_"):
            expected = int(col.split("_")[-1])
            tab_vec[i] = 1.0 if int(raw.get("is_adult", 0)) == expected else 0.0

    assert tab_vec[0] == 2010.0
    assert tab_vec[2] == 1.0
    assert tab_vec[3] == 0.0
    assert tab_vec[4] == 1.0
    assert tab_vec[5] == 0.0


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


def test_build_feature_vector_missing_cols():
    dummy_features = ["start_year", "runtime_minutes", "num_persons"]
    raw = {"start_year": 2015}
    tab_vec = np.zeros(len(dummy_features), dtype=np.float32)
    for i, col in enumerate(dummy_features):
        if col in raw:
            tab_vec[i] = float(raw[col])
    assert tab_vec[0] == 2015.0
    assert tab_vec[1] == 0.0
    assert tab_vec[2] == 0.0


def test_build_feature_vector_onehot_encoding():
    dummy_features = [
        "start_year", "title_type_movie", "title_type_tvSeries",
        "title_type_short", "is_adult_0", "is_adult_1",
    ]
    raw = {"start_year": 2020, "title_type": "tvSeries", "is_adult": 1}
    tab_vec = np.zeros(len(dummy_features), dtype=np.float32)
    for i, col in enumerate(dummy_features):
        if col in raw:
            tab_vec[i] = float(raw[col])
        elif col.startswith("title_type_"):
            tab_vec[i] = 1.0 if raw.get("title_type", "") == col.split("_", 2)[-1] else 0.0
        elif col.startswith("is_adult_"):
            tab_vec[i] = 1.0 if int(raw.get("is_adult", 0)) == int(col.split("_")[-1]) else 0.0

    assert tab_vec[0] == 2020.0
    assert tab_vec[1] == 0.0
    assert tab_vec[2] == 1.0
    assert tab_vec[3] == 0.0
    assert tab_vec[4] == 0.0
    assert tab_vec[5] == 1.0
