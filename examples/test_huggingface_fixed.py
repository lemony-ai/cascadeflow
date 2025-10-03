"""Fixed HuggingFace test with better error handling and model selection.

This will test what actually works and give you clear recommendations.
"""

import asyncio
import os
import time
from dotenv import load_dotenv

load_dotenv()


async def test_serverless_models():
    """Test multiple serverless models to find what works."""
    print("\n" + "="*70)
    print("Test 1: HuggingFace Serverless API (Free Tier)")
    print("="*70)

    if not os.getenv("HF_TOKEN"):
        print("❌ HF_TOKEN not set")
        print("   Get token: https://huggingface.co/settings/tokens")
        print("   Add to .env: HF_TOKEN=hf_...")
        return None

    print("✓ HF_TOKEN found")

    from cascadeflow.providers.huggingface import HuggingFaceProvider, get_serverless_models

    # Get recommended models
    test_models = get_serverless_models()

    print(f"\n📋 Testing {len(test_models)} models...")
    print("   (This may take a while, serverless is slow)\n")

    provider = HuggingFaceProvider.serverless(verbose=False)
    working_models = []

    for i, model in enumerate(test_models, 1):
        print(f"{i}/{len(test_models)} Testing: {model}")

        try:
            start = time.time()
            result = await provider.complete(
                model=model,
                prompt="Say 'test'",
                max_tokens=10,
                max_retries=2,
                retry_delay=1.0
            )
            latency = (time.time() - start) * 1000

            print(f"   ✅ Works! ({latency:.0f}ms)")
            print(f"   Response: {result.content[:50]}")
            working_models.append((model, latency, result.content))

        except Exception as e:
            error_msg = str(e).split('\n')[0][:80]
            print(f"   ❌ Failed: {error_msg}")

    await provider.client.aclose()

    # Summary
    print("\n" + "="*70)
    print("Serverless Results")
    print("="*70)

    if working_models:
        print(f"\n✅ Working Models: {len(working_models)}/{len(test_models)}")
        for model, latency, response in working_models:
            print(f"\n   • {model}")
            print(f"     Latency: {latency:.0f}ms")
            print(f"     Response: {response[:50]}")
    else:
        print("\n❌ No models working")
        print("\n⚠️  This is NORMAL for HuggingFace Serverless!")
        print("   Their free API is notoriously unreliable:")
        print("   • Models get unloaded frequently")
        print("   • 404 errors are common")
        print("   • 503 errors when overloaded")
        print("   • Not suitable for any real use")

    return working_models


async def test_inference_endpoint():
    """Test Inference Endpoint if configured."""
    print("\n" + "="*70)
    print("Test 2: HuggingFace Inference Endpoint (Paid, Reliable)")
    print("="*70)

    endpoint_url = os.getenv("HF_INFERENCE_ENDPOINT_URL")

    if not endpoint_url:
        print("⚠️  HF_INFERENCE_ENDPOINT_URL not set")
        print("\n📋 This is a PAID feature (~$0.60-$4/hour)")
        print("   Only needed for:")
        print("   • Custom/fine-tuned models")
        print("   • High volume (>1000 queries/hour)")
        print("   • Production reliability with specific models")
        print("\n💡 Setup:")
        print("   1. Go to: https://ui.endpoints.huggingface.co/")
        print("   2. Create endpoint with your model")
        print("   3. Copy endpoint URL")
        print("   4. Add to .env: HF_INFERENCE_ENDPOINT_URL=https://...")
        return None

    print(f"✓ Endpoint URL found: {endpoint_url[:50]}...")

    try:
        from cascadeflow.providers.huggingface import HuggingFaceProvider

        provider = HuggingFaceProvider.inference_endpoint(
            endpoint_url=endpoint_url,
            verbose=True
        )

        print("\nTesting endpoint...")
        start = time.time()

        result = await provider.complete(
            model="auto",  # Endpoint knows its model
            prompt="Say 'test'",
            max_tokens=10
        )

        latency = (time.time() - start) * 1000

        print(f"\n✅ Inference Endpoint Works!")
        print(f"   Latency: {latency:.0f}ms")
        print(f"   Response: {result.content}")
        print(f"   Cost: ${result.cost:.6f} (billed hourly)")

        await provider.client.aclose()
        return {"success": True, "latency": latency}

    except Exception as e:
        print(f"\n❌ Failed: {str(e)[:200]}")
        return {"success": False, "error": str(e)}


