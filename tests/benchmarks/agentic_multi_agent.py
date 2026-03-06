"""Agentic Multi-Agent Benchmark (Routing + Tool Calling, Real APIs).

This benchmark is designed to reflect how developers build agentic systems:
- A router/planner decides which sub-agent should handle the request.
- The chosen sub-agent emits structured tool calls (optionally multi-turn).

It reports:
- Correctness (router decision + tool-call correctness)
- Drafter acceptance rate (across both calls per task)
- Cost reduction vs a verifier-only baseline
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from cascadeflow import CascadeAgent, ModelConfig


WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the weather for a location and date.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "date": {"type": "string", "description": "Date or day"},
            },
            "required": ["location"],
        },
    },
}

CURRENCY_TOOL = {
    "type": "function",
    "function": {
        "name": "convert_currency",
        "description": "Convert an amount between currencies.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "from_currency": {"type": "string"},
                "to_currency": {"type": "string"},
            },
            "required": ["amount", "from_currency", "to_currency"],
        },
    },
}

ORDER_TOOL = {
    "type": "function",
    "function": {
        "name": "lookup_order",
        "description": "Lookup order status by order ID.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
}

UPDATE_ORDER_TOOL = {
    "type": "function",
    "function": {
        "name": "update_order_status",
        "description": "Update an order status by order ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "status": {"type": "string"},
            },
            "required": ["order_id", "status"],
        },
    },
}


@dataclass
class MultiAgentCase:
    case_id: str
    query: str
    expected_route: str  # weather | currency | orders
    expected_tool: str
    expected_params: dict[str, Any]
    messages: Optional[list[dict[str, Any]]] = None


CASES: list[MultiAgentCase] = [
    MultiAgentCase(
        case_id="MA/WEATHER/PARIS",
        query="What's the weather in Paris?",
        expected_route="weather",
        expected_tool="get_weather",
        expected_params={"location": "paris"},
    ),
    MultiAgentCase(
        case_id="MA/WEATHER/MULTITURN",
        query="And tomorrow?",
        expected_route="weather",
        expected_tool="get_weather",
        expected_params={"location": "berlin"},
        messages=[
            {"role": "user", "content": "What's the weather in Berlin?"},
            {"role": "assistant", "content": "Let me check that for you."},
            {"role": "user", "content": "And tomorrow?"},
        ],
    ),
    MultiAgentCase(
        case_id="MA/CURRENCY/USD_EUR",
        query="Convert 10 USD to EUR.",
        expected_route="currency",
        expected_tool="convert_currency",
        expected_params={"amount": 10, "from_currency": "USD", "to_currency": "EUR"},
    ),
    MultiAgentCase(
        case_id="MA/CURRENCY/MULTITURN",
        query="Actually convert 150 GBP to USD.",
        expected_route="currency",
        expected_tool="convert_currency",
        expected_params={"amount": 150, "from_currency": "GBP", "to_currency": "USD"},
        messages=[
            {"role": "user", "content": "Convert 100 GBP to USD."},
            {"role": "assistant", "content": "Sure, I can help with that."},
            {"role": "user", "content": "Actually convert 150 GBP to USD."},
        ],
    ),
    MultiAgentCase(
        case_id="MA/ORDER/LOOKUP",
        query="Track order #12345.",
        expected_route="orders",
        expected_tool="lookup_order",
        expected_params={"order_id": "12345"},
    ),
    MultiAgentCase(
        case_id="MA/ORDER/UPDATE_MULTITURN",
        query="Update it to shipped.",
        expected_route="orders",
        expected_tool="update_order_status",
        expected_params={"order_id": "12345", "status": "shipped"},
        messages=[
            {"role": "user", "content": "Track order #12345."},
            {"role": "assistant", "content": "I can help with that."},
            {"role": "user", "content": "Update it to shipped."},
        ],
    ),
]


ROUTER_PROMPT = """You are a router for an agent system.

Pick which specialist should handle the user request.

