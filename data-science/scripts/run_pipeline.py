import argparse
import yaml
import numpy as np
import json
import joblib
import torch
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.loader import GoldDataLoader
from src.data.splitter import temporal_split
from src.features.tabular import build_preprocessor, fit_transform_features, binarize_multilabel
from src.features.text import embed_text_batch
from src.models.genre.gmu import GatedMultimodalUnit
from src.models.rating.catboost_regressor import train_catboost
from src.evaluation.gates import QualityGateEvaluator
from src.utils.verification import verify_artifacts
from src.utils.logging import setup_logging

logger = setup_logging("elyssa.pipeline")


def load_config(config_path: str = "config/settings.yaml") -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def run_stage_eda(config: dict):
    logger.info("=== Stage: EDA ===")
    loader = GoldDataLoader(
        marts_dir=Path(config["paths"]["marts_dir"]),
        development_mode=config["development_mode"]["enabled"],
        sample_percent=config["development_mode"]["sample_percent"],
    )
    con = loader.connect()
    tables = ["dim_title", "dim_person", "fact_title_rating", "fact_title_principal", "fact_performance", "fact_episode"]
    for t in tables:
        count = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        sample = con.execute(f"SELECT * FROM {t} LIMIT 5").df()
        logger.info(f"{t}: {count:,} rows, {len(sample.columns)} columns")
        logger.info(f"  Columns: {list(sample.columns)}")
    loader.close()
    logger.info("EDA stage complete")


def run_stage_features(config: dict):
    logger.info("=== Stage: Feature Engineering ===")
    processed_dir = Path(config["paths"]["processed_dir"])
    processed_dir.mkdir(parents=True, exist_ok=True)

    loader = GoldDataLoader(
        marts_dir=Path(config["paths"]["marts_dir"]),
        development_mode=config["development_mode"]["enabled"],
        sample_percent=config["development_mode"]["sample_percent"],
    )
    con = loader.connect()

    logger.info("Loading dim_title...")
    dim_title = con.execute("SELECT * FROM dim_title").df()

    train_mask, val_mask, test_mask = temporal_split(dim_title)
    np.save(processed_dir / "train_mask.npy", train_mask.values)
    np.save(processed_dir / "val_mask.npy", val_mask.values)
    np.save(processed_dir / "test_mask.npy", test_mask.values)
    logger.info(f"Train: {train_mask.sum():,}, Val: {val_mask.sum():,}, Test: {test_mask.sum():,}")

    tab_cols = config["features"]["tabular_columns"]
    genre_col = "genre_list"
    y_genre_train, y_genre_val, y_genre_test, mlb = binarize_multilabel(dim_title, genre_col, train_mask, val_mask, test_mask)
    joblib.dump(mlb, processed_dir / "genre_list_mlb.joblib")
    logger.info(f"Genre binarizer saved: {len(mlb.classes_)} classes")

    categorical_cols = [c for c in tab_cols if dim_title[c].dtype == "object" or c.startswith("title_type_")]
    numeric_cols = [c for c in tab_cols if c not in categorical_cols]
    preprocessor = build_preprocessor(numeric_cols, categorical_cols)
    X_tab = fit_transform_features(preprocessor, dim_title, numeric_cols, categorical_cols, train_mask)
    joblib.dump(preprocessor, processed_dir / "preprocessor.joblib")
    np.save(processed_dir / "X_tab.npy", X_tab)
    logger.info(f"Tabular features: {X_tab.shape}")

    logger.info("Computing text embeddings via DistilBERT...")
    from src.features.text import load_text_encoder
    title_texts = dim_title["primary_title"].fillna("").tolist()
    tokenizer, model, device = load_text_encoder()
    X_text = embed_text_batch(title_texts, tokenizer, model, device)
    np.save(processed_dir / "X_text.npy", X_text)
    logger.info(f"Text embeddings: {X_text.shape}")

    num_tab = X_tab.shape[1]
    num_text = X_text.shape[1]
    feature_schema = {
        "tabular_features": tab_cols,
        "text_features": [f"text_emb_{i}" for i in range(num_text)],
        "total_features": num_tab + num_text,
    }
    with open(processed_dir / "feature_columns.json", "w") as f:
        json.dump(feature_schema, f, indent=2)
    logger.info(f"Feature schema saved ({num_tab} tab + {num_text} text = {num_tab + num_text} total)")

    rating_excluded = config["features"].get("rating_excluded_features", ["average_rating", "num_votes"])
    rating_cols = [c for c in tab_cols if c not in rating_excluded]
    X_rating_idx = [i for i, c in enumerate(tab_cols) if c in rating_cols]
    np.save(processed_dir / "rating_feature_indices.npy", X_rating_idx)

    con.execute("SELECT * FROM fact_title_rating").df().to_parquet(processed_dir / "fact_title_rating_features.parquet")

    loader.close()
    logger.info("Feature engineering stage complete")


