"""
Quick Diagnostic: Test ONE query with timeout to see what's failing.

Save as: tests/test_quick_diagnostic.py
Run: pytest tests/test_quick_diagnostic.py -v -s
"""

import asyncio
import time
from pathlib import Path

import pytest


def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                import os

                os.environ[key.strip()] = value.strip().strip('"').strip("'")


_load_env()

from cascadeflow.providers import PROVIDER_REGISTRY


@pytest.mark.asyncio
async def test_single_openai_query_with_timeout():
    """Test one OpenAI query to diagnose hanging."""

    print("\n" + "=" * 80)
    print("🔍 DIAGNOSTIC: Testing single OpenAI query with 30s timeout")
    print("=" * 80)

    try:
        provider = PROVIDER_REGISTRY["openai"]()
        print("\n✅ Provider initialized")

        print("\n📤 Sending request to gpt-4o-mini...")
        print("   Query: 'What is 2+2?'")
        print("   Timeout: 30 seconds")

        start = time.perf_counter()

        # Test with explicit timeout
        result = await asyncio.wait_for(
            provider.complete(
                model="gpt-4o-mini", prompt="What is 2+2?", max_tokens=50, temperature=0.7
            ),
            timeout=30.0,
        )

        elapsed = time.perf_counter() - start

        print(f"\n✅ SUCCESS! Response received in {elapsed:.2f}s")

        result_dict = result.to_dict() if hasattr(result, "to_dict") else result
        content = result_dict.get("content", "NO CONTENT")

        print(f"\n📝 Response: {content[:200]}")
        print(f"   Tokens: {result_dict.get('tokens_used', 'unknown')}")

        return True

    except asyncio.TimeoutError:
        print("\n❌ TIMEOUT after 30 seconds")
        print("   This means:")
        print("   1. OpenAI API is slow/overloaded")
        print("   2. Network issues")
        print("   3. Rate limiting (silent)")
        return False

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}")
        print(f"   Message: {str(e)}")

        error_str = str(e).lower()
        if "rate limit" in error_str or "429" in error_str:
            print("\n⚠️  RATE LIMIT DETECTED")
            print("   Solution: Wait a few minutes or upgrade OpenAI tier")
        elif "quota" in error_str:
            print("\n⚠️  QUOTA EXCEEDED")
            print("   Solution: Add credits to OpenAI account")
        elif "authentication" in error_str or "401" in error_str:
            print("\n⚠️  AUTHENTICATION ERROR")
            print("   Solution: Check OPENAI_API_KEY in .env")

        return False


@pytest.mark.asyncio
async def test_all_providers_quick():
    """Test all providers with one query each."""

    print("\n" + "=" * 80)
    print("🔍 DIAGNOSTIC: Testing all providers (1 query each)")
    print("=" * 80)

    providers_to_test = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-haiku-20240307",
        "groq": "llama-3.1-8b-instant",
        "together": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    }

    results = {}

    for name, model in providers_to_test.items():
        print(f"\n{'─'*80}")
        print(f"Testing {name.upper()}...")

        try:
            import os

            env_var = f"{name.upper()}_API_KEY"
            if not os.getenv(env_var):
                print(f"⚠️  Skipped: {env_var} not set")
                results[name] = "SKIPPED"
                continue

            provider = PROVIDER_REGISTRY[name]()

            start = time.perf_counter()
            result = await asyncio.wait_for(
                provider.complete(model=model, prompt="Hi", max_tokens=20, temperature=0.7),
                timeout=30.0,
            )
            elapsed = time.perf_counter() - start

            result_dict = result.to_dict() if hasattr(result, "to_dict") else result
            content = result_dict.get("content", "")[:50]

            print(f"✅ {name.upper()}: OK ({elapsed:.2f}s) - {content}")
            results[name] = "OK"

            # Small delay between providers
            await asyncio.sleep(1.0)

        except asyncio.TimeoutError:
            print(f"❌ {name.upper()}: TIMEOUT (>30s)")
            results[name] = "TIMEOUT"

        except Exception as e:
            error_str = str(e)[:100]
            print(f"❌ {name.upper()}: {type(e).__name__} - {error_str}")
            results[name] = f"ERROR: {type(e).__name__}"

    # Summary
    print("\n" + "=" * 80)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 80)

    for name, status in results.items():
        status_icon = "✅" if status == "OK" else "❌" if status == "SKIPPED" else "⚠️"
        print(f"  {status_icon} {name.upper():<15}: {status}")

    print("\n" + "=" * 80)

    # Check if any worked
    working = [name for name, status in results.items() if status == "OK"]

    if not working:
        print("❌ NO PROVIDERS WORKING")
        print("\nPossible issues:")
        print("  1. Rate limits on all providers")
        print("  2. Network/firewall blocking API calls")
        print("  3. All API keys invalid/expired")
        pytest.fail("No providers available")
    else:
        print(f"✅ {len(working)} provider(s) working: {', '.join(working)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