Return JSON ONLY:
{"route": "weather" | "currency" | "orders", "reason": "short"}
"""


def _extract_route(text: str) -> Optional[str]:
    try:
        obj = json.loads(text)
        route = obj.get("route")
        if isinstance(route, str):
            route = route.strip().lower()
            if route in {"weather", "currency", "orders"}:
                return route
    except Exception:
        pass

    # Tolerant fallback: look for route-like tokens.
    m = re.search(r"\b(weather|currency|orders)\b", text.lower())
    return m.group(1) if m else None


def _tool_call_matches(
    tool_calls: list[dict[str, Any]],
    expected_tool: str,
    expected_params: dict[str, Any],
) -> bool:
    for tool_call in tool_calls:
        name = (
            tool_call.get("name")
            or tool_call.get("tool")
            or (tool_call.get("function") or {}).get("name")
        )
        args = (
            tool_call.get("arguments")
            or tool_call.get("args")
            or tool_call.get("parameters")
            or (tool_call.get("function") or {}).get("arguments")
        )

        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if not isinstance(args, dict):
            args = {}

        if name != expected_tool:
            continue

        for key, expected_value in expected_params.items():
            if key not in args:
                return False
            actual_value = args.get(key)
            if expected_value is None:
                continue
            if isinstance(expected_value, (int, float)):
                try:
                    if float(actual_value) != float(expected_value):
                        return False
                except (TypeError, ValueError):
                    return False
            else:
                if str(expected_value).lower() not in str(actual_value).lower():
                    return False

        return True

    return False


async def run_agentic_multi_agent_benchmark(
    *,
    drafter_model: str = "claude-haiku-4-5-20251001",
    verifier_model: str = "claude-opus-4-5-20251101",
    quality_threshold: float = 0.7,
    max_tasks: int = 6,
    verbose: bool = True,
) -> dict[str, Any]:
    cases = CASES[:max_tasks]

    router = CascadeAgent(
        models=[
            ModelConfig(name=drafter_model, provider="anthropic", cost=0.003),
            ModelConfig(name=verifier_model, provider="anthropic", cost=0.045),
        ],
        quality={"threshold": quality_threshold},
    )

    tool_agent = CascadeAgent(
        models=[
            ModelConfig(name=drafter_model, provider="anthropic", cost=0.003),
            ModelConfig(name=verifier_model, provider="anthropic", cost=0.045),
        ],
        quality={"threshold": quality_threshold},
    )

    tools = [WEATHER_TOOL, CURRENCY_TOOL, ORDER_TOOL, UPDATE_ORDER_TOOL]

    total_cost = 0.0
    total_baseline = 0.0
    accepted_steps = 0
    total_steps = 0
    correct_router = 0
    correct_tool = 0
    correct_both = 0
    latencies: list[float] = []

    per_case: list[dict[str, Any]] = []

    print("=" * 70)
    print("AGENTIC MULTI-AGENT (ROUTER + TOOL CALLING)")
    print("=" * 70)
    print(f"Tasks: {len(cases)} | Drafter: {drafter_model} | Verifier: {verifier_model}")
    print()

    for idx, case in enumerate(cases, 1):
        case_start = time.time()

        # Step 1: router chooses route
        router_messages = [{"role": "system", "content": ROUTER_PROMPT}]
        router_messages.append({"role": "user", "content": case.query})
        router_res = await router.run(router_messages, max_tokens=80, temperature=0.0)
        route = _extract_route(router_res.content)
        router_ok = route == case.expected_route

        total_steps += 1
        accepted_steps += 1 if router_res.draft_accepted else 0

        # Step 2: tool agent emits tool call (using multi-turn messages when provided)
        tool_messages = case.messages or [{"role": "user", "content": case.query}]
        tool_res = await tool_agent.run(
            tool_messages,
            max_tokens=200,
            temperature=0.0,
            tools=tools,
            tool_choice="auto",
        )
        tool_calls = tool_res.tool_calls or []
        tool_ok = _tool_call_matches(tool_calls, case.expected_tool, case.expected_params)

        total_steps += 1
        accepted_steps += 1 if tool_res.draft_accepted else 0

        correct_router += 1 if router_ok else 0
        correct_tool += 1 if tool_ok else 0
        both_ok = router_ok and tool_ok
        correct_both += 1 if both_ok else 0

        # Costs (prefer cascadeflow's own baseline/cost semantics when available)
        for r in (router_res, tool_res):
            total_cost += float(r.total_cost or 0.0)
            baseline = r.baseline_cost
            if baseline is not None:
                total_baseline += float(baseline)

        latency_ms = (time.time() - case_start) * 1000
        latencies.append(latency_ms)

        row = {
            "case_id": case.case_id,
            "router_route": route,
            "expected_route": case.expected_route,
            "router_ok": router_ok,
            "expected_tool": case.expected_tool,
            "tool_ok": tool_ok,
            "draft_router": bool(router_res.draft_accepted),
            "draft_tool": bool(tool_res.draft_accepted),
            "latency_ms": latency_ms,
            "router_cost": float(router_res.total_cost or 0.0),
            "tool_cost": float(tool_res.total_cost or 0.0),
        }
        per_case.append(row)

        if verbose:
            status = "✓" if both_ok else "✗"
            print(
                f"[{idx}/{len(cases)}] {case.case_id}: {status} "
                f"router={route or '∅'} tool_calls={len(tool_calls)} "
                f"draft=[{'D' if router_res.draft_accepted else 'V'},{'D' if tool_res.draft_accepted else 'V'}] "
                f"${row['router_cost']+row['tool_cost']:.4f} {latency_ms:.0f}ms"
            )

    accuracy = (correct_both / len(cases)) if cases else 0.0
    router_acc = (correct_router / len(cases)) if cases else 0.0
    tool_acc = (correct_tool / len(cases)) if cases else 0.0

    acceptance = (accepted_steps / total_steps) if total_steps else 0.0

    savings = max(0.0, total_baseline - total_cost) if total_baseline > 0 else 0.0
    savings_pct = ((savings / total_baseline) * 100.0) if total_baseline > 0 else 0.0

    avg_latency_ms = (sum(latencies) / len(latencies)) if latencies else 0.0

    summary = {
        "dataset_name": f"Agentic-MultiAgent-{len(cases)}",
        "total_tasks": len(cases),
        "accuracy": accuracy,
        "router_accuracy": router_acc,
        "tool_accuracy": tool_acc,
        "draft_acceptance": acceptance,
        "total_cost": total_cost,
        "baseline_cost": total_baseline,
        "total_savings": savings,
        "cost_reduction_pct": savings_pct,
        "avg_latency_ms": avg_latency_ms,
        "results": per_case,
    }

    print()
    print("Summary:")
    print(f"  Accuracy (router+tool): {accuracy*100:.1f}%")
    print(f"  Router accuracy:        {router_acc*100:.1f}%")
    print(f"  Tool accuracy:          {tool_acc*100:.1f}%")
    print(f"  Drafter acceptance:     {acceptance*100:.1f}% (steps={total_steps})")
    if total_baseline > 0:
        print(f"  Cost reduction:         {savings_pct:.1f}%")
        print(f"  Total cost:             ${total_cost:.6f} (baseline ${total_baseline:.6f})")
    else:
        print(f"  Total cost:             ${total_cost:.6f} (baseline unavailable)")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agentic multi-agent benchmark (router + tool calls)"
    )
    parser.add_argument("--tasks", type=int, default=6, help="Number of tasks to run")
    parser.add_argument("--drafter", type=str, default="claude-haiku-4-5-20251001")
    parser.add_argument("--verifier", type=str, default="claude-opus-4-5-20251101")
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument("--quiet", action="store_true", help="Reduce per-task output")

    args = parser.parse_args()

    asyncio.run(
        run_agentic_multi_agent_benchmark(
            drafter_model=args.drafter,
            verifier_model=args.verifier,
            quality_threshold=args.threshold,
            max_tasks=args.tasks,
            verbose=not args.quiet,
        )
    )


if __name__ == "__main__":
    main()
