"""Practical examples of using HuggingFace with CascadeFlow.

Shows real-world usage patterns for all three endpoint types.
"""

import asyncio
import os
from dotenv import load_dotenv

from cascadeflow import ModelConfig, CascadeAgent
from cascadeflow.providers.huggingface import HuggingFaceProvider

load_dotenv()


async def example_1_serverless_simple():
    """Example 1: Simple serverless usage (free tier)."""
    print("\n" + "="*70)
    print("Example 1: Simple Serverless Usage (Free)")
    print("="*70)

    if not os.getenv("HF_TOKEN"):
        print("❌ Skipped: HF_TOKEN not set")
        return

    # Direct provider usage
    provider = HuggingFaceProvider.serverless()

    try:
        result = await provider.complete(
            model="gpt2",
            prompt="Explain AI in one sentence",
            max_tokens=30
        )

        print(f"✅ Success!")
        print(f"Response: {result.content}")
        print(f"Cost: ${result.cost:.6f} (free)")

    except Exception as e:
        print(f"❌ Failed: {e}")

    await provider.client.aclose()


async def example_2_serverless_in_cascade():
    """Example 2: Serverless in a cascade (free tier first)."""
    print("\n" + "="*70)
    print("Example 2: Serverless in Cascade")
    print("="*70)

    if not os.getenv("HF_TOKEN"):
        print("❌ Skipped: HF_TOKEN not set")
        return

    # Build cascade with serverless
    models = [
        ModelConfig(
            name="gpt2",
            provider="huggingface",
            base_url="https://api-inference.huggingface.co",
            cost=0.0,
            keywords=["simple"]
        ),
        ModelConfig(
            name="gpt-3.5-turbo",
            provider="openai",
            cost=0.002
        ),
    ]

    agent = CascadeAgent(models, verbose=True)

    try:
        result = await agent.run("What is 2+2?")

        print(f"\n✅ Result:")
        print(f"Response: {result.content}")
        print(f"Model used: {result.model_used}")
        print(f"Cost: ${result.total_cost:.6f}")
        print(f"Cascaded: {result.cascaded}")

    except Exception as e:
        print(f"❌ Failed: {e}")


async def example_3_inference_endpoint():
    """Example 3: Using Inference Endpoint (paid, custom model)."""
    print("\n" + "="*70)
    print("Example 3: Inference Endpoint (Custom Model)")
    print("="*70)

    endpoint_url = os.getenv("HF_INFERENCE_ENDPOINT_URL")

    if not endpoint_url:
        print("⚠️  Skipped: HF_INFERENCE_ENDPOINT_URL not set")
        print("\nThis example shows how to use your custom fine-tuned model.")
        print("Setup: https://ui.endpoints.huggingface.co/")
        return

    # Use inference endpoint
    provider = HuggingFaceProvider.inference_endpoint(
        endpoint_url=endpoint_url
    )

    try:
        result = await provider.complete(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",  # Your model
            prompt="Explain quantum computing",
            max_tokens=100
        )

        print(f"✅ Success!")
        print(f"Response: {result.content[:200]}...")
        print(f"Cost: ${result.cost:.6f} (billed hourly)")
        print(f"Latency: {result.latency_ms:.0f}ms")

    except Exception as e:
        print(f"❌ Failed: {e}")

    await provider.client.aclose()


async def example_4_production_cascade():
    """Example 4: Production cascade with HF Inference Endpoint."""
    print("\n" + "="*70)
    print("Example 4: Production Cascade")
    print("="*70)

    endpoint_url = os.getenv("HF_INFERENCE_ENDPOINT_URL")

    if not endpoint_url:
        print("⚠️  Skipped: HF_INFERENCE_ENDPOINT_URL not set")
        return

    # Production-grade cascade
    models = [
        # Tier 1: Free cloud (Groq)
        ModelConfig(
            name="llama-3.1-8b-instant",
            provider="groq",
            cost=0.0,
            keywords=["simple", "quick"]
        ),

        # Tier 2: Your custom fine-tuned model
        ModelConfig(
            name="my-custom-model",
            provider="huggingface",
            base_url=endpoint_url,
            cost=0.0,  # Billed hourly
            keywords=["specialized", "domain-specific"]
        ),

        # Tier 3: Powerful free
        ModelConfig(
            name="llama-3.1-70b-versatile",
            provider="groq",
            cost=0.0,
            keywords=["complex", "reasoning"]
        ),

        # Tier 4: Ultimate fallback
        ModelConfig(
            name="gpt-4",
            provider="openai",
            cost=0.03
        ),
    ]

    agent = CascadeAgent(models, verbose=True)

    # Test queries
    queries = [
        "What is 2+2?",  # Should use Groq
        "Analyze this complex business scenario...",  # Might use custom model
    ]

    for query in queries:
        print(f"\nQuery: {query[:50]}...")
        try:
            result = await agent.run(query)
            print(f"Model used: {result.model_used}")
            print(f"Cost: ${result.total_cost:.6f}")
        except Exception as e:
            print(f"Error: {e}")


