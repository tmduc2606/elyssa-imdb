import json
from pathlib import Path
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def save_feature_schema(
    processed_dir: Path,
    tabular_features: List[str],
    text_features: List[str],
    embedding_dim: int = 768,
):
    schema = {
        "tabular_features": tabular_features,
        "text_features": text_features,
        "total_features": len(tabular_features) + embedding_dim,
        "embedding_dim": embedding_dim,
    }
    with open(processed_dir / "feature_columns.json", "w") as f:
        json.dump(schema, f, indent=2)
    logger.info(f"Saved feature schema: {len(tabular_features)} tabular + {embedding_dim} text = {schema['total_features']} total")


def load_feature_schema(processed_dir: Path) -> Dict:
    path = processed_dir / "feature_columns.json"
    with open(path) as f:
        return json.load(f)