def run_stage_models(config: dict, model_name: str = "all"):
    logger.info(f"=== Stage: Models ({model_name}) ===")
    processed_dir = Path(config["paths"]["processed_dir"])

    mlflow_cfg = config.get("mlflow", {})
    mlflow_tracking_uri = mlflow_cfg.get("tracking_uri", "http://mlflow:5000")
    try:
        import mlflow
        mlflow.set_tracking_uri(mlflow_tracking_uri)
        MLFLOW_ACTIVE = True
    except ImportError:
        MLFLOW_ACTIVE = False
        logger.warning("MLflow not available — skipping model logging")

    X_tab = np.load(processed_dir / "X_tab.npy")
    X_text = np.load(processed_dir / "X_text.npy")
    train_mask = np.load(processed_dir / "train_mask.npy")
    val_mask = np.load(processed_dir / "val_mask.npy")
    test_mask = np.load(processed_dir / "test_mask.npy")

    y_genre_train = np.load(processed_dir / "y_train_genre.npy") if (processed_dir / "y_train_genre.npy").exists() else None
    y_genre_val = np.load(processed_dir / "y_val_genre.npy") if (processed_dir / "y_val_genre.npy").exists() else None
    y_genre_test = np.load(processed_dir / "y_test_genre.npy") if (processed_dir / "y_test_genre.npy").exists() else None
    mlb = joblib.load(processed_dir / "genre_list_mlb.joblib")
    num_classes = len(mlb.classes_)

    X_train_tab = X_tab[train_mask]
    X_val_tab = X_tab[val_mask]
    X_test_tab = X_tab[test_mask]
    X_train_text = X_text[train_mask]
    X_val_text = X_text[val_mask]
    X_test_text = X_text[test_mask]

    X_train = np.concatenate([X_train_tab, X_train_text], axis=1).astype(np.float32)
    X_val = np.concatenate([X_val_tab, X_val_text], axis=1).astype(np.float32)
    X_test = np.concatenate([X_test_tab, X_test_text], axis=1).astype(np.float32)

    inventory = []

    if model_name in ("all", "genre"):
        logger.info("Training GMU genre classification model...")
        gmu = GatedMultimodalUnit(
            dims_tab=X_train_tab.shape[1],
            dims_text=X_train_text.shape[1],
            hidden_dim=config["models"]["genre"]["gmu"]["hidden_dim"],
            dropout=config["models"]["genre"]["gmu"]["dropout"],
            output_dim=num_classes,
        )
        optimizer = torch.optim.Adam(gmu.parameters(), lr=1e-3)
        X_tab_t = torch.tensor(X_train_tab, dtype=torch.float32)
        X_text_t = torch.tensor(X_train_text, dtype=torch.float32)
        y_t = torch.tensor(y_genre_train, dtype=torch.float32) if y_genre_train is not None else None
        gmu.train()

        for epoch in range(min(30, config["models"]["genre"]["gmu"]["max_epochs"])):
            optimizer.zero_grad()
            logits = gmu(X_tab_t, X_text_t)
            if y_t is not None:
                loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, y_t)
                loss.backward()
                optimizer.step()
                if (epoch + 1) % 5 == 0:
                    logger.info(f"  Epoch {epoch + 1}/{config['models']['genre']['gmu']['max_epochs']}, Loss: {loss.item():.4f}")

        torch.save(gmu.state_dict(), processed_dir / "gmu_genre_best.pt")
        logger.info("GMU model saved")

        genre_metrics = {}
        if y_genre_val is not None and y_genre_test is not None:
            gmu.eval()
            with torch.no_grad():
                val_logits = gmu(torch.tensor(X_val_tab, dtype=torch.float32), torch.tensor(X_val_text, dtype=torch.float32))
                val_probs = torch.sigmoid(val_logits).numpy()
                from sklearn.metrics import f1_score
                genre_metrics["val_macro_f1"] = float(f1_score(y_genre_val, (val_probs > 0.5).astype(int), average="macro"))
                test_logits = gmu(torch.tensor(X_test_tab, dtype=torch.float32), torch.tensor(X_test_text, dtype=torch.float32))
                test_probs = torch.sigmoid(test_logits).numpy()
                genre_metrics["test_macro_f1"] = float(f1_score(y_genre_test, (test_probs > 0.5).astype(int), average="macro"))
            logger.info(f"GMU: val_macro_f1={genre_metrics['val_macro_f1']:.4f}, test_macro_f1={genre_metrics['test_macro_f1']:.4f}")

        if MLFLOW_ACTIVE:
            run_name = f"gmu_genre_{datetime.now():%Y%m%d_%H%M%S}"
            with mlflow.start_run(run_name=run_name) as run:
                mlflow.set_tag("model_type", "GMU")
                mlflow.set_tag("training_date", datetime.now().isoformat())
                mlflow.log_params(config["models"]["genre"]["gmu"])
                mlflow.log_metrics(genre_metrics)
                mlflow.log_artifact(str(processed_dir / "gmu_genre_best.pt"), artifact_path="models")
                mlflow.log_artifact(str(processed_dir / "feature_columns.json"), artifact_path="schema")
                mlflow.log_artifact(str(processed_dir / "genre_list_mlb.joblib"), artifact_path="encoders")
                mlflow.log_artifact(str(processed_dir / "preprocessor.joblib"), artifact_path="preprocessor")
                from src.registry.model_registry import ModelRegistry
                registry = ModelRegistry(tracking_uri=mlflow_tracking_uri)
                registry.register_model("Elyssa_Genre_GMU", run.info.run_id, genre_metrics)
                registry.promote_to_staging("Elyssa_Genre_GMU", "1")
                logger.info(f"GMU model logged to MLflow run {run.info.run_id}")

        inventory.append({
            "name": "genre_gmu",
            "type": "GMU",
            "metrics": genre_metrics,
            "params": {
                "hidden_dim": config["models"]["genre"]["gmu"]["hidden_dim"],
                "dropout": config["models"]["genre"]["gmu"]["dropout"],
            },
        })

    if model_name in ("all", "rating"):
        logger.info("Training CatBoost rating regression model...")
        rating_idx = np.load(processed_dir / "rating_feature_indices.npy")
        X_rating_train = np.concatenate([X_train_tab[:, rating_idx], X_train_text], axis=1)
        X_rating_val = np.concatenate([X_val_tab[:, rating_idx], X_val_text], axis=1)

        if y_genre_train is not None:
            y_rating_train = y_genre_train[:, 0] if y_genre_train.ndim > 1 else y_genre_train
        else:
            y_rating_train = np.zeros(X_rating_train.shape[0])
        if y_genre_val is not None:
            y_rating_val = y_genre_val[:, 0] if y_genre_val.ndim > 1 else y_genre_val
        else:
            y_rating_val = np.zeros(X_rating_val.shape[0])

        model, metrics = train_catboost(X_rating_train, y_rating_train, X_rating_val, y_rating_val)
        model.save_model(str(processed_dir / "catboost_rating_model.cbm"))
        logger.info(f"CatBoost model saved, val_rmse: {metrics.get('val_rmse', 'N/A')}")

        if MLFLOW_ACTIVE:
            run_name = f"catboost_rating_{datetime.now():%Y%m%d_%H%M%S}"
            with mlflow.start_run(run_name=run_name) as run:
                mlflow.set_tag("model_type", "CatBoost")
                mlflow.set_tag("training_date", datetime.now().isoformat())
                mlflow.log_params(config["models"]["rating"]["catboost"])
                mlflow.log_metrics(metrics)
                mlflow.log_artifact(str(processed_dir / "catboost_rating_model.cbm"), artifact_path="models")
                mlflow.log_artifact(str(processed_dir / "scaler.joblib"), artifact_path="preprocessor")
                from src.registry.model_registry import ModelRegistry
                registry = ModelRegistry(tracking_uri=mlflow_tracking_uri)
                registry.register_model("Elyssa_Rating_CatBoost", run.info.run_id, metrics)
                registry.promote_to_staging("Elyssa_Rating_CatBoost", "1")
                logger.info(f"CatBoost model logged to MLflow run {run.info.run_id}")

        inventory.append({
            "name": "rating_catboost",
            "type": "CatBoost",
            "metrics": metrics,
        })

    with open(processed_dir / "model_inventory.json", "w") as f:
        json.dump(inventory, f, indent=2)
    logger.info(f"Model inventory saved ({len(inventory)} models)")


def run_stage_analytics(config: dict):
    logger.info("=== Stage: Analytics ===")
    processed_dir = Path(config["paths"]["processed_dir"])

    logger.info("Verifying artifacts...")
    results = verify_artifacts(processed_dir)
    all_ok = all(v["status"] == "OK" for v in results.values())
    logger.info(f"Artifact verification: {'ALL OK' if all_ok else 'SOME MISSING'}")

    logger.info("Checking quality gates...")
    evaluator = QualityGateEvaluator()
    inventory_path = processed_dir / "model_inventory.json"
    if inventory_path.exists():
        metrics = {}
        with open(inventory_path) as f:
            inventory = json.load(f)
        for entry in inventory:
            metrics.update(entry.get("metrics", {}))
        gate_results = evaluator.evaluate(metrics)
        for gate, result in gate_results.items():
            status = "PASS" if result["pass"] else "FAIL"
            logger.info(f"  {gate}: {status} (value={result.get('value', 'N/A')}, threshold={result['threshold']})")
        logger.info(f"All gates passed: {evaluator.all_passed(gate_results)}")
    else:
        logger.warning("model_inventory.json not found — skipping quality gates")

    logger.info("Analytics stage complete")


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
