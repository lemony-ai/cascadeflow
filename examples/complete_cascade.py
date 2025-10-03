"""
Complete cascade with all 7 providers.

This is the ultimate example showing all providers working together.
"""

import asyncio
from dotenv import load_dotenv

from cascadeflow import CascadeAgent, ModelConfig, UserTier

load_dotenv()


async def main():
    """Run complete cascade with all providers."""

    print("🌊 CascadeFlow - Complete 7-Provider Cascade\n")

    # Define complete cascade (all providers, cheapest → most expensive)
    models = [
        # Tier 1: FREE Local
        ModelConfig(
            name="llama3:8b",
            provider="ollama",
            cost=0.0,
            keywords=["simple", "quick"]
        ),

        # Tier 2: FREE Self-Hosted (if available)
        ModelConfig(
            name="meta-llama/Llama-3-70B-Instruct",
            provider="vllm",
            base_url="http://localhost:8000/v1",
            cost=0.0,
            keywords=["moderate", "detailed"]
        ),

        # Tier 3: FREE Cloud
        ModelConfig(
            name="llama3-70b-8192",
            provider="groq",
            cost=0.0,
            keywords=["moderate"]
        ),

        # Tier 4: FREE/Cheap Specialists
        ModelConfig(
            name="codellama/CodeLlama-34b-Instruct-hf",
            provider="huggingface",
            cost=0.0,
            domains=["code"]
        ),

        # Tier 5: Cheap Cloud
        ModelConfig(
            name="meta-llama/Llama-3-70b-chat-hf",
            provider="together",
            cost=0.0009
        ),

        # Tier 6: Moderate Cost
        ModelConfig(
            name="gpt-3.5-turbo",
            provider="openai",
            cost=0.002
        ),

        # Tier 7: Premium
        ModelConfig(
            name="gpt-4",
            provider="openai",
            cost=0.03
        ),
    ]

    # Or just use smart_default!
    # agent = CascadeAgent.smart_default()

    agent = CascadeAgent(models, verbose=True)

    print(f"Initialized cascade with {len(models)} models across 7 providers:\n")
    for i, model in enumerate(models, 1):
        print(f"{i}. {model.name} ({model.provider}) - ${model.cost:.6f}")

    # Test query
    query = "Explain quantum computing in simple terms"

    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}\n")

    try:
        result = await agent.run(query)

        print(f"\n✅ Success!")
        print(f"Model used: {result.model_used}")
        print(f"Provider: {result.provider}")
        print(f"Cost: ${result.total_cost:.6f}")
        print(f"Tokens: {result.total_tokens}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Cascaded: {result.cascaded}")

        if result.cascaded:
            print(f"Cascade path: {' → '.join(result.cascade_path)}")
            print(f"Attempts: {result.attempts}")

        print(f"\n💰 Potential savings:")
        gpt4_cost = result.total_tokens / 1000 * 0.03
        savings = gpt4_cost - result.total_cost
        savings_pct = (savings / gpt4_cost * 100) if gpt4_cost > 0 else 0
        print(f"  If used GPT-4 only: ${gpt4_cost:.6f}")
        print(f"  Actual cost: ${result.total_cost:.6f}")
        print(f"  Saved: ${savings:.6f} ({savings_pct:.0f}%)")

        print(f"\nResponse:\n{result.content[:500]}...")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())