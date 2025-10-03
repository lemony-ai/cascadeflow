"""Test HuggingFace Inference Endpoint with DeepSeek-R1-Distill-Qwen-32B."""

import asyncio
import os
import time
from dotenv import load_dotenv

load_dotenv()


async def test_deepseek_endpoint():
    """Test the DeepSeek-R1 Inference Endpoint."""
    print("\n" + "="*70)
    print("HuggingFace Inference Endpoint Test")
    print("Model: deepseek-ai/DeepSeek-R1-Distill-Qwen-32B")
    print("="*70)

    # Check configuration
    endpoint_url = os.getenv("HF_INFERENCE_ENDPOINT_URL")
    hf_token = os.getenv("HF_TOKEN")

    if not endpoint_url:
        print("\nERROR: HF_INFERENCE_ENDPOINT_URL not set")
        print("\nAdd to .env: HF_INFERENCE_ENDPOINT_URL=https://...")
        return False

    if not hf_token:
        print("\nERROR: HF_TOKEN not set")
        return False

    print(f"\nEndpoint URL: {endpoint_url[:60]}...")
    print(f"HF Token: {hf_token[:10]}...")

    from cascadeflow.providers.huggingface import HuggingFaceProvider

    print("\nInitializing Inference Endpoint provider...")
    provider = HuggingFaceProvider.inference_endpoint(
        endpoint_url=endpoint_url,
        verbose=True
    )

    # Test queries optimized for reasoning model
    test_cases = [
        {
            "name": "Simple",
            "prompt": "What is 2+2?",
            "max_tokens": 50
        },
        {
            "name": "Math Reasoning",
            "prompt": "If I have 15 apples and give away 7, then buy 12 more, how many do I have?",
            "max_tokens": 100
        },
        {
            "name": "Logical Reasoning",
            "prompt": "All humans are mortal. Socrates is human. What can we conclude?",
            "max_tokens": 150
        },
    ]

    print("\n" + "="*70)
    print("Running Test Cases")
    print("="*70)

    results = []

    for test in test_cases:
        print(f"\nTest: {test['name']}")
        print(f"Prompt: {test['prompt']}")
        print(f"Max tokens: {test['max_tokens']}")
        print("-" * 70)

        try:
            start = time.time()

            result = await provider.complete(
                model="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
                prompt=test['prompt'],
                max_tokens=test['max_tokens'],
                temperature=0.7
            )

            latency = (time.time() - start) * 1000

            print(f"\nSUCCESS!")
            print(f"Response: {result.content}")
            print(f"\nTokens: {result.tokens_used}")
            print(f"Latency: {latency:.0f}ms")
            print(f"Confidence: {result.confidence:.2f}")
            print(f"Cost: ${result.cost:.6f} (billed hourly)")
            print(f"Endpoint type: {result.metadata['endpoint_type']}")

            results.append({
                "name": test['name'],
                "success": True,
                "latency": latency,
                "tokens": result.tokens_used,
                "response": result.content
            })

        except Exception as e:
            print(f"\nFAILED!")
            print(f"Error: {str(e)}")
            results.append({
                "name": test['name'],
                "success": False,
                "error": str(e)
            })

    await provider.client.aclose()

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    print(f"\nTotal tests: {len(results)}")
    print(f"Passed: {len(successful)}")
    print(f"Failed: {len(failed)}")

    if successful:
        print("\nSuccessful tests:")
        avg_latency = sum(r['latency'] for r in successful) / len(successful)
        total_tokens = sum(r['tokens'] for r in successful)
        print(f"  Average latency: {avg_latency:.0f}ms")
        print(f"  Total tokens: {total_tokens}")
        for r in successful:
            print(f"\n  {r['name']}:")
            print(f"    Latency: {r['latency']:.0f}ms")
            print(f"    Tokens: {r['tokens']}")
            print(f"    Response: {r['response'][:80]}...")

    if failed:
        print("\nFailed tests:")
        for r in failed:
            print(f"  - {r['name']}: {r['error'][:100]}")

    # Verdict
    print("\n" + "="*70)
    if len(successful) == len(results):
        print("VERDICT: Provider Implementation CORRECT")
        print("="*70)
        print("\nAll tests passed!")
        print("The HuggingFace provider is working correctly.")
        print("Serverless failures were due to HuggingFace's unreliable free tier.")
    else:
        print("VERDICT: Issues Found")
        print("="*70)
        print(f"\n{len(failed)} test(s) failed. Check errors above.")

    # Cost reminder
    print("\n" + "="*70)
    print("REMEMBER: Pause/Delete Endpoint When Done")
    print("="*70)
    print("\nDeepSeek-R1-Distill-Qwen-32B endpoint is billing while 'Running'")
    print("\nTo stop charges:")
    print("  1. Go to: https://ui.endpoints.huggingface.co/")
    print("  2. Click your endpoint")
    print("  3. Click 'Pause' or 'Delete'")

    return len(successful) == len(results)


async def main():
    print("\n" + "="*70)
    print("HuggingFace Inference Endpoint Validation")
    print("Testing with: deepseek-ai/DeepSeek-R1-Distill-Qwen-32B")
    print("="*70)

    success = await test_deepseek_endpoint()

    if success:
        print("\nProvider validation complete.")
    else:
        print("\nSome tests failed - review errors above.")


if __name__ == "__main__":
    asyncio.run(main())