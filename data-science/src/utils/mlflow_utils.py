import logging
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import mlflow
    import mlflow.sklearn
    import mlflow.catboost
    import mlflow.pytorch
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("MLflow not installed; experiment tracking disabled")


class MlflowWrapper:
    def __init__(self, tracking_uri: str = "sqlite:///mlflow.db"):
        self.available = MLFLOW_AVAILABLE
        if self.available:
            mlflow.set_tracking_uri(tracking_uri)

    @contextmanager
    def start_run(self, experiment_name: str, run_name: str):
        if not self.available:
            logger.info(f"[MLflow disabled] Would start run: {run_name}")
            yield None
            return

        mlflow.set_experiment(experiment_name)
        with mlflow.start_run(run_name=run_name) as run:
            yield run

    def log_params(self, params: dict):
        if self.available:
            mlflow.log_params(params)

    def log_metrics(self, metrics: dict):
        if self.available:
            sanitized = {
                k.replace("@", "_at_").replace("+", "_and_"): v
                for k, v in metrics.items()
            }
            mlflow.log_metrics(sanitized)

    def log_artifact(self, path: str):
        if self.available:
            mlflow.log_artifact(path)
