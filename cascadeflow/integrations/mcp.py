"""MCP tool adapter for running cascadeflow from compatible chat hosts.

The adapter intentionally keeps knowledge resolution server-side. MCP clients send
only a stable knowledge identifier and, when necessary, a concise conversation
handoff. This avoids duplicating an entire knowledge base in every tool call.
"""

from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Optional, Union

from ..context import KnowledgeInput, KnowledgeSnapshot

KnowledgeResolverResult = Union[KnowledgeInput, Awaitable[KnowledgeInput]]
KnowledgeResolver = Callable[[str, Optional[str]], KnowledgeResolverResult]


def _load_fastmcp() -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised without the optional extra
        raise ImportError(
            "The MCP integration requires Python 3.10+ and the MCP SDK. "
            "Install it with: pip install 'cascadeflow[mcp]'"
        ) from exc
    return FastMCP


async def _resolve_knowledge(
    resolver: KnowledgeResolver,
    key: str,
    version: Optional[str],
) -> KnowledgeInput:
    resolved = resolver(key, version)
    if inspect.isawaitable(resolved):
        resolved = await resolved
    if isinstance(resolved, str):
        return KnowledgeSnapshot(content=resolved, key=key, version=version)
    if not isinstance(resolved, KnowledgeSnapshot):
        raise TypeError("knowledge_resolver must return str or KnowledgeSnapshot")
    return resolved


def create_mcp_server(
    agent: Any,
    *,
    knowledge_resolver: Optional[KnowledgeResolver] = None,
    name: str = "cascadeflow",
    max_context_chars: int = 12_000,
) -> Any:
    """Create a tool-first MCP server backed by a configured ``CascadeAgent``.

    The returned FastMCP instance can run over stdio for local desktop clients or
    Streamable HTTP for remote hosts. Knowledge content stays behind the server;
    clients select it with ``knowledge_key`` and optional ``knowledge_version``.
    """
    if max_context_chars <= 0:
        raise ValueError("max_context_chars must be positive")

    FastMCP = _load_fastmcp()
    server = FastMCP(
        name,
        instructions=(
            "Use cascadeflow_run when the user wants a cost-aware answer from "
            "cascadeflow. Select server-side knowledge with knowledge_key and send "
            "conversation_context only as a concise factual handoff when prior turns "
            "are required."
        ),
        stateless_http=True,
        json_response=True,
    )

    @server.tool(
        title="Run cascadeflow",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": True,
        },
    )
    async def cascadeflow_run(
        query: str,
        knowledge_key: Optional[str] = None,
        knowledge_version: Optional[str] = None,
        conversation_context: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run a query through cascadeflow's cost-aware model routing.

        Use knowledge_key to select server-side knowledge. Send
        conversation_context only when the query depends on prior turns, and keep
        it to a concise factual handoff rather than the complete chat transcript.
        """
        if not query.strip():
            raise ValueError("query must be non-empty")
        if conversation_context and len(conversation_context) > max_context_chars:
            raise ValueError(
                f"conversation_context exceeds {max_context_chars} characters; "
                "send a concise relevant handoff"
            )

        knowledge: Optional[KnowledgeInput] = None
        if knowledge_key:
            if knowledge_resolver is None:
                raise ValueError("knowledge_key requires a configured knowledge_resolver")
            knowledge = await _resolve_knowledge(
                knowledge_resolver, knowledge_key, knowledge_version
            )

        messages = None
        if conversation_context and conversation_context.strip():
            messages = [
                {"role": "user", "content": conversation_context.strip()},
                {"role": "user", "content": query},
            ]

        result = await agent.run(query, messages=messages, knowledge=knowledge)
        return {
            "content": result.content,
            "model_used": result.model_used,
            "cascaded": result.cascaded,
            "draft_accepted": result.draft_accepted,
            "routing_strategy": result.routing_strategy,
            "total_cost": result.total_cost,
            "cost_saved": result.cost_saved,
            "latency_ms": result.latency_ms,
            "knowledge": result.metadata.get("knowledge"),
        }

    return server


__all__ = ["KnowledgeResolver", "create_mcp_server"]
