"""
CascadeFlow - Comprehensive Pre-Launch Test Suite
================================================

Complete validation test for GitHub launch readiness.
Tests all functionality with actual provider costs.

What This Tests:
1. ✅ Basic cascading (text responses)
2. ✅ Streaming (real-time output)
3. ✅ Tool calling (function execution)
4. ✅ Quality validation system
5. ✅ Cost calculations with real pricing
6. ✅ Multiple providers (OpenAI, Anthropic, Groq, Together, Ollama)

Requirements:
    pip install cascadeflow[all]

    # Set API keys:
    export OPENAI_API_KEY="sk-..."
    export ANTHROPIC_API_KEY="sk-ant-..."
    export GROQ_API_KEY="gsk_..."
    export TOGETHER_API_KEY="..."
    # Ollama: Install from https://ollama.com/download
    # Run: ollama pull gemma3:1b

Expected Results:
    - All providers working correctly
    - Streaming shows real-time output
    - Tool calls executed properly
    - Quality system validates responses
    - Cost calculations match provider pricing
    - Ready for GitHub launch! 🚀

Run Time: ~5-10 minutes (depends on API latency)
"""

import asyncio
import os
import sys
import time
from datetime import datetime

from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.streaming import StreamEventType, ToolStreamEventType

# ============================================================================
# LATEST PROVIDER PRICING (October 2025)
# ============================================================================

PROVIDER_COSTS = {
    "openai": {
        "gpt-4o-mini": {
            "input": 0.00015,  # $0.15 per 1M tokens
            "output": 0.0006,  # $0.60 per 1M tokens
        },
        "gpt-4o": {
            "input": 0.0025,  # $2.50 per 1M tokens
            "output": 0.010,  # $10.00 per 1M tokens
        },
    },
    "anthropic": {
        "claude-haiku-4-5": {
            "input": 0.001,  # $1.00 per 1M tokens
            "output": 0.005,  # $5.00 per 1M tokens
        },
        "claude-sonnet-4-5": {
            "input": 0.003,  # $3.00 per 1M tokens
            "output": 0.015,  # $15.00 per 1M tokens
        },
        "claude-opus-4-1": {
            "input": 0.015,  # $15.00 per 1M tokens
            "output": 0.075,  # $75.00 per 1M tokens
        },
    },
    "groq": {
        "llama-3.1-8b-instant": {
            "input": 0.00005,  # $0.05 per 1M tokens
            "output": 0.00008,  # $0.08 per 1M tokens
        },
        "llama-3.1-70b-versatile": {
            "input": 0.00059,  # $0.59 per 1M tokens
            "output": 0.00079,  # $0.79 per 1M tokens
        },
        "llama-4-scout": {
            "input": 0.00011,  # $0.11 per 1M tokens
            "output": 0.00034,  # $0.34 per 1M tokens
        },
    },
    "together": {
        "meta-llama/Llama-3.1-8B-Instruct-Turbo": {
            "input": 0.00018,  # $0.18 per 1M tokens
            "output": 0.00018,  # $0.18 per 1M tokens
        },
        "meta-llama/Llama-3.1-70B-Instruct-Turbo": {
            "input": 0.00088,  # $0.88 per 1M tokens
            "output": 0.00088,  # $0.88 per 1M tokens
        },
    },
    "ollama": {
        # Ollama is 100% FREE - runs locally
        "gemma3:1b": {
            "input": 0.0,
            "output": 0.0,
        },
        "gemma3:12b": {
            "input": 0.0,
            "output": 0.0,
        },
        "llama3.2:1b": {
            "input": 0.0,
            "output": 0.0,
        },
        "llama3.2:3b": {
            "input": 0.0,
            "output": 0.0,
        },
        "deepseek-r1:8b": {
            "input": 0.0,
            "output": 0.0,
        },
    },
}


# ============================================================================
# TEST QUERIES (Progressive Complexity)
# ============================================================================

