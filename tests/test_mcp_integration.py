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

    def tool(self, **kwargs: Any):
        def decorate(function):
            self.tools[function.__name__] = function
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


@pytest.mark.asyncio
async def test_mcp_sdk_discovers_and_calls_cascadeflow_tool() -> None:
    pytest.importorskip("mcp")

    server = create_mcp_server(FakeAgent())
    tools = await server.list_tools()

    tool = next(item for item in tools if item.name == "cascadeflow_run")
    assert tool.title == "Run cascadeflow"
    assert tool.outputSchema["type"] == "object"
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False
    assert tool.annotations.openWorldHint is True

    content, structured = await server.call_tool("cascadeflow_run", {"query": "current question"})
    assert content[0].type == "text"
    assert structured["content"] == "answer"
    assert structured["model_used"] == "draft"
