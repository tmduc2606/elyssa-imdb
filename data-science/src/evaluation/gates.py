import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

QUALITY_GATES = {
    "G1_rating_rmse": {"metric": "test_rmse", "threshold": 0.55, "op": "<="},
    "G2_genre_macro_f1": {"metric": "test_macro_f1", "threshold": 0.60, "op": ">"},
    "G3_temporal_generalization": {"metric": "val_test_delta", "threshold": 0.10, "op": "<"},
    "G4_mlflow_naming": {"metric": "naming_compliant", "threshold": True, "op": "=="},
    "G5_inference_latency": {"metric": "p95_latency_ms", "threshold": 100, "op": "<"},
    "G6_artifacts_exist": {"metric": "all_artifacts_present", "threshold": True, "op": "=="},
}

FEATURE_AUDIT_MAX_SINGLE_IMPORTANCE = 0.80


class QualityGateEvaluator:
    def evaluate(self, metrics: Dict[str, Any]) -> Dict[str, dict]:
        results = {}
        for gate_name, gate_config in QUALITY_GATES.items():
            metric_value = metrics.get(gate_config["metric"])
            threshold = gate_config["threshold"]
            op = gate_config["op"]

            if metric_value is None:
                results[gate_name] = {"pass": False, "reason": "Metric not found"}
                continue

            passed = self._compare(metric_value, threshold, op)
            results[gate_name] = {
                "pass": passed,
                "value": metric_value,
                "threshold": threshold,
                "op": op,
            }
            status = "PASS" if passed else "FAIL"
            logger.info(f"  {gate_name}: {metric_value} {op} {threshold} -> {status}")

        return results

    def all_passed(self, results: Dict[str, dict]) -> bool:
        return all(r["pass"] for r in results.values())

    @staticmethod
    def _compare(value, threshold, op) -> bool:
        ops = {
            "<": lambda a, b: a < b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            ">=": lambda a, b: a >= b,
            "==": lambda a, b: a == b,
        }
        return ops[op](value, threshold)


def evaluate_feature_audit(
    importances: Dict[str, float],
    max_single_importance: float = FEATURE_AUDIT_MAX_SINGLE_IMPORTANCE,
) -> Dict[str, dict]:
    """Gate G7: flag any single feature dominating the model (leakage audit).

    A normalized importance above ``max_single_importance`` is treated as a
    probable target leak (e.g. ``avg_rating_genre_year`` at ~0.91).
    """
    total = sum(importances.values()) or 1.0
    results = {}
    for feature, raw_importance in importances.items():
        norm = raw_importance / total
        results[feature] = {
            "importance": norm,
            "pass": norm <= max_single_importance,
        }
    return results


def feature_audit_passed(results: Dict[str, dict]) -> bool:
    return all(r["pass"] for r in results.values())