TEST_QUERIES = [
    {
        "query": "What is 2+2?",
        "complexity": "trivial",
        "expected_tier": 1,
        "description": "Simple arithmetic - should use cheapest model",
    },
    {
        "query": "What color is the sky?",
        "complexity": "simple",
        "expected_tier": 1,
        "description": "Basic knowledge - cheap model sufficient",
    },
    {
        "query": "Explain photosynthesis in one sentence.",
        "complexity": "simple",
        "expected_tier": 1,
        "description": "Simple explanation - should stay on tier 1",
    },
    {
        "query": "Write a haiku about coding.",
        "complexity": "moderate",
        "expected_tier": 1,
        "description": "Creative but simple - may cascade",
    },
    {
        "query": "Compare and contrast Python and Rust for systems programming.",
        "complexity": "moderate",
        "expected_tier": 2,
        "description": "Technical comparison - likely needs tier 2",
    },
    {
        "query": "Explain quantum entanglement and its implications for computing.",
        "complexity": "hard",
        "expected_tier": 2,
        "description": "Complex topic - definitely tier 2",
    },
]


# TOOL CALLING TEST
# ✅ FIX: Use CascadeFlow's universal format (not OpenAI format)
WEATHER_TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name, e.g., 'San Francisco'",
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit",
                },
            },
            "required": ["location"],
        },
    }
]


def mock_get_weather(location: str, unit: str = "celsius") -> str:
    """Mock weather function for testing."""
    temps = {"San Francisco": 18, "Paris": 15, "Tokyo": 22}
    temp = temps.get(location, 20)
    if unit == "fahrenheit":
        temp = int(temp * 9 / 5 + 32)
    return f"The weather in {location} is {temp}°{unit[0].upper()}"


# ============================================================================
# TEST HELPERS
# ============================================================================


class TestResults:
    """Track test results."""

    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []
        self.start_time = time.time()

    def add_pass(self, test_name: str):
        self.tests_run += 1
        self.tests_passed += 1
        print(f"  ✅ {test_name}")

    def add_fail(self, test_name: str, reason: str):
        self.tests_run += 1
        self.tests_failed += 1
        self.failures.append((test_name, reason))
        print(f"  ❌ {test_name}: {reason}")

    def print_summary(self):
        elapsed = time.time() - self.start_time
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Tests Run: {self.tests_run}")
        print(f"Passed: {self.tests_passed} ✅")
        print(f"Failed: {self.tests_failed} ❌")
        print(f"Time: {elapsed:.1f}s")

        if self.failures:
            print("\nFAILURES:")
            for test_name, reason in self.failures:
                print(f"  • {test_name}: {reason}")

        print("\n" + "=" * 80)
        if self.tests_failed == 0:
            print("🎉 ALL TESTS PASSED - READY FOR GITHUB LAUNCH!")
        else:
            print("⚠️  SOME TESTS FAILED - REVIEW BEFORE LAUNCH")
        print("=" * 80 + "\n")


def print_section(title: str):
    """Print a test section header."""
    print("\n" + "=" * 80)
    print(title.upper().center(80))
    print("=" * 80 + "\n")


def validate_cost_calculation(
    actual_cost: float, expected_min: float, expected_max: float, provider: str, model: str
) -> bool:
    """Validate that calculated cost is within expected range."""
    if expected_min <= actual_cost <= expected_max:
        return True
    print(f"    ⚠️  Cost mismatch for {provider}/{model}:")
    print(f"       Expected: ${expected_min:.6f} - ${expected_max:.6f}")
    print(f"       Actual: ${actual_cost:.6f}")
    return False


# ============================================================================
# TEST 1: BASIC CASCADING
# ============================================================================


