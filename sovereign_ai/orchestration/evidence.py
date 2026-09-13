"""Bridge orchestration evidence into the existing signed audit chain."""

from typing import Any

from ..common.audit import SignedAuditChain
from .models import EvidenceBundle


class AuditEvidenceRecorder:
    """Record canonical evidence as a signed audit event."""

    def __init__(self, chain: SignedAuditChain):
        self.chain = chain

    def __call__(self, bundle: EvidenceBundle) -> None:
        self.chain.log_event(
            component="orchestrator",
            action="TOOL_EVIDENCE",
            principal="agent-runtime",
            event_data=bundle.model_dump(mode="json"),
        )
