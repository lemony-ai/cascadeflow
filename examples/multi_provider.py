"""
Multi-Provider Cascade Example
===============================

Demonstrates mixing multiple AI providers in a single cascade for maximum
flexibility, cost savings, and reliability.

What it demonstrates:
- Mixing OpenAI, Anthropic, and Groq in one cascade
- Provider-specific features and capabilities
- Fallback strategies across providers
- Cost comparison between providers
- Different use cases for each provider
- API key management for multiple providers

Requirements:
    - cascadeflow[all]
    - At least 2 provider API keys (OpenAI, Anthropic, or Groq)

Setup:
    pip install cascadeflow[all]
    export OPENAI_API_KEY="sk-..."
    export ANTHROPIC_API_KEY="sk-ant-..."
    export GROQ_API_KEY="gsk_..."
    python examples/multi_provider.py

Why Mix Providers:
    1. Cost optimization - Use free/cheap providers first
    2. Feature diversity - Different providers excel at different tasks
    3. Reliability - Fallback if one provider is down
    4. Speed - Fast providers for drafts, accurate for verification
    5. Compliance - Some providers better for regulated industries

Provider Comparison:
    OpenAI (GPT-4o, GPT-4o-mini):
    - ✅ Best overall quality
    - ✅ Excellent tool calling
    - ✅ Wide model selection
    - ❌ Most expensive
    - ❌ Rate limits can be strict

    Anthropic (Claude 3 family):
    - ✅ Excellent for long context
    - ✅ Strong reasoning
    - ✅ Good for writing tasks
    - ❌ Mid-high cost
    - ❌ Fewer model options

    Groq (Llama 3.1, Mixtral):
    - ✅ Extremely fast (8x faster)
    - ✅ Free tier available
    - ✅ Good for simple queries
    - ❌ Limited context window
    - ❌ Lower quality on complex tasks

Documentation:
    📖 Provider Guide: docs/guides/providers.md
    📖 Quick Start: docs/guides/quickstart.md
    📚 Examples README: examples/README.md
"""

import asyncio
import os

from cascadeflow import CascadeAgent, ModelConfig

# ═══════════════════════════════════════════════════════════════════════════
# HELPER: Check Available Providers
# ═══════════════════════════════════════════════════════════════════════════


def check_available_providers():
    """Check which provider API keys are available."""
    providers = {
        "OpenAI": os.getenv("OPENAI_API_KEY"),
        "Anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "Groq": os.getenv("GROQ_API_KEY"),
    }

    available = {name: bool(key) for name, key in providers.items()}

    print("\n🔍 Checking available providers:")
    for name, is_available in available.items():
        status = "✅" if is_available else "❌"
        print(f"   {status} {name}: {'Available' if is_available else 'Not configured'}")

    return available


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN 1: Free-First Cascade (Maximum Cost Savings)
# ═══════════════════════════════════════════════════════════════════════════


