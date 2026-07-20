import numpy as np
import pandas as pd
from src.evaluation.metrics import (
    evaluate_multilabel,
    reg_metrics,
    precision_recall_at_k,
)
from src.evaluation.qerror import q_error, add_noise
from src.evaluation.gates import QualityGateEvaluator


def test_evaluate_multilabel():
    y_true = np.array([[1, 0], [0, 1], [1, 1], [0, 0]])
    y_pred = np.array([[0.9, 0.1], [0.2, 0.8], [0.7, 0.6], [0.3, 0.2]])
    result = evaluate_multilabel(y_true, y_pred, threshold=0.5)
    assert "macro_f1" in result
    assert "micro_f1" in result
    assert "hamming_loss" in result
    assert 0 <= result["macro_f1"] <= 1.0


def test_reg_metrics():
    y_true = np.array([7.0, 8.0, 6.0, 9.0])
    y_pred = np.array([7.1, 7.9, 6.2, 8.8])
    result = reg_metrics(y_true, y_pred, prefix="test")
    assert "test_rmse" in result
    assert "test_mae" in result
    assert "test_r2" in result
    assert result["test_rmse"] >= 0


def test_reg_metrics_perfect():
    y_true = np.array([7.0, 8.0, 6.0])
    y_pred = np.array([7.0, 8.0, 6.0])
    result = reg_metrics(y_true, y_pred, prefix="test")
    assert result["test_rmse"] == 0.0
    assert result["test_r2"] == 1.0


def test_q_error_basic():
    y_true = np.array([7.0, 8.0, 6.0])
    y_pred = np.array([7.0, 8.0, 6.0])
    result = q_error(y_true, y_pred)
    assert result["Q_error_p50"] == 1.0


def test_q_error_percentiles():
    y_true = np.array([10.0, 1.0, 5.0])
    y_pred = np.array([9.0, 2.0, 5.0])
    result = q_error(y_true, y_pred, percentiles=[50, 90])
    assert "Q_error_p50" in result
    assert "Q_error_p90" in result
    assert result["Q_error_p50"] >= 1.0


def test_precision_recall_at_k():
    df = pd.DataFrame({
        "user_idx": [0, 0, 0, 1, 1, 1],
        "item_idx": [0, 1, 2, 3, 4, 5],
        "rating": [8.0, 5.0, 9.0, 6.0, 7.0, 8.0],
    })
    scores = np.array([0.9, 0.3, 0.8, 0.4, 0.7, 0.6])
    prec, rec = precision_recall_at_k(df, scores, k=2, threshold=7.0)
    assert 0 <= prec <= 1
    assert 0 <= rec <= 1


def test_add_noise():
    X = np.ones((10, 5))
    feature_std = np.ones(5)
    X_noisy = add_noise(X, noise_level=0.1, feature_std=feature_std)
    assert X_noisy.shape == X.shape
    assert not np.allclose(X_noisy, X)


def test_quality_gate_evaluator():
    evaluator = QualityGateEvaluator()
    metrics = {"test_rmse": 0.5, "test_macro_f1": 0.65}
    results = evaluator.evaluate(metrics)
    assert "G1_rating_rmse" in results
    assert "G2_genre_macro_f1" in results


def test_quality_gate_all_passed():
    evaluator = QualityGateEvaluator()
    metrics = {"test_rmse": 0.3, "test_macro_f1": 0.7}
    results = evaluator.evaluate(metrics)
    assert evaluator.all_passed(results)


def test_quality_gate_some_failed():
    evaluator = QualityGateEvaluator()
    metrics = {"test_rmse": 1.0, "test_macro_f1": 0.3}
    results = evaluator.evaluate(metrics)
    assert not evaluator.all_passed(results)


def test_quality_gate_missing_metric():
    evaluator = QualityGateEvaluator()
    metrics = {}
    results = evaluator.evaluate(metrics)
    assert not evaluator.all_passed(results)
