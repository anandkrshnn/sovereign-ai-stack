"""Fail-closed consequence and tool policy hooks."""

from abc import ABC, abstractmethod
from collections.abc import Mapping

from .models import PolicyDecision, Step, Task, ToolCall

_CONSEQUENCES = {"read": 0, "write": 1, "destructive": 2}


def is_known_consequence(consequence: str) -> bool:
    """Whether a value belongs to the host consequence classification."""
    return isinstance(consequence, str) and consequence in _CONSEQUENCES


def consequence_requires_journal(consequence: str) -> bool:
    """Whether the existing host classification describes a remote mutation."""
    return (
        isinstance(consequence, str)
        and consequence in _CONSEQUENCES
        and _CONSEQUENCES[consequence] >= _CONSEQUENCES["write"]
    )


def strongest_consequence(*consequences: str) -> str:
    """Combine already validated consequences using the host's existing ordering."""
    return max(consequences, key=_CONSEQUENCES.__getitem__)


class Policy(ABC):
    @abstractmethod
    def decide(self, task: Task, tool_call: ToolCall) -> PolicyDecision:
        """Return a decision before a tool is invoked."""

    def decide_step(self, task: Task, step: Step) -> PolicyDecision:
        """Preserve legacy policy hooks while enforcing the host's step classification."""
        decision = self.decide(task, step.tool_call)
        if not decision.allowed:
            return decision
        classified = decision.consequence or step.consequence
        if step.consequence not in _CONSEQUENCES or classified not in _CONSEQUENCES:
            return PolicyDecision(allowed=False, reason="unknown_host_consequence")
        classified = max((classified, step.consequence), key=_CONSEQUENCES.__getitem__)
        return decision.model_copy(
            update={
                "consequence": classified,
                "requires_approval": decision.requires_approval or classified != "read",
            }
        )


class AllowListPolicy(Policy):
    def __init__(
        self,
        allowed_tools: set[str],
        approval_consequences: set[str] | None = None,
        tool_consequences: Mapping[str, str] | None = None,
    ):
        self.allowed_tools = frozenset(allowed_tools)
        self.approval_consequences = frozenset(
            {"write", "destructive"} | set(approval_consequences or ())
        )
        self.tool_consequences = dict(tool_consequences or {})

    def decide(self, task: Task, tool_call: ToolCall) -> PolicyDecision:
        """Standalone decisions require server-configured metadata, never a caller's read claim."""
        consequence = self.tool_consequences.get(tool_call.tool_name)
        if consequence is None:
            return PolicyDecision(allowed=False, reason="trusted_consequence_not_configured")
        return self._decide(tool_call, consequence)

    def decide_step(self, task: Task, step: Step) -> PolicyDecision:
        # Step.consequence is assigned by the authenticated host, not deserialized
        # from untrusted submissions. A tool registry may only strengthen that gate.
        registry = self.tool_consequences.get(step.tool_call.tool_name, step.consequence)
        if registry not in _CONSEQUENCES or step.consequence not in _CONSEQUENCES:
            return PolicyDecision(allowed=False, reason="unknown_host_consequence")
        consequence = max((registry, step.consequence), key=_CONSEQUENCES.__getitem__)
        return self._decide(step.tool_call, consequence)

    def _decide(self, tool_call: ToolCall, consequence: str) -> PolicyDecision:
        if tool_call.tool_name not in self.allowed_tools:
            return PolicyDecision(allowed=False, reason="tool_not_allowlisted")
        if consequence not in _CONSEQUENCES:
            return PolicyDecision(allowed=False, reason="unknown_host_consequence")
        # Retain conservative legacy escalation, but a caller's "read" value
        # or omission can NEVER downgrade trusted metadata.
        requested = tool_call.arguments.get("consequence")
        if isinstance(requested, str) and requested in {"write", "destructive"}:
            consequence = max((requested, consequence), key=_CONSEQUENCES.__getitem__)
        if consequence in self.approval_consequences or (
            isinstance(requested, str) and requested in {"write", "destructive"}
        ):
            return PolicyDecision(
                allowed=True,
                requires_approval=True,
                reason="approval_required_for_consequence",
                consequence=consequence,
                policy_version="2",
            )
        return PolicyDecision(
            allowed=True,
            reason="allowlisted_read_only_tool",
            consequence=consequence,
            policy_version="2",
        )
