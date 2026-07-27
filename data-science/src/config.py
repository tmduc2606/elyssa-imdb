import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class TemporalSplits:
    train_year_max: int = 2014
    val_year_min: int = 2015
    val_year_max: int = 2018
    test_year_min: int = 2019


@dataclass
class FeatureConfig:
    tabular_columns: List[str] = field(default_factory=lambda: [
        "start_year", "runtime_minutes",
        "num_persons", "unique_persons", "actor_count", "actress_count",
        "director_count", "writer_count", "producer_count", "composer_count",
        "editor_count", "cinematographer_count", "self_count",
        "series_episode_count", "series_avg_episode_rating",
        "min_season", "max_season", "genre_cnt",
        "dir_avg_career_len", "dir_max_career_len", "dir_avg_experience", "dir_avg_recent_activity",
        "wri_avg_career_len", "wri_max_career_len", "wri_avg_experience", "wri_avg_recent_activity",
    ])
    text_embedding_dim: int = 768
    rating_excluded_features: List[str] = field(default_factory=lambda: ["average_rating", "num_votes"])


@dataclass
class ModelGenreConfig:
    hidden_dim: int = 256
    dropout: float = 0.3
    optuna_trials: int = 5
    max_epochs: int = 30
    patience: int = 5


@dataclass
class ModelRatingConfig:
    optuna_trials: int = 5
    max_iterations: int = 400
    max_depth: int = 6
    early_stopping_rounds: int = 50


@dataclass
class ModelRecommenderConfig:
    svd_factors: int = 100
    ncf_embedding_dim: int = 64
    ncf_layers: List[int] = field(default_factory=lambda: [64, 32, 16])


@dataclass
class QualityGatesConfig:
    rating_rmse_max: float = 0.55
    genre_macro_f1_min: float = 0.60
    inference_latency_max_ms: int = 100
    cold_start_precision_min: float = 0.01


@dataclass
class ElyssaConfig:
    development_mode: bool = True
    sample_percent: int = 5
    random_seed: int = 42
    temporal_splits: TemporalSplits = field(default_factory=TemporalSplits)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    model_genre: ModelGenreConfig = field(default_factory=ModelGenreConfig)
    model_rating: ModelRatingConfig = field(default_factory=ModelRatingConfig)
    model_recommender: ModelRecommenderConfig = field(default_factory=ModelRecommenderConfig)
    quality_gates: QualityGatesConfig = field(default_factory=QualityGatesConfig)


def load_config(config_path: str = "config/settings.yaml") -> ElyssaConfig:
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Config not found at {config_path}, using defaults")
        return ElyssaConfig()

    with open(path) as f:
        raw = yaml.safe_load(f)

    cfg = ElyssaConfig(
        development_mode=raw.get("development_mode", {}).get("enabled", True),
        sample_percent=raw.get("development_mode", {}).get("sample_percent", 5),
        random_seed=raw.get("development_mode", {}).get("random_seed", 42),
    )

    if "temporal_splits" in raw:
        cfg.temporal_splits = TemporalSplits(**raw["temporal_splits"])
    if "features" in raw:
        feat = raw["features"]
        cfg.features = FeatureConfig(
            tabular_columns=feat.get("tabular_columns", cfg.features.tabular_columns),
            text_embedding_dim=feat.get("text_embedding_dim", cfg.features.text_embedding_dim),
            rating_excluded_features=feat.get("rating_excluded_features", cfg.features.rating_excluded_features),
        )
    if "models" in raw:
        models = raw["models"]
        if "genre" in models:
            cfg.model_genre = ModelGenreConfig(**models["genre"].get("gmu", {}))
        if "rating" in models:
            cfg.model_rating = ModelRatingConfig(**models["rating"].get("catboost", {}))
        if "recommender" in models:
            cfg.model_recommender = ModelRecommenderConfig(**models["recommender"])

    return cfg
