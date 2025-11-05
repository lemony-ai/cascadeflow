"""
LiteLLM Provider Integration Example

cascadeflow integrates with LiteLLM for:
- Cost tracking across 100+ models
- Access to additional providers (DeepSeek, Google, etc.)
- Automatic pricing updates
- Budget management

This example shows how to use LiteLLM's features with cascadeflow.

Requirements:
    pip install cascadeflow[all]
    pip install litellm  # For extended provider support

Setup:
    # For DeepSeek
    export DEEPSEEK_API_KEY="sk-..."

    # For Google/Vertex AI
    export GOOGLE_API_KEY="..."

    # For Azure OpenAI
    export AZURE_API_KEY="..."
    export AZURE_API_BASE="https://your-resource.openai.azure.com"

    python examples/integrations/litellm_providers.py

What you'll learn:
- Use LiteLLM for cost tracking
- Access additional providers via LiteLLM
- Compare costs across providers
- Manage budgets per user
"""

import asyncio
import os

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required if variables are already set

from cascadeflow.integrations.litellm import (
    SUPPORTED_PROVIDERS,
    LiteLLMBudgetTracker,
    LiteLLMCostProvider,
    calculate_cost,
    get_model_cost,
    get_provider_info,
)


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def example_1_supported_providers():
    """Example 1: List all supported providers via LiteLLM."""
    print_section("Example 1: Supported Providers via LiteLLM")

    print("cascadeflow supports these providers through LiteLLM integration:\n")

    for provider_name, provider_info in SUPPORTED_PROVIDERS.items():
        print(f"📦 {provider_info.display_name}")
        print(f"   Value: {provider_info.value_prop}")
        print(f"   Models: {', '.join(provider_info.example_models[:2])}...")
        print(f"   Pricing: {'✅ Available' if provider_info.pricing_available else '❌ Not available'}")
        print()

    print("💡 TIP: Use get_provider_info() to check provider capabilities at runtime.")


def example_2_cost_calculation():
    """Example 2: Calculate costs using LiteLLM's pricing database."""
    print_section("Example 2: Cost Calculation with LiteLLM")

    # Initialize cost provider
    cost_provider = LiteLLMCostProvider()

    # Test different models (with provider prefixes for accurate LiteLLM pricing)
    test_cases = [
        ("gpt-4o", 1000, 500, "OpenAI"),
        ("anthropic/claude-3-5-sonnet-20241022", 1000, 500, "Anthropic"),
        ("deepseek/deepseek-coder", 1000, 500, "DeepSeek"),
        ("gemini/gemini-1.5-flash", 1000, 500, "Google"),
    ]

    print("Cost comparison for 1K input + 500 output tokens:\n")

    for model, input_tokens, output_tokens, provider in test_cases:
        try:
            cost = cost_provider.calculate_cost(
                model=model, input_tokens=input_tokens, output_tokens=output_tokens
            )
            print(f"  {provider:15} {model:25} ${cost:.6f}")
        except Exception as e:
            print(f"  {provider:15} {model:25} ❌ Error: {e}")

    print("\n💡 TIP: LiteLLM automatically updates pricing - no manual updates needed!")


def example_3_model_pricing_info():
    """Example 3: Get detailed pricing information for models."""
    print_section("Example 3: Get Model Pricing Details")

    models_to_check = [
        "gpt-4o",
        "anthropic/claude-3-5-sonnet-20241022",
        "deepseek/deepseek-coder",
        "gemini/gemini-1.5-flash",
    ]

    print("Detailed pricing information:\n")

    for model in models_to_check:
        try:
            pricing = get_model_cost(model)
            print(f"📊 {model}")
            print(f"   Input:  ${pricing['input_cost_per_token']:.8f}/token")
            print(f"   Output: ${pricing['output_cost_per_token']:.8f}/token")
            print(f"   Context: {pricing['max_tokens']:,} tokens")
            print()
        except Exception as e:
            print(f"📊 {model}")
            print(f"   ❌ Error: {e}\n")


def example_4_cost_comparison():
    """Example 4: Compare costs across different use cases."""
    print_section("Example 4: Cost Comparison Across Use Cases")

    cost_provider = LiteLLMCostProvider()

    use_cases = [
        ("Simple query", 100, 50),
        ("Medium task", 500, 250),
        ("Complex task", 2000, 1000),
        ("Large document", 10000, 5000),
    ]

    models_to_test = [
        ("gpt-4o", "OpenAI Premium"),
        ("gpt-4o-mini", "OpenAI Budget"),
        ("gemini/gemini-1.5-flash", "Google Budget"),
    ]

    print("Cost comparison across different use cases:\n")
    print(f"{'Use Case':<20} {'Tokens':>15} {'GPT-4o':>12} {'GPT-4o-mini':>14} {'Gemini Flash':>15}")
    print("-" * 80)

    for use_case, input_tokens, output_tokens in use_cases:
        costs = []
        for model, _ in models_to_test:
            try:
                cost = cost_provider.calculate_cost(
                    model=model, input_tokens=input_tokens, output_tokens=output_tokens
                )
                costs.append(cost)
            except:
                costs.append(0)

        tokens_str = f"{input_tokens}+{output_tokens}"
        print(
            f"{use_case:<20} {tokens_str:>15} "
            f"${costs[0]:>11.6f} ${costs[1]:>13.6f} ${costs[2]:>14.6f}"
        )

    print("\n💡 INSIGHTS:")
    print("  - GPT-4o-mini is ~30x cheaper than GPT-4o")
    print("  - Gemini Flash is ~100x cheaper than GPT-4o")
    print("  - Use cascading to get quality at lower cost!")
    print("  - Start cheap, escalate only when needed")


