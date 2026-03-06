"""Tool-Calling Benchmark: Structured Tool Path Validation

Validates cascadeflow tool-call routing, acceptance, and savings on real tool schemas.
Includes both single-turn and multi-turn tool call scenarios.
"""

import json
from typing import Any

from cascadeflow import CascadeAgent, ModelConfig

from .base import Benchmark

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


class ToolCallsBenchmark(Benchmark):
    """Tool call benchmark for structured tool routing."""

    def __init__(
        self,
        drafter_model: str = "claude-haiku-4-5-20251001",
        verifier_model: str = "claude-opus-4-5-20251101",
        quality_threshold: float = 0.7,
        max_samples: int = 6,
    ):
        super().__init__(
            dataset_name="ToolCalls-6",
            drafter_model=drafter_model,
            verifier_model=verifier_model,
            baseline_model=verifier_model,
            quality_threshold=quality_threshold,
            max_samples=max_samples,
        )
        self.tools = [WEATHER_TOOL, CURRENCY_TOOL, ORDER_TOOL]

    def load_dataset(self) -> list[tuple[Any, Any]]:
        cases = [
            {
                "case_id": "TOOL/WEATHER/PARIS",
                "query": "What's the weather in Paris?",
                "messages": None,
                "expected_tool": "get_weather",
                "expected_params": {"location": "paris"},
            },
            {
                "case_id": "TOOL/CURRENCY/USD_EUR",
                "query": "Convert 10 USD to EUR.",
                "messages": None,
                "expected_tool": "convert_currency",
                "expected_params": {"amount": 10, "from_currency": "USD", "to_currency": "EUR"},
            },
            {
                "case_id": "TOOL/ORDER/LOOKUP",
                "query": "Track order #12345.",
                "messages": None,
                "expected_tool": "lookup_order",
                "expected_params": {"order_id": "12345"},
            },
            {
                "case_id": "TOOL/WEATHER/MULTITURN",
                "query": "And tomorrow?",
                "messages": [
                    {"role": "user", "content": "What's the weather in Berlin?"},
                    {"role": "assistant", "content": "Let me check that for you."},
                    {"role": "user", "content": "And tomorrow?"},
                ],
                "expected_tool": "get_weather",
                "expected_params": {"location": "berlin"},
            },
            {
                "case_id": "TOOL/CURRENCY/MULTITURN",
                "query": "Actually convert 150 GBP to USD.",
                "messages": [
                    {"role": "user", "content": "Convert 100 GBP to USD."},
                    {"role": "assistant", "content": "Sure, I can help with that."},
                    {"role": "user", "content": "Actually convert 150 GBP to USD."},
                ],
                "expected_tool": "convert_currency",
                "expected_params": {"amount": 150, "from_currency": "GBP", "to_currency": "USD"},
            },
            {
                "case_id": "TOOL/WEATHER/TOKYO",
                "query": "Get the weather in Tokyo for tomorrow.",
                "messages": None,
                "expected_tool": "get_weather",
                "expected_params": {"location": "tokyo"},
            },
        ]
        return [(case, case) for case in cases[: self.max_samples]]

    def evaluate_prediction(self, prediction: Any, ground_truth: Any) -> tuple[bool, float]:
        tool_calls = prediction if isinstance(prediction, list) else []
        if not tool_calls:
            return False, 0.0

        tool_call = tool_calls[0] if tool_calls else {}
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

        expected_tool = ground_truth.get("expected_tool")
        expected_params = ground_truth.get("expected_params", {})

        if name != expected_tool:
            return False, 0.0

        for key, expected_value in expected_params.items():
            if key not in args:
                return False, 0.0
            if expected_value is None:
                continue
            actual_value = args.get(key)
            if isinstance(expected_value, (int, float)):
                try:
                    if float(actual_value) != float(expected_value):
                        return False, 0.0
                except (TypeError, ValueError):
                    return False, 0.0
            elif isinstance(expected_value, str):
                if expected_value.lower() not in str(actual_value).lower():
                    return False, 0.0

        return True, 1.0

    async def run_cascade(self, query: Any) -> dict[str, Any]:
        case = query if isinstance(query, dict) else {"query": str(query)}
        prompt = case.get("query", "")
        messages = case.get("messages")

        agent = CascadeAgent(
            models=[
                ModelConfig(name=self.drafter_model, provider="anthropic", cost=0.003),
                ModelConfig(name=self.verifier_model, provider="anthropic", cost=0.045),
            ],
            quality={"threshold": self.quality_threshold},
        )

        result = await agent.run(
            prompt,
            max_tokens=200,
            temperature=0.0,
            tools=self.tools,
            tool_choice="auto",
            messages=messages,
        )

        prediction = result.tool_calls or []

        return {
            "prediction": prediction,
            "model_used": result.model_used,
            "accepted": result.draft_accepted,
            "quality_score": result.quality_score or 0.0,
            "drafter_cost": result.draft_cost or 0.0,
            "verifier_cost": result.verifier_cost or 0.0,
            "total_cost": result.total_cost,
            "latency_ms": result.latency_ms,
            "tokens_input": result.metadata.get("prompt_tokens", 0),
            "tokens_output": result.metadata.get("completion_tokens", 0),
        }


async def run_tool_calls_benchmark() -> Any:
    benchmark = ToolCallsBenchmark()
    return await benchmark.run()
