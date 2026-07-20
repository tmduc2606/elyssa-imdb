import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import GoldDataLoader
import logging

logger = logging.getLogger(__name__)


def export_marts(config: dict, output_dir: Path):
    logger.info(f"Exporting Gold marts to {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    loader = GoldDataLoader(
        marts_dir=Path(config["paths"]["marts_dir"]),
        development_mode=False,
        sample_percent=100,
    )
    con = loader.connect()

    tables = [
        "dim_title", "dim_person", "fact_title_rating",
        "fact_title_principal", "fact_performance", "fact_episode",
    ]

    for table in tables:
        df = con.execute(f"SELECT * FROM {table}").df()
        out_path = output_dir / f"{table}.parquet"
        df.to_parquet(out_path, index=False)
        logger.info(f"  Exported {table}: {len(df):,} rows -> {out_path}")

    loader.close()


def main():
    parser = argparse.ArgumentParser(description="Export Gold marts to Parquet")
    parser.add_argument("--output-dir", default="../marts_export")
    parser.add_argument("--config", default="config/settings.yaml")
    args = parser.parse_args()

    import yaml
    with open(args.config) as f:
        config = yaml.safe_load(f)

    export_marts(config, Path(args.output_dir))


if __name__ == "__main__":
    main()