async def show_recommendations(serverless_working, endpoint_working):
    """Show personalized recommendations."""
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)

    print("\n💡 Based on your setup:\n")

    # Serverless analysis
    if serverless_working:
        print("✅ HuggingFace Serverless works (sometimes)")
        print(f"   • {len(serverless_working)} model(s) working")
        print("   • But still unreliable (expect failures)")
        print("   • Use for: Learning/testing only")
    else:
        print("❌ HuggingFace Serverless not working")
        print("   • This is normal (free tier often down)")
        print("   • 404/503 errors are expected")

    # Endpoint analysis
    if endpoint_working:
        print("\n✅ HuggingFace Inference Endpoint configured!")
        print("   • RELIABLE for production")
        print("   • Use for: Custom models, high volume")
    else:
        print("\n⚠️  No Inference Endpoint configured")
        print("   • Only needed for custom models")

    # General recommendations
    print("\n" + "="*70)
    print("RECOMMENDED ALTERNATIVES (Better than HF Serverless)")
    print("="*70)

    print("\n1️⃣  Groq - FREE + RELIABLE ⭐⭐⭐")
    print("   • 14,400 free requests/day")
    print("   • Llama 3.1 8B & 70B models")
    print("   • Sub-second latency")
    print("   • 99%+ reliability")
    print("   • Setup: https://console.groq.com")

    has_groq = os.getenv("GROQ_API_KEY")
    if has_groq:
        print("   ✅ Already configured!")
    else:
        print("   ❌ Not configured - HIGHLY RECOMMENDED")
        print("   📝 Quick setup (2 minutes):")
        print("      1. Go to https://console.groq.com")
        print("      2. Sign up (free, no credit card)")
        print("      3. Create API key")
        print("      4. Add to .env: GROQ_API_KEY=gsk_...")

    print("\n2️⃣  Together.ai - $25 FREE CREDITS ⭐⭐")
    print("   • 50+ models (Llama, Mixtral, Qwen)")
    print("   • Fast inference")
    print("   • Very reliable")
    print("   • Setup: https://api.together.ai")

    has_together = os.getenv("TOGETHER_API_KEY")
    if has_together:
        print("   ✅ Already configured!")
    else:
        print("   ❌ Not configured")

    print("\n3️⃣  Ollama - FREE + LOCAL")
    print("   • Unlimited requests")
    print("   • 100% privacy")
    print("   • 100+ models")
    print("   • Setup: brew install ollama")


async def show_cascade_example():
    """Show optimal cascade configuration."""
    print("\n" + "="*70)
    print("OPTIMAL CASCADE CONFIGURATION")
    print("="*70)

    has_groq = os.getenv("GROQ_API_KEY")
    has_openai = os.getenv("OPENAI_API_KEY")

    if has_groq:
        print("\n✅ Recommended: Use Groq (you have it configured)")
        print("""
from cascadeflow import ModelConfig, CascadeAgent

models = [
    # Tier 1: Free, fast, reliable
    ModelConfig(
        name="llama-3.1-8b-instant",
        provider="groq",
        cost=0.0
    ),
    
    # Tier 2: Free, powerful
    ModelConfig(
        name="llama-3.1-70b-versatile",
        provider="groq",
        cost=0.0
    ),
    
    # Tier 3: Paid fallback (only if really needed)
    ModelConfig(
        name="gpt-4",
        provider="openai",
        cost=0.03
    ),
]

agent = CascadeAgent(models)
result = await agent.run("Your query")
# 95%+ of queries will use free Groq tier!
""")
    elif has_openai:
        print("\n⚠️  You have OpenAI but not Groq")
        print("   Get Groq for 95% cost savings!")
        print("""
# Current (expensive):
models = [
    ModelConfig("gpt-3.5-turbo", provider="openai", cost=0.002),
    ModelConfig("gpt-4", provider="openai", cost=0.03),
]

# Better (add Groq - free tier):
models = [
    ModelConfig("llama-3.1-8b-instant", provider="groq", cost=0.0),
    ModelConfig("llama-3.1-70b-versatile", provider="groq", cost=0.0),
    ModelConfig("gpt-3.5-turbo", provider="openai", cost=0.002),
    ModelConfig("gpt-4", provider="openai", cost=0.03),
]
# Now 95% of queries use free tier!
""")
    else:
        print("\n❌ No API keys configured")
        print("\n🔧 Quick start:")
        print("   1. Get Groq key: https://console.groq.com (2 min)")
        print("   2. Add to .env: GROQ_API_KEY=gsk_...")
        print("   3. Run test again")


async def main():
    """Run complete test suite."""
    print("\n" + "="*70)
    print("HuggingFace Complete Test (Fixed)")
    print("="*70)
    print("\nThis will:")
    print("• Test HuggingFace Serverless (free tier)")
    print("• Test HuggingFace Inference Endpoint (if configured)")
    print("• Show you what actually works")
    print("• Recommend better alternatives")

    # Run tests
    serverless_working = await test_serverless_models()
    await asyncio.sleep(1)

    endpoint_working = await test_inference_endpoint()
    await asyncio.sleep(1)

    # Show recommendations
    await show_recommendations(serverless_working, endpoint_working)

    # Show cascade example
    await show_cascade_example()

    # Final summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    print("\n📊 Test Results:")
    if serverless_working:
        print(f"   ✅ HF Serverless: {len(serverless_working)} model(s) working")
    else:
        print("   ❌ HF Serverless: Not working (expected)")

    if endpoint_working and endpoint_working.get("success"):
        print("   ✅ HF Inference Endpoint: Working")
    else:
        print("   ⚠️  HF Inference Endpoint: Not configured")

    print("\n🎯 Next Steps:")
    if not os.getenv("GROQ_API_KEY"):
        print("   1. Get Groq API key (takes 2 minutes)")
        print("      → https://console.groq.com")
        print("   2. Add to .env: GROQ_API_KEY=gsk_...")
        print("   3. Enjoy 14,400 free requests/day!")
    else:
        print("   ✅ You're all set with Groq!")
        print("   Just use smart_default() and you're good to go:")
        print()
        print("   from cascadeflow import CascadeAgent")
        print("   agent = CascadeAgent.smart_default()")
        print("   result = await agent.run('Your query')")


if __name__ == "__main__":
    asyncio.run(main())