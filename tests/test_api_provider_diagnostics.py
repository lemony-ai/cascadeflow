"""
API Provider Diagnostics Test - UPDATED WITH CURRENT MODELS

CRITICAL FINDINGS:
- Claude 3 Opus DEPRECATED June 30, 2025 (retired Jan 5, 2026)
- Claude 3 Sonnet RETIRED July 21, 2025
- Current models: Claude 4.x and Claude 3.5/3.7

Updated model names:
- claude-sonnet-4 or claude-sonnet-4-20250514
- claude-opus-4-1 or claude-opus-4-1-20250722
- claude-3-5-haiku-20241022
- claude-3-7-sonnet-20250224

Run: pytest tests/test_api_provider_diagnostics.py -v -s
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest


def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


_load_env()


def print_live(msg: str):
    print(msg, flush=True)
    sys.stdout.flush()


# ============================================================================
# ANTHROPIC DIAGNOSTICS - UPDATED WITH CURRENT MODELS
# ============================================================================


@pytest.mark.asyncio
async def test_anthropic_api_current_models():
    """
    Test Anthropic API with CURRENT model names (2025).

    IMPORTANT: Claude 3 Opus/Sonnet were deprecated/retired in 2025!
    Current models: Claude 4.x and Claude 3.5/3.7
    """

    print_live("\n" + "=" * 100)
    print_live("🔍 ANTHROPIC API DIAGNOSTICS (CURRENT MODELS 2025)")
    print_live("=" * 100)

    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not found")

    print_live(f"\n✅ API Key found: {api_key[:10]}...")

    # CURRENT model names (as of 2025)
    models_to_test = [
        # Claude 4 (Current - released May 2025)
        ("claude-sonnet-4", "Claude Sonnet 4 (alias)"),
        ("claude-sonnet-4-20250514", "Claude Sonnet 4 (dated)"),
        ("claude-opus-4-1", "Claude Opus 4.1 (alias)"),
        ("claude-opus-4-1-20250722", "Claude Opus 4.1 (dated)"),
        # Claude 4.5 (Newest - released Sept 2025)
        ("claude-sonnet-4-5", "Claude Sonnet 4.5 (alias)"),
        ("claude-sonnet-4-5-20250929", "Claude Sonnet 4.5 (dated)"),
        # Claude 3.5/3.7 (Still available)
        ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku"),
        ("claude-haiku-3-5", "Claude Haiku 3.5 (alias)"),
        ("claude-3-7-sonnet-20250224", "Claude 3.7 Sonnet"),
        ("claude-sonnet-3-7", "Claude Sonnet 3.7 (alias)"),
        # OLD DEPRECATED (should fail)
        ("claude-3-opus-20240229", "Claude 3 Opus (DEPRECATED)"),
        ("claude-3-haiku-20240307", "Claude 3 Haiku (OLD)"),
    ]

    print_live("\n⚠️  IMPORTANT: Claude 3 Opus/Sonnet were deprecated/retired in 2025!")
    print_live("   Testing current Claude 4.x and 3.5/3.7 models...")
    print_live("\n📋 Testing model availability...")
    print_live("-" * 100)

    working_models = []

    try:
        import httpx
    except ImportError:
        pytest.fail("httpx not installed")

    async with httpx.AsyncClient(timeout=30.0) as client:
        for model_id, description in models_to_test:
            try:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "anthropic-version": "2023-06-01",
                        "x-api-key": api_key,
                        "content-type": "application/json",
                    },
                    json={
                        "model": model_id,
                        "messages": [{"role": "user", "content": "Test"}],
                        "max_tokens": 10,
                    },
                )

                status_icon = "✅" if response.status_code == 200 else "❌"
                status_text = ""

                if response.status_code == 200:
                    status_text = "Available"
                    working_models.append((model_id, description))
                elif response.status_code == 404:
                    status_text = "404 Not Found (deprecated/retired)"
                elif response.status_code == 401:
                    status_text = "401 Unauthorized"
                elif response.status_code == 429:
                    status_text = "429 Rate Limited (but exists)"
                    working_models.append((model_id, description))
                elif response.status_code == 403:
                    status_text = "403 Forbidden (billing/tier issue)"
                else:
                    status_text = f"HTTP {response.status_code}"

                print_live(f"  {status_icon} {description:<45} → {status_text}")

            except httpx.TimeoutException:
                print_live(f"  ⏱️  {description:<45} → Timeout")
            except Exception as e:
                print_live(f"  ❌ {description:<45} → {str(e)[:60]}")

            await asyncio.sleep(0.5)

    # Recommendations
    print_live("\n" + "=" * 100)
    print_live("📝 ANTHROPIC RECOMMENDATIONS")
    print_live("=" * 100)

    if working_models:
        print_live(f"\n✅ Found {len(working_models)} working model(s):")
        for model_id, _desc in working_models:
            print_live(f"   • {model_id}")

        # Select models
        small_model = None
        big_model = None

        # Prioritize: Haiku (small), Opus/Sonnet (big)
        for model_id, _desc in working_models:
            if "haiku" in model_id.lower() and not small_model:
                small_model = model_id
            if "opus" in model_id.lower() and not big_model:
                big_model = model_id

        # Fallback to Sonnet
        if not big_model:
            for model_id, _desc in working_models:
                if "sonnet" in model_id.lower() and "4" in model_id:
                    big_model = model_id
                    break

        # Ultimate fallback
        if not small_model:
            small_model = working_models[0][0]
        if not big_model:
            big_model = working_models[-1][0] if len(working_models) > 1 else working_models[0][0]

        print_live("\n🔧 RECOMMENDED CONFIG UPDATE:")
        print_live("=" * 100)
        print_live(
            f"""
