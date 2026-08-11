import json
import numpy as np
import torch
import joblib
import pandas as pd
from pathlib import Path
from typing import Dict
import logging

from src.models.genre.gmu import GatedMultimodalUnit

logger = logging.getLogger(__name__)

MAX_LENGTH = 32


def load_inference_models(processed_dir: Path, device: str = "cpu"):
    with open(processed_dir / "feature_columns.json") as f:
        feat_info = json.load(f)
    num_tab = len(feat_info["tabular_features"])
    num_text = len(feat_info["text_features"])

    with open(processed_dir / "model_inventory.json") as f:
        inventory = json.load(f)

    gmu_params = None
    for entry in inventory:
        if entry["name"] == "genre_gmu":
            gmu_params = entry["params"]
            break

    mlb = joblib.load(processed_dir / "genre_list_mlb.joblib")
    num_classes = mlb.classes_.shape[0]

    params = gmu_params or {"hidden_dim": 256, "dropout": 0.3}
    model = GatedMultimodalUnit(
        num_tab, num_text, 0,
        hidden_dim=params["hidden_dim"],
        dropout=params["dropout"],
        output_dim=num_classes,
    )
    model.load_state_dict(torch.load(
        processed_dir / "gmu_genre_best.pt", map_location=device
    ))
    model.eval()

    import catboost as cb
    catboost_model = cb.CatBoostRegressor()
    catboost_model.load_model(str(processed_dir / "catboost_rating_model.cbm"))

    preprocessor = joblib.load(processed_dir / "preprocessor.joblib")
    scaler = joblib.load(processed_dir / "scaler.joblib")

    return {
        "feature_info": feat_info,
        "gmu_model": model,
        "catboost_model": catboost_model,
        "mlb_genre": mlb,
        "preprocessor": preprocessor,
        "scaler": scaler,
        "num_tab": num_tab,
        "num_text": num_text,
        "device": device,
    }


def _get_text_embedding(title_text: str) -> np.ndarray:
    from transformers import DistilBertTokenizer, DistilBertModel
    tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
    model = DistilBertModel.from_pretrained("distilbert-base-uncased")
    inputs = tokenizer(
        title_text, return_tensors="pt",
        truncation=True, max_length=MAX_LENGTH, padding=True,
    )
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state[:, 0, :].squeeze().numpy()


def _build_tabular_vector(raw_input: Dict, preprocessor) -> np.ndarray:
    numeric_cols = list(preprocessor.transformers_[0][2])
    categorical_cols = (
        list(preprocessor.transformers_[1][2])
        if len(preprocessor.transformers_) > 1 else []
    )
    data = {}
    for col in numeric_cols:
        val = raw_input.get(col)
        data[col] = val if val is not None else np.nan
    for col in categorical_cols:
        val = raw_input.get(col)
        data[col] = val if val is not None else "missing"
    df = pd.DataFrame([data])
    transformed = preprocessor.transform(df)
    return np.asarray(transformed).flatten().astype(np.float32)


def build_feature_vector(
    raw_input: Dict,
    models: Dict,
    title_text: str = "",
) -> np.ndarray:
    preprocessor = models["preprocessor"]
    num_text = models["num_text"]

    tab_vec = _build_tabular_vector(raw_input, preprocessor)
    if len(tab_vec) != models["num_tab"]:
        logger.warning(
            "Preprocessor output %d features does not match schema %d; truncating",
            len(tab_vec), models["num_tab"],
        )
        tab_vec = tab_vec[: models["num_tab"]]

    if title_text:
        text_emb = _get_text_embedding(title_text)
        if text_emb.shape[0] < num_text:
            text_emb = np.pad(text_emb, (0, num_text - text_emb.shape[0]), mode="constant")
        elif text_emb.shape[0] > num_text:
            text_emb = text_emb[:num_text]
    else:
        text_emb = np.zeros(num_text, dtype=np.float32)

    return np.concatenate([tab_vec, text_emb])


def predict_genre(raw_input: Dict, models: Dict, title_text: str = "") -> Dict:
    feature_vec = build_feature_vector(raw_input, models, title_text)
    num_tab = models["num_tab"]
    X_tab = torch.tensor(feature_vec[:num_tab], dtype=torch.float32).unsqueeze(0)
    text_tensor = torch.tensor(feature_vec[num_tab:], dtype=torch.float32).unsqueeze(0)

    with torch.no_grad():
        model = models["gmu_model"]
        logits = model(X_tab, text_tensor)
        probs = torch.sigmoid(logits).numpy().flatten()

    mlb = models["mlb_genre"]
    threshold = 0.5
    predicted_genres = mlb.classes_[probs > threshold].tolist()
    probabilities = {
        str(k): float(v)
        for k, v in zip(mlb.classes_, probs.tolist())
    }

    return {"genres": predicted_genres, "probabilities": probabilities}


def predict_rating(raw_input: Dict, models: Dict, title_text: str = "") -> Dict:
    feature_vec = build_feature_vector(raw_input, models, title_text).reshape(1, -1)

    catboost_model = models["catboost_model"]
    predicted_rating = float(catboost_model.predict(feature_vec)[0])
    predicted_rating = max(1.0, min(10.0, predicted_rating))

    return {"predicted_rating": predicted_rating}
