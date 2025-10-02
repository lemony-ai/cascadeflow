"""
Test smart_default() - auto-detects all your providers.
"""

import asyncio
from dotenv import load_dotenv

from cascadeflow import CascadeAgent

load_dotenv()


async def main():
    """Test smart_default."""

    print("🌊 CascadeFlow - Smart Default Test\n")

    try:
        # Auto-detect providers
        agent = CascadeAgent.smart_default()

        print(f"\nDetected {len(agent.models)} models:")
        for i, model in enumerate(agent.models, 1):
            print(f"{i}. {model.name} ({model.provider}) - ${model.cost:.6f}")

        # Test query
        query = "Explain AI in one sentence"

        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}\n")

        result = await agent.run(query)

        print(f"✅ Success!")
        print(f"Model: {result.model_used}")
        print(f"Provider: {result.provider}")
        print(f"Cost: ${result.total_cost:.6f}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Cascaded: {result.cascaded}")

        if result.cascaded:
            print(f"Cascade path: {' → '.join(result.cascade_path)}")

        print(f"\nResponse: {result.content}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())