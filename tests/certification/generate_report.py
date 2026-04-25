import json
import os
import sys
from pathlib import Path
from datetime import datetime
from .schema import SovereignCertificationReport, CertificationMetric, TestResult

def generate_report(results_path: str = "tests/certification/results.json", output_path: str = "CERTIFICATION.md"):
    """
    Generate the formal Sovereign AI Certification Report from structured test result evidence.
    """
    if not os.path.exists(results_path):
        print(f"Error: Results file not found at {results_path}. Run 'pytest --sovereign-cert' first.")
        sys.exit(1)
        
    with open(results_path, "r") as f:
        raw_results = json.load(f)
        
    metrics = []
    for r in raw_results:
        metrics.append(CertificationMetric(
            test_id=r["test_id"],
            node_id=r["node_id"],
            result=TestResult.PASS if r["outcome"] == "passed" else TestResult.FAIL,
            duration=r["duration"],
            error=r["error"]
        ))
        
    report = SovereignCertificationReport(metrics=metrics)
    report.calculate_scores()
    
    # Generate Markdown
    md = f"""# 🛡️ Sovereign Chaos Certification Report

**local-rag version**: {report.local_rag_version}  
**Timestamp**: {datetime.fromtimestamp(report.timestamp).isoformat()}  
**Philosophy**: "Shortcuts may support operations; only full verification supports claims."

## 🎯 Overall Certification: {"✅ CERTIFIED" if report.certified else "❌ NOT CERTIFIED"}

| Category | Score | Threshold | Status |
|----------|-------|-----------|--------|
| Tenant Isolation | {report.isolation_score:.1f}% | 100.0% | {"✅ PASS" if report.isolation_score == 100.0 else "❌ FAIL"} |
| Policy Fail-Closed | {report.policy_score:.1f}% | 95.0% | {"✅ PASS" if report.policy_score >= 95.0 else "❌ FAIL"} |
| Cache Isolation | {report.cache_score:.1f}% | 95.0% | {"✅ PASS" if report.cache_score >= 95.0 else "❌ FAIL"} |
| Audit Integrity | {report.forensic_score:.1f}% | 100.0% | {"✅ PASS" if report.forensic_score == 100.0 else "❌ FAIL"} |

## 🔍 Detailed Forensic Results

"""
    
    # Group by category
    categories = {"ISO": "Isolation", "POL": "Policy", "CAC": "Cache", "AUD": "Forensics"}
    for prefix, cat_name in categories.items():
        md += f"### {cat_name} Tests\n"
        cat_metrics = [m for m in metrics if m.test_id.startswith(prefix)]
        if not cat_metrics:
            md += "_No tests run in this category._\n\n"
            continue
            
        for m in cat_metrics:
            status_icon = "✅" if m.result == TestResult.PASS else "❌"
            md += f"- {status_icon} **{m.test_id}**: {m.result.value.upper()} ({m.duration:.3f}s)\n"
            if m.error:
                md += f"  - _Error_: {m.error.splitlines()[0][:100]}...\n"
        md += "\n"

    md += """
## 🔐 Verification & Attestation
Report generated via `tests/certification/generate_report.py`.  
Evidence stored in `tests/certification/results.json`.

---
_Sovereign AI Stack Gaia Release_
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)
    
    print(f"Certification report generated: {output_path}")
    if report.certified:
        print("✅ STACK CERTIFIED")
    else:
        print("❌ CERTIFICATION FAILED")

if __name__ == "__main__":
    generate_report()
