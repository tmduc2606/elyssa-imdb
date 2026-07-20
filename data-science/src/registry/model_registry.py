import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

try:
    import mlflow
    from mlflow.tracking import MlflowClient
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("MLflow not installed; model registry disabled")


class ModelRegistry:
    STAGES = ["None", "Staging", "Production", "Archived"]

    def __init__(self, tracking_uri: str = "sqlite:///mlflow.db"):
        if MLFLOW_AVAILABLE:
            mlflow.set_tracking_uri(tracking_uri)
            self.client = MlflowClient()
        else:
            self.client = None

    def register_model(self, model_name: str, source_run_id: str, metrics: Dict[str, float]) -> Optional[str]:
        if not MLFLOW_AVAILABLE:
            logger.info(f"[MLflow disabled] Would register model: {model_name}")
            return None
        try:
            model_version = mlflow.register_model(f"runs:/{source_run_id}/model", model_name)
            logger.info(f"Registered {model_name} v{model_version.version}")
            return model_version.version
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            return None

    def promote_to_staging(self, model_name: str, version: str) -> bool:
        return self._transition(model_name, version, "Staging")

    def promote_to_production(self, model_name: str, version: str) -> bool:
        return self._transition(model_name, version, "Production")

    def _transition(self, model_name: str, version: str, stage: str) -> bool:
        if not MLFLOW_AVAILABLE or self.client is None:
            logger.info(f"[MLflow disabled] Would promote {model_name} v{version} to {stage}")
            return False
        try:
            self.client.transition_model_version_stage(
                name=model_name, version=version, stage=stage
            )
            logger.info(f"Promoted {model_name} v{version} to {stage}")
            return True
        except Exception as e:
            logger.error(f"Promotion failed: {e}")
            return False

    def get_production_model(self, model_name: str) -> Optional[str]:
        if not MLFLOW_AVAILABLE or self.client is None:
            return None
        versions = self.client.get_latest_versions(model_name, stages=["Production"])
        if versions:
            return versions[0].version
        return None
