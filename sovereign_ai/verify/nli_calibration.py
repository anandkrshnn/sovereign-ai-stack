import logging
import math
from typing import List, Tuple

import numpy as np
from scipy.optimize import minimize

logger = logging.getLogger("sovereign_ai.verify.nli_calibration")


class PlattCalibrator:
    """
    Implements Platt Scaling (logistic calibration) for NLI probabilities.
    Maps uncalibrated model outputs to well-calibrated confidence scores.

    Formula: P(y=1|x) = 1 / (1 + exp(A * f(x) + B))
    """

    def __init__(self, A: float = -1.0, B: float = 0.0):
        self.A = A
        self.B = B

    def calibrate(self, probability: float) -> float:
        eps = 1e-7
        p = max(eps, min(1.0 - eps, probability))
        logit = math.log(p / (1.0 - p))

        # Logistic function
        calibrated_p = 1.0 / (1.0 + math.exp(self.A * logit + self.B))
        return calibrated_p

    def predict(self, probability: float) -> float:
        return self.calibrate(probability)

    def calibrate_batch(self, probabilities: List[float]) -> List[float]:
        return [self.calibrate(p) for p in probabilities]

    def fit(self, probabilities: List[float], labels: List[int]):
        """
        Learns parameters A and B from data using maximum likelihood.
        labels: 1 for entailment, 0 for contradiction/neutral.
        """
        probs = np.array(probabilities)
        y = np.array(labels)

        # Small epsilon to avoid log(0)
        eps = 1e-7
        probs = np.clip(probs, eps, 1 - eps)
        logits = np.log(probs / (1 - probs))

        def loss_fn(params):
            A, B = params
            # P(y=1) = 1 / (1 + exp(A*logit + B))
            p_cal = 1.0 / (1.0 + np.exp(A * logits + B))
            p_cal = np.clip(p_cal, eps, 1 - eps)
            # Binary Cross Entropy
            loss = -np.mean(y * np.log(p_cal) + (1 - y) * np.log(1 - p_cal))
            return loss

        # Initial guess
        res = minimize(loss_fn, [self.A, self.B], method="L-BFGS-B")
        if res.success:
            self.A, self.B = res.x
            logger.info(f"Calibration successful: A={self.A:.4f}, B={self.B:.4f}")
        else:
            logger.error(f"Calibration failed: {res.message}")


def get_calibrator(model_name: str) -> PlattCalibrator:
    if "deberta-v3-base" in model_name.lower():
        return PlattCalibrator(A=-1.25, B=0.05)
    elif "deberta-v3-small" in model_name.lower():
        return PlattCalibrator(A=-1.1, B=0.1)

    return PlattCalibrator()

