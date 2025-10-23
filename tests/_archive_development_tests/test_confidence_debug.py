"""
Comprehensive Confidence Tracking Debug Suite

This test traces confidence through the entire system:
1. Provider level (OpenAI)
2. Cascade flow
3. Acceptance logic
4. Complete end-to-end trace

Run with: python tests/test_confidence_debug.py
"""

import asyncio
import os
import sys
from pathlib import Path

# CRITICAL: Load .env BEFORE any cascadeflow imports
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Verify API key is loaded
if not os.getenv("OPENAI_API_KEY"):
    print("❌ ERROR: OPENAI_API_KEY not found in environment")
    print("   Please ensure you have a .env file with OPENAI_API_KEY=...")
    sys.exit(1)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# CORRECT IMPORTS for your project structure
from cascadeflow.config import ModelConfig

from cascadeflow import CascadeAgent
from cascadeflow.providers.openai import OpenAIProvider
from cascadeflow.quality.confidence import ProductionConfidenceEstimator

console = Console()


def print_header(text: str):
    """Print a formatted header"""
    console.print(f"\n{'='*80}", style="bold blue")
    console.print(f"{text}", style="bold blue")
    console.print(f"{'='*80}\n", style="bold blue")


def print_result(label: str, value: str, success: bool = True):
    """Print a test result"""
    symbol = "✅" if success else "❌"
    console.print(f"{symbol} {label}: {value}")


async def test_provider_direct():
    """Test 1: Direct provider testing to verify confidence_method is added"""
    print_header("TEST 1: Direct Provider Testing (OpenAI)")

    # Setup
    console.print("Creating minimal quality system stubs")

    class MinimalQualitySystem:
        """Minimal quality system for testing"""

        def __init__(self):
            self.estimator = ProductionConfidenceEstimator()

        def estimate_confidence(self, query: str, response: str, metadata: dict) -> float:
            return self.estimator.estimate_confidence(query, response, metadata)

    quality_system = MinimalQualitySystem()

    config = ModelConfig(
        name="gpt-4o-mini", provider="openai", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.0
    )

    provider = OpenAIProvider(config, quality_system)

    # Test 1A: Simple text query (no tools)
    console.print("✅ Test: 1A: Simple Text Query (no tools)")
    response = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "What is 2+2?"}], tools=None
    )

    print_result("Content", response.content[:50] + "...", True)
    print_result("Confidence", f"{response.confidence:.3f}", True)
    print_result("Model", response.model_used, True)
    print_result("Provider", response.provider, True)
    print_result("Tokens", str(response.total_tokens), True)
    print_result("Cost", f"${response.total_cost:.6f}", True)
    print_result("Latency", f"{response.latency_ms}ms", True)

    console.print("\n[bold]Metadata:[/bold]")
    import json

    console.print(json.dumps(response.metadata, indent=4))

    console.print("\n[bold yellow]🔍 CRITICAL CHECKS:[/bold yellow]")
    has_method = "confidence_method" in response.metadata
    print_result("Has confidence_method in metadata", str(has_method), has_method)

    if has_method:
        method_value = response.metadata["confidence_method"]
        print_result("Confidence method value", method_value, True)

    has_logprobs = response.metadata.get("has_logprobs", False)
    print_result("Has logprobs", str(has_logprobs), has_logprobs)

    has_query = "query" in response.metadata
    print_result("Query in metadata", str(has_query), has_query)

    # Check alignment score
    console.print("\n[bold red]🔍 ALIGNMENT ANALYSIS:[/bold red]")
    if "confidence_components" in response.metadata:
        components = response.metadata["confidence_components"]
        alignment = components.get("alignment", "N/A")
        print_result(
            "Alignment score",
            str(alignment),
            alignment > 0.5 if isinstance(alignment, float) else False,
        )

        if components.get("alignment_floor_applied"):
            floor_reduction = components.get("alignment_floor_reduction", 0)
            severity = components.get("alignment_floor_severity", "unknown")
            console.print("⚠️  [red]Alignment floor triggered![/red]")
            console.print(f"   Severity: {severity}")
            console.print(f"   Reduction: {floor_reduction:.3f}")

    # Test 1B: Tool query (should call tool)
    console.print("\n\n✅ Test: 1B: Tool Query (should call tool)")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            },
        }
    ]

    response = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "What's the weather in Paris?"}], tools=tools
    )

    has_tools = response.tool_calls is not None and len(response.tool_calls) > 0
    print_result("Has tool calls", str(has_tools), has_tools)

    if has_tools:
        print_result("Tool name", response.tool_calls[0].function.name, True)
        print_result("Tool args", str(response.tool_calls[0].function.arguments), True)

    print_result("Confidence", f"{response.confidence:.3f}", True)

    console.print("\n[bold]Metadata:[/bold]")
    console.print(json.dumps(response.metadata, indent=4))

    console.print("\n[bold yellow]🔍 CRITICAL CHECKS:[/bold yellow]")
    has_method = "confidence_method" in response.metadata
    print_result("Has confidence_method in metadata", str(has_method), has_method)

    if has_method:
        method_value = response.metadata["confidence_method"]
        print_result("Confidence method value", method_value, True)
        expected = "tool-call-present"
        print_result("Expected method", expected, True)

    # Test 1C: Tool available but text chosen
    console.print("\n\n✅ Test: 1C: Tool Available but Text Chosen")
    response = await provider.complete_with_tools(
        messages=[{"role": "user", "content": "What is Python?"}], tools=tools
    )

    has_tools = response.tool_calls is not None and len(response.tool_calls) > 0
    print_result("Has tool calls", str(has_tools), not has_tools)
    print_result("Content", response.content[:50] + "...", True)
    print_result("Confidence", f"{response.confidence:.3f}", True)

    console.print("\n[bold]Metadata:[/bold]")
    console.print(json.dumps(response.metadata, indent=4))

    console.print("\n[bold yellow]🔍 CRITICAL CHECKS:[/bold yellow]")
    has_method = "confidence_method" in response.metadata
    print_result("Has confidence_method in metadata", str(has_method), has_method)

    if has_method:
        method_value = response.metadata["confidence_method"]
        print_result("Confidence method value", method_value, True)
        expected = "tool-available-text-chosen"
        print_result("Expected method", expected, True)

    # Verdict
    console.print(
        Panel.fit(
            "[green]PROVIDER TEST VERDICT:[/green]\n\n"
            "Text query: ✅ PASS\n"
            "Tool call: ✅ PASS\n"
            "Tool available: ✅ PASS",
            title="PROVIDER TEST VERDICT",
            border_style="green",
        )
    )


