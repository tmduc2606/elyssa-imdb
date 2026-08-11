import argparse
import sys
import yaml
from pathlib import Path

import pandas as pd


def load_splits(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"ERROR: splits parquet not found: {path}")
        sys.exit(1)
    return pd.read_parquet(path)


def load_temporal_constants(config_path: Path) -> dict:
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    ts = raw.get("temporal_splits", {})
    return {
        "train_year_max": ts.get("train_year_max", 2014),
        "val_year_min": ts.get("val_year_min", 2015),
        "val_year_max": ts.get("val_year_max", 2018),
        "test_year_min": ts.get("test_year_min", 2019),
    }


def check_temporal_split(df: pd.DataFrame, constants: dict) -> dict:
    violations = []

    required = {"tconst", "start_year", "split"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        return {"pass": False, "violations": [f"missing columns: {sorted(missing_cols)}"]}

    if df["split"].isna().any():
        n_null = int(df["split"].isna().sum())
        violations.append(f"{n_null} rows with null split label")

    valid_labels = {"train", "val", "test"}
    unknown = set(df["split"].dropna().unique()) - valid_labels
    if unknown:
        violations.append(f"unknown split labels: {sorted(unknown)}")

    if df["start_year"].isna().any():
        n_null_year = int(df["start_year"].isna().sum())
        violations.append(f"{n_null_year} rows with null start_year")

    train_year_max = constants["train_year_max"]
    val_year_min = constants["val_year_min"]
    val_year_max = constants["val_year_max"]
    test_year_min = constants["test_year_min"]

    train_ok = df.loc[df["split"] == "train", "start_year"] <= train_year_max
    if not train_ok.all():
        n = int((~train_ok).sum())
        violations.append(f"{n} train rows after {train_year_max}")

    val_ok = (
        (df.loc[df["split"] == "val", "start_year"] >= val_year_min)
        & (df.loc[df["split"] == "val", "start_year"] <= val_year_max)
    )
    if not val_ok.all():
        n = int((~val_ok).sum())
        violations.append(f"{n} val rows outside [{val_year_min}, {val_year_max}]")

    test_ok = df.loc[df["split"] == "test", "start_year"] >= test_year_min
    if not test_ok.all():
        n = int((~test_ok).sum())
        violations.append(f"{n} test rows before {test_year_min}")

    dup = df.duplicated(subset=["tconst"]).sum()
    if dup:
        violations.append(f"{dup} duplicate tconst rows")

    per_split = df["split"].value_counts()
    if per_split.get("train", 0) == 0 or per_split.get("val", 0) == 0 or per_split.get("test", 0) == 0:
        violations.append(f"empty split: {per_split.to_dict()}")

    return {"pass": not violations, "violations": violations}


def main():
    parser = argparse.ArgumentParser(description="Post-hoc temporal split enforcement (DS.1)")
    parser.add_argument(
        "--splits-parquet",
        default="notebooks/models/shared/temporal_split.parquet",
        help="temporal_split.parquet produced by the feature engineering notebook",
    )
    parser.add_argument("--config", default="config/settings.yaml")
    args = parser.parse_args()

    df = load_splits(Path(args.splits_parquet))
    constants = load_temporal_constants(Path(args.config))
    result = check_temporal_split(df, constants)

    print(f"Split counts: {df['split'].value_counts().to_dict()}")
    print(f"Constants: {constants}")
    if result["pass"]:
        print("Temporal split integrity OK (no future leakage, no overlap, full coverage).")
        return 0
    for v in result["violations"]:
        print(f"  VIOLATION: {v}")
    print("Temporal split integrity CHECK FAILED.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
