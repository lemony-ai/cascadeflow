"""
Agentic + Multi-Agent Example (Python)
=====================================

Demonstrates:
- Multi-turn tool loop with automatic tool execution (tool_executor + max_steps)
- Multi-agent orchestration (agent-as-a-tool delegation)

Requirements:
    - cascadeflow[all]
    - OpenAI API key

Setup:
    pip install cascadeflow[all]
    export OPENAI_API_KEY="sk-..."
    python examples/agentic_multi_agent.py

Documentation:
    📖 Agentic Guide (Python): docs/guides/agentic-python.md
    📖 Tool Guide: docs/guides/tools.md
"""

import asyncio
import math
import os
import re
from typing import Any

from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.tools import ToolConfig, ToolExecutor


def safe_calculate(expression: str) -> dict[str, Any]:
    """
    Minimal, example-only calculator.

    Supports: numbers, whitespace, + - * / ( ) and sqrt()/pow()/abs().
    """
    # Very conservative allowlist for demo purposes.
    if not re.fullmatch(r"[\d\s+\-*/().,_a-zA-Z]+", expression):
        return {"expression": expression, "error": "Invalid expression"}

    try:
        # NOTE: This is intentionally a demo. Do not use eval for untrusted input in production.
        result = eval(
            expression,
            {"__builtins__": {}},
            {"sqrt": math.sqrt, "pow": math.pow, "abs": abs},
        )
        return {"expression": expression, "result": result}
    except Exception as exc:
        return {"expression": expression, "error": f"{type(exc).__name__}: {exc}"}


async def main() -> None:
    print("\n" + "=" * 80)
    print("🤖 CASCADEFLOW - AGENTIC + MULTI-AGENT EXAMPLE (PYTHON)")
    print("=" * 80 + "\n")

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit('Set OPENAI_API_KEY first: export OPENAI_API_KEY="sk-..."')

    # Specialist agent used for delegation.
    research_agent = CascadeAgent(
        models=[
            ModelConfig("gpt-4o-mini", "openai", cost=0.00015),
            ModelConfig("gpt-4o", "openai", cost=0.00625),
        ]
    )

    async def delegate_to_researcher(question: str) -> dict[str, Any]:
        res = await research_agent.run(
            [
                {
                    "role": "system",
                    "content": "You are a concise research assistant. Answer in 2-4 sentences.",
                },
                {"role": "user", "content": question},
            ],
            max_tokens=250,
            force_direct=True,
        )
        return {"answer": res.content, "model": res.model_used, "cost": res.total_cost}

    # Tool executor that will run tool calls emitted by the model.
    executor = ToolExecutor(
        tools=[
            ToolConfig(
                name="calculate",
                description="Perform a mathematical calculation (demo only).",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "Math expression"}
                    },
                    "required": ["expression"],
                },
                function=safe_calculate,
            ),
            ToolConfig(
                name="search_web",
                description="Search the web (stub example that returns fake results).",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results (1-5)",
                        },
                    },
                    "required": ["query"],
                },
                function=lambda query, num_results=3: {
                    "query": query,
                    "results": [
                        {
                            "title": f"Result {i+1} for '{query}'",
                            "url": f"https://example.com/{i+1}",
                        }
                        for i in range(max(1, min(5, int(num_results or 3))))
                    ],
                },
            ),
            ToolConfig(
                name="delegate_to_researcher",
                description="Ask the research agent for a focused explanation or summary.",
                parameters={
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Research question"}
                    },
                    "required": ["question"],
                },
                function=delegate_to_researcher,
            ),
        ]
    )

    agent = CascadeAgent(
        models=[
            ModelConfig("gpt-4o-mini", "openai", cost=0.00015, supports_tools=True),
            ModelConfig("gpt-4o", "openai", cost=0.00625, supports_tools=True),
        ],
        tool_executor=executor,
    )

    tools = [
        {
            "name": "calculate",
            "description": "Perform a mathematical calculation",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
        {
            "name": "search_web",
            "description": "Search the web (stub)",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "num_results": {"type": "integer"}},
                "required": ["query"],
            },
        },
        {
            "name": "delegate_to_researcher",
            "description": "Ask the research agent for help",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
    ]

    prompt = (
        "Compute sqrt(144) * 5 using the calculate tool, then ask the researcher to explain why the result is correct. "
        "Return the final answer with the calculation and the explanation."
    )

    result = await agent.run(
        [
            {
                "role": "system",
                "content": (
                    "You are an agent. Use tools when they help.\n"
                    "- Use calculate for any arithmetic.\n"
                    "- Use delegate_to_researcher for explanations you are unsure about.\n"
                    "When you have enough information, answer clearly and briefly."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        tools=tools,
        max_steps=6,
        force_direct=True,  # keep tool-loop deterministic for the example
        max_tokens=600,
    )

    print("Final answer:\n")
    print(result.content)
    print("\nDiagnostics:")
    print(f"- model_used: {result.model_used}")
    print(f"- total_cost: ${result.total_cost:.6f}")
    print(f"- latency_ms: {result.latency_ms:.1f}ms")


if __name__ == "__main__":
    asyncio.run(main())
