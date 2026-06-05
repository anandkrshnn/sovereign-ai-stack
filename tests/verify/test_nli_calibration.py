import pytest
import numpy as np
from sklearn.metrics import roc_auc_score, brier_score_loss
from sovereign_ai.verify.nli_calibration import PlattCalibrator

def test_platt_calibration_improves_reliability():
    np.random.seed(42)
    
    # Simulate uncalibrated outputs (confident but often wrong)
    # 0 = hallucination, 1 = true entailment
    y_true = np.array([1]*500 + [0]*500)
    
    # Overly confident distributions
    probs_true = np.random.normal(loc=0.9, scale=0.1, size=500)
    probs_false = np.random.normal(loc=0.8, scale=0.2, size=500) 
    raw_probs = np.clip(np.concatenate([probs_true, probs_false]), 0.01, 0.99)

    # Initial metrics
    pre_auc = roc_auc_score(y_true, raw_probs)
    pre_brier = brier_score_loss(y_true, raw_probs)

    # Fit calibration
    calibrator = PlattCalibrator()
    calibrator.fit(raw_probs.tolist(), y_true.tolist())
    calibrated_probs = calibrator.calibrate_batch(raw_probs.tolist())

    # Post metrics
    post_auc = roc_auc_score(y_true, calibrated_probs)
    post_brier = brier_score_loss(y_true, calibrated_probs)

    # AUC should be maintained or improved, Brier score must decrease (lower is better)
    assert post_auc >= pre_auc - 0.01, "Calibration severely degraded ROC AUC."
    assert post_brier < pre_brier, "Calibration failed to improve the Brier score."
