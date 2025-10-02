"""
Basic usage example for CascadeFlow.

Demonstrates the simplest way to use CascadeFlow.
"""

import asyncio
import os
from dotenv import load_dotenv

from cascadeflow import ModelConfig
from cascadeflow.providers import GroqProvider, OpenAIProvider

# Load environment variables
load_dotenv()


async def main():
    """Basic usage example."""

    print("🌊 CascadeFlow - Basic Usage\n")

    # Check which providers are available
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))

    if not has_groq and not has_openai:
        print("❌ No API keys found!")
        print("Please set GROQ_API_KEY or OPENAI_API_KEY in .env")
        return

    # Simple query
    query = "What is artificial intelligence in one sentence?"

    print(f"Query: {query}\n")

    # Example 1: Using Groq (free)
    if has_groq:
        print("Example 1: Using Groq (FREE)")
        print("-" * 50)

        provider = GroqProvider()

        try:
            result = await provider.complete(
                prompt=query,
                model="llama-3.1-8b-instant",
                max_tokens=100
            )

            print(f"✅ Success!")
            print(f"Response: {result.content}")
            print(f"Cost: ${result.cost:.6f} (FREE!)")
            print(f"Tokens: {result.tokens_used}")
            print(f"Latency: {result.latency_ms:.0f}ms")

        except Exception as e:
            print(f"❌ Error: {e}")

        finally:
            await provider.client.aclose()

    # Example 2: Using OpenAI (paid)
    if has_openai:
        print("\n\nExample 2: Using OpenAI (PAID)")
        print("-" * 50)

        provider = OpenAIProvider()

        try:
            result = await provider.complete(
                prompt=query,
                model="gpt-3.5-turbo",
                max_tokens=100
            )

            print(f"✅ Success!")
            print(f"Response: {result.content}")
            print(f"Cost: ${result.cost:.6f}")
            print(f"Tokens: {result.tokens_used}")
            print(f"Latency: {result.latency_ms:.0f}ms")

        except Exception as e:
            print(f"❌ Error: {e}")

        finally:
            await provider.client.aclose()

    # Summary
    print("\n" + "=" * 50)
    print("💡 Key Takeaways:")
    if has_groq:
        print("  - Groq is FREE and fast")
    if has_openai:
        print("  - OpenAI is paid but high quality")
    if has_groq and has_openai:
        print("  - Use Groq first, cascade to OpenAI if needed")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())