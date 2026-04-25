from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
import time

class TestResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"

class CertificationMetric(BaseModel):
    test_id: str
    node_id: str
    result: TestResult
    duration: float
    error: Optional[str] = None
    evidence_hash: Optional[str] = None

class SovereignCertificationReport(BaseModel):
    version: str = "1.0.0-GA"
    timestamp: float = Field(default_factory=time.time)
    local_rag_version: str = "1.0.0-GA"
    python_version: str = "3.10+"
    hardware_profile: Optional[str] = None
    
    # Category Scores
    isolation_score: float = 0.0
    policy_score: float = 0.0
    cache_score: float = 0.0
    forensic_score: float = 0.0
    
    certified: bool = False
    metrics: List[CertificationMetric] = []
    
    def calculate_scores(self):
        """Analyze metrics and update scores and certification status."""
        categories = {
            "ISO": [],
            "POL": [],
            "CAC": [],
            "AUD": []
        }
        
        for m in self.metrics:
            prefix = m.test_id.split("-")[0]
            if prefix in categories:
                categories[prefix].append(m.result == TestResult.PASS)
        
        def pct(results):
            return (sum(results) / len(results) * 100) if results else 0.0
            
        self.isolation_score = pct(categories["ISO"])
        self.policy_score = pct(categories["POL"])
        self.cache_score = pct(categories["CAC"])
        self.forensic_score = pct(categories["AUD"])
        
        # Hard Thresholds: 100% on Isolation & Forensic, 95%+ on others
        self.certified = (
            self.isolation_score == 100.0 and
            self.forensic_score == 100.0 and
            self.policy_score >= 95.0 and
            self.cache_score >= 95.0
        )