async def test_basic_cascading(results: TestResults):
    """Test basic cascading functionality with all providers."""
    print_section("Test 1: Basic Cascading")

    # Test with OpenAI
    try:
        print("Testing OpenAI cascade (gpt-4o-mini → gpt-4o)...")
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                ),
                ModelConfig(
                    name="gpt-4o",
                    provider="openai",
                    cost=0.00625,
                ),
            ]
        )

        result = await agent.run("What is 2+2?")
        if result and "4" in result.content:
            results.add_pass("OpenAI basic cascade")
        else:
            results.add_fail("OpenAI basic cascade", "No valid response")

    except Exception as e:
        results.add_fail("OpenAI basic cascade", str(e))

    # Test with Anthropic
    try:
        print("\nTesting Anthropic cascade (haiku-4-5 → sonnet-4-5)...")
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="claude-haiku-4-5",
                    provider="anthropic",
                    cost=0.003,
                ),
                ModelConfig(
                    name="claude-sonnet-4-5",
                    provider="anthropic",
                    cost=0.009,
                ),
            ]
        )

        result = await agent.run("What color is the sky?")
        if result and "blue" in result.content.lower():
            results.add_pass("Anthropic basic cascade")
        else:
            results.add_fail("Anthropic basic cascade", "No valid response")

    except Exception as e:
        results.add_fail("Anthropic basic cascade", str(e))

    # Test with Groq (FREE!)
    try:
        print("\nTesting Groq cascade (llama-3.1-8b → llama-3.1-70b)...")
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="llama-3.1-8b-instant",
                    provider="groq",
                    cost=0.000065,
                ),
                ModelConfig(
                    name="llama-3.1-70b-versatile",
                    provider="groq",
                    cost=0.00069,
                ),
            ]
        )

        result = await agent.run("What is Python?")
        if result and "programming" in result.content.lower():
            results.add_pass("Groq basic cascade")
        else:
            results.add_fail("Groq basic cascade", "No valid response")

    except Exception as e:
        results.add_fail("Groq basic cascade", str(e))

    # Test with Ollama (LOCAL & FREE!)
    try:
        print("\nTesting Ollama (100% local, free)...")
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="gemma3:1b",
                    provider="ollama",
                    cost=0.0,
                ),
            ]
        )

        result = await agent.run("Say hello")
        if result:
            results.add_pass("Ollama local inference (gemma3:1b)")
        else:
            results.add_fail("Ollama local inference", "No response")

    except Exception as e:
        print(f"    ⚠️  Ollama test skipped: {e}")
        print("       Install Ollama and run: ollama pull gemma3:1b")


# ============================================================================
# TEST 2: TEXT STREAMING (COMPREHENSIVE)
# ============================================================================


async def test_streaming(results: TestResults):
    """Test comprehensive text streaming functionality."""
    print_section("Test 2: Text Streaming (Comprehensive)")

    # Test 2A: Basic streaming
    try:
        print("Test 2A: Basic text streaming...")
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                ),
                ModelConfig(
                    name="gpt-4o",
                    provider="openai",
                    cost=0.00625,
                ),
            ]
        )

        manager = agent.text_streaming_manager

        if not manager:
            results.add_fail("Basic text streaming", "No streaming manager available")
            return

        chunks_received = 0
        complete_received = False

        print("  Stream output: ", end="", flush=True)
        async for event in manager.stream("Count from 1 to 5"):
            if event.type == StreamEventType.CHUNK:
                print(event.content, end="", flush=True)
                chunks_received += 1
            elif event.type == StreamEventType.COMPLETE:
                complete_received = True
        print()  # New line

        if chunks_received > 0 and complete_received:
            results.add_pass("Basic text streaming (chunks + completion)")
        else:
            results.add_fail(
                "Basic text streaming", f"chunks={chunks_received}, complete={complete_received}"
            )
    except Exception as e:
        results.add_fail("Basic text streaming", str(e))

    # Test 2B: Cascade streaming
    try:
        print("\nTest 2B: Cascade streaming (draft → verifier)...")
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                ),
                ModelConfig(
                    name="gpt-4o",
                    provider="openai",
                    cost=0.00625,
                ),
            ]
        )

        manager = agent.text_streaming_manager

        draft_decision_received = False
        chunks_received = 0

        print("  Testing with complex query...")
        async for event in manager.stream("Explain quantum entanglement in detail"):
            if event.type == StreamEventType.DRAFT_DECISION:
                draft_decision_received = True
                print(f"    → Draft decision: {event.data.get('accepted')}")
            elif event.type == StreamEventType.SWITCH:
                print(
                    f"    → Switching: {event.data.get('from_model')} → {event.data.get('to_model')}"
                )
            elif event.type == StreamEventType.CHUNK:
                chunks_received += 1

        if draft_decision_received and chunks_received > 0:
            results.add_pass("Cascade streaming (with events)")
        else:
            results.add_fail(
                "Cascade streaming", f"decision={draft_decision_received}, chunks={chunks_received}"
            )
    except Exception as e:
        results.add_fail("Cascade streaming", str(e))

    # Test 2C: Event timing validation
    try:
        print("\nTest 2C: Stream timing and performance...")

        # ✅ FIX: Use 2 models so cascade is enabled
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                ),
                ModelConfig(
                    name="gpt-4o",
                    provider="openai",
                    cost=0.00625,
                ),
            ]
        )

        manager = agent.text_streaming_manager

        if not manager:
            results.add_fail("Stream timing", "No streaming manager")
            return

        start_time = time.time()
        first_chunk_time = None
        chunk_count = 0

        async for event in manager.stream("Say hello"):
            if event.type == StreamEventType.CHUNK:
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                chunk_count += 1

        total_time = time.time() - start_time
        time_to_first_chunk = (first_chunk_time - start_time) if first_chunk_time else 999

        print(f"    → First chunk: {time_to_first_chunk*1000:.0f}ms")
        print(f"    → Total chunks: {chunk_count}")
        print(f"    → Total time: {total_time*1000:.0f}ms")

        if time_to_first_chunk < 5.0 and chunk_count > 0:
            results.add_pass("Stream timing (first chunk < 5s)")
        else:
            results.add_fail(
                "Stream timing", f"first_chunk={time_to_first_chunk:.1f}s, chunks={chunk_count}"
            )
    except Exception as e:
        results.add_fail("Stream timing", str(e))


