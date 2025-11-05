"""
LiteLLM Integration Example

Demonstrates using LiteLLM for accurate cost tracking across multiple providers.

Shows:
- Cost calculation with LiteLLM
- Provider comparison
- Budget tracking
- Cost forecasting

NEW in v0.2.0 (Phase 2, Milestone 2.1):
- LiteLLMCostProvider for accurate pricing
- 10 strategic providers with clear value props
- Automatic fallback if LiteLLM not installed
"""

from cascadeflow.integrations.litellm import (
    SUPPORTED_PROVIDERS,
    LiteLLMCostProvider,
    calculate_cost,
    get_model_cost,
    get_provider_info,
    validate_provider,
)


def print_section(title):
    """Print section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():
    print_section("LiteLLM Integration Demo")
    print()
    print("This demo shows how to use LiteLLM for accurate cost tracking.")
    print()

    # ==================================================
    # Part 1: Supported Providers
    # ==================================================
    print_section("Part 1: Supported Providers")
    print()
    print(f"cascadeflow supports {len(SUPPORTED_PROVIDERS)} strategic providers:")
    print()

    for name, info in SUPPORTED_PROVIDERS.items():
        requires = "API key required" if info.requires_api_key else "No API key (local/self-hosted)"
        pricing = "LiteLLM pricing" if info.pricing_available else "Free/self-hosted"

        print(f"▶ {info.display_name}")
        print(f"  Value prop: {info.value_prop}")
        print(f"  Pricing: {pricing}")
        print(f"  Auth: {requires}")
        print(f"  Example models: {', '.join(info.example_models[:2])}")
        print()

    # ==================================================
    # Part 2: Provider Validation
    # ==================================================
    print_section("Part 2: Provider Validation")
    print()

    # Validate providers
    test_providers = ["openai", "anthropic", "groq", "unknown_provider"]

    for provider in test_providers:
        is_valid = validate_provider(provider)
        status = "✓ Supported" if is_valid else "✗ Not supported"
        print(f"  {provider:20s} → {status}")

    print()

    # Get provider info
    print("▶ Detailed info for Groq:")
    groq_info = get_provider_info("groq")
    if groq_info:
        print(f"  Display name: {groq_info.display_name}")
        print(f"  Value prop: {groq_info.value_prop}")
        print(f"  Example models: {', '.join(groq_info.example_models)}")

    # ==================================================
    # Part 3: Cost Calculation
    # ==================================================
    print_section("Part 3: Cost Calculation")
    print()

    # Create cost provider
    cost_provider = LiteLLMCostProvider()

    # Calculate costs for different models (use provider prefixes for accurate pricing)
    models = [
        {"name": "gpt-4", "in": 1000, "out": 500},
        {"name": "gpt-4o-mini", "in": 1000, "out": 500},
        {"name": "anthropic/claude-3-opus-20240229", "in": 1000, "out": 500},
        {"name": "anthropic/claude-3-haiku-20240307", "in": 1000, "out": 500},
    ]

    print("▶ Cost comparison (1000 input, 500 output tokens):")
    print()

    for model in models:
        cost = cost_provider.calculate_cost(
            model["name"], input_tokens=model["in"], output_tokens=model["out"]
        )
        print(f"  {model['name']:20s} → ${cost:.6f}")

    # ==================================================
    # Part 4: Pricing Information
    # ==================================================
    print_section("Part 4: Pricing Information")
    print()

    # Get detailed pricing
    print("▶ Detailed pricing for GPT-4:")
    pricing = cost_provider.get_model_cost("gpt-4")

    print(f"  Input cost:  ${pricing['input_cost_per_token']:.8f} per token")
    print(f"  Output cost: ${pricing['output_cost_per_token']:.8f} per token")
    print(f"  Max tokens:  {pricing['max_tokens']:,}")
    print(f"  Streaming:   {pricing['supports_streaming']}")

    # Calculate cost per 1M tokens
    input_per_1m = pricing["input_cost_per_token"] * 1_000_000
    output_per_1m = pricing["output_cost_per_token"] * 1_000_000

    print()
    print(f"  Cost per 1M input tokens:  ${input_per_1m:.2f}")
    print(f"  Cost per 1M output tokens: ${output_per_1m:.2f}")

    # ==================================================
    # Part 5: Budget Tracking
    # ==================================================
    print_section("Part 5: Budget Tracking")
    print()

    # Simulate budget tracking
    budget = 0.10  # $0.10 budget
    spent = 0.0

    print(f"▶ Budget: ${budget:.2f}")
    print()

    queries = [
        {"model": "gpt-4", "in": 500, "out": 250, "desc": "Complex analysis"},
        {"model": "gpt-4", "in": 300, "out": 150, "desc": "Follow-up question"},
        {"model": "gpt-4o-mini", "in": 200, "out": 100, "desc": "Simple query"},
        {"model": "gpt-3.5-turbo", "in": 100, "out": 50, "desc": "Quick check"},
    ]

    for i, query in enumerate(queries, 1):
        cost = cost_provider.calculate_cost(
            query["model"], input_tokens=query["in"], output_tokens=query["out"]
        )

        spent += cost
        remaining = budget - spent
        percent = (spent / budget) * 100

        print(f"  Query {i}: {query['desc']}")
        print(f"    Model: {query['model']}")
        print(f"    Cost: ${cost:.6f}")
        print(f"    Spent: ${spent:.6f} ({percent:.1f}% of budget)")
        print(f"    Remaining: ${remaining:.6f}")

        if remaining < 0:
            print(f"    ⚠️  OVER BUDGET by ${abs(remaining):.6f}")
        elif remaining < budget * 0.2:
            print(f"    ⚠️  WARNING: Only ${remaining:.6f} left")

        print()

    # ==================================================
    # Part 6: Cost Forecasting
    # ==================================================
    print_section("Part 6: Cost Forecasting")
    print()

    # Forecast costs for different scenarios
    scenarios = [
        {"name": "Low usage", "queries_per_day": 10, "tokens_per_query": 500},
        {"name": "Medium usage", "queries_per_day": 100, "tokens_per_query": 1000},
        {"name": "High usage", "queries_per_day": 1000, "tokens_per_query": 2000},
    ]

    print("▶ Monthly cost forecast (using gpt-4):")
    print()

    for scenario in scenarios:
        # Estimate tokens (50/50 input/output split)
        input_tokens = scenario["tokens_per_query"] // 2
        output_tokens = scenario["tokens_per_query"] // 2

        # Cost per query
        cost_per_query = cost_provider.calculate_cost(
            "gpt-4", input_tokens=input_tokens, output_tokens=output_tokens
        )

        # Daily cost
        daily_cost = cost_per_query * scenario["queries_per_day"]

        # Monthly cost (30 days)
        monthly_cost = daily_cost * 30

        print(f"  {scenario['name']}:")
        print(f"    Queries/day: {scenario['queries_per_day']}")
        print(f"    Tokens/query: {scenario['tokens_per_query']}")
        print(f"    Cost/query: ${cost_per_query:.6f}")
        print(f"    Daily cost: ${daily_cost:.2f}")
        print(f"    Monthly cost: ${monthly_cost:.2f}")
        print()

    # ==================================================
    # Part 7: Provider Comparison
    # ==================================================
    print_section("Part 7: Provider Comparison")
    print()

    # Compare cost across providers for same workload
    workload_input = 10000
    workload_output = 5000

    print(f"▶ Cost comparison for {workload_input} input + {workload_output} output tokens:")
    print()

    comparison_models = [
        "gpt-4",
        "gpt-4o-mini",
        "gpt-3.5-turbo",
        "anthropic/claude-3-opus-20240229",
        "anthropic/claude-3-haiku-20240307",
    ]

    costs = []
    for model in comparison_models:
        cost = cost_provider.calculate_cost(
            model, input_tokens=workload_input, output_tokens=workload_output
        )
        costs.append((model, cost))

    # Sort by cost
    costs.sort(key=lambda x: x[1])

    for model, cost in costs:
        print(f"  {model:20s} → ${cost:.6f}")

    print()
    cheapest = costs[0]
    most_expensive = costs[-1]

    savings = most_expensive[1] - cheapest[1]
    percent_savings = (savings / most_expensive[1]) * 100

    print(
        f"  💡 Using {cheapest[0]} instead of {most_expensive[0]} saves "
        f"${savings:.6f} ({percent_savings:.1f}%)"
    )

    # ==================================================
    # Part 8: Convenience Functions
    # ==================================================
    print_section("Part 8: Convenience Functions")
    print()

    # Direct function calls (no need to create provider instance)
    print("▶ Using convenience functions:")
    print()

    # Calculate cost directly
    cost = calculate_cost("gpt-4", input_tokens=100, output_tokens=50)
    print(f"  calculate_cost('gpt-4', 100, 50) → ${cost:.6f}")

    # Get pricing directly
    pricing = get_model_cost("gpt-4")
    print(
        f"  get_model_cost('gpt-4')['input_cost_per_token'] → ${pricing['input_cost_per_token']:.8f}"
    )

    # ==================================================
    # Summary
    # ==================================================
    print_section("Summary")
    print()
    print("✅ Benefits of LiteLLM integration:")
    print("   - Always up-to-date pricing (maintained by LiteLLM team)")
    print("   - Covers 100+ models across 10+ providers")
    print("   - Handles input/output token pricing separately")
    print("   - Automatic fallback if LiteLLM not installed")
    print()
    print("✅ Strategic provider selection:")
    print("   - 10 providers with clear value propositions")
    print("   - Mix of cloud and self-hosted options")
    print("   - Provider validation and info lookup")
    print()
    print("✅ Production-ready cost tracking:")
    print("   - Pre-flight cost estimation")
    print("   - Real-time budget tracking")
    print("   - Cost forecasting and comparison")
    print()
    print("=" * 70)
    print()
    print("Installation:")
    print("  pip install litellm")
    print()
    print("  Optional for more providers:")
    print("  pip install litellm[extra_providers]")
    print("=" * 70)


if __name__ == "__main__":
    main()
