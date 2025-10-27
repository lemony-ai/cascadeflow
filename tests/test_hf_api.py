import asyncio
import os

import httpx


async def test_hf():
    token = os.getenv("HF_TOKEN")

    # Test different models
    models = ["distilgpt2", "gpt2", "openai-community/gpt2"]

    for model in models:
        print(f"\nTesting: {model}")
        print("=" * 50)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Updated to new HuggingFace Inference Providers API endpoint
                # Old: https://api-inference.huggingface.co (deprecated Jan 2025)
                # New: https://router.huggingface.co/hf-inference (as of Nov 2025)
                response = await client.post(
                    f"https://router.huggingface.co/hf-inference/models/{model}",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"inputs": "Hello"},
                )

                print(f"Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Success: {data}")
                    return model  # Return working model
                else:
                    print(f"❌ Error: {response.text[:200]}")

        except Exception as e:
            print(f"❌ Exception: {e}")

    return None


if __name__ == "__main__":
    working_model = asyncio.run(test_hf())
    if working_model:
        print(f"\n✅ Use this model in tests: {working_model}")
    else:
        print("\n❌ No models working - HF API may be down or account issue")