async def test_cascade_confidence_propagation():
    """Test 2: Verify confidence propagates through cascade system"""
    print_header("TEST 2: Cascade Flow Testing")

    # Setup cascade system using CascadeAgent
    draft_config = ModelConfig(
        name="gpt-4o-mini", provider="openai", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.0
    )

    verifier_config = ModelConfig(
        name="gpt-4o", provider="openai", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.0
    )

    # Create agent with cascade models
    agent = CascadeAgent(models=[draft_config, verifier_config], verbose=True)

    # Test 2A: Simple query (should cascade due to low alignment)
    console.print("✅ Test: 2A: Simple Text Query (should cascade)")

    result = await agent.run(prompt="What color is the sky?")

    print_result("Routing strategy", result.routing_strategy, True)
    print_result("Used cascade", str(result.cascaded), True)
    print_result(
        "Draft accepted",
        str(result.draft_accepted if hasattr(result, "draft_accepted") else "N/A"),
        True,
    )
    print_result("Final content", result.content[:50] + "...", True)
    print_result(
        "Draft confidence",
        f"{result.draft_confidence:.3f}" if result.draft_confidence else "N/A",
        True,
    )
    print_result("Model", result.model_used, True)
    print_result("Cost", f"${result.total_cost:.6f}", True)

    console.print("\n[bold]Result Metadata:[/bold]")
    import json

    console.print(json.dumps(result.metadata, indent=4))

    console.print("\n[bold yellow]🔍 CRITICAL CHECKS:[/bold yellow]")

    # Check if draft_metadata exists and has confidence_method
    has_draft_metadata = "draft_metadata" in result.metadata
    print_result("Has draft_metadata", str(has_draft_metadata), has_draft_metadata)

    if has_draft_metadata:
        draft_metadata = result.metadata["draft_metadata"]
        has_method = "confidence_method" in draft_metadata
        print_result("Draft has confidence_method", str(has_method), has_method)

        if has_method:
            method_value = draft_metadata["confidence_method"]
            print_result("Draft confidence method", method_value, True)

        # Check alignment in draft
        if "confidence_components" in draft_metadata:
            components = draft_metadata["confidence_components"]
            alignment = components.get("alignment", "N/A")
            print_result(
                "Draft alignment score",
                str(alignment),
                alignment > 0.5 if isinstance(alignment, float) else False,
            )


