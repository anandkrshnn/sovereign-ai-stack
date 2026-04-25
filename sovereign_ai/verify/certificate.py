import json
import hashlib
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict

@dataclass
class ComplianceCertificate:
    query: str
    answer: str
    grounding_score: float
    faithfulness_score: float
    overall_score: float
    passed: bool
    timestamp: str
    judge_model: str
    certificate_id: str

    @classmethod
    def from_evaluation(cls, query: str, answer: str, eval_result: Dict, judge_model: str = "Qwen2.5-1.5B"):
        cert_id = hashlib.sha256(
            f"{query}{answer}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        return cls(
            query=query,
            answer=answer[:500] + "..." if len(answer) > 500 else answer,
            grounding_score=eval_result["grounding_score"],
            faithfulness_score=eval_result["faithfulness_score"],
            overall_score=eval_result["overall_score"],
            passed=eval_result["passed"],
            timestamp=datetime.now().isoformat(),
            judge_model=judge_model,
            certificate_id=cert_id,
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
