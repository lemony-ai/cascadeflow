"""
Test LiteLLM Integration with All Providers

Tests all 10 strategic providers to verify:
- API key configuration
- Cost calculation
- Budget tracking (if LiteLLM installed)
- Provider-specific features

Run this to validate the complete LiteLLM integration.
"""

import os
import sys

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ Loaded .env file")
except ImportError:
    print("⚠️  python-dotenv not installed, trying manual .env loading")
    # Manual .env loading
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        print(f"✓ Manually loaded {env_file}")

from cascadeflow.integrations.litellm import (
    SUPPORTED_PROVIDERS,
    LiteLLMCostProvider,
    validate_provider,
    get_provider_info,
)


def print_section(title):
    """Print section header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def check_api_keys():
    """Check which API keys are configured."""
    print_section("API Key Status Check")
    print()

    # Map providers to their expected environment variables
    provider_env_vars = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "groq": "GROQ_API_KEY",
        "together": "TOGETHER_API_KEY",
        "huggingface": ["HF_TOKEN", "HUGGINGFACE_API_KEY"],  # HF accepts both
        "google": ["GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS"],
        "azure": ["AZURE_API_KEY", "AZURE_OPENAI_API_KEY"],
        "deepseek": "DEEPSEEK_API_KEY",
        "ollama": None,  # No API key needed (local)
        "vllm": None,  # No API key needed (self-hosted)
    }

    configured = []
    missing = []
    local = []

    for provider_name, env_vars in provider_env_vars.items():
        provider_info = SUPPORTED_PROVIDERS[provider_name]

        if not provider_info.requires_api_key:
            # Local/self-hosted providers
            local.append({
                "name": provider_name,
                "display_name": provider_info.display_name,
                "status": "local",
            })
            continue

        # Check if API key is set
        has_key = False
        key_name = None

        if isinstance(env_vars, list):
            for env_var in env_vars:
                if os.getenv(env_var):
                    has_key = True
                    key_name = env_var
                    break
        else:
            if os.getenv(env_vars):
                has_key = True
                key_name = env_vars

        if has_key:
            configured.append({
                "name": provider_name,
                "display_name": provider_info.display_name,
                "env_var": key_name,
                "value_prop": provider_info.value_prop,
            })
        else:
            missing.append({
                "name": provider_name,
                "display_name": provider_info.display_name,
                "env_var": env_vars if isinstance(env_vars, str) else env_vars[0],
                "value_prop": provider_info.value_prop,
            })

    # Print configured providers
    print(f"✓ CONFIGURED PROVIDERS ({len(configured)}):")
    print()
    for p in configured:
        print(f"  ✓ {p['display_name']:25s} ({p['env_var']})")
        print(f"    → {p['value_prop']}")
        print()

    # Print local providers
    print(f"✓ LOCAL/SELF-HOSTED PROVIDERS ({len(local)}):")
    print()
    for p in local:
        provider_info = SUPPORTED_PROVIDERS[p['name']]
        print(f"  ✓ {p['display_name']:25s} (no API key needed)")
        print(f"    → {provider_info.value_prop}")
        print()

    # Print missing providers
    if missing:
        print(f"✗ MISSING API KEYS ({len(missing)}):")
        print()
        for p in missing:
            print(f"  ✗ {p['display_name']:25s} (needs {p['env_var']})")
            print(f"    → {p['value_prop']}")
            print()

    return configured, missing, local


def test_cost_calculations(configured_providers):
    """Test cost calculations for configured providers."""
    print_section("Cost Calculation Tests")
    print()

    cost_provider = LiteLLMCostProvider()

    # Test with common models from each provider
    test_cases = []

    for provider in configured_providers:
        provider_name = provider['name']
        provider_info = SUPPORTED_PROVIDERS[provider_name]

        # Use first example model
        if provider_info.example_models:
            model = provider_info.example_models[0]
            test_cases.append({
                "provider": provider_info.display_name,
                "model": model,
            })

    if not test_cases:
        print("⚠️  No configured providers to test")
        return

    print("Testing cost calculations (100 input, 50 output tokens):")
    print()

    for test in test_cases:
        try:
            cost = cost_provider.calculate_cost(
                model=test['model'],
                input_tokens=100,
                output_tokens=50
            )
            print(f"  ✓ {test['provider']:25s} | {test['model']:30s} | ${cost:.6f}")
        except Exception as e:
            print(f"  ✗ {test['provider']:25s} | {test['model']:30s} | Error: {e}")

    print()


def test_provider_validation():
    """Test provider validation."""
    print_section("Provider Validation Tests")
    print()

    print("Testing validate_provider():")
    print()

    # Test valid providers
    for provider_name in list(SUPPORTED_PROVIDERS.keys())[:5]:
        result = validate_provider(provider_name)
        status = "✓" if result else "✗"
        print(f"  {status} {provider_name:20s} → {result}")

    # Test invalid provider
    result = validate_provider("invalid_provider")
    status = "✓" if not result else "✗"
    print(f"  {status} {'invalid_provider':20s} → {result} (expected False)")
    print()


def generate_env_template(missing_providers):
    """Generate .env template for missing providers."""
    print_section("Environment Variable Template")
    print()

    if not missing_providers:
        print("✓ All providers configured! No template needed.")
        return

    print("Add these to your .env file:")
    print()
    print("# ============================================")
    print("# Missing Provider API Keys")
    print("# ============================================")
    print()

    for p in missing_providers:
        print(f"# {p['display_name']} - {p['value_prop']}")
        print(f"{p['env_var']}=your_api_key_here")
        print()

    # Write to file
    template_path = ".env.template"
    with open(template_path, "w") as f:
        f.write("# ============================================\n")
        f.write("# cascadeflow Provider API Keys\n")
        f.write("# ============================================\n\n")

        for p in missing_providers:
            f.write(f"# {p['display_name']} - {p['value_prop']}\n")
            f.write(f"{p['env_var']}=your_api_key_here\n\n")

    print(f"✓ Template saved to: {template_path}")
    print()


def test_litellm_availability():
    """Test if LiteLLM is installed."""
    print_section("LiteLLM Installation Check")
    print()

    try:
        import litellm
        print("✓ LiteLLM is installed")
        print(f"  Version: {litellm.__version__ if hasattr(litellm, '__version__') else 'unknown'}")
        print()
        print("✓ Can use:")
        print("  - BudgetManager for actual spending tracking")
        print("  - Callbacks for automatic cost tracking")
        print("  - Accurate pricing from LiteLLM database")
        print()
        return True
    except ImportError:
        print("✗ LiteLLM is NOT installed")
        print()
        print("Install with:")
        print("  pip install litellm")
        print()
        print("Or for extra providers:")
        print("  pip install litellm[extra_providers]")
        print()
        print("⚠️  Using fallback cost estimates")
        print()
        return False


def main():
    """Run all provider tests."""
    print_section("cascadeflow LiteLLM Integration Test Suite")
    print()
    print("Testing all 10 strategic providers...")
    print()

    # Check LiteLLM installation
    litellm_available = test_litellm_availability()

    # Check API keys
    configured, missing, local = check_api_keys()

    # Test provider validation
    test_provider_validation()

    # Test cost calculations
    test_cost_calculations(configured)

    # Generate template for missing keys
    if missing:
        generate_env_template(missing)

    # Summary
    print_section("Summary")
    print()
    print(f"✓ Configured providers:  {len(configured)}")
    print(f"✓ Local providers:       {len(local)}")
    print(f"✗ Missing API keys:      {len(missing)}")
    print(f"✓ LiteLLM installed:     {'Yes' if litellm_available else 'No (using fallback)'}")
    print()

    if missing:
        print("⚠️  Action needed:")
        print(f"   - Add {len(missing)} missing API keys to .env file")
        print(f"   - See .env.template for the template")
        print()

    total_ready = len(configured) + len(local)
    print(f"✓ Ready to use: {total_ready}/10 providers ({(total_ready/10)*100:.0f}%)")
    print()

    if total_ready == 10:
        print("🎉 All providers configured!")
    elif total_ready >= 7:
        print("👍 Most providers configured - good to go!")
    elif total_ready >= 4:
        print("⚠️  Some providers missing - add keys for more options")
    else:
        print("⚠️  Many providers missing - add keys to .env file")

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
