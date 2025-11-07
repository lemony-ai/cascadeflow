"""
vLLM + Cloud Cascade Test

Tests cascadeflow cascade logic with vLLM (local draft) + OpenAI (cloud verifier).
This demonstrates the same quality_threshold configuration as basic_usage.py.

Prerequisites:
1. Start vLLM server:
   python -m vllm.entrypoints.openai.api_server \
     --model Qwen/Qwen2.5-7B-Instruct \
     --host 0.0.0.0 \
     --port 8000

2. Set OpenAI API key:
   export OPENAI_API_KEY="your-key-here"
"""

import asyncio
from cascadeflow import CascadeAgent, ModelConfig


async def main():
    print("=" * 80)
    print("vLLM + Cloud Cascade Test")
    print("=" * 80)
    print()

    # Create agent with vLLM draft + OpenAI verifier (same thresholds as basic_usage.py)
    agent = CascadeAgent(
        models=[
            # Draft model - vLLM (local, free)
            ModelConfig(
                name="Qwen/Qwen2.5-7B-Instruct",
                provider="vllm",
                cost=0.0,  # Free local execution
                base_url="http://localhost:8000/v1",
                quality_threshold=0.7,  # Accept if confidence >= 70%
            ),
            # Verifier model - OpenAI (cloud, expensive)
            ModelConfig(
                name="gpt-4o",
                provider="openai",
                cost=0.00625,  # $6.25 per 1M tokens (blended estimate)
                quality_threshold=0.95,  # Very high quality
            ),
        ]
    )

    print(f"✅ Agent created with 2-tier cascade:")
    print(f"   Tier 1: Qwen/Qwen2.5-7B-Instruct (vLLM) - quality_threshold=0.7")
    print(f"   Tier 2: gpt-4o (OpenAI) - quality_threshold=0.95")
    print()

    # Test query
    query = "What is TypeScript in one sentence?"
    print(f"Query: {query}")
    print()

    try:
        result = await agent.run(query)

        print("Result:")
        print(f"  Model used: {result.model_used}")
        print(f"  Cascaded: {result.cascaded}")
        print(f"  Cost: ${result.total_cost:.6f}")

        if hasattr(result, "draft_accepted"):
            print(f"  Draft accepted: {result.draft_accepted}")

        if hasattr(result, "complexity"):
            print(f"  Complexity: {result.complexity}")

        print()
        print(f"Response: {result.content}")
        print()

        print("=" * 80)
        print("✅ SUCCESS: vLLM cascade test passed")
        print("=" * 80)

    except Exception as e:
        print(f"❌ ERROR: {e}")
        print()
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
