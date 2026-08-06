from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest

from cascadeflow.context import KnowledgeSnapshot
from cascadeflow.integrations.mcp import create_mcp_server


class FakeFastMCP:
    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name = name
        self.kwargs = kwargs
        self.tools: dict[str, Any] = {}
        self.tool_metadata: dict[str, dict[str, Any]] = {}
        self.resources: dict[str, Any] = {}
        self.resource_metadata: dict[str, dict[str, Any]] = {}

    def tool(self, **kwargs: Any):
        def decorate(function):
            self.tools[function.__name__] = function
            self.tool_metadata[function.__name__] = kwargs
            return function

        return decorate

    def resource(self, uri: str, **kwargs: Any):
        def decorate(function):
            self.resources[uri] = function
            self.resource_metadata[uri] = kwargs
            return function

        return decorate


@dataclass
class FakeResult:
    content: str = "answer"
    model_used: str = "draft"
    cascaded: bool = False
    draft_accepted: bool = True
    routing_strategy: str = "cascade"
    total_cost: float = 0.001
    cost_saved: float = 0.009
    latency_ms: float = 12.0
    metadata: dict[str, Any] = field(default_factory=lambda: {"knowledge": {"identity": "docs:v2"}})


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run(self, query: str, **kwargs: Any) -> FakeResult:
        self.calls.append({"query": query, **kwargs})
        return FakeResult()


@pytest.mark.asyncio
async def test_mcp_tool_resolves_knowledge_server_side_and_returns_compact_trace() -> None:
    agent = FakeAgent()

    async def resolve(key: str, version: str | None) -> KnowledgeSnapshot:
        return KnowledgeSnapshot("private docs", key=key, version=version)

    with patch("cascadeflow.integrations.mcp._load_fastmcp", return_value=FakeFastMCP):
        server = create_mcp_server(agent, knowledge_resolver=resolve)

    response = await server.tools["cascadeflow_run"](
        "current question",
        knowledge_key="docs",
        knowledge_version="v2",
        conversation_context="Only the relevant prior fact.",
    )

    call = agent.calls[0]
    assert call["knowledge"].content == "private docs"
    assert call["knowledge"].identity == "docs:v2"
    assert call["messages"][-1] == {"role": "user", "content": "current question"}
    assert response["content"] == "answer"
    assert response["knowledge"] == {"identity": "docs:v2"}


@pytest.mark.asyncio
async def test_mcp_tool_requires_resolver_and_bounds_conversation_handoff() -> None:
    with patch("cascadeflow.integrations.mcp._load_fastmcp", return_value=FakeFastMCP):
        server = create_mcp_server(FakeAgent(), max_context_chars=5)

    tool = server.tools["cascadeflow_run"]
    with pytest.raises(ValueError, match="knowledge_resolver"):
        await tool("query", knowledge_key="docs")
    with pytest.raises(ValueError, match="concise relevant handoff"):
        await tool("query", conversation_context="too long")


def test_mcp_app_is_opt_in_and_uses_portable_ui_metadata() -> None:
    from cascadeflow.integrations.mcp_app import ROUTING_APP_MIME_TYPE, ROUTING_APP_URI

    with patch("cascadeflow.integrations.mcp._load_fastmcp", return_value=FakeFastMCP):
        tool_only = create_mcp_server(FakeAgent())
        with_ui = create_mcp_server(FakeAgent(), include_ui=True)

    assert tool_only.resources == {}
    assert tool_only.tool_metadata["cascadeflow_run"]["meta"] is None
    assert with_ui.tool_metadata["cascadeflow_run"]["meta"] == {
        "ui": {"resourceUri": ROUTING_APP_URI},
        "openai/outputTemplate": ROUTING_APP_URI,
    }
    assert with_ui.resource_metadata[ROUTING_APP_URI]["mime_type"] == ROUTING_APP_MIME_TYPE
    html = with_ui.resources[ROUTING_APP_URI]()
    assert "ui/initialize" in html
    assert "ui/notifications/tool-result" in html
    assert "http://" not in html
    assert "https://" not in html


def test_mcp_server_validates_and_forwards_http_settings() -> None:
    with patch("cascadeflow.integrations.mcp._load_fastmcp", return_value=FakeFastMCP):
        server = create_mcp_server(
            FakeAgent(), host="0.0.0.0", port=9000, streamable_http_path="/cascade"
        )

    assert server.kwargs["host"] == "0.0.0.0"
    assert server.kwargs["port"] == 9000
    assert server.kwargs["streamable_http_path"] == "/cascade"

    with pytest.raises(ValueError, match="host must be non-empty"):
        create_mcp_server(FakeAgent(), host=" ")
    with pytest.raises(ValueError, match="port must be between"):
        create_mcp_server(FakeAgent(), port=0)
    with pytest.raises(ValueError, match="must start with"):
        create_mcp_server(FakeAgent(), streamable_http_path="mcp")


@pytest.mark.asyncio
async def test_mcp_sdk_discovers_and_calls_cascadeflow_tool() -> None:
    pytest.importorskip("mcp")

    from cascadeflow.integrations.mcp_app import ROUTING_APP_MIME_TYPE, ROUTING_APP_URI
    from mcp.shared.memory import create_connected_server_and_client_session

    server = create_mcp_server(FakeAgent(), include_ui=True)
    async with create_connected_server_and_client_session(server) as client:
        tools = (await client.list_tools()).tools
        tool = next(item for item in tools if item.name == "cascadeflow_run")
        assert tool.title == "Run cascadeflow"
        assert tool.outputSchema["type"] == "object"
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.openWorldHint is True
        assert tool.meta["ui"]["resourceUri"] == ROUTING_APP_URI

        resources = (await client.list_resources()).resources
        resource = next(item for item in resources if str(item.uri) == ROUTING_APP_URI)
        assert resource.mimeType == ROUTING_APP_MIME_TYPE
        contents = (await client.read_resource(ROUTING_APP_URI)).contents
        assert contents[0].mimeType == ROUTING_APP_MIME_TYPE
        assert contents[0].meta["ui"]["csp"]["connectDomains"] == []
        assert "ui/notifications/initialized" in contents[0].text

        result = await client.call_tool("cascadeflow_run", {"query": "current question"})
        assert result.content[0].type == "text"
        assert result.structuredContent["content"] == "answer"
        assert result.structuredContent["model_used"] == "draft"
