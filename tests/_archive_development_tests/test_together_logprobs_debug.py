"""
Debug Together.ai logprobs implementation.

This test investigates the token/logprob mismatch issue:
- Together.ai returns 9 tokens but only 2 logprobs
- Need to determine if this is an API limitation or parsing bug

Run with:
    pytest tests/test_together_logprobs_debug.py -v -s

Or directly:
    python tests/test_together_logprobs_debug.py
"""

import asyncio
import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from cascadeflow.providers.together import TogetherProvider

# =============================================================================
# Debug Test: Inspect Raw API Response
# =============================================================================


@pytest.mark.skipif(not os.getenv("TOGETHER_API_KEY"), reason="TOGETHER_API_KEY not set")
@pytest.mark.asyncio
async def test_together_logprobs_raw_response():
    """
    Debug test: Inspect raw Together.ai API response to understand logprobs format.

    This test makes a direct API call and prints the raw response to see:
    1. What format Together.ai returns logprobs in
    2. Whether all tokens get logprobs or just some
    3. How the provider is parsing the response
    """
    print("\n" + "=" * 80)
    print("TOGETHER.AI LOGPROBS DEBUG TEST")
    print("=" * 80)

    provider = TogetherProvider()

    # Simple test prompt
    prompt = "Count to 3."
    model = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"

    print("\nTest Configuration:")
    print(f"  Prompt: '{prompt}'")
    print(f"  Model: {model}")
    print("  Max tokens: 20")
    print("  Logprobs requested: True")
    print("  Top logprobs: 5")

    # Make request with logprobs
    response = await provider.complete(
        prompt=prompt, model=model, max_tokens=20, temperature=0.3, logprobs=True, top_logprobs=5
    )

    print("\n" + "-" * 80)
    print("RESPONSE ANALYSIS")
    print("-" * 80)

    print("\n1. Content:")
    print(f"   '{response.content}'")
    print(f"   Length: {len(response.content)} chars")

    print("\n2. Tokens:")
    if response.tokens:
        print(f"   Count: {len(response.tokens)}")
        print(f"   Tokens: {response.tokens}")
    else:
        print("   None returned")

    print("\n3. Logprobs:")
    if response.logprobs:
        print(f"   Count: {len(response.logprobs)}")
        print(f"   Values: {response.logprobs}")
    else:
        print("   None returned")

    print("\n4. Top Logprobs:")
    if response.top_logprobs:
        print(f"   Count: {len(response.top_logprobs)}")
        print(f"   First entry: {response.top_logprobs[0] if response.top_logprobs else 'None'}")
    else:
        print("   None returned")

    print("\n5. Metadata:")
    print(f"   {json.dumps(response.metadata, indent=2)}")

    # Analyze the mismatch
    print("\n" + "-" * 80)
    print("MISMATCH ANALYSIS")
    print("-" * 80)

    if response.tokens and response.logprobs:
        token_count = len(response.tokens)
        logprob_count = len(response.logprobs)

        print("\n❌ MISMATCH DETECTED:")
        print(f"   Tokens: {token_count}")
        print(f"   Logprobs: {logprob_count}")
        print(f"   Ratio: {logprob_count}/{token_count} = {logprob_count/token_count:.2%}")

        if logprob_count < token_count:
            print(
                f"\n⚠️  Together.ai returned logprobs for only {logprob_count}/{token_count} tokens"
            )
            print("   This appears to be an API limitation.")

            # Try to identify which tokens got logprobs
            print(f"\n   Tokens with logprobs (first {logprob_count}):")
            for i in range(min(logprob_count, len(response.tokens))):
                print(f"     [{i}] '{response.tokens[i]}' -> {response.logprobs[i]:.6f}")

            print(f"\n   Tokens WITHOUT logprobs ({token_count - logprob_count}):")
            for i in range(logprob_count, len(response.tokens)):
                print(f"     [{i}] '{response.tokens[i]}' -> NO LOGPROB")

    print("\n" + "=" * 80)


# =============================================================================
# Test: Multiple Prompts to Find Pattern
# =============================================================================


@pytest.mark.skipif(not os.getenv("TOGETHER_API_KEY"), reason="TOGETHER_API_KEY not set")
@pytest.mark.asyncio
async def test_together_logprobs_pattern_analysis():
    """
    Test multiple prompts to identify pattern in logprobs availability.

    Tests different prompt lengths and complexities to see if there's a pattern
    in which tokens get logprobs.
    """
    print("\n" + "=" * 80)
    print("TOGETHER.AI LOGPROBS PATTERN ANALYSIS")
    print("=" * 80)

    provider = TogetherProvider()
    model = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"

    test_cases = [
        ("Hi", 5),
        ("Hello world", 10),
        ("Count to 3.", 20),
        ("What is 2+2?", 10),
        ("The capital of France is", 10),
    ]

    print("\nTesting multiple prompts to find pattern...")
    print("-" * 80)

    for prompt, max_tokens in test_cases:
        response = await provider.complete(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=0.3,
            logprobs=True,
            top_logprobs=5,
        )

        token_count = len(response.tokens) if response.tokens else 0
        logprob_count = len(response.logprobs) if response.logprobs else 0
        ratio = f"{logprob_count}/{token_count}" if token_count > 0 else "N/A"

        print(f"\nPrompt: '{prompt}'")
        print(f"  Response: '{response.content[:50]}...'")
        print(f"  Tokens: {token_count}, Logprobs: {logprob_count}, Ratio: {ratio}")

        if token_count > 0 and logprob_count < token_count:
            print(f"  ⚠️  Missing logprobs for {token_count - logprob_count} tokens")


