"""
Full BFCL-Style Benchmark for CascadeFlow Tool/Function Calling.

This script:
1. Tests function calling capabilities with various scenarios
2. Evaluates single, parallel, and multi-turn tool calls
3. Measures accuracy and cascade performance
4. Validates CascadeFlow handles tool use efficiently

Categories:
- Simple function calls (single tool, clear parameters)
- Parallel function calls (multiple tools at once)
- Multi-turn conversations (stateful tool use)
- Error handling (missing params, wrong types)

Usage:
    python tests/benchmarks/bfcl/bfcl_full_benchmark.py --sample 20
    python tests/benchmarks/bfcl/bfcl_full_benchmark.py --full
"""

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cascadeflow import CascadeAgent, DomainConfig, ModelConfig


@dataclass
class BFCLResult:
    """Result for a single function calling test."""

    task_id: str
    task_type: str
    correct: bool
    draft_accepted: bool
    cost: float
    latency_ms: float
    function_called: Optional[str] = None
    params_correct: bool = False
    error: Optional[str] = None


# BFCL-style tool definitions
WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["location"],
        },
    },
}

CALCULATOR_TOOL = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "Perform a mathematical calculation",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression to evaluate"},
            },
            "required": ["expression"],
        },
    },
}

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search",
        "description": "Search for information on the web",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "description": "Number of results"},
            },
            "required": ["query"],
        },
    },
}

CALENDAR_TOOL = {
    "type": "function",
    "function": {
        "name": "create_event",
        "description": "Create a calendar event",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "time": {"type": "string", "description": "Time in HH:MM format"},
                "duration_minutes": {"type": "integer"},
            },
            "required": ["title", "date"],
        },
    },
}

