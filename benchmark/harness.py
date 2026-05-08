import json
import asyncio
import time
import argparse
from pathlib import Path
from sovereign_ai.common.airlock import NLIEntailmentAirlock

async def run_benchmark(dataset_path: str, threshold: float = 0.85):
    with open(dataset_path, "r") as f:
        samples = json.load(f)
    
    airlock = NLIEntailmentAirlock(threshold=threshold)
    results = []
    
    print(f"🚀 Starting Sovereign Benchmark Harness")
    print(f"📊 Dataset: {dataset_path} ({len(samples)} samples)")
    print(f"🛡️  Airlock Threshold: {threshold}")
    print("-" * 50)
    
    correct_blocks = 0
    total_adversarial = 0
    
    for sample in samples:
        query = sample["query"]
        grounding = sample["expected_grounding"]
        claim = sample["hallucinated_claim"]
        
        start_time = time.perf_counter()
        # Verify the hallucinated claim against the correct grounding context
        res = await airlock.verify(claim, [grounding])
        duration = time.perf_counter() - start_time
        
        passed_filter = res.is_safe
        
        is_correct = False
        if sample.get("is_adversarial"):
            total_adversarial += 1
            # If it's adversarial (hallucinated), it SHOULD be blocked (is_safe=False)
            if not passed_filter:
                correct_blocks += 1
                is_correct = True
        
        print(f"[{sample['id']}] {'PASS' if passed_filter else 'BLOCK'} | Score: {res.score:.4f} | Time: {duration*1000:.1f}ms | {'✅' if is_correct else '❌'}")
        
        results.append({
            "id": sample["id"],
            "score": res.score,
            "blocked": not passed_filter,
            "latency_ms": duration * 1000,
            "correct": is_correct
        })
    
    accuracy = (correct_blocks / total_adversarial) * 100 if total_adversarial > 0 else 0
    
    print("-" * 50)
    print(f"✅ Benchmark Complete")
    print(f"📈 Hallucination Blocking Accuracy: {accuracy:.1f}% ({correct_blocks}/{total_adversarial})")
    
    return {
        "accuracy": accuracy,
        "results": results,
        "config": {"threshold": threshold, "dataset": dataset_path}
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="benchmark/dataset.json")
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--output", default="benchmark/report.json")
    args = parser.parse_args()
    
    report = asyncio.run(run_benchmark(args.dataset, args.threshold))
    
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    print(f"📝 Report saved to {args.output}")
