import re
from typing import Dict
import logging

logger = logging.getLogger(__name__)

MLFLOW_METRIC_PATTERN = re.compile(r"^[a-zA-Z0-9_/. -]+$")


def validate_metric_name(name: str) -> bool:
    return bool(MLFLOW_METRIC_PATTERN.match(name))


def sanitize_metric_name(name: str) -> str:
    sanitized = name.replace("@", "_at_").replace("+", "_and_")
    if not validate_metric_name(sanitized):
        sanitized = re.sub(r"[^a-zA-Z0-9_/. -]", "_", sanitized)
    return sanitized


def sanitize_metrics_dict(metrics: Dict[str, float]) -> Dict[str, float]:
    return {sanitize_metric_name(k): v for k, v in metrics.items()}