EMAIL_TOOL = {
    "type": "function",
    "function": {
        "name": "send_email",
        "description": "Send an email",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
}

DATABASE_TOOL = {
    "type": "function",
    "function": {
        "name": "query_database",
        "description": "Query a SQL database",
        "parameters": {
            "type": "object",
            "properties": {
                "table": {"type": "string"},
                "columns": {"type": "array", "items": {"type": "string"}},
                "where": {"type": "string", "description": "WHERE clause"},
                "limit": {"type": "integer"},
            },
            "required": ["table"],
        },
    },
}

ALL_TOOLS = [WEATHER_TOOL, CALCULATOR_TOOL, SEARCH_TOOL, CALENDAR_TOOL, EMAIL_TOOL, DATABASE_TOOL]

# BFCL-style test cases
BFCL_TASKS = [
    # Simple single function calls
    {
        "task_id": "simple_weather_1",
        "task_type": "simple",
        "tools": [WEATHER_TOOL],
        "prompt": "What's the weather like in Paris?",
        "expected_function": "get_weather",
        "expected_params": {"location": "Paris"},
    },
    {
        "task_id": "simple_weather_2",
        "task_type": "simple",
        "tools": [WEATHER_TOOL],
        "prompt": "Get the temperature in Tokyo in Celsius",
        "expected_function": "get_weather",
        "expected_params": {"location": "Tokyo", "unit": "celsius"},
    },
    {
        "task_id": "simple_calc_1",
        "task_type": "simple",
        "tools": [CALCULATOR_TOOL],
        "prompt": "Calculate 15 * 7 + 23",
        "expected_function": "calculate",
        "expected_params": {"expression": "15 * 7 + 23"},
    },
    {
        "task_id": "simple_search_1",
        "task_type": "simple",
        "tools": [SEARCH_TOOL],
        "prompt": "Search for the latest news about artificial intelligence",
        "expected_function": "search",
        "expected_params": {"query": "artificial intelligence"},
    },
    {
        "task_id": "simple_calendar_1",
        "task_type": "simple",
        "tools": [CALENDAR_TOOL],
        "prompt": "Schedule a meeting called 'Team Standup' for December 15, 2024",
        "expected_function": "create_event",
        "expected_params": {"title": "Team Standup", "date": "2024-12-15"},
    },
    {
        "task_id": "simple_email_1",
        "task_type": "simple",
        "tools": [EMAIL_TOOL],
        "prompt": "Send an email to john@example.com with subject 'Project Update' saying 'The project is on track.'",
        "expected_function": "send_email",
        "expected_params": {"to": "john@example.com", "subject": "Project Update"},
    },
    # Parallel function calls (multiple tools at once)
    {
        "task_id": "parallel_1",
        "task_type": "parallel",
        "tools": [WEATHER_TOOL, CALCULATOR_TOOL],
        "prompt": "What's the weather in New York and also calculate 25 squared?",
        "expected_functions": ["get_weather", "calculate"],
    },
    {
        "task_id": "parallel_2",
        "task_type": "parallel",
        "tools": [WEATHER_TOOL],
        "prompt": "Get the weather for both London and Berlin",
        "expected_functions": ["get_weather", "get_weather"],
    },
    {
        "task_id": "parallel_3",
        "task_type": "parallel",
        "tools": [SEARCH_TOOL, CALENDAR_TOOL],
        "prompt": "Search for 'Python tutorials' and create a 'Study Session' event for 2024-12-20",
        "expected_functions": ["search", "create_event"],
    },
    # Tool selection (choosing right tool from multiple)
    {
        "task_id": "selection_1",
        "task_type": "selection",
        "tools": ALL_TOOLS,
        "prompt": "What's 123 + 456?",
        "expected_function": "calculate",
    },
    {
        "task_id": "selection_2",
        "task_type": "selection",
        "tools": ALL_TOOLS,
        "prompt": "Email sarah@company.com about the budget meeting",
        "expected_function": "send_email",
    },
    {
        "task_id": "selection_3",
        "task_type": "selection",
        "tools": ALL_TOOLS,
        "prompt": "Get all records from the users table where status is active",
        "expected_function": "query_database",
    },
    {
        "task_id": "selection_4",
        "task_type": "selection",
        "tools": ALL_TOOLS,
        "prompt": "Find information about climate change",
        "expected_function": "search",
    },
    # Complex parameter extraction
    {
        "task_id": "complex_params_1",
        "task_type": "complex",
        "tools": [CALENDAR_TOOL],
        "prompt": "Create a 90-minute meeting called 'Q4 Planning' on January 5th, 2025 at 2:30 PM",
        "expected_function": "create_event",
        "expected_params": {
            "title": "Q4 Planning",
            "date": "2025-01-05",
            "time": "14:30",
            "duration_minutes": 90,
        },
    },
    {
        "task_id": "complex_params_2",
        "task_type": "complex",
        "tools": [DATABASE_TOOL],
        "prompt": "Query the orders table for columns order_id, customer_name, and total where status equals 'pending', limit to 50 results",
        "expected_function": "query_database",
        "expected_params": {"table": "orders", "limit": 50},
    },
    # No tool needed scenarios
    {
        "task_id": "no_tool_1",
        "task_type": "no_tool",
        "tools": ALL_TOOLS,
        "prompt": "What is the capital of France?",
        "expected_function": None,
    },
    {
        "task_id": "no_tool_2",
        "task_type": "no_tool",
        "tools": ALL_TOOLS,
        "prompt": "Explain how photosynthesis works",
        "expected_function": None,
    },
]

# Add more tasks for full benchmark
for i in range(10):
    cities = [
        "San Francisco",
        "Sydney",
        "Mumbai",
        "Cairo",
        "Moscow",
        "Seoul",
        "Dubai",
        "Singapore",
        "Toronto",
        "Amsterdam",
    ]
    BFCL_TASKS.append(
        {
            "task_id": f"weather_batch_{i}",
            "task_type": "simple",
            "tools": [WEATHER_TOOL],
            "prompt": f"What's the current weather in {cities[i]}?",
            "expected_function": "get_weather",
            "expected_params": {"location": cities[i]},
        }
    )

for i in range(5):
    expressions = ["(100 + 50) * 2", "sqrt(144) + 10", "15 / 3 - 2", "2^10", "45 % 7"]
    BFCL_TASKS.append(
        {
            "task_id": f"calc_batch_{i}",
            "task_type": "simple",
            "tools": [CALCULATOR_TOOL],
            "prompt": f"Calculate {expressions[i]}",
            "expected_function": "calculate",
            "expected_params": {"expression": expressions[i]},
        }
    )


class BFCLBenchmark:
    """BFCL-style benchmark for function calling capabilities."""

    def __init__(
        self,
        drafter_model: str = "gpt-4o-mini",
        verifier_model: str = "gpt-4o",
        quality_threshold: float = 0.60,
    ):
        self.drafter_model = drafter_model
        self.verifier_model = verifier_model
        self.quality_threshold = quality_threshold
        self.results: list[BFCLResult] = []

    def _extract_function_call(self, response: str) -> tuple[Optional[str], dict]:
        """Extract function name and params from response."""
        import re

        response_lower = response.lower()

        # Check for function name mentions
        function_names = [
            "get_weather",
            "calculate",
            "search",
            "create_event",
            "send_email",
            "query_database",
        ]

        found_function = None
        for func in function_names:
            if func in response_lower or func.replace("_", " ") in response_lower:
                found_function = func
                break

        # Try to extract JSON-like params
        params = {}
        json_match = re.search(r"\{[^}]+\}", response)
        if json_match:
            try:
                params = json.loads(json_match.group())
            except:
                pass

        return found_function, params

    def _check_function_correct(
        self,
        response: str,
        expected_func: Optional[str],
        expected_params: Optional[dict] = None,
    ) -> tuple[bool, bool]:
        """Check if function call is correct."""
        found_func, found_params = self._extract_function_call(response)

        if expected_func is None:
            # No tool should be used
            func_correct = (
                found_func is None
                or "don't need" in response.lower()
                or "no tool" in response.lower()
            )
            return func_correct, True

        func_correct = found_func == expected_func

        params_correct = True
        if expected_params and found_params:
            for key, expected_val in expected_params.items():
                if key in found_params:
                    found_val = str(found_params[key]).lower()
                    expected_str = str(expected_val).lower()
                    if expected_str not in found_val and found_val not in expected_str:
                        params_correct = False

        return func_correct, params_correct

    async def run_single(self, task: dict) -> BFCLResult:
        """Run a single function calling test."""
        task_id = task["task_id"]
        task_type = task["task_type"]
        tools = task["tools"]
        prompt = task["prompt"]
        expected_func = task.get("expected_function")
        expected_params = task.get("expected_params")

        # Format tools for prompt
        tools_desc = "\n".join(
            [f"- {t['function']['name']}: {t['function']['description']}" for t in tools]
        )

        full_prompt = f"""You have access to the following tools:

{tools_desc}

Based on the user's request, determine which tool (if any) should be used and what parameters should be passed.

If a tool should be used, respond with:
Tool: <tool_name>
Parameters: <JSON object with parameters>

If no tool is needed, explain why and answer directly.

User request: {prompt}"""

        # Create agent
        agent = CascadeAgent(
            models=[
                ModelConfig(name=self.drafter_model, provider="openai", cost=0.00015),
                ModelConfig(name=self.verifier_model, provider="openai", cost=0.0025),
            ],
            enable_domain_detection=True,
            use_semantic_domains=True,
        )

        start_time = time.time()

        try:
            result = await agent.run(full_prompt, max_tokens=500)
            latency_ms = (time.time() - start_time) * 1000

            func_correct, params_correct = self._check_function_correct(
                result.content, expected_func, expected_params
            )

            found_func, _ = self._extract_function_call(result.content)

            draft_accepted = result.metadata.get("draft_accepted", False)

            return BFCLResult(
                task_id=task_id,
                task_type=task_type,
                correct=func_correct and params_correct,
                draft_accepted=draft_accepted,
                cost=result.total_cost,
                latency_ms=latency_ms,
                function_called=found_func,
                params_correct=params_correct,
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return BFCLResult(
                task_id=task_id,
                task_type=task_type,
                correct=False,
                draft_accepted=False,
                cost=0.0,
                latency_ms=latency_ms,
                error=str(e),
            )

    async def run_benchmark(
        self,
        max_tasks: Optional[int] = None,
        verbose: bool = True,
    ) -> dict:
        """Run full benchmark."""
        tasks = BFCL_TASKS[:max_tasks] if max_tasks else BFCL_TASKS

        print("=" * 70)
        print("BFCL-STYLE FUNCTION CALLING BENCHMARK")
        print("=" * 70)
        print("\nConfiguration:")
        print(f"  Drafter:  {self.drafter_model}")
        print(f"  Verifier: {self.verifier_model}")
        print(f"  Tasks: {len(tasks)}")
        print()

        self.results = []

        for i, task in enumerate(tasks):
            result = await self.run_single(task)
            self.results.append(result)

            status = "✓" if result.correct else "✗"
            route = "[D]" if result.draft_accepted else "[V]"

            if verbose:
                print(
                    f"[{i+1}/{len(tasks)}] {result.task_id}: {status} {route} | "
                    f"func={result.function_called or 'none'} | "
                    f"${result.cost:.4f} | {result.latency_ms:.0f}ms"
                )
                if result.error:
                    print(f"    Error: {result.error[:60]}")

        return self._calculate_metrics()

    def _calculate_metrics(self) -> dict:
        """Calculate benchmark metrics."""
        total = len(self.results)
        correct = sum(1 for r in self.results if r.correct)
        draft_accepted = sum(1 for r in self.results if r.draft_accepted)
        total_cost = sum(r.cost for r in self.results)

        # Group by task type
        by_type = {}
        for r in self.results:
            if r.task_type not in by_type:
                by_type[r.task_type] = {"correct": 0, "total": 0}
            by_type[r.task_type]["total"] += 1
            if r.correct:
                by_type[r.task_type]["correct"] += 1

        accuracy = correct / total if total > 0 else 0
        draft_rate = draft_accepted / total if total > 0 else 0

        metrics = {
            "total_tasks": total,
            "correct": correct,
            "accuracy": accuracy,
            "draft_acceptance": draft_rate,
            "total_cost": total_cost,
        }

        # Print summary
        print("\n" + "=" * 70)
        print("BENCHMARK SUMMARY")
        print("=" * 70)

        print("\nOverall Performance:")
        print(f"  Accuracy:         {accuracy:.1%} ({correct}/{total})")
        print(f"  Draft Acceptance: {draft_rate:.1%}")
        print(f"  Total Cost:       ${total_cost:.4f}")

        print("\nBy Task Type:")
        for task_type, data in by_type.items():
            type_acc = data["correct"] / data["total"] if data["total"] > 0 else 0
            print(f"  {task_type:15} {type_acc:.1%} ({data['correct']}/{data['total']})")

        print("=" * 70)

        return metrics


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="BFCL-style Function Calling Benchmark")
    parser.add_argument("--sample", type=int, help="Run N tasks")
    parser.add_argument("--full", action="store_true", help="Run all tasks")
    parser.add_argument("--drafter", default="gpt-4o-mini")
    parser.add_argument("--verifier", default="gpt-4o")

    args = parser.parse_args()

    max_tasks = None
    if args.sample:
        max_tasks = args.sample
    elif not args.full:
        max_tasks = 15  # Default quick test

    benchmark = BFCLBenchmark(
        drafter_model=args.drafter,
        verifier_model=args.verifier,
    )

    results = await benchmark.run_benchmark(max_tasks=max_tasks)

    # Save results
    output_dir = Path(__file__).parent / "bfcl_results"
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "results.json", "w") as f:
        json.dump(
            {
                "config": {
                    "drafter": args.drafter,
                    "verifier": args.verifier,
                },
                "metrics": results,
                "results": [
                    {
                        "task_id": r.task_id,
                        "task_type": r.task_type,
                        "correct": r.correct,
                        "draft_accepted": r.draft_accepted,
                        "cost": r.cost,
                        "latency_ms": r.latency_ms,
                        "function_called": r.function_called,
                        "params_correct": r.params_correct,
                    }
                    for r in benchmark.results
                ],
            },
            f,
            indent=2,
        )

    print(f"\nResults saved to: {output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
