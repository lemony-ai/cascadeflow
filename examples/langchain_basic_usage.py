"""Basic usage example for CascadeFlow LangChain integration.

This example demonstrates:
- Basic cascade setup with OpenAI models
- Automatic quality-based routing
- Cost tracking with metadata
- Accessing cascade results

Run:
    OPENAI_API_KEY=your-key python examples/langchain_basic_usage.py
"""

import asyncio
import os

from langchain_openai import ChatOpenAI

from cascadeflow.integrations.langchain import CascadeFlow


async def main():
    # Verify API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return

    print("=" * 60)
    print("CascadeFlow LangChain Integration - Basic Usage")
    print("=" * 60)

    # Setup drafter (cheap, fast) and verifier (expensive, accurate)
    drafter = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    verifier = ChatOpenAI(model="gpt-4o", temperature=0)

    # Create cascade with quality threshold
    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.7,
        enable_cost_tracking=True,
        cost_tracking_provider="cascadeflow",  # Use built-in pricing
    )

    print("\n1. Testing with simple question (should use drafter):")
    print("-" * 60)

    response = await cascade.ainvoke("What is 2+2?")
    result = cascade.get_last_cascade_result()

    print("\nQuestion: What is 2+2?")
    print(f"Response: {response.content}")
    print(f"\nModel used: {result['model_used']}")
    print(f"Drafter quality: {result.get('drafter_quality', 0):.2f}")
    print(f"Accepted: {result['accepted']}")
    print(f"Drafter cost: ${result['drafter_cost']:.6f}")
    print(f"Verifier cost: ${result['verifier_cost']:.6f}")
    print(f"Total cost: ${result['total_cost']:.6f}")
    print(f"Savings: {result['savings_percentage']:.1f}%")
    print(f"Latency: {result['latency_ms']:.0f}ms")

    print("\n2. Testing with complex question (may use verifier):")
    print("-" * 60)

    response = await cascade.ainvoke(
        "Explain the difference between synchronous and asynchronous programming "
        "in Python, including examples and best practices."
    )
    result = cascade.get_last_cascade_result()

    print("\nQuestion: Explain sync vs async in Python...")
    print(f"Response: {response.content[:200]}...")
    print(f"\nModel used: {result['model_used']}")
    print(f"Drafter quality: {result.get('drafter_quality', 0):.2f}")
    print(f"Accepted: {result['accepted']}")
    print(f"Drafter cost: ${result['drafter_cost']:.6f}")
    print(f"Verifier cost: ${result['verifier_cost']:.6f}")
    print(f"Total cost: ${result['total_cost']:.6f}")
    print(f"Savings: {result['savings_percentage']:.1f}%")
    print(f"Latency: {result['latency_ms']:.0f}ms")

    print("\n3. Testing bind() method:")
    print("-" * 60)

    # Create a bound instance with temperature
    bound_cascade = cascade.bind(temperature=1.0)

    response = await bound_cascade.ainvoke("Tell me a creative story in one sentence.")
    result = bound_cascade.get_last_cascade_result()

    print("\nQuestion: Tell me a creative story...")
    print(f"Response: {response.content}")
    print(f"\nModel used: {result['model_used']}")
    print(f"Accepted: {result['accepted']}")

    print("\n" + "=" * 60)
    print("Basic usage demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
