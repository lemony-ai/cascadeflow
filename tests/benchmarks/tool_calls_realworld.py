"""Tool-Calling Benchmark: Real-World Tool Routing (Single + Multi-Turn).

Validates cascadeflow tool-call routing, acceptance, and savings on realistic
product tasks with mixed schemas and multi-turn follow-ups.
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

CALENDAR_TOOL = {
    "type": "function",
    "function": {
        "name": "create_calendar_event",
        "description": "Create a calendar event with attendees.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "date": {"type": "string"},
                "time": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "date"],
        },
    },
}

STOCK_TOOL = {
    "type": "function",
    "function": {
        "name": "get_stock_quote",
        "description": "Get the latest stock price for a ticker.",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
        },
    },
}

FLIGHT_TOOL = {
    "type": "function",
    "function": {
        "name": "book_flight",
        "description": "Book a flight between two cities.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string"},
                "destination": {"type": "string"},
                "date": {"type": "string"},
                "passengers": {"type": "number"},
            },
            "required": ["origin", "destination", "date"],
        },
    },
}

PROFILE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_user_profile",
        "description": "Fetch a user profile by ID.",
        "parameters": {
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
            "required": ["user_id"],
        },
    },
}

HELP_TOOL = {
    "type": "function",
    "function": {
        "name": "search_help_center",
        "description": "Search support docs for a query.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}

TICKET_TOOL = {
    "type": "function",
    "function": {
        "name": "create_support_ticket",
        "description": "Create a support ticket.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string"},
            },
            "required": ["subject", "description"],
        },
    },
}


class ToolCallsRealWorldBenchmark(Benchmark):
    """Tool call benchmark for realistic tool routing and multi-turn context."""

    def __init__(
        self,
        drafter_model: str = "claude-haiku-4-5-20251001",
        verifier_model: str = "claude-opus-4-5-20251101",
        quality_threshold: float = 0.7,
        max_samples: int = 18,
    ):
        super().__init__(
            dataset_name="ToolCalls-RealWorld-18",
            drafter_model=drafter_model,
            verifier_model=verifier_model,
            baseline_model=verifier_model,
            quality_threshold=quality_threshold,
            max_samples=max_samples,
        )
        self.tools = [
            WEATHER_TOOL,
            CURRENCY_TOOL,
            ORDER_TOOL,
            UPDATE_ORDER_TOOL,
            CALENDAR_TOOL,
            STOCK_TOOL,
            FLIGHT_TOOL,
            PROFILE_TOOL,
            HELP_TOOL,
            TICKET_TOOL,
        ]

    def load_dataset(self) -> list[tuple[Any, Any]]:
        cases = [
            {
                "case_id": "REAL/WEATHER/PARIS",
                "query": "What's the weather in Paris?",
                "messages": None,
                "expected_tool": "get_weather",
                "expected_params": {"location": "paris"},
            },
            {
                "case_id": "REAL/WEATHER/TOKYO",
                "query": "Get the weather in Tokyo for tomorrow.",
                "messages": None,
                "expected_tool": "get_weather",
                "expected_params": {"location": "tokyo", "date": "tomorrow"},
            },
            {
                "case_id": "REAL/WEATHER/MULTITURN",
                "query": "And tomorrow?",
                "messages": [
                    {"role": "user", "content": "What's the weather in Berlin?"},
                    {"role": "assistant", "content": "Let me check that for you."},
                    {"role": "user", "content": "And tomorrow?"},
                ],
                "expected_tool": "get_weather",
                "expected_params": {"location": "berlin", "date": "tomorrow"},
            },
            {
                "case_id": "REAL/CURRENCY/USD_EUR",
                "query": "Convert 10 USD to EUR.",
                "messages": None,
                "expected_tool": "convert_currency",
                "expected_params": {"amount": 10, "from_currency": "USD", "to_currency": "EUR"},
            },
            {
                "case_id": "REAL/CURRENCY/MULTITURN",
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
                "case_id": "REAL/ORDER/LOOKUP",
                "query": "Track order #12345.",
                "messages": None,
                "expected_tool": "lookup_order",
                "expected_params": {"order_id": "12345"},
            },
            {
                "case_id": "REAL/ORDER/UPDATE_DIRECT",
                "query": "Update order #555 to delivered.",
                "messages": None,
                "expected_tool": "update_order_status",
                "expected_params": {"order_id": "555", "status": "delivered"},
            },
            {
                "case_id": "REAL/ORDER/UPDATE_MULTITURN",
                "query": "Update it to shipped.",
                "messages": [
                    {"role": "user", "content": "Track order #12345."},
                    {"role": "assistant", "content": "I can help with that."},
                    {"role": "user", "content": "Update it to shipped."},
                ],
                "expected_tool": "update_order_status",
                "expected_params": {"order_id": "12345", "status": "shipped"},
            },
            {
                "case_id": "REAL/STOCK/TSLA",
                "query": "What's the current TSLA stock price?",
                "messages": None,
                "expected_tool": "get_stock_quote",
                "expected_params": {"symbol": "TSLA"},
            },
            {
                "case_id": "REAL/CALENDAR/MEETING",
                "query": "Schedule a meeting with Alex tomorrow at 2pm.",
                "messages": None,
                "expected_tool": "create_calendar_event",
                "expected_params": {
                    "title": "meeting",
                    "date": "tomorrow",
                    "time": "2pm",
                    "attendees": ["alex"],
                },
            },
            {
                "case_id": "REAL/FLIGHT/BOOK",
                "query": "Book a flight from SFO to JFK next Monday.",
                "messages": None,
                "expected_tool": "book_flight",
                "expected_params": {
                    "origin": "SFO",
                    "destination": "JFK",
                    "date": "next monday",
                },
            },
            {
                "case_id": "REAL/PROFILE/LOOKUP",
                "query": "Show me the profile for user 42.",
                "messages": None,
                "expected_tool": "get_user_profile",
                "expected_params": {"user_id": "42"},
            },
            {
                "case_id": "REAL/HELP/SEARCH",
                "query": "Search the help center for password reset steps.",
                "messages": None,
                "expected_tool": "search_help_center",
                "expected_params": {"query": "password reset"},
            },
            {
                "case_id": "REAL/TICKET/CREATE",
                "query": "Create a support ticket: login is broken, priority high.",
                "messages": None,
                "expected_tool": "create_support_ticket",
                "expected_params": {"subject": "login", "priority": "high"},
            },
            {
                "case_id": "REAL/WEATHER/NYC",
                "query": "What's the weather in New York next Friday?",
                "messages": None,
                "expected_tool": "get_weather",
                "expected_params": {"location": "new york", "date": "next friday"},
            },
            {
                "case_id": "REAL/CURRENCY/EUR_JPY",
                "query": "Convert 99 EUR to JPY.",
                "messages": None,
                "expected_tool": "convert_currency",
                "expected_params": {"amount": 99, "from_currency": "EUR", "to_currency": "JPY"},
            },
            {
                "case_id": "REAL/ORDER/LOOKUP/MULTITURN",
                "query": "What's the status now?",
                "messages": [
                    {"role": "user", "content": "Track order #888."},
                    {"role": "assistant", "content": "Let me check that for you."},
                    {"role": "user", "content": "What's the status now?"},
                ],
                "expected_tool": "lookup_order",
                "expected_params": {"order_id": "888"},
            },
            {
                "case_id": "REAL/CALENDAR/TEAM",
                "query": "Create a calendar event for team sync on Friday at 10am with sara@acme.com.",
                "messages": None,
                "expected_tool": "create_calendar_event",
                "expected_params": {
                    "title": "team sync",
                    "date": "friday",
                    "time": "10am",
                    "attendees": ["sara@acme.com"],
                },
            },
            {
                "case_id": "REAL/FLIGHT/MULTITURN",
                "query": "Make it for two passengers.",
                "messages": [
                    {"role": "user", "content": "Book a flight from LAX to SEA next Tuesday."},
                    {"role": "assistant", "content": "Sure, I can book that."},
                    {"role": "user", "content": "Make it for two passengers."},
                ],
                "expected_tool": "book_flight",
                "expected_params": {
                    "origin": "LAX",
                    "destination": "SEA",
                    "date": "next tuesday",
                    "passengers": 2,
                },
            },
        ]
        return [(case, case) for case in cases[: self.max_samples]]

    def evaluate_prediction(self, prediction: Any, ground_truth: Any) -> tuple[bool, float]:
        tool_calls = prediction if isinstance(prediction, list) else []
        if not tool_calls:
            return False, 0.0

        expected_tool = ground_truth.get("expected_tool")
        expected_params = ground_truth.get("expected_params", {})

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

            params_match = True
            for key, expected_value in expected_params.items():
                if key not in args:
                    params_match = False
                    break
                if expected_value is None:
                    continue
                actual_value = args.get(key)
                if isinstance(expected_value, list):
                    actual_list = actual_value if isinstance(actual_value, list) else [actual_value]
                    actual_text = " ".join(str(item).lower() for item in actual_list)
                    for expected_item in expected_value:
                        if str(expected_item).lower() not in actual_text:
                            params_match = False
                            break
                    if not params_match:
                        break
                elif isinstance(expected_value, (int, float)):
                    try:
                        if float(actual_value) != float(expected_value):
                            params_match = False
                            break
                    except (TypeError, ValueError):
                        params_match = False
                        break
                elif isinstance(expected_value, str):
                    if expected_value.lower() not in str(actual_value).lower():
                        params_match = False
                        break

            if params_match:
                return True, 1.0

        return False, 0.0

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
            max_tokens=220,
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
            "routing_strategy": result.routing_strategy,
            "drafter_cost": result.draft_cost or 0.0,
            "verifier_cost": result.verifier_cost or 0.0,
            "total_cost": result.total_cost,
            "latency_ms": result.latency_ms,
            "cascadeflow_latency_ms": (
                (result.complexity_detection_ms or 0)
                + (result.metadata.get("domain_detection_ms", 0) if result.metadata else 0)
                + (
                    result.metadata.get("tool_complexity_analysis_ms", 0)
                    if result.metadata
                    else 0
                )
                + (result.quality_verification_ms or 0)
            ),
            "tokens_input": result.metadata.get("prompt_tokens", 0),
            "tokens_output": result.metadata.get("completion_tokens", 0),
        }


async def run_tool_calls_realworld_benchmark() -> Any:
    benchmark = ToolCallsRealWorldBenchmark()
    return await benchmark.run()
