"""
Comprehensive test script for CascadeFlow Day 4.

Tests everything before proceeding to Day 4.2:
- All imports and configuration
- All providers (with real API calls)
- CascadeAgent functionality
- All example files
- Unit tests
- Integration tests
"""

import asyncio
import os
import sys
import subprocess
import py_compile
import glob
from dotenv import load_dotenv

# Load environment
load_dotenv()


class TestRunner:
    """Test runner with colored output."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []

    def success(self, message):
        """Print success message."""
        print(f"✅ {message}")
        self.passed += 1

    def fail(self, message, error=None):
        """Print failure message."""
        print(f"❌ {message}")
        if error:
            print(f"   Error: {error}")
            self.errors.append((message, str(error)))
        self.failed += 1

    def skip(self, message):
        """Print skip message."""
        print(f"⚠️  {message}")
        self.skipped += 1

    def info(self, message):
        """Print info message."""
        print(f"ℹ️  {message}")

    def section(self, title):
        """Print section header."""
        print(f"\n{'=' * 70}")
        print(f"  {title}")
        print(f"{'=' * 70}\n")

    def summary(self):
        """Print test summary."""
        print(f"\n{'=' * 70}")
        print(f"  TEST SUMMARY")
        print(f"{'=' * 70}")
        print(f"✅ Passed:  {self.passed}")
        print(f"❌ Failed:  {self.failed}")
        print(f"⚠️  Skipped: {self.skipped}")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"   Total:   {self.passed + self.failed + self.skipped}")

        if self.errors:
            print(f"\n{'=' * 70}")
            print(f"  ERRORS DETAIL")
            print(f"{'=' * 70}")
            for msg, err in self.errors:
                print(f"\n❌ {msg}")
                print(f"   {err}")

        print(f"\n{'=' * 70}")
        if self.failed == 0:
            print(f"  🎉 ALL TESTS PASSED!")
            print(f"  ✅ Ready for Day 4.2: Speculative Cascades")
        else:
            print(f"  ⚠️  {self.failed} TEST(S) FAILED")
            print(f"  ❌ Fix issues before proceeding")
        print(f"{'=' * 70}\n")

        return self.failed == 0


# ============================================================================
# SECTION 1: IMPORTS
# ============================================================================

async def test_imports(runner):
    """Test all imports."""
    runner.section("1. IMPORTS")

    try:
        from cascadeflow import (
            ModelConfig, CascadeConfig, UserTier,
            CascadeAgent, CascadeResult,
            ModelResponse, BaseProvider,
            setup_logging, format_cost, estimate_tokens,
            CascadeFlowError, BudgetExceededError,
            ProviderError, ModelError, QualityThresholdError
        )
        runner.success("Core imports")
    except Exception as e:
        runner.fail("Core imports", e)
        return

    try:
        from cascadeflow.providers import (
            OpenAIProvider, AnthropicProvider,
            OllamaProvider, GroqProvider
        )
        runner.success("Provider imports")
    except Exception as e:
        runner.fail("Provider imports", e)


# ============================================================================
# SECTION 2: CONFIGURATION CLASSES
# ============================================================================

async def test_config_classes(runner):
    """Test configuration classes."""
    runner.section("2. CONFIGURATION CLASSES")

    # ModelConfig
    try:
        from cascadeflow import ModelConfig

        model = ModelConfig(
            name="gpt-3.5-turbo",
            provider="openai",
            cost=0.002
        )
        assert model.name == "gpt-3.5-turbo"
        assert model.provider == "openai"
        assert model.cost == 0.002
        runner.success("ModelConfig: basic creation")
    except Exception as e:
        runner.fail("ModelConfig: basic creation", e)

    try:
        model = ModelConfig(
            name="codellama",
            provider="ollama",
            cost=0.0,
            domains=["code"],
            keywords=["programming"]
        )
        assert "code" in model.domains
        assert "programming" in model.keywords
        runner.success("ModelConfig: with domains/keywords")
    except Exception as e:
        runner.fail("ModelConfig: with domains/keywords", e)

    # CascadeConfig
    try:
        from cascadeflow import CascadeConfig

        config = CascadeConfig(
            quality_threshold=0.85,
            max_budget=0.10,
            use_speculative=True
        )
        assert config.quality_threshold == 0.85
        assert config.max_budget == 0.10
        assert config.use_speculative == True
        runner.success("CascadeConfig: creation")
    except Exception as e:
        runner.fail("CascadeConfig: creation", e)

    # UserTier
    try:
        from cascadeflow import UserTier

        tier = UserTier(
            name="premium",
            max_budget=0.10,
            quality_threshold=0.9
        )
        assert tier.name == "premium"
        config_dict = tier.to_cascade_config()
        assert config_dict["max_budget"] == 0.10
        runner.success("UserTier: creation and conversion")
    except Exception as e:
        runner.fail("UserTier: creation and conversion", e)


# ============================================================================
# SECTION 3: UTILITY FUNCTIONS
# ============================================================================

async def test_utilities(runner):
    """Test utility functions."""
    runner.section("3. UTILITY FUNCTIONS")

    try:
        from cascadeflow import format_cost

        result = format_cost(0.002)
        assert result == "$0.0020", f"Expected '$0.0020', got '{result}'"

        result = format_cost(1.5)
        assert result == "$1.5000", f"Expected '$1.5000', got '{result}'"

        runner.success("format_cost()")
    except Exception as e:
        runner.fail("format_cost()", e)

    try:
        from cascadeflow import estimate_tokens

        tokens = estimate_tokens("This is a test")
        assert tokens > 0
        runner.success("estimate_tokens()")
    except Exception as e:
        runner.fail("estimate_tokens()", e)

    try:
        from cascadeflow import setup_logging
        setup_logging("INFO")
        runner.success("setup_logging()")
    except Exception as e:
        runner.fail("setup_logging()", e)


# ============================================================================
# SECTION 4: API KEY CONFIGURATION
# ============================================================================

async def test_api_keys(runner):
    """Check API key configuration."""
    runner.section("4. API KEY CONFIGURATION")

    keys = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
        "HF_TOKEN": os.getenv("HF_TOKEN"),
        "TOGETHER_API_KEY": os.getenv("TOGETHER_API_KEY"),
    }

    configured = 0
    for key_name, key_value in keys.items():
        if key_value:
            runner.success(f"{key_name} ({key_value[:10]}...)")
            configured += 1
        else:
            runner.info(f"{key_name} not set (optional)")

    if configured == 0:
        runner.info("⚠️  No API keys configured - integration tests will be skipped")


# ============================================================================
# SECTION 5: PROVIDER INITIALIZATION
# ============================================================================

async def test_provider_initialization(runner):
    """Test provider initialization."""
    runner.section("5. PROVIDER INITIALIZATION")

    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        try:
            from cascadeflow.providers import OpenAIProvider
            provider = OpenAIProvider()
            assert provider.api_key is not None
            assert provider.base_url is not None
            await provider.client.aclose()
            runner.success("OpenAI provider initialized")
        except Exception as e:
            runner.fail("OpenAI provider initialization", e)
    else:
        runner.skip("OpenAI provider (no API key)")

    # Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            from cascadeflow.providers import AnthropicProvider
            provider = AnthropicProvider()
            assert provider.api_key is not None
            await provider.client.aclose()
            runner.success("Anthropic provider initialized")
        except Exception as e:
            runner.fail("Anthropic provider initialization", e)
    else:
        runner.skip("Anthropic provider (no API key)")

    # Groq
    if os.getenv("GROQ_API_KEY"):
        try:
            from cascadeflow.providers import GroqProvider
            provider = GroqProvider()
            assert provider.api_key is not None
            await provider.client.aclose()
            runner.success("Groq provider initialized")
        except Exception as e:
            runner.fail("Groq provider initialization", e)
    else:
        runner.skip("Groq provider (no API key)")

    # Ollama
    try:
        from cascadeflow.providers import OllamaProvider
        provider = OllamaProvider()
        assert provider.base_url is not None
        await provider.client.aclose()
        runner.success("Ollama provider initialized")
    except Exception as e:
        runner.fail("Ollama provider initialization", e)


# ============================================================================
# SECTION 6: OLLAMA CONNECTION
# ============================================================================

async def test_ollama_connection(runner):
    """Test Ollama connection."""
    runner.section("6. OLLAMA CONNECTION")

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://localhost:11434/api/version",
                timeout=2.0
            )
            if response.status_code == 200:
                version = response.json().get("version", "unknown")
                runner.success(f"Ollama running (v{version})")

                # Check models
                tags = await client.get("http://localhost:11434/api/tags", timeout=2.0)
                if tags.status_code == 200:
                    models = tags.json().get("models", [])
                    if models:
                        model_names = [m["name"] for m in models[:3]]
                        runner.info(f"Models: {', '.join(model_names)}")
                        runner.success(f"Ollama has {len(models)} model(s)")
                    else:
                        runner.skip("Ollama running but no models")
            else:
                runner.skip("Ollama not responding")
    except Exception as e:
        runner.skip(f"Ollama not available ({e})")


# ============================================================================
# SECTION 7: REAL API CALLS
# ============================================================================

async def test_real_api_calls(runner):
    """Test real API calls to providers."""
    runner.section("7. REAL API CALLS")

    # Test OpenAI
    if os.getenv("OPENAI_API_KEY"):
        try:
            from cascadeflow.providers import OpenAIProvider

            provider = OpenAIProvider()
            result = await provider.complete(
                prompt="Say 'test' and nothing else",
                model="gpt-3.5-turbo",
                max_tokens=10
            )

            assert result.content is not None
            assert result.cost > 0
            assert result.provider == "openai"

            runner.success(f"OpenAI API call (${result.cost:.6f})")
            runner.info(f"Response: {result.content[:50]}")

            await provider.client.aclose()
        except Exception as e:
            runner.fail("OpenAI API call", e)
    else:
        runner.skip("OpenAI API call (no key)")

    # Test Groq
    if os.getenv("GROQ_API_KEY"):
        try:
            from cascadeflow.providers import GroqProvider

            provider = GroqProvider()
            result = await provider.complete(
                prompt="Say 'test' and nothing else",
                model="llama-3.1-8b-instant",
                max_tokens=10
            )

            assert result.content is not None
            assert result.cost == 0.0  # Free
            assert result.provider == "groq"

            runner.success(f"Groq API call (FREE)")
            runner.info(f"Response: {result.content[:50]}")

            await provider.client.aclose()
        except Exception as e:
            runner.fail("Groq API call", e)
    else:
        runner.skip("Groq API call (no key)")

    # Test Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            from cascadeflow.providers import AnthropicProvider

            provider = AnthropicProvider()
            result = await provider.complete(
                prompt="Say 'test' and nothing else",
                model="claude-3-haiku-20240307",
                max_tokens=10
            )

            assert result.content is not None
            assert result.provider == "anthropic"

            runner.success(f"Anthropic API call (${result.cost:.6f})")
            runner.info(f"Response: {result.content[:50]}")

            await provider.client.aclose()
        except Exception as e:
            runner.fail("Anthropic API call", e)
    else:
        runner.skip("Anthropic API call (no key)")


# ============================================================================
# SECTION 8: CASCADE AGENT
# ============================================================================

async def test_cascade_agent(runner):
    """Test CascadeAgent functionality."""
    runner.section("8. CASCADE AGENT")

    if not os.getenv("OPENAI_API_KEY"):
        runner.skip("CascadeAgent tests (no OpenAI key)")
        return

    # Basic initialization
    try:
        from cascadeflow import CascadeAgent, ModelConfig

        models = [
            ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002),
            ModelConfig(name="gpt-4", provider="openai", cost=0.03),
        ]

        agent = CascadeAgent(models)
        assert len(agent.models) == 2
        assert agent.config is not None

        runner.success("CascadeAgent: initialization")
    except Exception as e:
        runner.fail("CascadeAgent: initialization", e)
        return

    # Test run
    try:
        result = await agent.run("What is 2+2?")

        assert result.content is not None
        assert result.model_used in ["gpt-3.5-turbo", "gpt-4"]
        assert result.total_cost > 0
        assert result.confidence > 0

        runner.success(f"CascadeAgent: run() - used {result.model_used}")
        runner.info(f"Cost: ${result.total_cost:.6f}, Cascaded: {result.cascaded}")
    except Exception as e:
        runner.fail("CascadeAgent: run()", e)

    # Test with user tiers
    try:
        from cascadeflow import UserTier

        tiers = {
            "free": UserTier(name="free", max_budget=0.001, quality_threshold=0.6),
            "premium": UserTier(name="premium", max_budget=0.10, quality_threshold=0.9),
        }

        agent_with_tiers = CascadeAgent(models, tiers=tiers)
        result = await agent_with_tiers.run("Test", user_tier="free")

        assert result.user_tier == "free"
        runner.success("CascadeAgent: user tiers")
    except Exception as e:
        runner.fail("CascadeAgent: user tiers", e)

    # Test stats
    try:
        stats = agent.get_stats()
        assert "total_queries" in stats
        assert "total_cost" in stats
        runner.success("CascadeAgent: get_stats()")
    except Exception as e:
        runner.fail("CascadeAgent: get_stats()", e)


# ============================================================================
# SECTION 9: SMART DEFAULT
# ============================================================================

async def test_smart_default(runner):
    """Test smart_default() provider detection."""
    runner.section("9. SMART DEFAULT")

    try:
        from cascadeflow import CascadeAgent

        agent = CascadeAgent.smart_default()

        assert len(agent.models) > 0
        runner.success(f"smart_default() detected {len(agent.models)} model(s)")

        for model in agent.models:
            runner.info(f"  - {model.name} ({model.provider})")

    except Exception as e:
        # This might fail if no providers configured
        if "No providers detected" in str(e):
            runner.skip("smart_default() (no providers configured)")
        else:
            runner.fail("smart_default()", e)


# ============================================================================
# SECTION 10: UNIT TESTS (PYTEST)
# ============================================================================

async def test_unit_tests(runner):
    """Run pytest unit tests."""
    runner.section("10. UNIT TESTS (pytest)")

    try:
        result = subprocess.run(
            ["pytest", "tests/", "-v", "--tb=short", "-x"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            output = result.stdout
            if "passed" in output:
                # Extract number of passed tests
                for line in output.split('\n'):
                    if "passed" in line:
                        runner.success(f"pytest: {line.strip()}")
                        break
            else:
                runner.success("pytest: all tests passed")
        else:
            runner.fail("pytest: some tests failed")
            # Show failure details
            lines = result.stdout.split('\n')
            for line in lines[-15:]:
                if line.strip() and ("FAILED" in line or "ERROR" in line):
                    print(f"   {line}")

    except subprocess.TimeoutExpired:
        runner.fail("pytest: tests timed out (>60s)")
    except FileNotFoundError:
        runner.skip("pytest not installed")
    except Exception as e:
        runner.fail("pytest execution", e)


# ============================================================================
# SECTION 11: EXAMPLE FILE SYNTAX
# ============================================================================

async def test_example_syntax(runner):
    """Check example files for syntax errors."""
    runner.section("11. EXAMPLE FILES (syntax)")

    example_files = glob.glob("examples/*.py")

    if not example_files:
        runner.skip("No example files found")
        return

    for filepath in sorted(example_files):
        filename = os.path.basename(filepath)

        # Skip test files
        if filename.startswith("test_"):
            continue

        try:
            py_compile.compile(filepath, doraise=True)
            runner.success(f"Syntax: {filename}")
        except Exception as e:
            runner.fail(f"Syntax: {filename}", e)


# ============================================================================
# SECTION 12: EXAMPLE EXECUTION
# ============================================================================

async def test_example_execution(runner):
    """Test that key examples actually run."""
    runner.section("12. EXAMPLE FILES (execution)")

    # Only test if we have API keys
    has_keys = bool(os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY"))

    if not has_keys:
        runner.skip("Example execution (no API keys)")
        return

    # Test basic_cascade.py
    try:
        result = subprocess.run(
            ["python", "examples/basic_cascade.py"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and "Success!" in result.stdout:
            runner.success("basic_cascade.py execution")
        else:
            runner.fail("basic_cascade.py execution",
                        result.stderr or "No 'Success!' in output")
    except subprocess.TimeoutExpired:
        runner.fail("basic_cascade.py", "Timeout")
    except FileNotFoundError:
        runner.skip("basic_cascade.py not found")
    except Exception as e:
        runner.fail("basic_cascade.py", e)

    # Test smart_default_test.py
    try:
        result = subprocess.run(
            ["python", "examples/smart_default_test.py"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and "Success!" in result.stdout:
            runner.success("smart_default_test.py execution")
        else:
            runner.fail("smart_default_test.py execution",
                        result.stderr or "No 'Success!' in output")
    except subprocess.TimeoutExpired:
        runner.fail("smart_default_test.py", "Timeout")
    except FileNotFoundError:
        runner.skip("smart_default_test.py not found")
    except Exception as e:
        runner.fail("smart_default_test.py", e)


# ============================================================================
# SECTION 13: EXCEPTION HANDLING
# ============================================================================

async def test_exceptions(runner):
    """Test exception handling."""
    runner.section("13. EXCEPTION HANDLING")

    try:
        from cascadeflow import BudgetExceededError

        error = BudgetExceededError("Test", remaining=0.5)
        assert error.remaining == 0.5
        runner.success("BudgetExceededError")
    except Exception as e:
        runner.fail("BudgetExceededError", e)

    try:
        from cascadeflow import QualityThresholdError

        error = QualityThresholdError("Test")
        assert "Test" in str(error)
        runner.success("QualityThresholdError")
    except Exception as e:
        runner.fail("QualityThresholdError", e)

    try:
        from cascadeflow import ProviderError

        error = ProviderError("Test", provider="openai")
        assert error.provider == "openai"
        runner.success("ProviderError")
    except Exception as e:
        runner.fail("ProviderError", e)


# ============================================================================
# SECTION 14: INTEGRATION TEST
# ============================================================================

async def test_full_integration(runner):
    """Test full end-to-end integration."""
    runner.section("14. FULL INTEGRATION")

    # Need at least one provider
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")):
        runner.skip("Full integration (no API keys)")
        return

    try:
        from cascadeflow import CascadeAgent, ModelConfig, UserTier

        # Build model list
        models = []

        if os.getenv("GROQ_API_KEY"):
            models.append(ModelConfig(
                name="llama-3.1-8b-instant",
                provider="groq",
                cost=0.0
            ))

        if os.getenv("OPENAI_API_KEY"):
            models.append(ModelConfig(
                name="gpt-3.5-turbo",
                provider="openai",
                cost=0.002
            ))

        # Create tiers
        tiers = {
            "free": UserTier(name="free", max_budget=0.001, quality_threshold=0.6),
            "pro": UserTier(name="pro", max_budget=0.01, quality_threshold=0.8),
        }

        # Create agent
        agent = CascadeAgent(models, tiers=tiers)

        # Run queries
        queries = [
            ("What is 2+2?", "free"),
            ("Explain AI briefly", "pro"),
        ]

        for query, tier in queries:
            result = await agent.run(query, user_tier=tier)
            assert result.content is not None
            assert result.user_tier == tier

        # Check stats
        stats = agent.get_stats()
        assert stats["total_queries"] == 2

        runner.success("Full integration test passed")
        runner.info(f"Total cost: ${stats['total_cost']:.6f}")

    except Exception as e:
        runner.fail("Full integration test", e)


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Run all tests."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║          🌊 CascadeFlow - Day 4 Validation Suite 🌊             ║
║                                                                  ║
║  Complete test suite before proceeding to Day 4.2               ║
║  (Speculative Cascades Implementation)                          ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    runner = TestRunner()

    # Run all test sections
    await test_imports(runner)
    await test_config_classes(runner)
    await test_utilities(runner)
    await test_api_keys(runner)
    await test_provider_initialization(runner)
    await test_ollama_connection(runner)
    await test_real_api_calls(runner)
    await test_cascade_agent(runner)
    await test_smart_default(runner)
    await test_exceptions(runner)
    await test_unit_tests(runner)
    await test_example_syntax(runner)
    await test_example_execution(runner)
    await test_full_integration(runner)

    # Show summary
    success = runner.summary()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())