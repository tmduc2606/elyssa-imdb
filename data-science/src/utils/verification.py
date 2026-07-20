from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

REQUIRED_ARTIFACTS = [
    "feature_columns.json",
    "preprocessor.joblib",
    "genre_list_mlb.joblib",
    "scaler.joblib",
    "X_train_genre.npy",
    "X_val_genre.npy",
    "X_test_genre.npy",
    "y_train_genre.npy",
    "y_val_genre.npy",
    "y_test_genre.npy",
    "gmu_genre_best.pt",
    "catboost_rating_model.cbm",
    "model_inventory.json",
]


def verify_artifacts(processed_dir: Path) -> dict:
    results = {}
    for artifact in REQUIRED_ARTIFACTS:
        path = processed_dir / artifact
        results[artifact] = {
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "status": "OK" if path.exists() and path.stat().st_size > 0 else "MISSING",
        }

    missing = [k for k, v in results.items() if v["status"] == "MISSING"]
    if missing:
        logger.warning(f"Missing artifacts: {missing}")
    else:
        logger.info(f"All {len(REQUIRED_ARTIFACTS)} artifacts verified OK.")

    return results