async def pattern_1_free_first():
    """
    Pattern 1: Free-First Cascade

    Start with free/cheap providers, escalate only when needed.
    Best for: High-volume applications, cost-sensitive workloads
    """

    print("\n" + "=" * 70)
    print("PATTERN 1: Free-First Cascade")
    print("=" * 70)
    print("\nStrategy: Groq (free) → GPT-4o-mini (cheap) → GPT-4o (premium)")
    print("Best for: Cost optimization, high volume, simple queries\n")

    # Build model list based on available providers
    models = []

    # Tier 1: Groq (free and fast!)
    if os.getenv("GROQ_API_KEY"):
        models.append(
            ModelConfig(
                name="llama-3.1-8b-instant",
                provider="groq",
                cost=0.0,  # Free!
                speed_ms=200,  # Very fast
            )
        )
        print("✅ Tier 1: Groq Llama 3.1 8B (FREE, 200ms)")

    # Tier 2: OpenAI Mini (cheap)
    if os.getenv("OPENAI_API_KEY"):
        models.append(
            ModelConfig(
                name="gpt-4o-mini",
                provider="openai",
                cost=0.00015,  # Very cheap
                speed_ms=600,
            )
        )
        print("✅ Tier 2: GPT-4o-mini ($0.00015 per request)")

    # Tier 3: OpenAI Premium (expensive but best quality)
    if os.getenv("OPENAI_API_KEY"):
        models.append(
            ModelConfig(
                name="gpt-4o",
                provider="openai",
                cost=0.00625,  # Premium pricing
                speed_ms=1500,
            )
        )
        print("✅ Tier 3: GPT-4o ($0.00625 per request)")

    if len(models) < 2:
        print("\n⚠️  Need at least 2 providers for cascade")
        print("   Set GROQ_API_KEY and/or OPENAI_API_KEY")
        return

    # Create agent
    agent = CascadeAgent(models=models)

    # Test queries at different complexity levels
    queries = [
        ("What is 2+2?", "simple"),
        ("Explain Python in one sentence.", "moderate"),
        ("Write a technical explanation of quantum computing.", "complex"),
    ]

    total_cost = 0

    for query, complexity in queries:
        print(f"\n{'─'*70}")
        print(f"Query ({complexity}): {query}")
        print(f"{'─'*70}")

        result = await agent.run(query, max_tokens=200, temperature=0.7)
        total_cost += result.total_cost

        print(f"\n💡 Answer: {result.content[:150]}...")
        print("\n📊 Stats:")
        print(f"   Model Used: {result.model_used}")
        print(f"   Cost: ${result.total_cost:.6f}")
        print(f"   Latency: {result.latency_ms:.0f}ms")
        if result.draft_accepted:
            print("   ✅ Draft Accepted (Verifier skipped!)")
        else:
            print("   🔄 Cascaded (Both models used)")

    print(f"\n{'='*70}")
    print(f"💰 Pattern 1 Total Cost: ${total_cost:.6f}")
    print(f"{'='*70}")

    # Show savings vs all-GPT-4o
    all_gpt4o_cost = len(queries) * 0.00625
    savings = ((all_gpt4o_cost - total_cost) / all_gpt4o_cost) * 100
    print(f"\n💡 Savings vs all-GPT-4o: {savings:.1f}%")
    print(f"   All GPT-4o: ${all_gpt4o_cost:.6f}")
    print(f"   With cascade: ${total_cost:.6f}")


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN 2: Cross-Provider Drafter/Verifier
# ═══════════════════════════════════════════════════════════════════════════


async def pattern_2_cross_provider():
    """
    Pattern 2: Cross-Provider Drafter/Verifier

    Use one provider for drafting, another for verification.
    Best for: Leveraging strengths of different providers
    """

    print("\n\n" + "=" * 70)
    print("PATTERN 2: Cross-Provider Drafter/Verifier")
    print("=" * 70)
    print("\nStrategy: Fast provider drafts → Premium provider validates")
    print("Best for: Quality assurance, specialized tasks\n")

    # Check what we have available
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))

    if not (has_groq or has_openai or has_anthropic):
        print("⚠️  Need at least one provider API key")
        return

    # Build best combination from available providers
    models = []

    if has_groq:
        # Groq as fast drafter
        models.append(
            ModelConfig(
                name="llama-3.3-70b-versatile",
                provider="groq",
                cost=0.0,
                speed_ms=300,
            )
        )
        print("✅ Drafter: Groq Llama 3.1 70B (FREE, 300ms)")

    if has_anthropic:
        # Claude as premium verifier
        models.append(
            ModelConfig(
                name="claude-sonnet-4-5-20250929",
                provider="anthropic",
                cost=0.003,
                speed_ms=1000,
            )
        )
        print("✅ Verifier: Claude Sonnet 4.5 ($0.003)")
    elif has_openai:
        # GPT-4o as fallback verifier
        models.append(
            ModelConfig(
                name="gpt-4o",
                provider="openai",
                cost=0.00625,
                speed_ms=1500,
            )
        )
        print("✅ Verifier: GPT-4o ($0.00625)")

    if len(models) < 2:
        print("\n⚠️  Need at least 2 providers for this pattern")
        print("   Try Pattern 1 or Pattern 3 instead")
        return

    agent = CascadeAgent(models=models)

    # Test with a writing task (good for cross-provider validation)
    query = "Write a professional email requesting a meeting with a client."

    print(f"\n{'─'*70}")
    print(f"Query: {query}")
    print(f"{'─'*70}")

    result = await agent.run(query, max_tokens=300, temperature=0.7)

    print("\n✉️  Generated Email:\n")
    print(result.content)

    print("\n📊 Stats:")
    print(f"   Model Used: {result.model_used}")
    print(f"   Cost: ${result.total_cost:.6f}")
    print(f"   Latency: {result.latency_ms:.0f}ms")
    print(f"   Providers: {models[0].provider} → {models[-1].provider}")


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN 3: Provider-Specific Specialization
# ═══════════════════════════════════════════════════════════════════════════


