"""SHAP explainability for tree-based models."""
import numpy as np
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("SHAP not installed; explainability disabled")


def explain_model(model, X_sample: np.ndarray, output_dir: Optional[Path] = None) -> dict:
    if not SHAP_AVAILABLE:
        return {"error": "SHAP not installed"}
    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_sample)
        if output_dir:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            shap.summary_plot(shap_values, X_sample, show=False)
            plt.savefig(output_dir / "shap_summary.png", bbox_inches="tight")
            plt.close()
        return {"shape": list(shap_values.shape) if hasattr(shap_values, "shape") else "scalar"}
    except Exception as e:
        logger.warning(f"SHAP explainer failed: {e}")
        return {"error": str(e)}
