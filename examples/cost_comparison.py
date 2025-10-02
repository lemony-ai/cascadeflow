"""
Cost comparison between different providers and cascading strategies.

Shows how much money you can save with CascadeFlow.
"""

import asyncio
import os
from dotenv import load_dotenv

from cascadeflow import ModelConfig
from cascadeflow.providers import GroqProvider, OpenAIProvider

load_dotenv()


async def compare_costs():
    """Compare costs across different approaches."""

    print("💰 Cost Comparison\n")
    print("=" * 70)

    # Scenario: 10,000 queries per month
    monthly_queries = 10000

    print(f"Scenario: {monthly_queries:,} queries per month")
    print("Average query: ~30 tokens input, ~100 tokens output\n")

    # Approach 1: OpenAI GPT-4 only
    print("Approach 1: OpenAI GPT-4 Only")
    print("-" * 70)
    gpt4_cost_per_query = 0.03
    gpt4_monthly = monthly_queries * gpt4_cost_per_query
    print(f"Cost per query: ${gpt4_cost_per_query}")
    print(f"Monthly cost: ${gpt4_monthly:,.2f}")
    print(f"Annual cost: ${gpt4_monthly * 12:,.2f}\n")

    # Approach 2: OpenAI GPT-3.5 only
    print("Approach 2: OpenAI GPT-3.5 Only")
    print("-" * 70)
    gpt35_cost_per_query = 0.002
    gpt35_monthly = monthly_queries * gpt35_cost_per_query
    print(f"Cost per query: ${gpt35_cost_per_query}")
    print(f"Monthly cost: ${gpt35_monthly:,.2f}")
    print(f"Annual cost: ${gpt35_monthly * 12:,.2f}")
    print(f"Savings vs GPT-4: ${(gpt4_monthly - gpt35_monthly):,.2f}/month\n")

    # Approach 3: Groq free tier only
    print("Approach 3: Groq Free Tier Only")
    print("-" * 70)
    groq_cost_per_query = 0.0
    groq_monthly = monthly_queries * groq_cost_per_query
    print(f"Cost per query: ${groq_cost_per_query}")
    print(f"Monthly cost: ${groq_monthly:,.2f}")
    print(f"Annual cost: ${groq_monthly * 12:,.2f}")
    print(f"Savings vs GPT-4: ${(gpt4_monthly - groq_monthly):,.2f}/month")
    print(f"Savings vs GPT-3.5: ${(gpt35_monthly - groq_monthly):,.2f}/month\n")

    # Approach 4: Smart Cascade (Groq → GPT-3.5 → GPT-4)
    print("Approach 4: CascadeFlow Smart Cascade")
    print("-" * 70)
    print("Distribution:")
    print("  - 70% handled by Groq (free)")
    print("  - 25% cascade to GPT-3.5 ($0.002)")
    print("  - 5% cascade to GPT-4 ($0.03)")

    groq_queries = monthly_queries * 0.70
    gpt35_queries = monthly_queries * 0.25
    gpt4_queries = monthly_queries * 0.05

    cascade_monthly = (
            groq_queries * 0.0 +
            gpt35_queries * 0.002 +
            gpt4_queries * 0.03
    )

    print(f"\nMonthly cost: ${cascade_monthly:,.2f}")
    print(f"Annual cost: ${cascade_monthly * 12:,.2f}")
    print(f"Savings vs GPT-4: ${(gpt4_monthly - cascade_monthly):,.2f}/month ({((gpt4_monthly - cascade_monthly) / gpt4_monthly * 100):.0f}%)")
    print(f"Savings vs GPT-3.5: ${(gpt35_monthly - cascade_monthly):,.2f}/month ({((gpt35_monthly - cascade_monthly) / gpt35_monthly * 100):.0f}%)\n")

    # Summary
    print("=" * 70)
    print("SUMMARY: Annual Costs")
    print("=" * 70)
    print(f"GPT-4 Only:        ${gpt4_monthly * 12:>10,.2f}")
    print(f"GPT-3.5 Only:      ${gpt35_monthly * 12:>10,.2f}")
    print(f"Groq Only:         ${groq_monthly * 12:>10,.2f}")
    print(f"Smart Cascade:     ${cascade_monthly * 12:>10,.2f}")
    print("=" * 70)
    print(f"💰 Best Savings: ${(gpt4_monthly - cascade_monthly) * 12:,.2f}/year with Smart Cascade!")


async def real_cost_test():
    """Test actual costs with real API calls."""

    print("\n\n🧪 Real Cost Test\n")

    has_groq = bool(os.getenv("GROQ_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))

    if not has_groq and not has_openai:
        print("❌ No API keys found")
        return

    test_query = "Explain AI in one sentence"

    # Test Groq
    if has_groq:
        print("Testing Groq (FREE)...")
        provider = GroqProvider()
        try:
            result = await provider.complete(
                prompt=test_query,
                model="llama-3.1-8b-instant",
                max_tokens=100
            )
            print(f"✅ Groq cost: ${result.cost:.6f}")
        except Exception as e:
            print(f"❌ Groq error: {e}")
        finally:
            await provider.client.aclose()

    # Test OpenAI
    if has_openai:
        print("\nTesting OpenAI GPT-3.5...")
        provider = OpenAIProvider()
        try:
            result = await provider.complete(
                prompt=test_query,
                model="gpt-3.5-turbo",
                max_tokens=100
            )
            print(f"✅ GPT-3.5 cost: ${result.cost:.6f}")
        except Exception as e:
            print(f"❌ OpenAI error: {e}")
        finally:
            await provider.client.aclose()


async def main():
    """Run all comparisons."""

    await compare_costs()
    await real_cost_test()

    print("\n✅ Cost comparison complete!")


if __name__ == "__main__":
    asyncio.run(main())