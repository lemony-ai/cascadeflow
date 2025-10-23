#!/usr/bin/env python3
"""
CascadeFlow Comprehensive Test Suite - OpenAI Only

Tests and visualizes:
1. Text Cascading (TRIVIAL → EXPERT queries)
2. Tool Cascading (simple → complex tool calls)
3. Quality System (validation, acceptance/rejection)
4. Pre-Routing (complexity-based decisions)
5. Streaming (text and tools)
6. Telemetry (comprehensive metrics)

UPDATED: Uses ONLY OpenAI models to eliminate Groq issues
- Drafter: gpt-4o-mini (fast, cheap, tool-capable)
- Verifier: gpt-4o (high quality, tool-capable)
- Fixes: Groq API errors, improves text acceptance rates

Run: python tests/test_cascade_insights.py
"""

import asyncio
import os
import time

from cascadeflow.config import ModelConfig
from dotenv import load_dotenv

from cascadeflow import CascadeAgent
from cascadeflow.quality import QualityConfig

# Load environment
load_dotenv()


# ============================================================================
# TERMINAL VISUALIZATION HELPERS
# ============================================================================


class Colors:
    """ANSI colors for terminal output."""

    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(title, emoji="🔍"):
    """Print section header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{emoji} {title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}\n")


def print_subheader(title, emoji="→"):
    """Print subsection header."""
    print(f"\n{Colors.BOLD}{emoji} {title}{Colors.END}")
    print(f"{'-'*60}")


def print_success(msg):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")


def print_info(msg):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")


def print_warning(msg):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")


def print_error(msg):
    """Print error message."""
    print(f"{Colors.RED}❌ {msg}{Colors.END}")


def print_metric(label, value, unit=""):
    """Print formatted metric."""
    print(f"  {Colors.CYAN}{label:30s}{Colors.END}: {Colors.BOLD}{value}{unit}{Colors.END}")


def print_quality_check(passed, score, threshold, reason=None):
    """Print quality validation result."""
    status = f"{Colors.GREEN}PASSED" if passed else f"{Colors.RED}FAILED"
    print(f"\n  {Colors.YELLOW}🔍 QUALITY CHECK{Colors.END}: {status}{Colors.END}")
    print(
        f"  {Colors.CYAN}Score{Colors.END}: {Colors.BOLD}{score:.3f}{Colors.END} / {threshold:.3f}"
    )
    if reason:
        print(f"  {Colors.CYAN}Reason{Colors.END}: {reason}")


def print_tool_call(call, index=1):
    """Print tool call details."""
    print(f"\n  {Colors.GREEN}🔧 TOOL CALL #{index}{Colors.END}")
    print(f"     Name: {Colors.BOLD}{call.get('name', 'N/A')}{Colors.END}")
    print(f"     ID: {call.get('id', 'N/A')}")
    print(f"     Arguments: {call.get('arguments', {})}")


# ============================================================================
# TEST QUERIES
# ============================================================================

TEXT_QUERIES = [
    {
        "query": "What is 2+2?",
        "expected_complexity": "trivial",
        "expected_routing": "cascade",
        "description": "Trivial arithmetic - should cascade",
    },
    {
        "query": "Explain how photosynthesis works",
        "expected_complexity": "simple",
        "expected_routing": "cascade",
        "description": "Simple explanation - should cascade",
    },
    {
        "query": "Compare and contrast Keynesian and Austrian economics",
        "expected_complexity": "moderate",
        "expected_routing": "cascade",
        "description": "Moderate analysis - should cascade",
    },
    {
        "query": "Prove Gödel's incompleteness theorems with formal logic",
        "expected_complexity": "hard",
        "expected_routing": "direct",
        "description": "Hard proof - should route directly",
    },
    {
        "query": "Design a distributed consensus algorithm with Byzantine fault tolerance",
        "expected_complexity": "expert",
        "expected_routing": "direct",
        "description": "Expert task - should route directly",
    },
]

TOOL_QUERIES = [
    {
        "query": "What's the weather in Paris?",
        "expected_complexity": "simple",
        "expected_routing": "cascade",
        "description": "Simple tool call - should cascade",
    },
    {
        "query": "Calculate 47 * 89 and tell me if it's prime",
        "expected_complexity": "moderate",
        "expected_routing": "cascade",
        "description": "Multi-step tool use - should cascade",
    },
    {
        "query": "Analyze weather patterns across 10 cities, calculate correlations, and predict trends",
        "expected_complexity": "hard",
        "expected_routing": "direct",
        "description": "Complex multi-tool analysis - should route directly",
    },
]

TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string", "description": "City name"}},
            "required": ["location"],
        },
    },
    {
        "name": "calculator",
        "description": "Perform mathematical calculations",
        "parameters": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "Math expression"}},
            "required": ["expression"],
        },
    },
    {
        "name": "is_prime",
        "description": "Check if a number is prime",
        "parameters": {
            "type": "object",
            "properties": {"number": {"type": "integer", "description": "Number to check"}},
            "required": ["number"],
        },
    },
]


# ============================================================================
# AGENT CREATION
# ============================================================================


def create_openai_only_agent():
    """
    Create CascadeAgent with ONLY OpenAI models.

    This eliminates Groq API errors and improves draft acceptance rates.

    Configuration:
    - Drafter: gpt-4o-mini (fast, cheap, tool-capable, good quality)
    - Verifier: gpt-4o (high quality, tool-capable)
    - Quality: Uses QualityConfig.for_cascade() (optimized thresholds)
    """

    # Define OpenAI models only
    models = [
        # Fast drafter with tool support
        ModelConfig(
            name="gpt-4o-mini",
            provider="openai",
            input_cost=0.000150,  # $0.15/1M tokens
            output_cost=0.000600,  # $0.60/1M tokens
            supports_tools=True,
            max_tokens=16384,
        ),
        # High-quality verifier
        ModelConfig(
            name="gpt-4o",
            provider="openai",
            input_cost=0.0025,  # $2.50/1M tokens
            output_cost=0.010,  # $10/1M tokens
            supports_tools=True,
            max_tokens=16384,
        ),
    ]

    # Use cascade-optimized quality config
    # This has lower thresholds for better acceptance rates
    quality = QualityConfig.for_cascade()

    # Create agent
    agent = CascadeAgent(models=models, quality_config=quality, enable_cascade=True, verbose=True)

    print_info("OpenAI-only agent created:")
    print(f"  🎯 Drafter: {models[0].name} (${models[0].output_cost:.6f}/1K tokens)")
    print(f"  ✅ Verifier: {models[-1].name} (${models[-1].output_cost:.6f}/1K tokens)")
    print(f"  🔧 Both support tools: {models[0].supports_tools and models[-1].supports_tools}")
    print("  📊 Quality config: cascade-optimized")

    return agent


# ============================================================================
# TEST FUNCTIONS
# ============================================================================


async def test_text_cascading(agent):
    """Test text cascading with different complexity levels."""
    print_header("TEXT CASCADING TESTS", "📝")

    results = []

    for i, test in enumerate(TEXT_QUERIES, 1):
        print_subheader(f"Test {i}/{len(TEXT_QUERIES)}: {test['description']}", "🔬")
        print(f"  Query: \"{test['query']}\"")
        print(f"  Expected: {test['expected_complexity']} → {test['expected_routing']}")

        start = time.time()
        try:
            result = await agent.run(test["query"], max_tokens=100, temperature=0.7)
            (time.time() - start) * 1000

            # Print results
            print_metric("Detected Complexity", result.complexity)
            print_metric("Routing Strategy", result.routing_strategy)
            print_metric("Model Used", result.model_used)
            print_metric("Cascaded", str(result.cascaded))

            if result.cascaded:
                print_metric("Draft Accepted", str(result.draft_accepted))
                if result.draft_accepted:
                    print_success("Draft was good enough!")
                else:
                    print_warning("Draft rejected, used verifier")

            print_metric("Total Latency", f"{result.latency_ms:.1f}", "ms")
            print_metric("Total Cost", f"${result.total_cost:.6f}")

            if result.cascaded and result.draft_accepted:
                savings = (result.cost_saved / result.total_cost * 100) if result.cost_saved else 0
                print_metric("Cost Savings", f"{savings:.1f}", "%")

            # Show quality check
            if result.quality_score is not None:
                print_quality_check(
                    result.quality_check_passed,
                    result.quality_score,
                    result.quality_threshold or 0.7,
                    result.rejection_reason,
                )

            # Show response preview
            preview = result.content[:150] + "..." if len(result.content) > 150 else result.content
            print(f"\n  {Colors.CYAN}Response{Colors.END}: {preview}")

            # Verify expectations
            complexity_match = result.complexity == test["expected_complexity"]
            routing_match = result.routing_strategy == test["expected_routing"]

            if complexity_match and routing_match:
                print_success("Behavior matches expectations!")
            else:
                print_warning(
                    f"Unexpected behavior (complexity: {complexity_match}, routing: {routing_match})"
                )

            results.append(
                {
                    "test": test["description"],
                    "complexity": result.complexity,
                    "routing": result.routing_strategy,
                    "cascaded": result.cascaded,
                    "accepted": result.draft_accepted if result.cascaded else None,
                    "latency_ms": result.latency_ms,
                    "cost": result.total_cost,
                    "quality_score": result.quality_score,
                    "success": True,
                }
            )

        except Exception as e:
            print_error(f"Test failed: {e}")
            results.append({"test": test["description"], "success": False, "error": str(e)})

        print()  # Spacing

    return results


async def test_tool_cascading(agent):
    """Test tool cascading with different complexity levels."""
    print_header("TOOL CASCADING TESTS", "🔧")

    results = []

    for i, test in enumerate(TOOL_QUERIES, 1):
        print_subheader(f"Test {i}/{len(TOOL_QUERIES)}: {test['description']}", "🔬")
        print(f"  Query: \"{test['query']}\"")
        print(f"  Expected: {test['expected_complexity']} → {test['expected_routing']}")
        print(f"  Tools available: {len(TOOLS)}")

        start = time.time()
        try:
            result = await agent.run(test["query"], tools=TOOLS, max_tokens=150, temperature=0.7)
            (time.time() - start) * 1000

            # Print results
            print_metric("Detected Complexity", result.complexity)
            print_metric("Routing Strategy", result.routing_strategy)
            print_metric("Model Used", result.model_used)
            print_metric("Cascaded", str(result.cascaded))
            print_metric("Has Tool Calls", str(result.has_tool_calls))

            if result.tool_calls:
                print(f"\n  {Colors.GREEN}🎉 TOOL CALLS DETECTED!{Colors.END}")
                for idx, call in enumerate(result.tool_calls, 1):
                    print_tool_call(call, idx)

            if result.cascaded:
                print_metric("Draft Accepted", str(result.draft_accepted))
                if result.draft_accepted:
                    print_success("Draft tool calls were correct!")
                else:
                    print_warning("Draft tool calls rejected, used verifier")

            print_metric("Total Latency", f"{result.latency_ms:.1f}", "ms")
            print_metric("Total Cost", f"${result.total_cost:.6f}")

            # Show quality check for tools
            if result.quality_score is not None:
                print_quality_check(
                    result.quality_check_passed,
                    result.quality_score,
                    result.quality_threshold or 0.7,
                    result.rejection_reason,
                )

            # Show response preview
            if result.content:
                preview = (
                    result.content[:150] + "..." if len(result.content) > 150 else result.content
                )
                print(f"\n  {Colors.CYAN}Response{Colors.END}: {preview}")

            results.append(
                {
                    "test": test["description"],
                    "complexity": result.complexity,
                    "routing": result.routing_strategy,
                    "cascaded": result.cascaded,
                    "accepted": result.draft_accepted if result.cascaded else None,
                    "has_tools": result.has_tool_calls,
                    "tool_count": len(result.tool_calls) if result.tool_calls else 0,
                    "latency_ms": result.latency_ms,
                    "cost": result.total_cost,
                    "success": True,
                }
            )

        except Exception as e:
            print_error(f"Test failed: {e}")
            results.append({"test": test["description"], "success": False, "error": str(e)})

        print()  # Spacing

    return results


async def test_streaming(agent):
    """Test streaming for both text and tools."""
    print_header("STREAMING TESTS", "⚡")

    # Test 1: Text streaming
    print_subheader("Text Streaming Test", "📝")
    print("  Query: 'Explain Python in 50 words'")
    print(f"  {Colors.CYAN}Streaming output{Colors.END}: ", end="", flush=True)

    try:
        start = time.time()
        result = await agent.run_streaming(
            "Explain Python in 50 words",
            max_tokens=100,
            enable_visual=False,  # We'll print manually
        )
        elapsed = (time.time() - start) * 1000

        print()  # New line after streaming
        print_metric("Streaming Latency", f"{elapsed:.1f}", "ms")
        print_metric("Model Used", result.model_used)
        print_success("Text streaming works!")
    except Exception as e:
        print()
        print_error(f"Text streaming failed: {e}")
        import traceback

        traceback.print_exc()

    # Test 2: Tool streaming
    print_subheader("Tool Streaming Test", "🔧")
    print("  Query: 'What's the weather in London?'")
    print(f"  {Colors.CYAN}Streaming with tools{Colors.END}: ", end="", flush=True)

    try:
        start = time.time()
        result = await agent.run_streaming(
            "What's the weather in London?", tools=TOOLS, max_tokens=100, enable_visual=False
        )
        elapsed = (time.time() - start) * 1000

        print()  # New line
        print_metric("Streaming Latency", f"{elapsed:.1f}", "ms")
        print_metric("Has Tool Calls", str(result.has_tool_calls))

        if result.tool_calls:
            print_success("Tool streaming works!")
            for call in result.tool_calls:
                print(f"  🔧 Called: {call['name']}")
        else:
            print_info("No tools called (model's choice)")
    except Exception as e:
        print()
        print_error(f"Tool streaming failed: {e}")
        import traceback

        traceback.print_exc()

    print()


async def analyze_telemetry(agent):
    """Analyze and display comprehensive telemetry."""
    print_header("TELEMETRY ANALYSIS", "📊")

    stats = agent.get_stats()

    # Overall metrics
    print_subheader("Overall Metrics", "📈")
    print_metric("Total Queries", stats.get("total_queries", 0))
    print_metric("Total Cost", f"${stats.get('total_cost', 0):.6f}")
    print_metric("Average Cost/Query", f"${stats.get('avg_cost', 0):.6f}")
    print_metric("Average Latency", f"{stats.get('avg_latency_ms', 0):.1f}", "ms")

    # Routing breakdown
    print_subheader("Routing Breakdown", "🎯")
    cascade_used = stats.get("cascade_used", 0)
    direct_routed = stats.get("direct_routed", 0)
    total = cascade_used + direct_routed

    if total > 0:
        cascade_pct = (cascade_used / total) * 100
        direct_pct = (direct_routed / total) * 100
        print_metric("Cascade Used", f"{cascade_used} ({cascade_pct:.1f}%)")
        print_metric("Direct Routed", f"{direct_routed} ({direct_pct:.1f}%)")

    # Cascade performance - HIGHLIGHT THIS
    if cascade_used > 0:
        print_subheader("⭐ CASCADE PERFORMANCE (KEY METRIC)", "⚡")
        draft_accepted = stats.get("draft_accepted", 0)
        draft_rejected = stats.get("draft_rejected", 0)
        acceptance_rate = stats.get("acceptance_rate", 0)

        print_metric("Drafts Accepted", f"{draft_accepted} ({acceptance_rate:.1f}%)")
        print_metric("Drafts Rejected", draft_rejected)

        if acceptance_rate >= 60:
            print_success("🎉 Excellent acceptance rate!")
        elif acceptance_rate >= 40:
            print_info("✅ Good acceptance rate")
        elif acceptance_rate >= 20:
            print_warning("⚠️  Fair acceptance rate - consider tuning")
        else:
            print_error("❌ Low acceptance rate - needs investigation")

    # Complexity distribution
    print_subheader("Complexity Distribution", "📊")
    by_complexity = stats.get("by_complexity", {})
    for complexity, count in sorted(by_complexity.items()):
        if count > 0:
            pct = (count / total * 100) if total > 0 else 0
            print_metric(complexity.title(), f"{count} ({pct:.1f}%)")

    # Tool usage
    tool_queries = stats.get("tool_queries", 0)
    if tool_queries > 0:
        print_subheader("Tool Usage", "🔧")
        tool_pct = (tool_queries / total * 100) if total > 0 else 0
        print_metric("Queries with Tools", f"{tool_queries} ({tool_pct:.1f}%)")

    # Quality metrics
    if "quality_stats" in stats:
        print_subheader("Quality Metrics", "🎯")
        qs = stats["quality_stats"]
        print_metric("Mean Quality Score", f"{qs.get('mean', 0):.3f}")
        print_metric("Median Quality Score", f"{qs.get('median', 0):.3f}")
        print_metric("Quality Range", f"{qs.get('min', 0):.3f} - {qs.get('max', 0):.3f}")

    # Timing breakdown
    if "timing_stats" in stats:
        print_subheader("Timing Breakdown (Average)", "⏱️")
        ts = stats["timing_stats"]
        for key in ["draft_generation", "quality_verification", "verifier_generation"]:
            avg_key = f"avg_{key}_ms"
            if avg_key in ts:
                print_metric(key.replace("_", " ").title(), f"{ts[avg_key]:.1f}", "ms")

    print()


def print_summary(text_results, tool_results):
    """Print test summary with emphasis on acceptance rates."""
    print_header("📋 TEST SUMMARY - ACCEPTANCE RATE COMPARISON", "📊")

    # Filter successful results
    text_success = [r for r in text_results if r.get("success", True)]
    tool_success = [r for r in tool_results if r.get("success", True)]

    # Text tests summary
    print_subheader("📝 Text Cascading Summary", "")
    cascaded = sum(1 for r in text_success if r.get("cascaded"))
    accepted = sum(1 for r in text_success if r.get("accepted"))

    print_metric("Tests Run", len(text_results))
    print_metric("Successful", len(text_success))
    print_metric("Cascaded", f"{cascaded}/{len(text_success)}")

    if cascaded > 0:
        acceptance_rate = accepted / cascaded * 100
        print(
            f"\n  {Colors.BOLD}{Colors.YELLOW}⭐ TEXT ACCEPTANCE RATE: {acceptance_rate:.1f}%{Colors.END}"
        )
        print_metric("Drafts Accepted", accepted)
        print_metric("Drafts Rejected", cascaded - accepted)

        if acceptance_rate >= 60:
            print_success("Excellent! OpenAI drafter produces high-quality text")
        elif acceptance_rate >= 40:
            print_info("Good acceptance rate for text cascading")
        else:
            print_warning("Text quality may need tuning")

    if text_success:
        avg_latency = sum(r["latency_ms"] for r in text_success) / len(text_success)
        avg_cost = sum(r["cost"] for r in text_success) / len(text_success)
        print_metric("Avg Latency", f"{avg_latency:.1f}", "ms")
        print_metric("Avg Cost", f"${avg_cost:.6f}")

    # Tool tests summary
    print_subheader("🔧 Tool Cascading Summary", "")
    tool_cascaded = sum(1 for r in tool_success if r.get("cascaded"))
    tool_accepted = sum(1 for r in tool_success if r.get("accepted"))
    had_tools = sum(1 for r in tool_success if r.get("has_tools"))

    print_metric("Tests Run", len(tool_results))
    print_metric("Successful", len(tool_success))
    print_metric("Cascaded", f"{tool_cascaded}/{len(tool_success)}")
    print_metric("Tool Calls Made", f"{had_tools}/{len(tool_success)}")

    if tool_cascaded > 0:
        tool_acceptance = tool_accepted / tool_cascaded * 100
        print(
            f"\n  {Colors.BOLD}{Colors.GREEN}⭐ TOOL ACCEPTANCE RATE: {tool_acceptance:.1f}%{Colors.END}"
        )
        print_metric("Drafts Accepted", tool_accepted)
        print_metric("Drafts Rejected", tool_cascaded - tool_accepted)

        if tool_acceptance >= 80:
            print_success("Excellent! Tool validation working perfectly")
        else:
            print_warning("Tool validation may need improvement")

    if tool_success:
        avg_tool_latency = sum(r["latency_ms"] for r in tool_success) / len(tool_success)
        avg_tool_cost = sum(r["cost"] for r in tool_success) / len(tool_success)
        print_metric("Avg Latency", f"{avg_tool_latency:.1f}", "ms")
        print_metric("Avg Cost", f"${avg_tool_cost:.6f}")

    # Comparison
    if cascaded > 0 and tool_cascaded > 0:
        text_rate = accepted / cascaded * 100
        tool_rate = tool_accepted / tool_cascaded * 100
        diff = tool_rate - text_rate

        print_subheader("📊 Acceptance Rate Comparison", "")
        print(f"  {Colors.CYAN}Text Cascading{Colors.END}:  {text_rate:>6.1f}%")
        print(f"  {Colors.CYAN}Tool Cascading{Colors.END}:  {tool_rate:>6.1f}%")
        print(f"  {Colors.CYAN}Difference{Colors.END}:      {diff:>+6.1f}%")

        if diff > 20:
            print_warning("\n⚠️  Large gap between text and tool acceptance")
            print_info("Tool validation is structural, text is confidence-based")
        elif text_rate >= 60 and tool_rate >= 60:
            print_success("\n✅ Both cascading types working well!")

    print()


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================


async def main():
    """Run comprehensive test suite with OpenAI-only configuration."""
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("╔══════════════════════════════════════════════════════════════════════════════╗")
    print("║            CASCADEFLOW COMPREHENSIVE TEST SUITE - OPENAI ONLY               ║")
    print("║                                                                              ║")
    print("║  Tests: Text Cascading, Tool Cascading, Quality, Routing, Streaming         ║")
    print("║  Models: gpt-4o-mini (drafter) + gpt-4o (verifier)                          ║")
    print("║  Focus: Draft Acceptance Rate Analysis                                      ║")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")
    print(Colors.END)

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print_error("OPENAI_API_KEY not found in environment!")
        print_info("Set OPENAI_API_KEY in your .env file")
        return

    # Initialize OpenAI-only agent
    print_info("Initializing OpenAI-only CascadeAgent...")
    try:
        agent = create_openai_only_agent()
        print_success("Agent ready for testing!")
        print()

    except Exception as e:
        print_error(f"Failed to initialize agent: {e}")
        import traceback

        traceback.print_exc()
        return

    # Run tests
    try:
        # Test 1: Text Cascading
        text_results = await test_text_cascading(agent)

        # Test 2: Tool Cascading
        tool_results = await test_tool_cascading(agent)

        # Test 3: Streaming
        await test_streaming(agent)

        # Analyze telemetry
        await analyze_telemetry(agent)

        # Print summary with acceptance rate comparison
        print_summary(text_results, tool_results)

        # Final message
        print_header("✅ TEST SUITE COMPLETE", "🎉")
        print_success("All tests completed!")
        print_info("Key metric: Check the acceptance rate comparison above")
        print_info("OpenAI-only configuration should eliminate Groq errors")

    except Exception as e:
        print_error(f"Test suite failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
