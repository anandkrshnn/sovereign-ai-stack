"""Provider-neutral tool adapter contracts; external systems remain optional."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class AdapterError(RuntimeError):
    """A tool adapter failed without producing a trusted result."""


class ToolAdapter(ABC):
    name: str

    @abstractmethod
    def execute(self, arguments: Mapping[str, Any], timeout_seconds: float) -> dict[str, Any]:
        """Execute one bounded call and return JSON-compatible output."""


class HttpToolAdapter(ToolAdapter):
    name = "http"

    def __init__(self, client: Any):
        self.client = client

    def execute(self, arguments: Mapping[str, Any], timeout_seconds: float) -> dict[str, Any]:
        response = self.client.request(
            str(arguments["method"]),
            str(arguments["url"]),
            timeout=timeout_seconds,
            json=arguments.get("json"),
        )
        return {"status_code": response.status_code, "body": response.text}


class CliToolAdapter(ToolAdapter):
    name = "cli"

    def __init__(self, runner: Any):
        self.runner = runner

    def execute(self, arguments: Mapping[str, Any], timeout_seconds: float) -> dict[str, Any]:
        completed = self.runner(
            list(arguments["argv"]),
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode:
            raise AdapterError(f"CLI exited with status {completed.returncode}")
        return {"returncode": completed.returncode, "stdout": completed.stdout}


class N8nWebhookAdapter(HttpToolAdapter):
    """Contract adapter for an externally hosted n8n webhook/workflow."""

    name = "n8n_webhook"


class McpToolAdapter(ToolAdapter):
    """Provider-neutral MCP client adapter; the MCP client is injected by the host."""

    name = "mcp"

    def __init__(self, client: Any):
        self.client = client

    def execute(self, arguments: Mapping[str, Any], timeout_seconds: float) -> dict[str, Any]:
        return dict(
            self.client.call_tool(
                str(arguments["tool"]), dict(arguments.get("input", {})), timeout=timeout_seconds
            )
        )
