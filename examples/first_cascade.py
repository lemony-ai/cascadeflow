"""
First working cascade example.

This demonstrates a real cascade between OpenAI models.
"""

import asyncio
import os
from dotenv import load_dotenv

from cascadeflow import ModelConfig
from cascadeflow.providers import OpenAIProvider

# Load environment variables
load_dotenv()


async def main():
    """Run first cascade example."""

    print("🌊 CascadeFlow - First Real Cascade\n")

    # Check if API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not set")
        print("Please add it to your .env file")
        return

    # Initialize provider
    provider = OpenAIProvider()

    # Test with simple query
    query = "Explain AI in one sentence"

    print(f"Query: {query}\n")
    print("Trying GPT-3.5 Turbo (cheap)...")

    try:
        # Try cheap model first
        result = await provider.complete(
            prompt=query,
            model="gpt-3.5-turbo",
            max_tokens=100
        )

        print(f"✅ Success!")
        print(f"Response: {result.content}")
        print(f"Cost: ${result.cost:.6f}")
        print(f"Tokens: {result.tokens_used}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Latency: {result.latency_ms:.0f}ms")

        # If confidence is low, we would cascade to GPT-4
        if result.confidence < 0.7:
            print("\n⚠️ Low confidence, would cascade to GPT-4...")
            print("(Skipping actual GPT-4 call to save money)")
        else:
            print("\n✅ High confidence, no cascade needed!")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        await provider.client.aclose()


if __name__ == "__main__":
    asyncio.run(main())