import numpy as np
import joblib
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FeatureBuilder:
    RATING_EXCLUDED = {
        "average_rating",
        "num_votes",
        "rating_bucket",
        "avg_rating_genre_year",
        "avg_votes_genre_year",
    }

    def __init__(self, processed_dir: Path):
        self.processed_dir = processed_dir
        self.preprocessor = None
        self.mlb_genre = None
        self.mlb_region = None
        self.scaler = None

    def load_preprocessors(self):
        pp_path = self.processed_dir / "preprocessor.joblib"
        if pp_path.exists():
            self.preprocessor = joblib.load(pp_path)
        else:
            logger.warning("preprocessor.joblib not found")

        genre_path = self.processed_dir / "genre_list_mlb.joblib"
        if genre_path.exists():
            self.mlb_genre = joblib.load(genre_path)

        region_path = self.processed_dir / "region_list_mlb.joblib"
        if region_path.exists():
            self.mlb_region = joblib.load(region_path)

        scaler_path = self.processed_dir / "scaler.joblib"
        if scaler_path.exists():
            self.scaler = joblib.load(scaler_path)

    def get_rating_features(self, feature_cols: list) -> list:
        return [c for c in feature_cols if c not in self.RATING_EXCLUDED]

    def build_genre_matrix(
        self,
        X_tab: np.ndarray,
        X_text: np.ndarray,
        y_genre: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        X = np.concatenate([X_tab, X_text], axis=1).astype(np.float32)
        return {"X": X, "y": y_genre}

    def build_rating_matrix(
        self,
        X_tab: np.ndarray,
        X_text: np.ndarray,
        y_rating: np.ndarray,
        exclude_cols: Optional[list] = None,
    ) -> Dict[str, np.ndarray]:
        if exclude_cols:
            mask = ~np.isin(range(X_tab.shape[1]), exclude_cols)
            X_tab = X_tab[:, mask]
        X = np.concatenate([X_tab, X_text], axis=1).astype(np.float32)
        return {"X": X, "y": y_rating}
