"""
Ollama + Cloud Cascade Test

Tests cascadeflow cascade logic with Ollama (local draft) + OpenAI (cloud verifier).
This demonstrates the same quality_threshold configuration as basic_usage.py.

Environment Variables (optional):
- OLLAMA_MODEL: Ollama model name (default: mistral:7b-instruct)
- OLLAMA_BASE_URL: Ollama server URL (default: http://localhost:11434)
- CLOUD_MODEL: Cloud verifier model (default: gpt-4o)

Usage:
    # Use default models
    python examples/ollama_cascade.py

    # Use your own Ollama model
    export OLLAMA_MODEL="gemma3:12b"
    python examples/ollama_cascade.py

    # Use custom Ollama server
    export OLLAMA_BASE_URL="http://192.168.0.199:11434"
    export OLLAMA_MODEL="deepseek-r1:7b"
    python examples/ollama_cascade.py
"""

import asyncio
import os
from cascadeflow import CascadeAgent, ModelConfig


async def main():
    print("=" * 80)
    print("Ollama + Cloud Cascade Test")
    print("=" * 80)
    print()

    # Get model names from environment or use defaults
    ollama_model = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    cloud_model = os.getenv("CLOUD_MODEL", "gpt-4o")

    print(f"Configuration:")
    print(f"  Ollama model: {ollama_model}")
    print(f"  Ollama URL: {ollama_base_url}")
    print(f"  Cloud model: {cloud_model}")
    print()

    # Create agent with Ollama draft + OpenAI verifier (same thresholds as basic_usage.py)
    agent = CascadeAgent(
        models=[
            # Draft model - Ollama (local, free)
            ModelConfig(
                name=ollama_model,
                provider="ollama",
                cost=0.0,  # Free local execution
                base_url=ollama_base_url,
                quality_threshold=0.7,  # Accept if confidence >= 70%
            ),
            # Verifier model - OpenAI (cloud, expensive)
            ModelConfig(
                name=cloud_model,
                provider="openai",
                cost=0.00625,  # $6.25 per 1M tokens (blended estimate)
                quality_threshold=0.95,  # Very high quality
            ),
        ]
    )

    print(f"✅ Agent created with 2-tier cascade:")
    print(f"   Tier 1: {ollama_model} (Ollama) - quality_threshold=0.7")
    print(f"   Tier 2: {cloud_model} (OpenAI) - quality_threshold=0.95")
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
        print("✅ SUCCESS: Ollama cascade test passed")
        print("=" * 80)

    except Exception as e:
        print(f"❌ ERROR: {e}")
        print()
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