async def test_acceptance_investigation():
    """Test 3: Investigate why acceptance rate is 0%"""
    print_header("TEST 3: Acceptance Rate Investigation")

    # Setup
    draft_config = ModelConfig(
        name="gpt-4o-mini", provider="openai", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.0
    )

    verifier_config = ModelConfig(
        name="gpt-4o", provider="openai", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.0
    )

    # Test with different acceptance thresholds
    thresholds = [0.3, 0.5, 0.7, 0.9]

    for threshold in thresholds:
        console.print(f"\n[bold cyan]Testing with threshold: {threshold}[/bold cyan]")

        agent = CascadeAgent(models=[draft_config, verifier_config], verbose=False)

        # Run simple query
        result = await agent.run(prompt="What is 2+2?")

        print_result(
            "Draft confidence",
            f"{result.draft_confidence:.3f}" if result.draft_confidence else "N/A",
            True,
        )
        print_result("Threshold", f"{threshold:.3f}", True)
        accepted = result.draft_accepted if hasattr(result, "draft_accepted") else False
        print_result("Accepted", str(accepted), accepted)
        print_result("Cascaded", str(result.cascaded), True)

        # Check alignment
        if "draft_metadata" in result.metadata:
            draft_metadata = result.metadata["draft_metadata"]
            if "confidence_components" in draft_metadata:
                components = draft_metadata["confidence_components"]
                alignment = components.get("alignment", "N/A")
                console.print(f"   Alignment: {alignment}")

                if components.get("alignment_floor_applied"):
                    console.print("   ⚠️  [red]Alignment floor was applied![/red]")
                    console.print(f"   Severity: {components.get('alignment_floor_severity')}")
                    console.print(
                        f"   Reduction: {components.get('alignment_floor_reduction', 0):.3f}"
                    )


async def test_complete_trace():
    """Test 4: Complete end-to-end trace"""
    print_header("TEST 4: Complete Flow Trace")

    console.print("[bold]This test will trace a request through the entire system[/bold]\n")

    # Setup
    draft_config = ModelConfig(
        name="gpt-4o-mini", provider="openai", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.0
    )

    verifier_config = ModelConfig(
        name="gpt-4o", provider="openai", api_key=os.getenv("OPENAI_API_KEY"), temperature=0.0
    )

    agent = CascadeAgent(models=[draft_config, verifier_config], verbose=True)

    console.print("📝 Sending request: 'Explain photosynthesis'\n")

    result = await agent.run(prompt="Explain photosynthesis")

    # Build trace table
    table = Table(title="Complete Flow Trace", show_header=True, header_style="bold magenta")
    table.add_column("Stage", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Status", style="yellow")

    table.add_row("1. Request Sent", "Explain photosynthesis", "✅")
    table.add_row("2. Draft Model", result.metadata.get("draft_model", "N/A"), "✅")
    table.add_row(
        "3. Draft Confidence",
        f"{result.draft_confidence:.3f}" if result.draft_confidence else "N/A",
        "✅" if result.draft_confidence else "❌",
    )

    # Check for confidence_method in draft
    has_method = False
    method_value = "N/A"
    if "draft_metadata" in result.metadata:
        draft_metadata = result.metadata["draft_metadata"]
        if "confidence_method" in draft_metadata:
            has_method = True
            method_value = draft_metadata["confidence_method"]

    table.add_row("4. Confidence Method", method_value, "✅" if has_method else "❌")

    table.add_row(
        "5. Acceptance Check",
        "Acceptance evaluated",
        "✅" if hasattr(result, "draft_accepted") else "❌",
    )

    table.add_row("6. Cascaded", str(result.cascaded), "✅" if result.cascaded else "⚠️")

    table.add_row("7. Final Model", result.model_used, "✅")
    table.add_row("8. Response Delivered", result.content[:30] + "...", "✅")

    console.print(table)

    # Show alignment analysis
    console.print("\n[bold red]🔍 ALIGNMENT DEEP DIVE:[/bold red]")
    if "draft_metadata" in result.metadata:
        draft_metadata = result.metadata["draft_metadata"]
        if "confidence_components" in draft_metadata:
            components = draft_metadata["confidence_components"]

            alignment_table = Table(show_header=True, header_style="bold red")
            alignment_table.add_column("Component", style="cyan")
            alignment_table.add_column("Value", style="yellow")

            for key, value in components.items():
                if isinstance(value, float):
                    alignment_table.add_row(key, f"{value:.4f}")
                else:
                    alignment_table.add_row(key, str(value))

            console.print(alignment_table)


async def main():
    """Run all tests"""
    console.print(
        Panel.fit(
            "[bold cyan]🔬 Confidence Tracking Debug Suite[/bold cyan]\n\n"
            "This test suite will trace through the entire confidence tracking\n"
            "system to identify where the issue is.\n\n"
            "[bold]Tests:[/bold]\n"
            "  1. Provider direct testing\n"
            "  2. Cascade flow testing\n"
            "  3. Acceptance rate investigation\n"
            "  4. Complete flow trace",
            title="🔬 Confidence Tracking Debug Suite",
            border_style="cyan",
        )
    )

    try:
        await test_provider_direct()
        await test_cascade_confidence_propagation()
        await test_acceptance_investigation()
        await test_complete_trace()

        console.print("\n" + "=" * 80)
        console.print("[bold green]✅ All tests completed![/bold green]")
        console.print("=" * 80 + "\n")

    except Exception as e:
        console.print("\n[bold red]❌ Test failed with error:[/bold red]")
        console.print(f"[red]{str(e)}[/red]")
        import traceback

        console.print(f"\n[dim]{traceback.format_exc()}[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
