"""
Free Cascade Example - 100% FREE AI!

Demonstrates cascading between:
1. Ollama (local, unlimited free)
2. Groq (cloud, 14,400 free/day)
3. OpenAI (paid, only if needed)

Cost savings: 95%+ of queries = $0!
"""

import asyncio
import os
from dotenv import load_dotenv

from cascadeflow import ModelConfig
from cascadeflow.providers import OllamaProvider, GroqProvider, OpenAIProvider

# Load environment variables
load_dotenv()

# DEBUG: Check if API keys are loaded
print("DEBUG: Checking API keys...")
print(f"GROQ_API_KEY loaded: {bool(os.getenv('GROQ_API_KEY'))}")
if os.getenv('GROQ_API_KEY'):
    print(f"GROQ_API_KEY preview: {os.getenv('GROQ_API_KEY')[:20]}...")
print(f"OPENAI_API_KEY loaded: {bool(os.getenv('OPENAI_API_KEY'))}")
print()


async def check_ollama_available():
    """Check if Ollama is running and has models."""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:11434/api/tags", timeout=2.0)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return True, [m["name"] for m in models]
    except:
        pass
    return False, []


async def main():
    """Run free cascade example."""

    print("🌊 CascadeFlow - 100% FREE Cascade\n")
    print("=" * 60)

    # Test query
    query = "Explain AI in one simple sentence"

    print(f"Query: {query}\n")

    # Check what's available
    ollama_available, ollama_models = await check_ollama_available()
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))

    print("📊 Available Providers:")
    print(f"  ✅ Ollama (local): {'Yes' if ollama_available else 'No'}")
    if ollama_available and ollama_models:
        print(f"     Models: {', '.join(ollama_models[:3])}")
    print(f"  {'✅' if has_groq else '❌'} Groq (cloud): {'Yes' if has_groq else 'No - Set GROQ_API_KEY'}")
    print(f"  {'✅' if has_openai else '❌'} OpenAI (paid): {'Yes' if has_openai else 'No - Set OPENAI_API_KEY'}")
    print()

    # Cascade Strategy
    print("📊 Cascade Strategy:")
    print("  1. Try Ollama (local, FREE, unlimited)")
    print("  2. Try Groq (cloud, FREE, 14.4k/day)")
    print("  3. Try OpenAI (paid, only if needed)\n")

    # Step 1: Try Ollama (local, free)
    if ollama_available:
        print("-" * 60)
        print("TIER 1: Trying Ollama (local)...")

        # Choose best available model
        preferred_models = ["llama3.2:1b", "llama3.1:8b", "gemma2:2b", "qwen2.5:1.5b"]
        ollama_model = None
        for model in preferred_models:
            if model in ollama_models:
                ollama_model = model
                break

        if not ollama_model and ollama_models:
            ollama_model = ollama_models[0]  # Use first available

        if ollama_model:
            print(f"Using model: {ollama_model}")

            ollama = OllamaProvider()

            try:
                result = await ollama.complete(
                    prompt=query,
                    model=ollama_model,
                    max_tokens=100
                )

                print(f"✅ Success with Ollama!")
                print(f"Response: {result.content[:100]}...")
                print(f"Cost: ${result.cost:.6f} (FREE!)")
                print(f"Tokens: {result.tokens_used}")
                print(f"Latency: {result.latency_ms:.0f}ms")
                print(f"Confidence: {result.confidence:.2f}")

                if result.confidence >= 0.7:
                    print("\n🎉 High confidence! No need to cascade.")
                    print("💰 Saved money by using free local model!")
                    await ollama.client.aclose()
                    return

                print("\n⚠️ Confidence below threshold (0.7), cascading to Groq...")
                await ollama.client.aclose()

            except Exception as e:
                print(f"⚠️ Ollama failed: {e}")
                print("Cascading to Groq...")
                await ollama.client.aclose()
        else:
            print("⚠️ No suitable Ollama models found")
            print("Run: ollama pull llama3.2:1b")
    else:
        print("-" * 60)
        print("TIER 1: Ollama not available")
        print("⚠️ Ollama is not running locally")
        print("Install from: https://ollama.com")
        print("Then run: ollama pull llama3.2:1b")
        print("Skipping to Groq...")

    # Step 2: Try Groq (cloud, free)
    if has_groq:
        print("\n" + "-" * 60)
        print("TIER 2: Trying Groq (cloud, free)...")

        groq = GroqProvider()

        try:
            # FIXED: Updated model name
            result = await groq.complete(
                prompt=query,
                model="llama-3.1-8b-instant",  # ✅ UPDATED MODEL NAME
                max_tokens=100
            )

            print(f"✅ Success with Groq!")
            print(f"Response: {result.content[:100]}...")
            print(f"Cost: ${result.cost:.6f} (FREE!)")
            print(f"Tokens: {result.tokens_used}")
            print(f"Latency: {result.latency_ms:.0f}ms")
            print(f"Confidence: {result.confidence:.2f}")

            if result.confidence >= 0.8:
                print("\n🎉 High confidence! No need to cascade further.")
                print("💰 Still $0 cost using Groq!")
                await groq.client.aclose()
                return

            print("\n⚠️ Confidence still below threshold (0.8), would cascade to OpenAI...")
            await groq.client.aclose()

        except Exception as e:
            print(f"⚠️ Groq failed: {e}")
            print("Would cascade to OpenAI...")
            await groq.client.aclose()
    else:
        print("\n" + "-" * 60)
        print("TIER 2: Groq not available")
        print("⚠️ GROQ_API_KEY not set in .env")
        print("Get free key at: https://console.groq.com")
        print("Add to .env: GROQ_API_KEY=gsk_...")

    # Step 3: Would try OpenAI (paid)
    if has_openai:
        print("\n" + "-" * 60)
        print("TIER 3: Would try OpenAI (paid)...")
        print("(Skipping actual call to save money in demo)")
        print("💡 This is where paid models would be used as last resort.")
        print("   Only ~5% of queries need this tier!")
    else:
        print("\n" + "-" * 60)
        print("TIER 3: OpenAI not available")
        print("⚠️ OPENAI_API_KEY not set in .env")
        print("Add to .env: OPENAI_API_KEY=sk-proj-...")

    # Summary
    print("\n" + "=" * 60)
    print("📊 CASCADE SUMMARY")
    print("=" * 60)

    tiers_available = []
    if ollama_available:
        tiers_available.append("Ollama (local)")
    if has_groq:
        tiers_available.append("Groq (cloud)")
    if has_openai:
        tiers_available.append("OpenAI (paid)")

    print(f"✅ Available tiers: {', '.join(tiers_available) if tiers_available else 'None'}")
    print("💰 Total cost this demo: $0.00")
    print("🎯 Typical savings: 95%+ of queries cost $0 with this strategy!")

    if not has_groq and not ollama_available:
        print("\n⚠️ To get started with FREE tier:")
        print("   1. Install Ollama: https://ollama.com")
        print("   2. Get Groq key: https://console.groq.com")
        print("   3. Add to .env: GROQ_API_KEY=gsk_...")


if __name__ == "__main__":
    asyncio.run(main())