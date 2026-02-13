"""LangSmith tracing example for cascadeflow LangChain integration.

Demonstrates LangSmith integration with cascade metadata tracking.

Run:
    OPENAI_API_KEY=sk-... \
    LANGSMITH_API_KEY=lsv2_pt_... \
    LANGSMITH_PROJECT=cascadeflow-langchain \
    LANGSMITH_TRACING=true \
    python examples/langchain_langsmith.py
"""

import asyncio
import os

from langchain_openai import ChatOpenAI

from cascadeflow.integrations.langchain import CascadeFlow


async def main():
    # Verify environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return
    if not os.getenv("LANGSMITH_API_KEY"):
        print("Error: LANGSMITH_API_KEY environment variable not set")
        return
    if not os.getenv("LANGSMITH_TRACING"):
        print("Warning: LANGSMITH_TRACING not set to 'true'")

    print("=" * 80)
    print("cascadeflow LangSmith Integration - Python")
    print("=" * 80)

    # Check if LangSmith tracing is enabled
    if os.getenv("LANGSMITH_TRACING") == "true":
        print("\n✅ LangSmith tracing enabled")
        print(f"   Project: {os.getenv('LANGSMITH_PROJECT', 'default')}")
        print("   View traces at: https://smith.langchain.com/\n")
    else:
        print("\n⚠️  LangSmith tracing NOT enabled")
        print("   Set LANGSMITH_TRACING=true to enable\n")

    # Setup cascade
    drafter = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    verifier = ChatOpenAI(model="gpt-4o", temperature=0)

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.7,
        enable_cost_tracking=True,
        cost_tracking_provider="cascadeflow",  # Use built-in cost calculation
    )

    print("Running test queries...\n")

    # Test 1: Simple query (high quality, should use drafter)
    print("--- Test 1: Simple Query (High Quality) ---")
    response = await cascade.ainvoke("What is 2 + 2?")
    result = cascade.get_last_cascade_result()

    print(f"Answer: {response.content}")
    print(f"Model used: {result['model_used']}")
    print(f"Quality score: {result['drafter_quality']:.2f}")
    print(f"Cost: ${result['total_cost']:.6f}")
    print(f"Latency: {result['latency_ms']:.0f}ms\n")

    # Test 2: Complex query (may cascade)
    print("--- Test 2: Complex Query ---")
    response = await cascade.ainvoke(
        "Explain the differences between Python's asyncio and threading models, "
        "including when to use each and their performance characteristics."
    )
    result = cascade.get_last_cascade_result()

    print(f"Answer: {response.content[:100]}...")
    print(f"Model used: {result['model_used']}")
    print(f"Quality score: {result['drafter_quality']:.2f}")
    print(f"Accepted: {result['accepted']}")
    print(f"Cost: ${result['total_cost']:.6f}")
    print(f"Latency: {result['latency_ms']:.0f}ms\n")

    # Test 3: Direct query (no cascade metadata expected)
    print("--- Test 3: Streaming Query ---")
    full_content = ""
    async for chunk in cascade.astream("Tell me a short joke about programming."):
        full_content += chunk.content

    result = cascade.get_last_cascade_result()
    print(f"Answer: {full_content}")
    print(f"Model used: {result['model_used']}")
    print(f"Accepted: {result['accepted']}")
    print(f"Cost: ${result['total_cost']:.6f}\n")

    # Test 4: With custom quality threshold
    print("--- Test 4: Custom Quality Threshold ---")
    cascade.quality_threshold = 0.9  # Stricter threshold
    response = await cascade.ainvoke("What is the capital of France?")
    result = cascade.get_last_cascade_result()

    print(f"Answer: {response.content}")
    print(f"Model used: {result['model_used']}")
    print(f"Quality score: {result['drafter_quality']:.2f}")
    print("Threshold: 0.9")
    print(f"Accepted: {result['accepted']}\n")

    print("=" * 80)
    print("📊 Check LangSmith to see cascade metadata in traces:")
    print("   - drafterTokens, verifierTokens")
    print("   - drafterCost, verifierCost, totalCost")
    print("   - savingsPercentage, modelUsed, accepted, drafterQuality")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
