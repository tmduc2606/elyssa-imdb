import argparse
import yaml
import logging
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import GoldDataLoader
from src.data.splitter import temporal_split
from src.features.builder import FeatureBuilder
from src.utils.verification import verify_artifacts
from src.utils.logging import setup_logging

logger = setup_logging("elyssa.pipeline")


def load_config(config_path: str = "config/settings.yaml") -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def run_stage_eda(config: dict):
    logger.info("=== Stage: EDA ===")


def run_stage_features(config: dict):
    logger.info("=== Stage: Feature Engineering ===")
    loader = GoldDataLoader(
        marts_dir=Path(config["paths"]["marts_dir"]),
        development_mode=config["development_mode"]["enabled"],
        sample_percent=config["development_mode"]["sample_percent"],
    )
    con = loader.connect()
    loader.close()


def run_stage_models(config: dict, model_name: str = "all"):
    logger.info(f"=== Stage: Models ({model_name}) ===")


def run_stage_analytics(config: dict):
    logger.info("=== Stage: Analytics ===")


def main():
    parser = argparse.ArgumentParser(description="Elyssa Pipeline")
    parser.add_argument("--stage", choices=["eda", "features", "models", "analytics", "all"])
    parser.add_argument("--model", default="all", help="Specific model to train")
    parser.add_argument("--config", default="config/settings.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    start = datetime.now()
    logger.info(f"Pipeline started at {start}")

    stages = {
        "eda": run_stage_eda,
        "features": run_stage_features,
        "models": lambda c: run_stage_models(c, args.model),
        "analytics": run_stage_analytics,
    }

    if args.stage == "all":
        for stage_name, stage_fn in stages.items():
            stage_fn(config)
    else:
        stages[args.stage](config)

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"Pipeline completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
