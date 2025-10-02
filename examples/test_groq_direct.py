"""
Direct test of Groq provider with updated models.

Tests real API calls to verify Groq integration works.
"""

import asyncio
import os
from dotenv import load_dotenv
from cascadeflow.providers.groq import GroqProvider

load_dotenv()


async def test_groq_models():
    """Test all current Groq models."""

    print("🧪 Testing Groq Provider\n")

    if not os.getenv("GROQ_API_KEY"):
        print("❌ GROQ_API_KEY not set in .env file")
        print("Get your free key at: https://console.groq.com")
        return

    provider = GroqProvider()

    # All current Groq models
    models = [
        ("llama-3.1-8b-instant", "Fastest, most efficient"),
        ("llama-3.1-70b-versatile", "Most capable, versatile"),
        ("mixtral-8x7b-32768", "Large context window (32K)"),
        ("gemma2-9b-it", "Compact Google model"),
    ]

    test_query = "Say hello to CascadeFlow in a creative way!"

    print(f"Test Query: {test_query}\n")
    print("=" * 70)

    results = []

    for model_name, description in models:
        print(f"\n🔹 Testing: {model_name}")
        print(f"   Description: {description}")
        print("-" * 70)

        try:
            result = await provider.complete(
                prompt=test_query,
                model=model_name,
                max_tokens=100
            )

            print(f"✅ Success!")
            print(f"Response: {result.content}")
            print(f"Cost: ${result.cost:.6f} (FREE!)")
            print(f"Tokens: {result.tokens_used}")
            print(f"Latency: {result.latency_ms:.0f}ms")
            print(f"Confidence: {result.confidence:.2f}")

            results.append({
                "model": model_name,
                "success": True,
                "latency": result.latency_ms
            })

        except Exception as e:
            print(f"❌ Failed: {e}")
            results.append({
                "model": model_name,
                "success": False,
                "error": str(e)
            })

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    successful = sum(1 for r in results if r.get("success"))
    print(f"✅ Successful: {successful}/{len(models)}")

    if successful > 0:
        avg_latency = sum(r.get("latency", 0) for r in results if r.get("success")) / successful
        print(f"📊 Average latency: {avg_latency:.0f}ms")
        print(f"💰 Total cost: $0.00 (All FREE!)")
        print(f"🎉 Groq free tier: 14,400 requests/day")

    if successful < len(models):
        print(f"\n⚠️ Some models failed. Check:")
        print("   1. Is GROQ_API_KEY valid?")
        print("   2. Have you exceeded rate limits?")
        print("   3. Are model names up to date?")

    await provider.client.aclose()


async def quick_test():
    """Quick test with just one model."""

    print("\n\n🚀 Quick Test - Single Model\n")

    if not os.getenv("GROQ_API_KEY"):
        print("❌ GROQ_API_KEY not set")
        return

    provider = GroqProvider()

    try:
        result = await provider.complete(
            prompt="Say 'Hello from CascadeFlow!'",
            model="llama-3.1-8b-instant",
            max_tokens=50
        )

        print(f"✅ Groq is working!")
        print(f"Response: {result.content}")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        await provider.client.aclose()


async def main():
    """Run all tests."""

    print("=" * 70)
    print("🌊 CascadeFlow - Groq Provider Test")
    print("=" * 70)

    await test_groq_models()
    await quick_test()

    print("\n" + "=" * 70)
    print("✅ All tests complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())