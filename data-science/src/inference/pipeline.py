import json
import numpy as np
import torch
import joblib
import pandas as pd
from pathlib import Path
from typing import Dict, Optional
import logging

from src.models.genre.gmu import GatedMultimodalUnit

logger = logging.getLogger(__name__)


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
    inputs = tokenizer(title_text, return_tensors="pt", truncation=True, max_length=128, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).squeeze().numpy()


def build_feature_vector(
    raw_input: Dict,
    models: Dict,
    title_text: str = "",
) -> np.ndarray:
    feature_info = models["feature_info"]
    preprocessor = models["preprocessor"]
    scaler = models["scaler"]
    num_text = models["num_text"]
    tab_cols = feature_info["tabular_features"]

    row = {}
    for col in tab_cols:
        val = raw_input.get(col, 0)
        if col.startswith("title_type_"):
            title_type = raw_input.get("title_type", "")
            val = 1.0 if title_type == col.split("_", 2)[-1] else 0.0
        elif col.startswith("is_adult_"):
            is_adult = int(raw_input.get("is_adult", 0))
            expected_val = int(col.split("_")[-1])
            val = 1.0 if is_adult == expected_val else 0.0
        row[col] = val

    df = pd.DataFrame([row])
    tab_features = scaler.transform(preprocessor.transform(df))
    tab_vec = np.asarray(tab_features).flatten().astype(np.float32)

    if title_text:
        text_emb = _get_text_embedding(title_text)
        if text_emb.shape[0] < num_text:
            text_emb = np.pad(text_emb, (0, num_text - text_emb.shape[0]), mode="constant")
    else:
        text_emb = np.zeros(num_text, dtype=np.float32)

    return np.concatenate([tab_vec, text_emb])


def predict_genre(raw_input: Dict, models: Dict) -> Dict:
    num_tab = models["num_tab"]
    tabular_cols = models["feature_info"]["tabular_features"]
    tab_vec = np.zeros(num_tab, dtype=np.float32)
    for i, col in enumerate(tabular_cols):
        if col in raw_input:
            tab_vec[i] = float(raw_input[col])
        elif col.startswith("title_type_"):
            title_type = raw_input.get("title_type", "")
            expected_type = col.split("_", 2)[-1]
            tab_vec[i] = 1.0 if title_type == expected_type else 0.0
        elif col.startswith("is_adult_"):
            is_adult = int(raw_input.get("is_adult", 0))
            expected_val = int(col.split("_")[-1])
            tab_vec[i] = 1.0 if is_adult == expected_val else 0.0

    X_tab = torch.tensor(tab_vec, dtype=torch.float32).unsqueeze(0)
    text_tensor = torch.zeros(1, models["num_text"], dtype=torch.float32)

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


def predict_rating(raw_input: Dict, models: Dict) -> Dict:
    num_tab = models["num_tab"]
    tabular_cols = models["feature_info"]["tabular_features"]
    tab_vec = np.zeros(num_tab, dtype=np.float32)
    for i, col in enumerate(tabular_cols):
        if col in raw_input:
            tab_vec[i] = float(raw_input[col])
        elif col.startswith("title_type_"):
            title_type = raw_input.get("title_type", "")
            expected_type = col.split("_", 2)[-1]
            tab_vec[i] = 1.0 if title_type == expected_type else 0.0
        elif col.startswith("is_adult_"):
            is_adult = int(raw_input.get("is_adult", 0))
            expected_val = int(col.split("_")[-1])
            tab_vec[i] = 1.0 if is_adult == expected_val else 0.0
    text_emb = np.zeros(models["num_text"], dtype=np.float32)
    feature_vec = np.concatenate([tab_vec, text_emb]).reshape(1, -1)

    catboost_model = models["catboost_model"]
    predicted_rating = float(catboost_model.predict(feature_vec)[0])
    predicted_rating = max(1.0, min(10.0, predicted_rating))

    return {"predicted_rating": predicted_rating}
