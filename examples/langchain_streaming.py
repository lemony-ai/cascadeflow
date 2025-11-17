"""Streaming example with CascadeFlow LangChain integration.

Demonstrates optimistic drafter streaming with mid-stream cascade.

The streaming pattern:
1. Stream drafter optimistically (user sees real-time output)
2. Collect chunks and check quality after completion
3. If quality insufficient: show switch message + stream verifier

Run:
    OPENAI_API_KEY=sk-... python examples/langchain_streaming.py
"""

import asyncio
import os
import sys
from langchain_openai import ChatOpenAI

# Add parent directory to path for local import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cascadeflow.integrations.langchain import CascadeFlow


async def demo_streaming_simple():
    """Demo streaming with a simple query (drafter accepted)."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Simple Query (Drafter Accepted)")
    print("=" * 80)
    print("\nQuery: What is Python?\n")

    drafter = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    verifier = ChatOpenAI(model="gpt-4o", temperature=0)

    cascade = CascadeFlow(
        drafter=drafter, verifier=verifier, quality_threshold=0.7  # Most queries will pass
    )

    # Stream the response
    print("Streaming response:")
    print("-" * 80)
    async for chunk in cascade.astream("What is Python?"):
        print(chunk.content, end="", flush=True)
    print("\n" + "-" * 80)

    # Show cascade result
    result = cascade.get_last_cascade_result()
    if result:
        print(f"\nModel used: {result['model_used']}")
        print(f"Drafter quality: {result.get('drafter_quality', 'N/A')}")
        print(f"Accepted: {result['accepted']}")
        print(f"Latency: {result['latency_ms']:.0f}ms")


async def demo_streaming_complex():
    """Demo streaming with a complex query (drafter rejected)."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Complex Query (Drafter Rejected → Cascade)")
    print("=" * 80)

    complex_query = """Explain the quantum mechanical principles behind
Bose-Einstein condensation and how it relates to superfluidity."""

    print(f"\nQuery: {complex_query}\n")

    drafter = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    verifier = ChatOpenAI(model="gpt-4o", temperature=0)

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.9,  # High threshold - drafter likely fails
    )

    # Stream the response
    print("Streaming response:")
    print("-" * 80)
    async for chunk in cascade.astream(complex_query):
        print(chunk.content, end="", flush=True)
    print("\n" + "-" * 80)

    # Show cascade result
    result = cascade.get_last_cascade_result()
    if result:
        print(f"\nModel used: {result['model_used']}")
        print(f"Drafter quality: {result.get('drafter_quality', 'N/A')}")
        print(f"Accepted: {result['accepted']}")
        print(f"Latency: {result['latency_ms']:.0f}ms")


async def demo_streaming_with_prerouter():
    """Demo streaming with PreRouter enabled."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Streaming with PreRouter")
    print("=" * 80)

    from cascadeflow.integrations.langchain.routers import create_pre_router

    drafter = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    verifier = ChatOpenAI(model="gpt-4o", temperature=0)

    # Create PreRouter with verbose mode
    pre_router = create_pre_router(
        {
            "enable_cascade": True,
            "cascade_complexities": ["trivial", "simple", "moderate"],
            "verbose": True,
        }
    )

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.7,
        enable_pre_router=True,
        pre_router=pre_router,
    )

    # Test with simple query (should cascade)
    simple_query = "What is 2+2?"
    print(f"\nQuery 1: {simple_query}\n")
    print("Streaming response:")
    print("-" * 80)
    async for chunk in cascade.astream(simple_query):
        print(chunk.content, end="", flush=True)
    print("\n" + "-" * 80)

    result1 = cascade.get_last_cascade_result()
    if result1:
        print(f"Model used: {result1['model_used']}")
        print(f"Accepted: {result1['accepted']}")

    # Test with complex query (should go direct)
    complex_query = """Derive the Navier-Stokes equations from first principles
using tensor calculus and explain the Reynolds number."""

    print(f"\n\nQuery 2: {complex_query}\n")
    print("Streaming response:")
    print("-" * 80)
    async for chunk in cascade.astream(complex_query):
        print(chunk.content, end="", flush=True)
    print("\n" + "-" * 80)

    result2 = cascade.get_last_cascade_result()
    if result2:
        print(f"Model used: {result2['model_used']}")
        print(f"Accepted: {result2['accepted']}")

    # Show PreRouter stats
    print("\n")
    pre_router.print_stats()


async def main():
    """Run all streaming examples."""
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Usage: OPENAI_API_KEY=sk-... python examples/langchain_streaming.py")
        return

    print("\n" + "=" * 80)
    print("CascadeFlow LangChain - Streaming Examples")
    print("=" * 80)
    print("\nDemonstrating optimistic drafter streaming with mid-stream cascade.\n")

    # Run examples
    await demo_streaming_simple()
    await demo_streaming_complex()
    await demo_streaming_with_prerouter()

    print("\n" + "=" * 80)
    print("All streaming examples completed!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
