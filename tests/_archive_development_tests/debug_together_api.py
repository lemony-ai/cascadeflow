"""Debug script to see raw Together.ai API response."""

import asyncio
import json
import os

import httpx


async def test_together_logprobs():
    """Test what Together.ai actually returns."""

    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        print("❌ TOGETHER_API_KEY not set")
        return

    client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=60.0,
    )

    print("=" * 70)
    print("TOGETHER.AI LOGPROBS DEBUG")
    print("=" * 70)

    # Test 1: With logprobs=5 (integer)
    print("\n1. Testing with logprobs=5 (integer)...")
    payload1 = {
        "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "messages": [{"role": "user", "content": "The capital of France is"}],
        "max_tokens": 3,
        "temperature": 0.7,
        "logprobs": 5,  # Integer format
    }

    print(f"Payload: {json.dumps(payload1, indent=2)}")

    response1 = await client.post("https://api.together.xyz/v1/chat/completions", json=payload1)

    print(f"\nStatus: {response1.status_code}")

    if response1.status_code == 200:
        data1 = response1.json()
        print("\nFull Response:")
        print(json.dumps(data1, indent=2))

        # Check for logprobs
        choice = data1["choices"][0]
        print("\n--- LOGPROBS CHECK ---")
        print(f"Has 'logprobs' key: {'logprobs' in choice}")

        if "logprobs" in choice:
            print(f"Logprobs value: {choice['logprobs']}")
            print(f"Logprobs type: {type(choice['logprobs'])}")

            if choice["logprobs"]:
                print(f"Logprobs keys: {choice['logprobs'].keys()}")
                if "content" in choice["logprobs"]:
                    print(f"Content length: {len(choice['logprobs']['content'])}")
                    if choice["logprobs"]["content"]:
                        print("\nFirst token data:")
                        print(json.dumps(choice["logprobs"]["content"][0], indent=2))
            else:
                print("⚠️  Logprobs is present but NULL/empty!")
        else:
            print("❌ No 'logprobs' key in response")
    else:
        print(f"❌ Error: {response1.text}")

    # Test 2: With logprobs=1 (minimum)
    print("\n" + "=" * 70)
    print("2. Testing with logprobs=1 (minimum)...")
    payload2 = {
        "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 3,
        "temperature": 0.7,
        "logprobs": 1,  # Minimum
    }

    response2 = await client.post("https://api.together.xyz/v1/chat/completions", json=payload2)

    print(f"Status: {response2.status_code}")

    if response2.status_code == 200:
        data2 = response2.json()
        choice2 = data2["choices"][0]

        if "logprobs" in choice2 and choice2["logprobs"]:
            print("✅ Logprobs returned!")
            print(f"Content entries: {len(choice2['logprobs'].get('content', []))}")
        else:
            print("❌ Still no logprobs")

    # Test 3: Different model
    print("\n" + "=" * 70)
    print("3. Testing with different model (Qwen)...")
    payload3 = {
        "model": "Qwen/Qwen2.5-7B-Instruct-Turbo",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 3,
        "temperature": 0.7,
        "logprobs": 3,
    }

    response3 = await client.post("https://api.together.xyz/v1/chat/completions", json=payload3)

    if response3.status_code == 200:
        data3 = response3.json()
        choice3 = data3["choices"][0]

        if "logprobs" in choice3 and choice3["logprobs"]:
            print("✅ Qwen returns logprobs!")
        else:
            print("❌ Qwen also doesn't return logprobs")
    else:
        print(f"❌ Error with Qwen: {response3.status_code}")

    await client.aclose()

    print("\n" + "=" * 70)
    print("DEBUG COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_together_logprobs())
