#!/usr/bin/env python3
"""
Interactive Terminal Streaming Demo
===================================

Demonstrates CascadeFlow streaming in terminal with visual feedback.

Features:
- Real-time streaming output
- Visual pulsing dot indicator
- Cascade switch notifications
- Performance metrics
- Interactive mode

Run:
    python demo_streaming.py

Or run specific demo:
    python demo_streaming.py --demo simple
    python demo_streaming.py --demo cascade
    python demo_streaming.py --demo interactive
"""

import argparse
import asyncio
import sys
import time

from dotenv import load_dotenv

# Load environment
load_dotenv()

from cascadeflow.agent import CascadeAgent

# ============================================================================
# DEMO QUERIES
# ============================================================================

DEMO_QUERIES = {
    "simple": [
        "What is Python?",
        "Explain how photosynthesis works",
        "What are the primary colors?",
    ],
    "complex": [
        "Explain quantum entanglement and its implications for quantum computing",
        "Analyze the economic impact of artificial intelligence on labor markets",
        "Discuss the philosophical implications of consciousness in AI systems",
    ],
    "trivial": [
        "What is 2+2?",
        "Name a color",
        "What is the capital of France?",
    ],
}


# ============================================================================
# VISUAL FORMATTING
# ============================================================================


class Colors:
    """Terminal color codes."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}\n")


def print_subheader(text: str):
    """Print a formatted subheader."""
    print(f"\n{Colors.BOLD}{Colors.YELLOW}{text}{Colors.RESET}")
    print(f"{Colors.DIM}{'─'*70}{Colors.RESET}")


def print_info(label: str, value: str, color=Colors.WHITE):
    """Print formatted info."""
    print(f"{Colors.DIM}{label}:{Colors.RESET} {color}{value}{Colors.RESET}")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")


# ============================================================================
# DEMO FUNCTIONS
# ============================================================================


async def demo_simple_streaming():
    """Demo 1: Simple streaming with visual feedback."""
    print_header("DEMO 1: Simple Streaming")

    # Create agent
    agent = CascadeAgent.from_env(verbose=False)

    query = DEMO_QUERIES["simple"][0]

    print_info("Query", query, Colors.CYAN)
    print_info("Mode", "Streaming with visual feedback", Colors.YELLOW)

    print_subheader("Streaming Output")

    # Stream with visual feedback
    start_time = time.time()
    result = await agent.run_streaming(query, max_tokens=150, enable_visual=True)
    elapsed = (time.time() - start_time) * 1000

    # Display result
    print("\n")
    print_subheader("Result")
    print(f"\n{result.content}\n")

    print_subheader("Metrics")
    print_info("Model", result.model_used, Colors.GREEN)
    print_info("Strategy", result.routing_strategy, Colors.BLUE)
    print_info("Cascaded", str(result.cascaded), Colors.MAGENTA)
    print_info(
        "Draft accepted",
        str(result.draft_accepted),
        Colors.GREEN if result.draft_accepted else Colors.RED,
    )
    print_info("Cost", f"${result.total_cost:.6f}", Colors.YELLOW)
    print_info("Latency", f"{elapsed:.1f}ms", Colors.CYAN)

    print_success("Simple streaming demo complete!")


async def demo_cascade_comparison():
    """Demo 2: Compare cascade vs direct routing with streaming."""
    print_header("DEMO 2: Cascade vs Direct Routing")

    agent = CascadeAgent.from_env(verbose=False)

    # Test 1: Simple query (should cascade)
    print_subheader("Test 1: Simple Query (Expected: Cascade)")

    query1 = DEMO_QUERIES["simple"][0]
    print_info("Query", query1[:60] + "...", Colors.CYAN)

    print("\n🔄 Streaming...")
    start1 = time.time()
    result1 = await agent.run_streaming(query1, max_tokens=100, enable_visual=True)
    elapsed1 = (time.time() - start1) * 1000

    print("\n")
    print_info("Strategy", result1.routing_strategy, Colors.BLUE)
    print_info("Cascaded", str(result1.cascaded), Colors.GREEN)
    print_info("Model", result1.model_used, Colors.MAGENTA)
    print_info("Latency", f"{elapsed1:.1f}ms", Colors.CYAN)

    # Test 2: Complex query (should use direct)
    print_subheader("Test 2: Complex Query (Expected: Direct)")

    query2 = DEMO_QUERIES["complex"][0]
    print_info("Query", query2[:60] + "...", Colors.CYAN)

    print("\n🔄 Streaming...")
    start2 = time.time()
    result2 = await agent.run_streaming(query2, max_tokens=150, enable_visual=True)
    elapsed2 = (time.time() - start2) * 1000

    print("\n")
    print_info("Strategy", result2.routing_strategy, Colors.BLUE)
    print_info("Cascaded", str(result2.cascaded), Colors.RED)
    print_info("Model", result2.model_used, Colors.MAGENTA)
    print_info("Latency", f"{elapsed2:.1f}ms", Colors.CYAN)

    # Comparison
    print_subheader("Comparison")
    print(f"\n{Colors.BOLD}Simple Query (Cascade):{Colors.RESET}")
    print(f"  └─ Strategy: {Colors.GREEN}cascade{Colors.RESET}")
    print(f"  └─ Latency: {Colors.CYAN}{elapsed1:.1f}ms{Colors.RESET}")
    print(f"  └─ Cost: {Colors.YELLOW}${result1.total_cost:.6f}{Colors.RESET}")

    print(f"\n{Colors.BOLD}Complex Query (Direct):{Colors.RESET}")
    print(f"  └─ Strategy: {Colors.BLUE}direct{Colors.RESET}")
    print(f"  └─ Latency: {Colors.CYAN}{elapsed2:.1f}ms{Colors.RESET}")
    print(f"  └─ Cost: {Colors.YELLOW}${result2.total_cost:.6f}{Colors.RESET}")

    print_success("Cascade comparison demo complete!")


async def demo_batch_streaming():
    """Demo 3: Batch queries with streaming."""
    print_header("DEMO 3: Batch Streaming")

    agent = CascadeAgent.from_env(verbose=False)

    queries = DEMO_QUERIES["trivial"]

    print_info("Queries", f"{len(queries)} trivial queries", Colors.CYAN)
    print_subheader("Processing")

    results = []
    for i, query in enumerate(queries, 1):
        print(f"\n{Colors.BOLD}Query {i}/{len(queries)}:{Colors.RESET} {query}")

        start = time.time()
        result = await agent.run_streaming(query, max_tokens=50, enable_visual=True)
        elapsed = (time.time() - start) * 1000

        results.append({"query": query, "result": result, "elapsed_ms": elapsed})

        print(
            f"  {Colors.DIM}└─{Colors.RESET} {result.content[:50]}... "
            f"{Colors.CYAN}({elapsed:.0f}ms){Colors.RESET}"
        )

    # Statistics
    print_subheader("Statistics")

    total_time = sum(r["elapsed_ms"] for r in results)
    avg_time = total_time / len(results)
    total_cost = sum(r["result"].total_cost for r in results)
    cascaded = sum(1 for r in results if r["result"].cascaded)
    accepted = sum(1 for r in results if r["result"].cascaded and r["result"].draft_accepted)

    print_info("Total queries", str(len(results)), Colors.WHITE)
    print_info("Total time", f"{total_time:.1f}ms", Colors.CYAN)
    print_info("Avg time/query", f"{avg_time:.1f}ms", Colors.CYAN)
    print_info("Total cost", f"${total_cost:.6f}", Colors.YELLOW)
    print_info("Cascaded", f"{cascaded}/{len(results)}", Colors.GREEN)
    if cascaded > 0:
        print_info(
            "Draft acceptance",
            f"{accepted}/{cascaded} ({accepted/cascaded*100:.0f}%)",
            Colors.GREEN,
        )

    print_success("Batch streaming demo complete!")


async def demo_interactive():
    """Demo 4: Interactive streaming mode."""
    print_header("DEMO 4: Interactive Streaming")

    agent = CascadeAgent.from_env(verbose=False)

    print(f"{Colors.BOLD}Enter your queries (or 'quit' to exit):{Colors.RESET}\n")

    while True:
        try:
            # Get query from user
            query = input(f"{Colors.CYAN}Query>{Colors.RESET} ").strip()

            if query.lower() in ["quit", "exit", "q"]:
                print_success("Goodbye!")
                break

            if not query:
                continue

            # Process query
            print(f"\n{Colors.DIM}Processing...{Colors.RESET}")

            start = time.time()
            result = await agent.run_streaming(query, max_tokens=200, enable_visual=True)
            elapsed = (time.time() - start) * 1000

            # Display result
            print(f"\n{Colors.BOLD}Response:{Colors.RESET}")
            print(f"{result.content}\n")

            # Display metadata
            print(f"{Colors.DIM}┌─ Metadata ─────────────────────────{Colors.RESET}")
            print(f"{Colors.DIM}│{Colors.RESET} Strategy: {result.routing_strategy}")
            print(f"{Colors.DIM}│{Colors.RESET} Model: {result.model_used}")
            print(f"{Colors.DIM}│{Colors.RESET} Cost: ${result.total_cost:.6f}")
            print(f"{Colors.DIM}│{Colors.RESET} Latency: {elapsed:.1f}ms")
            print(f"{Colors.DIM}└────────────────────────────────────{Colors.RESET}\n")

        except KeyboardInterrupt:
            print("\n")
            print_success("Interrupted. Goodbye!")
            break
        except Exception as e:
            print_error(f"Error: {e}")


async def demo_all():
    """Run all demos in sequence."""
    await demo_simple_streaming()
    await asyncio.sleep(1)

    await demo_cascade_comparison()
    await asyncio.sleep(1)

    await demo_batch_streaming()
    await asyncio.sleep(1)

    print_header("All Demos Complete!")
    print(f"\n{Colors.BOLD}To run interactive mode:{Colors.RESET}")
    print("  python demo_streaming.py --demo interactive\n")


# ============================================================================
# MAIN
# ============================================================================


async def main():
    parser = argparse.ArgumentParser(description="CascadeFlow Streaming Demo")
    parser.add_argument(
        "--demo",
        choices=["simple", "cascade", "batch", "interactive", "all"],
        default="all",
        help="Which demo to run (default: all)",
    )

    args = parser.parse_args()

    # Print welcome
    print_header("🌊 CascadeFlow Streaming Demo 🌊")
    print(f"{Colors.DIM}Interactive demonstration of streaming features{Colors.RESET}\n")

    # Check TTY
    if not sys.stdout.isatty():
        print_warning("Not running in a TTY - visual feedback will be limited")

    # Run selected demo
    try:
        if args.demo == "simple":
            await demo_simple_streaming()
        elif args.demo == "cascade":
            await demo_cascade_comparison()
        elif args.demo == "batch":
            await demo_batch_streaming()
        elif args.demo == "interactive":
            await demo_interactive()
        elif args.demo == "all":
            await demo_all()
    except Exception as e:
        print_error(f"Demo failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