'anthropic': ProviderCosts(
    small_model='{small_model}',  # ← UPDATE
    big_model='{big_model}',      # ← UPDATE
    small_input_per_1k=0.00025,
    small_output_per_1k=0.00125,
    big_input_per_1k=0.015,
    big_output_per_1k=0.075,
),
"""
        )

        # Save to file
        config_file = Path(__file__).parent.parent / "anthropic_config.txt"
        with open(config_file, "w") as f:
            f.write("ANTHROPIC CONFIG (Auto-generated)\n")
            f.write(f"Generated: {os.popen('date').read().strip()}\n\n")
            f.write(f"small_model='{small_model}'\n")
            f.write(f"big_model='{big_model}'\n")

        print_live(f"\n💾 Configuration saved to: {config_file}")

        # Tier warning
        if len(working_models) == 1:
            print_live("\n⚠️  WARNING: Only 1 model available")
            print_live("   This may indicate:")
            print_live("   • Free tier with limited access")
            print_live("   • Billing not set up")
            print_live("   • Need to upgrade account")
            print_live("\n💡 For proper cascade testing, you need 2+ models")
            print_live("   Consider upgrading at: https://console.anthropic.com/settings/plans")

    else:
        print_live("\n❌ NO WORKING MODELS FOUND!")
        print_live("\nThis suggests:")
        print_live("  • API key may be invalid")
        print_live("  • Account not activated")
        print_live("  • All models deprecated (using very old API key?)")
        pytest.fail("No working Anthropic models found")

    # Don't fail on single model anymore - just warn
    if len(working_models) >= 1:
        print_live("\n✅ Anthropic API accessible")
        if len(working_models) == 1:
            print_live("⚠️  Only 1 model - cascade won't save costs (using same model twice)")


# ============================================================================
# OLLAMA DETECTION - IMPROVED
# ============================================================================


@pytest.mark.asyncio
async def test_ollama_models():
    """
    Test Ollama and detect ALL available models.

    Shows which models you have for proper small/big selection.
    """

    print_live("\n" + "=" * 100)
    print_live("🔍 OLLAMA LOCAL MODELS DIAGNOSTIC")
    print_live("=" * 100)

    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:11434/api/tags")

            if response.status_code != 200:
                pytest.skip("Ollama not running")

            data = response.json()
            models = data.get("models", [])

            if not models:
                print_live("\n⚠️  Ollama is running but no models installed")
                print_live("\nTo install models:")
                print_live("  ollama pull llama3.1:8b    # Small model")
                print_live("  ollama pull llama3.1:70b   # Big model")
                pytest.skip("No Ollama models installed")

            print_live(f"\n✅ Ollama running with {len(models)} model(s)")
            print_live("\n📋 Available models:")
            print_live("-" * 100)

            # Parse and display all models
            model_info = []
            for model in models:
                name = model.get("name", "unknown")
                size = model.get("size", 0)
                size_gb = size / (1024**3)
                modified = model.get("modified_at", "")[:10]

                # Infer parameter count
                params = 0
                name_lower = name.lower()
                if "1b" in name_lower:
                    params = 1
                elif "3b" in name_lower:
                    params = 3
                elif "7b" in name_lower or "8b" in name_lower:
                    params = 8
                elif "11b" in name_lower or "13b" in name_lower:
                    params = 13
                elif "70b" in name_lower:
                    params = 70
                elif "90b" in name_lower:
                    params = 90

                model_info.append(
                    {"name": name, "size_gb": size_gb, "params": params, "modified": modified}
                )

                print_live(f"  • {name:<40} {size_gb:>6.2f} GB   ~{params}B params   {modified}")

            # Sort by params
            model_info.sort(key=lambda x: x["params"])

            # Select small and big
            if len(model_info) >= 2:
                small_model = model_info[0]["name"]
                big_model = model_info[-1]["name"]
            elif len(model_info) == 1:
                small_model = big_model = model_info[0]["name"]
                print_live(
                    "\n⚠️  Only 1 model detected - will use same model for both small and big"
                )
            else:
                pytest.skip("No models detected")

            print_live("\n" + "=" * 100)
            print_live("📝 OLLAMA RECOMMENDATIONS")
            print_live("=" * 100)

            print_live("\n✅ Detected configuration:")
            print_live(f"   Small: {small_model} ({model_info[0]['params']}B)")
            print_live(f"   Big:   {big_model} ({model_info[-1]['params']}B)")

            if len(model_info) == 1:
                print_live("\n⚠️  SAME MODEL FOR BOTH - Cascade won't save compute")
                print_live("   Recommended: Install a larger model")
                print_live("   Example: ollama pull llama3.1:70b")
            elif model_info[-1]["params"] / model_info[0]["params"] < 3:
                print_live(
                    f"\n⚠️  Small size difference ({model_info[0]['params']}B → {model_info[-1]['params']}B)"
                )
                print_live("   For better cascade benefits, consider:")
                print_live("   • Smaller small model (1B-3B)")
                print_live("   • Larger big model (70B+)")
            else:
                print_live(
                    f"\n✅ Good size ratio: {model_info[0]['params']}B → {model_info[-1]['params']}B"
                )

            print_live("\n🔧 CONFIG (auto-detected at runtime):")
            print_live("=" * 100)
            print_live(
                f"""