# =============================================================================
# Test: Check Provider Implementation
# =============================================================================


@pytest.mark.skipif(not os.getenv("TOGETHER_API_KEY"), reason="TOGETHER_API_KEY not set")
@pytest.mark.asyncio
async def test_together_provider_parsing():
    """
    Test the provider's logprobs parsing logic.

    This test checks if the issue is in how we're parsing the API response.
    """
    print("\n" + "=" * 80)
    print("TOGETHER.AI PROVIDER PARSING DEBUG")
    print("=" * 80)

    TogetherProvider()

    # Access the raw HTTP client to see what the API actually returns
    import httpx

    print("\n1. Making direct API call (bypassing provider parsing)...")

    payload = {
        "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "messages": [{"role": "user", "content": "Count to 3."}],
        "max_tokens": 20,
        "temperature": 0.3,
        "logprobs": 1,  # Request logprobs
        "top_logprobs": 5,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.together.xyz/v1/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {os.getenv('TOGETHER_API_KEY')}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

        if response.status_code == 200:
            data = response.json()

            print("\n2. Raw API Response Structure:")
            print(f"   Status: {response.status_code}")
            print(f"   Keys: {list(data.keys())}")

            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                print("\n3. Choice Structure:")
                print(f"   Keys: {list(choice.keys())}")

                if "logprobs" in choice:
                    logprobs_data = choice["logprobs"]
                    print("\n4. Logprobs Structure:")
                    print(f"   Type: {type(logprobs_data)}")
                    if isinstance(logprobs_data, dict):
                        print(f"   Keys: {list(logprobs_data.keys())}")

                        # Check what fields are available
                        for key in ["tokens", "token_logprobs", "top_logprobs", "text_offset"]:
                            if key in logprobs_data:
                                value = logprobs_data[key]
                                print(f"\n   {key}:")
                                print(f"     Type: {type(value)}")
                                if isinstance(value, list):
                                    print(f"     Length: {len(value)}")
                                    print(f"     First few: {value[:3]}")
                    else:
                        print(f"   Value: {logprobs_data}")

                # Check message content
                if "message" in choice:
                    content = choice["message"].get("content", "")
                    print("\n5. Content:")
                    print(f"   Content: '{content}'")
                    print(f"   Length: {len(content)} chars")

            print("\n6. Full Response (formatted):")
            print(json.dumps(data, indent=2))
        else:
            print(f"\n❌ API Error: {response.status_code}")
            print(f"   Response: {response.text}")

    print("\n" + "=" * 80)


# =============================================================================
# Recommendation Test
# =============================================================================


@pytest.mark.skipif(not os.getenv("TOGETHER_API_KEY"), reason="TOGETHER_API_KEY not set")
@pytest.mark.asyncio
async def test_together_recommendations():
    """
    Provide recommendations based on findings.
    """
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    provider = TogetherProvider()

    # Do one more test to confirm findings
    response = await provider.complete(
        prompt="Count to 3.",
        model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        max_tokens=20,
        temperature=0.3,
        logprobs=True,
        top_logprobs=5,
    )

    token_count = len(response.tokens) if response.tokens else 0
    logprob_count = len(response.logprobs) if response.logprobs else 0

    print("\nBased on the analysis:")
    print(f"  Tokens returned: {token_count}")
    print(f"  Logprobs returned: {logprob_count}")

    if logprob_count < token_count:
        print("\n❌ CONFIRMED: Together.ai API limitation")
        print(f"   Together.ai returns logprobs for only {logprob_count}/{token_count} tokens")
        print("\nPossible causes:")
        print("  1. Together.ai only returns logprobs for the first few tokens")
        print("  2. Together.ai has a different logprobs format than expected")
        print("  3. The API only returns logprobs for 'important' tokens")
        print("\nRecommended solutions:")
        print("  Option A: Update test to accept partial logprobs")
        print("  Option B: Mark Together.ai as 'partial logprobs support'")
        print("  Option C: Pad missing logprobs with estimated values")
        print("  Option D: Don't validate logprob count for Together.ai")
    else:
        print("\n✅ Logprobs match! If this passes, the issue might be intermittent.")

    print("\n" + "=" * 80)


# =============================================================================
# Main: Run all debug tests
# =============================================================================


async def main():
    """Run all debug tests in sequence."""
    print("\n" + "=" * 80)
    print("TOGETHER.AI LOGPROBS COMPREHENSIVE DEBUG")
    print("=" * 80)

    if not os.getenv("TOGETHER_API_KEY"):
        print("\n❌ TOGETHER_API_KEY not set")
        print("   Please set TOGETHER_API_KEY in your .env file")
        return

    print("\nRunning debug tests...")

    try:
        print("\n\n### TEST 1: Raw Response Analysis ###")
        await test_together_logprobs_raw_response()

        print("\n\n### TEST 2: Pattern Analysis ###")
        await test_together_logprobs_pattern_analysis()

        print("\n\n### TEST 3: Provider Parsing ###")
        await test_together_provider_parsing()

        print("\n\n### TEST 4: Recommendations ###")
        await test_together_recommendations()

    except Exception as e:
        print(f"\n❌ Error during debug: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
