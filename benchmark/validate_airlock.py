import json
import time
from pathlib import Path
from typing import List, Dict, Any
from sovereign_ai.verify.evaluator import SovereignEvaluator
from sovereign_ai.verify.config import Config

class AirlockValidator:
    """
    Automated Validation Suite for the Sovereign Airlock.
    Calculates statistical reliability scores (Precision, Recall, F1).
    """
    
    def __init__(self, dataset_path: str, threshold: float = 0.85):
        self.dataset_path = Path(dataset_path)
        self.threshold = threshold
        self.evaluator = SovereignEvaluator(config=Config(grounding_threshold=threshold))
        
    def run_validation(self, results: List[Dict[str, Any]], quiet: bool = False):
        tp, fp, tn, fn = 0, 0, 0, 0
        
        for item in results:
            eval_result = self.evaluator.evaluate(
                item["query"], item["context"], item["answer"]
            )
            
            score = eval_result["grounding_score"]
            actual_label = "grounded" if score >= self.threshold else "hallucination"
            expected_label = item["label"]
            
            if expected_label == "hallucination":
                if actual_label == "hallucination":
                    tp += 1
                else:
                    fn += 1
            else: # grounded
                if actual_label == "grounded":
                    tn += 1
                else:
                    fp += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = (tp + tn) / len(results)
        
        return {
            "threshold": self.threshold,
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4)
        }

def calibrate_thresholds(dataset_path: str):
    print("--- THRESHOLD CALIBRATION SWEEP (OPTIMIZED) ---")
    
    # Load dataset once
    results = []
    with open(dataset_path, "r") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    
    # Load model once
    validator = AirlockValidator(dataset_path, threshold=0.5)
    
    print(f"{'TYPE':<20} | {'EXPECTED':<15} | {'SCORE':<10}")
    print("-" * 50)
    for item in results:
        eval_result = validator.evaluator.evaluate(
            item["query"], item["context"], item["answer"]
        )
        print(f"{item['type']:<20} | {item['label']:<15} | {eval_result['grounding_score']:.4f}")
    
    sweep_results = []
    for t in range(5, 100, 5):
        threshold = t / 100.0
        validator.threshold = threshold  # Update threshold without reloading
        metrics = validator.run_validation(results, quiet=True)
        sweep_results.append(metrics)
        print(f"T={threshold:.2f} | Recall: {metrics['recall']:.2f} | Precision: {metrics['precision']:.2f} | F1: {metrics['f1_score']:.2f}")

    # Optimal: Highest threshold where recall == 1.0
    valid_candidates = [m for m in sweep_results if m["recall"] >= 1.0]
    if not valid_candidates:
        valid_candidates = sweep_results
        
    optimal = max(valid_candidates, key=lambda x: x["threshold"])
    
    print("\n--- OPTIMAL CALIBRATION FOUND ---")
    print(f"Recommended Threshold: {optimal['threshold']:.2f}")
    print(f"Safety Constraint (Recall): {optimal['recall']*100:.1f}%")
    print(f"Efficiency (Precision): {optimal['precision']*100:.1f}%")
    
    with open("benchmark/calibration_results.json", "w") as f:
        json.dump(sweep_results, f, indent=2)
    
    return optimal["threshold"]

if __name__ == "__main__":
    dataset = "tests/adversarial/adversarial_dataset.jsonl"
    calibrate_thresholds(dataset)
