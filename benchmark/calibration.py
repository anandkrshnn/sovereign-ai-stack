import numpy as np
import matplotlib.pyplot as plt
import json
from pathlib import Path

def calibrate_threshold(scores_labels_file: str):
    """
    Analyzes NLI scores against ground truth to find the optimal 'Airlock' threshold.
    This provides statistical rigor instead of using an arbitrary 0.85.
    """
    with open(scores_labels_file, "r") as f:
        data = json.load(f)
    
    scores = np.array([d["score"] for d in data])
    labels = np.array([1 if d["label"] == "entailment" else 0 for d in data])
    
    thresholds = np.linspace(0, 1, 100)
    precision = []
    recall = []
    f1 = []
    
    for t in thresholds:
        preds = (scores >= t).astype(int)
        tp = np.sum((preds == 1) & (labels == 1))
        fp = np.sum((preds == 1) & (labels == 0))
        fn = np.sum((preds == 0) & (labels == 1))
        
        p = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        
        precision.append(p)
        recall.append(r)
        f1.append(f)
    
    # Find optimal F1
    idx = np.argmax(f1)
    best_t = thresholds[idx]
    
    print(f"--- Calibration Report ---")
    print(f"Optimal Threshold (Max F1): {best_t:.4f}")
    print(f"Precision at Best T: {precision[idx]:.4f}")
    print(f"Recall at Best T: {recall[idx]:.4f}")
    print(f"F1 Score: {f1[idx]:.4f}")
    
    # In a real environment, we would save this plot
    # plt.plot(thresholds, precision, label="Precision")
    # plt.plot(thresholds, recall, label="Recall")
    # plt.axvline(best_t, color='r', linestyle='--', label=f"Optimum ({best_t:.2f})")
    # plt.legend()
    # plt.savefig("benchmark/calibration_curve.png")
    
    return best_t

if __name__ == "__main__":
    # Mock data for demonstration of methodology
    mock_data = [
        {"score": 0.95, "label": "entailment"},
        {"score": 0.88, "label": "entailment"},
        {"score": 0.12, "label": "neutral"},
        {"score": 0.05, "label": "contradiction"},
        {"score": 0.82, "label": "entailment"},
        {"score": 0.45, "label": "neutral"},
    ]
    with open("benchmark/calibration_data.json", "w") as f:
        json.dump(mock_data, f)
    
    calibrate_threshold("benchmark/calibration_data.json")
