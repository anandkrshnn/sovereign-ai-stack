"""Versioned orchestration contracts and state values."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RunState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPENSATING = "compensating"


class ToolCallState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    TIMED_OUT = "timed_out"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Agent(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=200)
    version: str = "1"
    capabilities: list[str] = Field(default_factory=list)


class Task(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(min_length=1)
    agent_id: UUID
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=256)
    created_at: datetime = Field(default_factory=_now)


class ToolCall(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    tool_name: str = Field(min_length=1, max_length=200)
    arguments: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1, max_length=256)
    timeout_seconds: float = Field(default=30.0, gt=0, le=3600)
    max_attempts: int = Field(default=1, ge=1, le=10)
    state: ToolCallState = ToolCallState.PENDING


class Step(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    tool_call: ToolCall
    consequence: str = "read"


class Run(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    state: RunState = RunState.CREATED
    step_index: int = Field(default=0, ge=0)
    attempts: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    error: str | None = None


class PolicyDecision(ContractModel):
    allowed: bool
    reason: str = Field(min_length=1)
    requires_approval: bool = False
    policy_version: str = "1"


class VerificationResult(ContractModel):
    passed: bool
    score: float | None = Field(default=None, ge=0, le=1)
    reason: str = Field(min_length=1)


class Approval(ContractModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    step_id: UUID
    requested_at: datetime = Field(default_factory=_now)
    approved_by: str | None = None
    approved_at: datetime | None = None


class ArtifactRef(ContractModel):
    uri: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str = "application/octet-stream"


class EvidenceBundle(ContractModel):
    version: str = "1"
    run_id: UUID
    step_id: UUID
    tool_call_id: UUID
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy: PolicyDecision
    verification: VerificationResult
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    recorded_at: datetime = Field(default_factory=_now)
    record_hash: str | None = None
