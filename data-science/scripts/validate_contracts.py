import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def validate_feature_schema(path: Path) -> dict:
    with open(path) as f:
        schema = json.load(f)
    assert "tabular_features" in schema, "Missing tabular_features"
    assert "text_features" in schema, "Missing text_features"
    assert "total_features" in schema, "Missing total_features"
    assert schema["total_features"] == len(schema["tabular_features"]) + len(schema["text_features"]), \
        f"total_features ({schema['total_features']}) != tabular ({len(schema['tabular_features'])}) + text ({len(schema['text_features'])})"
    return {"columns": len(schema["tabular_features"]), "total_dim": schema["total_features"]}


def validate_preprocessor(path: Path) -> dict:
    import joblib
    pp = joblib.load(path)
    n_transformers = len(pp.transformers_)
    return {"transformers": n_transformers}


def validate_mlb(path: Path) -> dict:
    import joblib
    mlb = joblib.load(path)
    return {"classes": len(mlb.classes_)}


def validate_pytorch_model(path: Path) -> dict:
    import torch
    state = torch.load(path, map_location="cpu")
    return {"layers": len(state)}


def validate_catboost_model(path: Path) -> dict:
    from catboost import CatBoostRegressor
    model = CatBoostRegressor()
    model.load_model(str(path))
    return {"tree_count": model.tree_count_}


def validate_api_contract(processed_dir: Path) -> dict:
    required = {
        "feature_columns.json": validate_feature_schema,
        "preprocessor.joblib": validate_preprocessor,
        "genre_list_mlb.joblib": validate_mlb,
        "gmu_genre_best.pt": validate_pytorch_model,
        "catboost_rating_model.cbm": validate_catboost_model,
    }

    results = {}
    for artifact, validator in required.items():
        path = processed_dir / artifact
        try:
            result = validator(path)
            results[artifact] = {"status": "PASS", "details": result}
        except Exception as e:
            results[artifact] = {"status": "FAIL", "error": str(e)}

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate DS-to-Web contracts")
    parser.add_argument("--processed-dir", default="marts/processed")
    args = parser.parse_args()

    processed_dir = Path(args.processed_dir)
    if not processed_dir.exists():
        print(f"ERROR: processed_dir not found: {processed_dir}")
        sys.exit(1)

    print(f"Validating contracts in {processed_dir}...")
    results = validate_api_contract(processed_dir)

    all_pass = True
    for artifact, result in results.items():
        status_icon = "PASS" if result["status"] == "PASS" else "FAIL"
        print(f"  [{status_icon}] {artifact}")
        if result["status"] == "FAIL":
            print(f"          Error: {result['error']}")
            all_pass = False
        else:
            print(f"          {result['details']}")

    if all_pass:
        print("\nAll contracts validated successfully.")
    else:
        print("\nSome contracts FAILED validation.")
        sys.exit(1)


if __name__ == "__main__":
    main()