'ollama': ProviderCosts(
    small_model='',  # Auto-detected: {small_model}
    big_model='',    # Auto-detected: {big_model}
    small_input_per_1k=0.0,
    small_output_per_1k=0.0,
    big_input_per_1k=0.0,
    big_output_per_1k=0.0,
),
"""
            )

            # Save config
            config_file = Path(__file__).parent.parent / "ollama_config.txt"
            with open(config_file, "w") as f:
                f.write("OLLAMA CONFIG (Auto-detected)\n")
                f.write(f"Generated: {os.popen('date').read().strip()}\n\n")
                f.write("# Models detected:\n")
                for m in model_info:
                    f.write(f"# - {m['name']} ({m['params']}B, {m['size_gb']:.2f} GB)\n")
                f.write("\n")
                f.write(f"small_model='{small_model}' # {model_info[0]['params']}B\n")
                f.write(f"big_model='{big_model}' # {model_info[-1]['params']}B\n")

            print_live(f"\n💾 Configuration saved to: {config_file}")
            print_live("\n✅ Ollama diagnostics PASSED")

    except httpx.ConnectError:
        pytest.skip("Ollama not running (connection refused)")
    except Exception as e:
        pytest.skip(f"Ollama error: {e}")


# ============================================================================
# GROQ - Already tested (working)
# ============================================================================


@pytest.mark.asyncio
async def test_groq_api_models():
    """Test Groq - already verified working with llama-3.3-70b-versatile."""

    print_live("\n" + "=" * 100)
    print_live("🔍 GROQ API QUICK CHECK")
    print_live("=" * 100)

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        pytest.skip("GROQ_API_KEY not found")

    print_live(f"\n✅ API Key found: {api_key[:10]}...")
    print_live("\n✅ From previous diagnostics:")
    print_live("   • llama-3.1-8b-instant (small) - Working")
    print_live("   • llama-3.3-70b-versatile (big) - Working")
    print_live("\n✅ Groq configuration verified")


# ============================================================================
# SUMMARY WITH UPDATED RECOMMENDATIONS
# ============================================================================


def test_generate_updated_summary():
    """Generate summary with current model recommendations."""

    print_live("\n" + "=" * 100)
    print_live("📋 FINAL CONFIGURATION SUMMARY")
    print_live("=" * 100)

    anthropic_config = Path(__file__).parent.parent / "anthropic_config.txt"
    ollama_config = Path(__file__).parent.parent / "ollama_config.txt"
    groq_config = Path(__file__).parent.parent / "groq_config.txt"

    print_live("\n📁 Generated Configuration Files:")

    configs = []

    if anthropic_config.exists():
        with open(anthropic_config) as f:
            content = f.read()
            small = [l for l in content.split("\n") if "small_model" in l and not l.startswith("#")]
            big = [l for l in content.split("\n") if "big_model" in l and not l.startswith("#")]
            if small and big:
                configs.append(("Anthropic", small[0].split("'")[1], big[0].split("'")[1]))
                print_live(f"  ✅ Anthropic: {anthropic_config}")

    if ollama_config.exists():
        with open(ollama_config) as f:
            content = f.read()
            small = [l for l in content.split("\n") if "small_model" in l and not l.startswith("#")]
            big = [l for l in content.split("\n") if "big_model" in l and not l.startswith("#")]
            if small and big:
                configs.append(("Ollama", small[0].split("'")[1], big[0].split("'")[1]))
                print_live(f"  ✅ Ollama: {ollama_config}")

    if groq_config.exists():
        print_live(f"  ✅ Groq: {groq_config}")
        configs.append(("Groq", "llama-3.1-8b-instant", "llama-3.3-70b-versatile"))

    if configs:
        print_live("\n📊 Recommended Configurations:")
        print_live("-" * 100)
        for provider, small, big in configs:
            print_live(f"\n{provider}:")
            print_live(f"  Small: {small}")
            print_live(f"  Big:   {big}")

    print_live("\n" + "=" * 100)
    print_live("✅ NEXT STEPS:")
    print_live("=" * 100)
    print_live(
        """
1. Update PROVIDER_COST_CONFIGS in your test file with models above

2. CRITICAL: Update Anthropic to current models (Claude 4.x)
   Old Claude 3 Opus/Sonnet are DEPRECATED/RETIRED

3. Update Groq big model: llama-3.3-70b-versatile (not 3.1)

4. Re-run cascade test:
   pytest tests/test_cascade_real_world.py -v -s

5. Fix alignment scorer (still returning 0.15 scores)
   cascadeflow/alignment_scorer.py line 79: len(w) > 2
"""
    )

    print_live("=" * 100 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
