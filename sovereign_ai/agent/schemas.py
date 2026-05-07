from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


from pydantic import BaseModel, Field, ConfigDict


class SovereignError(Exception):
    """Base error for the Sovereign Agent."""
    pass


class SecurityHalt(SovereignError):
    """Raised when the circuit breaker is triggered."""
    pass


class VerifyFailSignal(SovereignError):
    """Raised when the NLI Gate blocks an action with an out-of-band signal."""
    def __init__(
        self, 
        failure_type: str, 
        action_id: str, 
        retry_count: int,
        signed_failure_hash: str
    ):
        self.failure_type = failure_type
        self.action_id = action_id
        self.retry_count = retry_count
        self.signed_failure_hash = signed_failure_hash
        super().__init__(f"Verification failed [{action_id}]: {failure_type}")


from ..common.schemas import SigningAlgorithm, RecordStatus


class AgentState(BaseModel):
    """External state management for agent sessions to prevent session bleed."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: Optional[str] = None
    retry_count: int = 0
    principal_id: str = "anonymous"
    tenant_id: str = "default"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseAuditRecord(BaseModel):
    """Base schema for all forensic audit records."""
    model_config = ConfigDict(populate_by_name=True)

    action_id: str
    session_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class IntentRecord(BaseAuditRecord):
    """Signed record of the agent's intent before verification or execution."""
    tool_name: str
    arguments: str  # Canonical JSON string
    abac_result: RecordStatus
    risk_level: str = "medium"


class VerificationRecord(BaseAuditRecord):
    """Signed record of the NLI verification gate outcome."""
    nli_score: float
    status: RecordStatus  # PASS | FAIL
    failure_type: Optional[str] = None
    grounding_score: float
    faithfulness_score: float


class ObservationRecord(BaseAuditRecord):
    """Signed record of the tool execution outcome."""
    status: RecordStatus  # SUCCESS | EXEC_ERROR
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