async def pattern_3_specialization():
    """
    Pattern 3: Provider-Specific Specialization

    Route different types of queries to providers that excel at them.
    Best for: Maximizing quality while controlling costs
    """

    print("\n\n" + "=" * 70)
    print("PATTERN 3: Provider-Specific Specialization")
    print("=" * 70)
    print("\nStrategy: Match provider strengths to query types")
    print("Best for: Quality optimization, diverse workloads\n")

    # Build specialized model list
    models = []

    # OpenAI: Best for technical/code tasks
    if os.getenv("OPENAI_API_KEY"):
        models.append(
            ModelConfig(
                name="gpt-4o",
                provider="openai",
                cost=0.00625,
                speed_ms=1500,
            )
        )
        print("✅ Technical/Code: GPT-4o (OpenAI)")

    # Anthropic: Best for long-form writing
    if os.getenv("ANTHROPIC_API_KEY"):
        models.append(
            ModelConfig(
                name="claude-sonnet-4-5-20250929",
                provider="anthropic",
                cost=0.003,
                speed_ms=1000,
            )
        )
        print("✅ Writing/Analysis: Claude Sonnet 4.5 (Anthropic)")

    # Groq: Best for simple/fast queries
    if os.getenv("GROQ_API_KEY"):
        models.append(
            ModelConfig(
                name="llama-3.1-8b-instant",
                provider="groq",
                cost=0.0,
                speed_ms=200,
            )
        )
        print("✅ Simple/Fast: Llama 3.1 8B (Groq)")

    if len(models) < 2:
        print("\n⚠️  Need at least 2 providers")
        return

    agent = CascadeAgent(models=models)

    # Test queries that showcase different provider strengths
    test_cases = [
        ("Write Python code to sort a list", "Technical (OpenAI strength)"),
        ("Write a 200-word essay on climate change", "Writing (Anthropic strength)"),
        ("What is the capital of France?", "Simple fact (Groq strength)"),
    ]

    total_cost = 0

    for query, task_type in test_cases:
        print(f"\n{'─'*70}")
        print(f"Task: {task_type}")
        print(f"Query: {query}")
        print(f"{'─'*70}")

        result = await agent.run(query, max_tokens=250, temperature=0.7)
        total_cost += result.total_cost

        print("\n📊 Result:")
        print(
            f"   Provider: {result.model_used.split('-')[0] if '-' in result.model_used else 'unknown'}"
        )
        print(f"   Model: {result.model_used}")
        print(f"   Cost: ${result.total_cost:.6f}")
        print(f"   Latency: {result.latency_ms:.0f}ms")

    print(f"\n{'='*70}")
    print(f"💰 Pattern 3 Total Cost: ${total_cost:.6f}")
    print(f"{'='*70}")


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN 4: Reliability with Fallbacks
# ═══════════════════════════════════════════════════════════════════════════


async def pattern_4_reliability():
    """
    Pattern 4: Reliability with Fallbacks

    Use multiple providers for redundancy and high availability.
    Best for: Production systems, critical applications
    """

    print("\n\n" + "=" * 70)
    print("PATTERN 4: Reliability with Fallbacks")
    print("=" * 70)
    print("\nStrategy: Multiple providers for redundancy")
    print("Best for: High availability, production systems\n")

    # Build redundant model list (same tier, different providers)
    models = []

    if os.getenv("OPENAI_API_KEY"):
        models.append(
            ModelConfig(
                name="gpt-4o-mini",
                provider="openai",
                cost=0.00015,
            )
        )
        print("✅ Primary: GPT-4o-mini (OpenAI)")

    if os.getenv("ANTHROPIC_API_KEY"):
        models.append(
            ModelConfig(
                name="claude-3-5-haiku-20241022",
                provider="anthropic",
                cost=0.001,
            )
        )
        print("✅ Fallback: Claude 3.5 Haiku (Anthropic)")

    if os.getenv("GROQ_API_KEY"):
        models.append(
            ModelConfig(
                name="llama-3.3-70b-versatile",
                provider="groq",
                cost=0.0,
            )
        )
        print("✅ Fallback: Llama 3.1 70B (Groq)")

    if len(models) < 2:
        print("\n⚠️  Need at least 2 providers for fallback pattern")
        return

    print(f"\n💡 Configured {len(models)} providers for redundancy")
    print("   If one fails, cascade automatically tries the next\n")

    agent = CascadeAgent(models=models)

    query = "Explain microservices architecture in 100 words."

    print(f"{'─'*70}")
    print(f"Query: {query}")
    print(f"{'─'*70}")

    result = await agent.run(query, max_tokens=150, temperature=0.7)

    print(f"\n💡 Answer: {result.content[:200]}...")
    print("\n📊 Stats:")
    print(f"   Provider Used: {result.model_used}")
    print(f"   Cost: ${result.total_cost:.6f}")
    print("   ✅ System remained available despite potential failures")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════


