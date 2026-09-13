"""Fail-closed consequence and tool policy hooks."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from .models import PolicyDecision, Task, ToolCall


class Policy(ABC):
    @abstractmethod
    def decide(self, task: Task, tool_call: ToolCall) -> PolicyDecision:
        """Return a decision before a tool is invoked."""


class AllowListPolicy(Policy):
    def __init__(self, allowed_tools: set[str], approval_consequences: set[str] | None = None):
        self.allowed_tools = frozenset(allowed_tools)
        self.approval_consequences = frozenset(approval_consequences or {"write", "destructive"})

    def decide(self, task: Task, tool_call: ToolCall) -> PolicyDecision:
        consequence = str(tool_call.arguments.get("consequence", "read"))
        if tool_call.tool_name not in self.allowed_tools:
            return PolicyDecision(allowed=False, reason="tool_not_allowlisted")
        if consequence in self.approval_consequences:
            return PolicyDecision(
                allowed=True, requires_approval=True, reason="approval_required_for_consequence"
            )
        return PolicyDecision(allowed=True, reason="allowlisted_read_only_tool")
