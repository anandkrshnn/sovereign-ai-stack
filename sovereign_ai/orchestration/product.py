"""Product-facing write admission for the experimental orchestration layer."""

import logging
from collections.abc import Callable, Mapping
from typing import Any

from .adapters import ToolAdapter
from .journal import SQLiteExecutionJournal
from .models import EvidenceBundle, Step, Task, VerificationResult
from .policy import (
    AllowListPolicy,
    Policy,
    consequence_requires_journal,
    is_known_consequence,
)
from .runner import DeterministicOrchestrator, OrchestratorEvent

logger = logging.getLogger(__name__)


class ProductOrchestrator(DeterministicOrchestrator):
    """Reject product writes unless a durable execution journal is configured.

    Every allowed tool must carry an explicit trusted consequence in the
    existing ``AllowListPolicy`` registry. Read-only tools may omit a journal.
    For legacy low-level tests and development, use ``VolatileOrchestrator``
    explicitly; this product-facing entry point has no volatile-mode option.
    """

    def __init__(
        self,
        adapters: Mapping[str, ToolAdapter],
        policy: AllowListPolicy,
        verify: Callable[[Task, Step, Mapping[str, Any]], VerificationResult] | None = None,
        record_evidence: Callable[[EvidenceBundle], None] | None = None,
        emit: Callable[[OrchestratorEvent], None] | None = None,
        approval_ttl_seconds: float = 300,
        journal: SQLiteExecutionJournal | None = None,
    ) -> None:
        if not isinstance(policy, AllowListPolicy):
            raise TypeError("product_orchestrator_requires_allow_list_policy")

        configured_tools = policy.allowed_tools
        consequence_registry = policy.tool_consequences
        unclassified = configured_tools.difference(consequence_registry)
        if unclassified:
            raise ValueError("trusted_consequence_not_configured")
        if any(not is_known_consequence(consequence_registry[tool]) for tool in configured_tools):
            raise ValueError("unknown_host_consequence")
        if journal is not None and not isinstance(journal, SQLiteExecutionJournal):
            raise TypeError("product_orchestrator_requires_sqlite_execution_journal")
        writes = any(
            consequence_requires_journal(consequence_registry[tool]) for tool in configured_tools
        )
        if writes and journal is None:
            raise ValueError("durable_journal_required_for_write")

        super().__init__(
            adapters=adapters,
            policy=policy,
            verify=verify,
            record_evidence=record_evidence,
            emit=emit,
            approval_ttl_seconds=approval_ttl_seconds,
            journal=journal,
            _require_durable_writes=True,
        )


class VolatileOrchestrator(DeterministicOrchestrator):
    """Explicit test/development-only alternative; never a product configuration."""

    def __init__(
        self,
        adapters: Mapping[str, ToolAdapter],
        policy: Policy,
        verify=None,
        record_evidence=None,
        emit=None,
        approval_ttl_seconds: float = 300,
    ) -> None:
        logger.warning(
            "VolatileOrchestrator is test/development only; product writes require "
            "ProductOrchestrator with SQLiteExecutionJournal"
        )
        super().__init__(
            adapters=adapters,
            policy=policy,
            verify=verify,
            record_evidence=record_evidence,
            emit=emit,
            approval_ttl_seconds=approval_ttl_seconds,
            journal=None,
            _require_durable_writes=False,
        )


__all__ = ["ProductOrchestrator", "VolatileOrchestrator"]