async def main():
    """
    Main example demonstrating multi-provider patterns.
    """

    print("🌊 cascadeflow Multi-Provider Examples")
    print("=" * 70)
    print("\nDemonstrating 4 patterns for mixing AI providers:")
    print("  1. Free-First Cascade - Maximum cost savings")
    print("  2. Cross-Provider Drafter/Verifier - Quality assurance")
    print("  3. Provider-Specific Specialization - Quality optimization")
    print("  4. Reliability with Fallbacks - High availability")

    # Check available providers
    available = check_available_providers()

    provider_count = sum(available.values())

    if provider_count == 0:
        print("\n❌ No provider API keys found!")
        print("\nTo run this example, set at least one API key:")
        print("   export OPENAI_API_KEY='sk-...'")
        print("   export ANTHROPIC_API_KEY='sk-ant-...'")
        print("   export GROQ_API_KEY='gsk_...'")
        return

    print(f"\n✅ Found {provider_count} provider(s) configured")

    if provider_count == 1:
        print("\n💡 Tip: Set multiple provider API keys to try all patterns!")

    # Run available patterns based on configured providers
    print("\n" + "=" * 70)
    print("RUNNING PATTERNS")
    print("=" * 70)

    # Pattern 1: Always try (works with any providers)
    await pattern_1_free_first()

    # Pattern 2: Try if we have at least 2 providers
    if provider_count >= 2:
        await pattern_2_cross_provider()

    # Pattern 3: Try if we have at least 2 providers
    if provider_count >= 2:
        await pattern_3_specialization()

    # Pattern 4: Best with 3 providers, but works with 2
    if provider_count >= 2:
        await pattern_4_reliability()

    # Summary
    print("\n\n" + "=" * 70)
    print("🎓 KEY TAKEAWAYS")
    print("=" * 70)

    print("\n1. Provider Selection:")
    print("   ├─ Groq: Best for speed and cost (FREE!)")
    print("   ├─ OpenAI: Best for overall quality and features")
    print("   └─ Anthropic: Best for long context and reasoning")

    print("\n2. Mixing Benefits:")
    print("   ├─ Cost optimization (use free/cheap first)")
    print("   ├─ Quality specialization (right provider for task)")
    print("   ├─ High availability (fallback if provider down)")
    print("   └─ Flexibility (switch based on requirements)")

    print("\n3. Pattern Selection:")
    print("   ├─ High volume? → Pattern 1 (Free-First)")
    print("   ├─ Quality critical? → Pattern 2 (Cross-Provider)")
    print("   ├─ Diverse tasks? → Pattern 3 (Specialization)")
    print("   └─ Production system? → Pattern 4 (Reliability)")

    print("\n4. Cost Comparison:")
    print("   ├─ OpenAI GPT-4o: $0.00625 per request (premium)")
    print("   ├─ Anthropic Claude: $0.003 per request (mid-tier)")
    print("   ├─ OpenAI GPT-4o-mini: $0.00015 per request (cheap)")
    print("   └─ Groq Llama: $0.00 per request (FREE!)")

    print("\n5. Provider Features:")
    print("   ├─ All support: Text generation, streaming")
    print("   ├─ OpenAI: Best tool calling, function calling")
    print("   ├─ Anthropic: 200k token context, XML support")
    print("   └─ Groq: 8x faster inference, lower latency")

    print("\n📚 Learn more:")
    print("   • docs/guides/providers.md - Provider comparison")
    print("   • docs/guides/quickstart.md - Getting started")
    print("   • examples/basic_usage.py - Single provider basics\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        print("\n💡 Tip: Check your API keys are set correctly")