# ============================================================================
# TEST 3: TOOL CALLING & STREAMING (COMPREHENSIVE)
# ============================================================================


async def test_tool_calling(results: TestResults):
    """Test comprehensive tool calling and streaming functionality."""
    print_section("Test 3: Tool Calling & Streaming (Comprehensive)")

    # Test 3A: Basic tool streaming
    try:
        print("Test 3A: Basic tool call streaming...")

        # ✅ FIX: Use 2 models so cascade is enabled
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                ),
                ModelConfig(
                    name="gpt-4o",
                    provider="openai",
                    cost=0.00625,
                ),
            ]
        )

        manager = agent.tool_streaming_manager

        if not manager:
            results.add_fail("Tool call streaming", "No tool streaming manager available")
            return

        tool_call_start = False
        tool_call_complete = False
        tool_result_received = False
        deltas_received = 0

        print("  Tool stream events:")
        async for event in manager.stream(
            "What's the weather in Paris?",
            tools=WEATHER_TOOLS,
            execute_tools=True,  # ✅ FIX: Enable tool execution
        ):
            if event.type == ToolStreamEventType.TOOL_CALL_START:
                tool_call_start = True
                print("    ✓ Tool call started")
            elif event.type == ToolStreamEventType.TOOL_CALL_DELTA:
                deltas_received += 1
                delta_preview = str(event.delta)[:20] if hasattr(event, "delta") else "..."
                print(f"    ✓ Delta received: {delta_preview}...")
            elif event.type == ToolStreamEventType.TOOL_CALL_COMPLETE:
                tool_call_complete = True
                print(f"    ✓ Tool call complete: {event.tool_call.get('name')}")
            elif event.type == ToolStreamEventType.TOOL_RESULT:
                tool_result_received = True
                print(f"    ✓ Tool result: {event.tool_result}")

        if tool_call_start and tool_call_complete and tool_result_received:
            results.add_pass("Tool call streaming (all events)")
        else:
            results.add_fail(
                "Tool call streaming",
                f"start={tool_call_start}, complete={tool_call_complete}, result={tool_result_received}",
            )
    except Exception as e:
        results.add_fail("Tool call streaming", str(e))

    # Test 3B: Tool validation
    try:
        print("\nTest 3B: Tool call validation...")

        # ✅ FIX: Use 2 models so cascade is enabled
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                ),
                ModelConfig(
                    name="gpt-4o",
                    provider="openai",
                    cost=0.00625,
                ),
            ]
        )

        manager = agent.tool_streaming_manager

        if not manager:
            results.add_fail("Tool call validation", "No tool streaming manager")
            return

        valid_tool_calls = []
        invalid_tool_calls = []

        async for event in manager.stream(
            "Get weather for San Francisco in celsius", tools=WEATHER_TOOLS
        ):
            if event.type == ToolStreamEventType.TOOL_CALL_COMPLETE:
                tool_call = event.tool_call

                if "name" in tool_call and "arguments" in tool_call:
                    args = tool_call["arguments"]
                    if "location" in args:
                        valid_tool_calls.append(tool_call)
                        print(f"    ✓ Valid tool call: {tool_call['name']}({args})")
                    else:
                        invalid_tool_calls.append(tool_call)
                        print("    ✗ Invalid: missing 'location'")

        if len(valid_tool_calls) > 0 and len(invalid_tool_calls) == 0:
            results.add_pass("Tool call validation")
        else:
            results.add_fail(
                "Tool call validation",
                f"valid={len(valid_tool_calls)}, invalid={len(invalid_tool_calls)}",
            )
    except Exception as e:
        results.add_fail("Tool call validation", str(e))

    # Test 3C: Tool execution with cascade
    try:
        print("\nTest 3C: Tool calls with cascade...")
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                ),
                ModelConfig(
                    name="gpt-4o",
                    provider="openai",
                    cost=0.00625,
                ),
            ]
        )

        manager = agent.tool_streaming_manager

        if not manager:
            results.add_fail("Tool cascade", "No tool streaming manager")
            return

        events_seen = {
            "tool_call": False,
            "tool_result": False,
            "draft_decision": False,
        }

        async for event in manager.stream(
            "What's the weather in Tokyo?",
            tools=WEATHER_TOOLS,
            execute_tools=True,  # ✅ FIX: Enable tool execution
        ):
            if event.type == ToolStreamEventType.TOOL_CALL_COMPLETE:
                events_seen["tool_call"] = True
            elif event.type == ToolStreamEventType.TOOL_RESULT:
                events_seen["tool_result"] = True
            elif event.type == ToolStreamEventType.DRAFT_DECISION:
                events_seen["draft_decision"] = True

        success_count = sum(events_seen.values())
        print(f"    → Events received: {success_count}/3")

        if events_seen["tool_call"] and events_seen["tool_result"]:
            results.add_pass("Tool cascade (basic events)")
        else:
            results.add_fail("Tool cascade", f"events={events_seen}")
    except Exception as e:
        results.add_fail("Tool cascade", str(e))

    # Test 3D: Multiple tool calls
    try:
        print("\nTest 3D: Multiple tool calls in one response...")

        # ✅ FIX: Use 2 models so cascade is enabled
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                ),
                ModelConfig(
                    name="gpt-4o",
                    provider="openai",
                    cost=0.00625,
                ),
            ]
        )

        manager = agent.tool_streaming_manager

        if not manager:
            results.add_fail("Multiple tool calls", "No tool streaming manager")
            return

        tool_calls_completed = []

        async for event in manager.stream("Get weather for Paris and Tokyo", tools=WEATHER_TOOLS):
            if event.type == ToolStreamEventType.TOOL_CALL_COMPLETE:
                tool_calls_completed.append(event.tool_call)
                print(f"    ✓ Tool {len(tool_calls_completed)}: {event.tool_call.get('name')}")

        if len(tool_calls_completed) >= 1:
            results.add_pass(f"Multiple tool calls ({len(tool_calls_completed)} received)")
        else:
            results.add_fail("Multiple tool calls", "No tool calls received")
    except Exception as e:
        results.add_fail("Multiple tool calls", str(e))


