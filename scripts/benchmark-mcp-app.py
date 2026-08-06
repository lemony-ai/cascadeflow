#!/usr/bin/env python3
"""Measure MCP Apps transport overhead without making provider calls."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from cascadeflow.integrations.mcp import create_mcp_server
from cascadeflow.integrations.mcp_app import ROUTING_APP_URI


@dataclass
class _Result:
    content: str = "answer"
    model_used: str = "draft"
    cascaded: bool = False
    draft_accepted: bool = True
    routing_strategy: str = "cascade"
    total_cost: float = 0.001
    cost_saved: float = 0.009
    latency_ms: float = 12.0
    metadata: dict[str, Any] = field(default_factory=lambda: {"knowledge": {"identity": "docs:v2"}})


class _Agent:
    async def run(self, query: str, **kwargs: Any) -> _Result:
        return _Result()


def _json_bytes(value: Any) -> int:
    return len(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


async def main() -> None:
    tool_only = create_mcp_server(_Agent())
    with_ui = create_mcp_server(_Agent(), include_ui=True)

    tool_only_schema = (await tool_only.list_tools())[0].model_dump(
        by_alias=True, exclude_none=True
    )
    ui_schema = (await with_ui.list_tools())[0].model_dump(by_alias=True, exclude_none=True)
    model_visible_tool_only = {
        key: value for key, value in tool_only_schema.items() if key != "_meta"
    }
    model_visible_ui = {key: value for key, value in ui_schema.items() if key != "_meta"}
    if model_visible_tool_only != model_visible_ui:
        raise RuntimeError("UI changed the model-visible MCP tool schema")

    _, tool_only_result = await tool_only.call_tool("cascadeflow_run", {"query": "hello"})
    _, ui_result = await with_ui.call_tool("cascadeflow_run", {"query": "hello"})
    if tool_only_result != ui_result:
        raise RuntimeError("UI changed the provider-facing tool result")

    app = (await with_ui.read_resource(ROUTING_APP_URI))[0]
    metadata_bytes = _json_bytes(ui_schema) - _json_bytes(tool_only_schema)
    app_bytes = len(app.content.encode())

    print("cascadeflow MCP Apps overhead")
    print("  model-visible schema delta:  0 bytes")
    print("  provider query/result delta: 0 bytes")
    print(f"  host-only tool metadata:     {metadata_bytes} bytes")
    print(f"  cacheable ui:// resource:    {app_bytes} bytes")


if __name__ == "__main__":
    asyncio.run(main())