def example_5_provider_info():
    """Example 5: Get provider information dynamically."""
    print_section("Example 5: Get Provider Information")

    providers_to_check = ["deepseek", "google", "openai", "anthropic"]

    print("Provider information:\n")

    for provider_name in providers_to_check:
        info = get_provider_info(provider_name)
        if info:
            print(f"🔧 {info.display_name}")
            print(f"   Value Proposition: {info.value_prop}")
            print(f"   Example Models: {', '.join(info.example_models[:3])}")
            print(f"   Requires API Key: {'Yes' if info.requires_api_key else 'No'}")
            print()
        else:
            print(f"❌ {provider_name} - Not found\n")


def example_6_convenience_functions():
    """Example 6: Use convenience functions for quick calculations."""
    print_section("Example 6: Convenience Functions")

    print("Quick cost calculations without creating instances:\n")

    # Direct cost calculation
    cost1 = calculate_cost("gpt-4o", input_tokens=1000, output_tokens=500)
    print(f"  GPT-4o (1K+500):     ${cost1:.6f}")

    cost2 = calculate_cost("deepseek/deepseek-coder", input_tokens=1000, output_tokens=500)
    print(f"  DeepSeek (1K+500):   ${cost2:.6f}")

    cost3 = calculate_cost("gemini/gemini-1.5-flash", input_tokens=1000, output_tokens=500)
    print(f"  Gemini (1K+500):     ${cost3:.6f}")

    print("\n💰 Cost savings using DeepSeek:")
    savings = ((cost1 - cost2) / cost1) * 100
    print(f"   {savings:.1f}% cheaper than GPT-4o!")


def example_7_check_api_keys():
    """Example 7: Check which API keys are configured."""
    print_section("Example 7: API Key Status")

    api_keys = {
        "OpenAI": "OPENAI_API_KEY",
        "Anthropic": "ANTHROPIC_API_KEY",
        "Groq": "GROQ_API_KEY",
        "DeepSeek": "DEEPSEEK_API_KEY",
        "Google": "GOOGLE_API_KEY",
        "Together": "TOGETHER_API_KEY",
        "Hugging Face": "HF_TOKEN",
    }

    print("API Key Configuration:\n")

    for provider, env_var in api_keys.items():
        value = os.getenv(env_var)
        if value:
            masked = value[:10] + "..." if len(value) > 10 else "***"
            print(f"  ✅ {provider:20} {masked}")
        else:
            print(f"  ❌ {provider:20} Not configured")

    print("\n💡 TIP: Set API keys in .env file or as environment variables")


def example_8_real_world_usage():
    """Example 8: Real-world usage pattern with cascadeflow."""
    print_section("Example 8: Real-World Usage Pattern")

    print("How to use LiteLLM with cascadeflow agents:\n")

    print("""
# Step 1: Import cascadeflow and LiteLLM
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.integrations.litellm import LiteLLMCostProvider

# Step 2: Create cost provider
cost_provider = LiteLLMCostProvider()

# Step 3: Calculate costs for your models
deepseek_cost = cost_provider.calculate_cost(
    model="deepseek-coder",
    input_tokens=1000,
    output_tokens=500
)

# Step 4: Use costs in ModelConfig
agent = CascadeAgent(models=[
    ModelConfig(
        name="deepseek-coder",
        provider="openai",  # DeepSeek uses OpenAI-compatible API
        cost=deepseek_cost * 1000,  # Convert to per-1K token cost
        base_url="https://api.deepseek.com/v1"  # Custom endpoint
    ),
    ModelConfig(
        name="gpt-4o",
        provider="openai",
        cost=0.00625
    )
])

# Step 5: Run queries with automatic cost tracking
result = await agent.run("Write a Python function to sort a list")
print(f"Cost: ${result.total_cost:.6f}")
print(f"Model used: {result.model_used}")
""")

    print("💡 BENEFITS:")
    print("  - Accurate cost tracking via LiteLLM")
    print("  - Access to 100+ models")
    print("  - Automatic pricing updates")
    print("  - Budget management per user")


def main():
    """Run all examples."""
    print("\n" + "🎯" * 40)
    print("  LiteLLM Provider Integration Examples")
    print("🎯" * 40)

    # Run examples
    example_1_supported_providers()
    example_2_cost_calculation()
    example_3_model_pricing_info()
    example_4_cost_comparison()
    example_5_provider_info()
    example_6_convenience_functions()
    example_7_check_api_keys()
    example_8_real_world_usage()

    # Summary
    print_section("Summary & Next Steps")

    print("✅ You've learned:")
    print("  1. Which providers are supported via LiteLLM")
    print("  2. How to calculate costs accurately")
    print("  3. How to get model pricing information")
    print("  4. How to compare costs across use cases")
    print("  5. How to check provider capabilities")
    print("  6. How to use convenience functions")
    print("  7. How to check API key configuration")
    print("  8. How to integrate with cascadeflow agents")

    print("\n📚 Next Steps:")
    print("  - Set up API keys for providers you want to use")
    print("  - Try mixing providers in a cascade")
    print("  - Implement per-user budget tracking")
    print("  - Explore other examples in examples/integrations/")

    print("\n📖 Documentation:")
    print("  - Provider Guide: docs/guides/providers.md")
    print("  - Cost Tracking: docs/guides/cost_tracking.md")
    print("  - LiteLLM Integration: cascadeflow/integrations/litellm.py")

    print("\n💡 Pro Tips:")
    print("  - DeepSeek is 5-10x cheaper than GPT-4 for code tasks")
    print("  - Gemini Flash is fast and cheap for simple queries")
    print("  - Use LiteLLM's budget manager for production")
    print("  - Cost tracking happens automatically with cascadeflow")

    print("\n" + "=" * 80)
    print("  Ready to optimize your AI costs! 🚀")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