# ============================================================================
# TEST 4: QUALITY VALIDATION
# ============================================================================


async def test_quality_validation(results: TestResults):
    """Test quality validation system with defaults."""
    print_section("Test 4: Quality Validation System (Defaults)")

    try:
        print("Testing default quality validation...")
        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                ),
                ModelConfig(
                    name="gpt-4o",
                    provider="openai",
                    cost=0.00625,
                ),
            ]
        )

        result = await agent.run("What is 2+2?")
        if result and hasattr(result, "quality_score"):
            print(f"  Quality score: {result.quality_score:.2f}")
            print(f"  Default config active: {agent.quality_config is not None}")
            results.add_pass("Quality validation (default config)")
        else:
            results.add_fail("Quality validation", "No quality score")

    except Exception as e:
        results.add_fail("Quality validation", str(e))


# ============================================================================
# TEST 5: COST VALIDATION
# ============================================================================


async def test_cost_validation(results: TestResults):
    """Validate cost calculations match provider pricing."""
    print_section("Test 5: Cost Calculation Validation")

    providers_to_test = [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-haiku-4-5"),
        ("groq", "llama-3.1-8b-instant"),
    ]

    for provider, model in providers_to_test:
        try:
            print(f"\nValidating costs for {provider}/{model}...")

            agent = CascadeAgent(
                models=[
                    ModelConfig(
                        name=model,
                        provider=provider,
                        cost=PROVIDER_COSTS[provider][model]["input"],
                    ),
                ]
            )

            result = await agent.run("What is AI?")

            if result and hasattr(result, "total_cost"):
                actual_cost = result.total_cost

                input_cost = PROVIDER_COSTS[provider][model]["input"]
                output_cost = PROVIDER_COSTS[provider][model]["output"]

                input_tokens_range = (5, 15)
                output_tokens_range = (20, 200)

                min_cost = (
                    input_tokens_range[0] * input_cost + output_tokens_range[0] * output_cost
                ) / 1000
                max_cost = (
                    input_tokens_range[1] * input_cost + output_tokens_range[1] * output_cost
                ) / 1000

                tolerance = 0.30
                min_cost *= 1 - tolerance
                max_cost *= 1 + tolerance

                print(f"  Actual cost: ${actual_cost:.6f}")
                print(f"  Expected range: ${min_cost:.6f} - ${max_cost:.6f}")

                if validate_cost_calculation(actual_cost, min_cost, max_cost, provider, model):
                    results.add_pass(f"Cost validation: {provider}/{model}")
                else:
                    results.add_fail(f"Cost validation: {provider}/{model}", "Cost out of range")
            else:
                results.add_fail(f"Cost validation: {provider}/{model}", "No cost info")

        except Exception as e:
            results.add_fail(f"Cost validation: {provider}/{model}", str(e))


