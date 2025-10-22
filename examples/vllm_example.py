"""
vLLM provider example.

Demonstrates using vLLM for high-performance local inference.

Prerequisites:
1. Install vLLM: pip install vllm
2. Start vLLM server:
   python -m vllm.entrypoints.openai.api_server \
     --model meta-llama/Llama-3-8B-Instruct \
     --host 0.0.0.0 \
     --port 8000
"""

import asyncio

from cascadeflow.providers.vllm import VLLMProvider


async def main():
    """Test vLLM provider."""

    print("vLLM Provider Test\n")

    # Initialize provider
    provider = VLLMProvider(base_url="http://localhost:8000/v1")

    try:
        # List available models
        print("Checking available models...")
        models = await provider.list_models()
        print(f"Available models: {models}\n")

        if not models:
            print("No models found. Make sure vLLM server is running.")
            return

        # Use first available model
        model = models[0]
        print(f"Using model: {model}\n")

        # Test completion
        print("Testing completion...")
        result = await provider.complete(
            prompt="Explain AI in one sentence", model=model, max_tokens=100
        )

        print(f"Response: {result.content}")
        print(f"Tokens: {result.tokens_used}")
        print(f"Latency: {result.latency_ms:.0f}ms")
        print(f"Cost: ${result.cost:.4f} (self-hosted)")

    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure vLLM server is running:")
        print("  python -m vllm.entrypoints.openai.api_server \\")
        print("    --model meta-llama/Llama-3-8B-Instruct \\")
        print("    --host 0.0.0.0 --port 8000")

    finally:
        await provider.client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