async def example_5_cost_comparison():
    """Example 5: Cost comparison between endpoints."""
    print("\n" + "="*70)
    print("Example 5: Cost Comparison")
    print("="*70)

    print("\n📊 Cost Analysis (10,000 queries/month)")
    print("-" * 70)

    print("\nOption 1: HF Serverless (Free)")
    print("  Cost: $0")
    print("  Models: gpt2, distilgpt2 (small models only)")
    print("  Reliability: ⭐⭐ (50% - often down)")
    print("  Verdict: Good for testing, NOT for production")

    print("\nOption 2: Groq (Free) ⭐ RECOMMENDED")
    print("  Cost: $0 (up to 14,400/day)")
    print("  Models: Llama 3.1 70B, Mixtral")
    print("  Reliability: ⭐⭐⭐⭐⭐ (99%+)")
    print("  Verdict: Best free option for production")

    print("\nOption 3: HF Inference Endpoint")
    print("  Setup: $1/hour × 24h × 30 days = $720/month")
    print("  Capacity: ~30k-60k queries/month per instance")
    print("  Cost per query: $0.012-$0.024")
    print("  Models: Any model you want")
    print("  Reliability: ⭐⭐⭐⭐⭐ (99%+)")
    print("  Verdict: Only if you need custom models or very high volume")

    print("\nOption 4: Together.ai ⭐ RECOMMENDED")
    print("  Cost: ~$0.0002-$0.0009 per query")
    print("  Monthly: $2-$9 for 10k queries")
    print("  Models: 50+ models (Llama, Mixtral, Qwen, etc.)")
    print("  Reliability: ⭐⭐⭐⭐⭐ (99%+)")
    print("  Verdict: Best paid option for most use cases")

    print("\nOption 5: OpenAI GPT-4")
    print("  Cost: $0.03 per query")
    print("  Monthly: $300 for 10k queries")
    print("  Reliability: ⭐⭐⭐⭐⭐ (99.9%)")
    print("  Verdict: Most expensive, best quality")

    print("\n💡 Recommendation for 10k queries/month:")
    print("   1. Use Groq (free)")
    print("   2. If you need more: Together.ai ($2-$9)")
    print("   3. Only use HF Endpoint if you need custom models")


async def example_6_hybrid_approach():
    """Example 6: Hybrid approach (free + paid)."""
    print("\n" + "="*70)
    print("Example 6: Hybrid Approach (Best of Both)")
    print("="*70)

    # This is the optimal setup for most applications
    models = [
        # Layer 1: Free local (privacy + zero cost)
        ModelConfig(
            name="llama3:8b",
            provider="ollama",
            cost=0.0,
            keywords=["simple", "quick", "private"]
        ),

        # Layer 2: Free cloud (speed + zero cost)
        ModelConfig(
            name="llama-3.1-70b-versatile",
            provider="groq",
            cost=0.0,
            keywords=["moderate", "analysis"]
        ),

        # Layer 3: Paid fallback (reliability + quality)
        ModelConfig(
            name="gpt-4",
            provider="openai",
            cost=0.03,
            keywords=["complex", "critical"]
        ),
    ]

    print("\n✅ This cascade gives you:")
    print("   • 70-80% queries: Free (Ollama)")
    print("   • 15-20% queries: Free (Groq)")
    print("   • 5-10% queries: Paid (GPT-4)")
    print("   • Average cost: ~$0.002 per query (93% savings vs GPT-4)")
    print("   • No HuggingFace needed!")

    if os.getenv("GROQ_API_KEY"):
        agent = CascadeAgent(models, verbose=True)

        print("\n🧪 Testing cascade...")
        result = await agent.run("Explain machine learning")

        print(f"\nModel used: {result.model_used}")
        print(f"Cost: ${result.total_cost:.6f}")
        print(f"Quality: {'Good' if result.confidence > 0.7 else 'OK'}")
    else:
        print("\n⚠️  GROQ_API_KEY not set - can't test")
        print("   Get free key: https://console.groq.com")


async def main():
    """Run all examples."""
    print("\nHuggingFace Usage Examples")
    print("Practical patterns for real applications")
    print("="*70)

    await example_1_serverless_simple()
    await asyncio.sleep(1)

    await example_2_serverless_in_cascade()
    await asyncio.sleep(1)

    await example_3_inference_endpoint()
    await asyncio.sleep(1)

    await example_4_production_cascade()
    await asyncio.sleep(1)

    await example_5_cost_comparison()

    await example_6_hybrid_approach()

    print("\n" + "="*70)
    print("Summary")
    print("="*70)

    print("\n✅ Key Takeaways:")
    print("   1. HF Serverless: Free but unreliable (testing only)")
    print("   2. HF Inference Endpoint: For custom models or high volume")
    print("   3. Groq: Best free option for production")
    print("   4. Together.ai: Best paid option for most use cases")
    print("   5. Hybrid cascade: 90%+ queries free, 10% paid (optimal)")

    print("\n🎯 For Most Developers:")
    print("   Skip HuggingFace entirely, use:")
    print("   • Ollama (local, free)")
    print("   • Groq (cloud, free, 14.4k/day)")
    print("   • OpenAI (paid fallback)")

    print("\n🎯 Only Use HuggingFace If:")
    print("   • You have custom/fine-tuned models")
    print("   • You need very high volume (>10k queries/hour)")
    print("   • You need specific model versions")


if __name__ == "__main__":
    asyncio.run(main())