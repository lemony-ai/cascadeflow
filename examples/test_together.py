"""Test Together.ai provider with real API."""

import asyncio
import os
from dotenv import load_dotenv

from cascadeflow.providers.together import TogetherProvider

load_dotenv()


async def main():
    """Test Together.ai provider."""
    print("Together.ai Provider Test\n")

    # Check API key
    if not os.getenv("TOGETHER_API_KEY"):
        print("❌ Error: TOGETHER_API_KEY not set")
        print("Get key at: https://api.together.xyz/settings/api-keys")
        print("New signups get $25 free credits!")
        return

    print("✓ TOGETHER_API_KEY found")

    # Initialize provider
    provider = TogetherProvider()

    # Test model
    model = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
    print(f"\nUsing model: {model}")

    # Test completion
    print("\nTesting completion...")
    query = "What is artificial intelligence in one sentence?"

    try:
        result = await provider.complete(
            prompt=query,
            model=model,
            max_tokens=100
        )

        print(f"\n✅ Success!")
        print(f"Response: {result.content}")
        print(f"Tokens: {result.tokens_used}")
        print(f"Latency: {result.latency_ms:.0f}ms")
        print(f"Cost: ${result.cost:.6f}")
        print(f"Confidence: {result.confidence:.2f}")

    except Exception as e:
        print(f"\n❌ Error: {e}")

    finally:
        await provider.client.aclose()


if __name__ == "__main__":
    asyncio.run(main())