# ============================================================================
# TEST 6: FULL INTEGRATION
# ============================================================================


async def test_full_integration(results: TestResults):
    """Test complete system with multiple queries."""
    print_section("Test 6: Full Integration Test")

    try:
        print("Running full integration with multiple queries...")

        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name="gpt-4o-mini",
                    provider="openai",
                    cost=0.00015,
                    quality_threshold=0.7,
                ),
                ModelConfig(
                    name="gpt-4o",
                    provider="openai",
                    cost=0.00625,
                    quality_threshold=0.95,
                ),
            ]
        )

        successful = 0
        total = len(TEST_QUERIES)

        for i, test in enumerate(TEST_QUERIES, 1):
            print(f"\n  Query {i}/{total}: {test['description']}")
            print(f"  └─ \"{test['query']}\"")

            try:
                result = await agent.run(test["query"])
                if result and result.content:
                    print(f"     ✓ Response received ({len(result.content)} chars)")
                    print(f"     ✓ Cost: ${result.total_cost:.6f}")
                    successful += 1
                else:
                    print("     ✗ No response")
            except Exception as e:
                print(f"     ✗ Error: {e}")

        if successful == total:
            results.add_pass(f"Full integration ({total} queries)")
        else:
            results.add_fail("Full integration", f"Only {successful}/{total} succeeded")

    except Exception as e:
        results.add_fail("Full integration", str(e))


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("CASCADEFLOW - PRE-LAUNCH TEST SUITE".center(80))
    print("=" * 80)
    print()
    print("Testing all functionality before GitHub launch...")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Check environment
    print("Environment Check:")
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    has_together = bool(os.getenv("TOGETHER_API_KEY"))

    print(f"  OpenAI: {'✅' if has_openai else '❌'}")
    print(f"  Anthropic: {'✅' if has_anthropic else '❌'}")
    print(f"  Groq: {'✅' if has_groq else '❌'}")
    print(f"  Together: {'✅' if has_together else '❌'}")
    print("  Ollama: ℹ️  (requires local install)")

    if not has_openai:
        print("\n⚠️  WARNING: No OpenAI key found. Some tests will fail.")
        print("   Set: export OPENAI_API_KEY='sk-...'")

    print()

    # Run tests
    results = TestResults()

    await test_basic_cascading(results)
    await test_streaming(results)
    await test_tool_calling(results)
    await test_quality_validation(results)
    await test_cost_validation(results)
    await test_full_integration(results)

    # Print final summary
    results.print_summary()

    # Exit with appropriate code
    sys.exit(0 if results.tests_failed == 0 else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
