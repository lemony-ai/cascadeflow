"""
Comprehensive test script for CascadeFlow.

Tests everything before git commit:
- Configuration classes
- All providers
- Examples
- Unit tests
"""

import asyncio
import os
import sys
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
            self.errors.append((message, error))
        self.failed += 1

    def skip(self, message):
        """Print skip message."""
        print(f"⚠️ {message}")
        self.skipped += 1

    def info(self, message):
        """Print info message."""
        print(f"ℹ️  {message}")

    def section(self, title):
        """Print section header."""
        print(f"\n{'=' * 70}")
        print(f"{title}")
        print(f"{'=' * 70}\n")

    def summary(self):
        """Print test summary."""
        print(f"\n{'=' * 70}")
        print(f"TEST SUMMARY")
        print(f"{'=' * 70}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"⚠️ Skipped: {self.skipped}")
        print(f"Total: {self.passed + self.failed + self.skipped}")

        if self.errors:
            print(f"\n{'=' * 70}")
            print(f"ERRORS")
            print(f"{'=' * 70}")
            for msg, err in self.errors:
                print(f"\n❌ {msg}")
                print(f"   {err}")

        print(f"\n{'=' * 70}")
        if self.failed == 0:
            print(f"🎉 ALL TESTS PASSED!")
            print(f"✅ Ready to commit to git")
        else:
            print(f"⚠️ {self.failed} TESTS FAILED")
            print(f"❌ Fix issues before committing")
        print(f"{'=' * 70}\n")

        return self.failed == 0


async def test_imports(runner):
    """Test all imports."""
    runner.section("TEST 1: IMPORTS")

    try:
        from cascadeflow import ModelConfig, CascadeConfig, UserTier
        runner.success("Core config imports")
    except Exception as e:
        runner.fail("Core config imports", e)
        return

    try:
        from cascadeflow.providers import BaseProvider, ModelResponse
        runner.success("Base provider imports")
    except Exception as e:
        runner.fail("Base provider imports", e)

    try:
        from cascadeflow.providers import OpenAIProvider
        runner.success("OpenAI provider import")
    except Exception as e:
        runner.fail("OpenAI provider import", e)

    try:
        from cascadeflow.providers import AnthropicProvider
        runner.success("Anthropic provider import")
    except Exception as e:
        runner.fail("Anthropic provider import", e)

    try:
        from cascadeflow.providers import OllamaProvider
        runner.success("Ollama provider import")
    except Exception as e:
        runner.fail("Ollama provider import", e)

    try:
        from cascadeflow.providers import GroqProvider
        runner.success("Groq provider import")
    except Exception as e:
        runner.fail("Groq provider import", e)

    try:
        from cascadeflow.exceptions import (
            CascadeFlowError, BudgetExceededError,
            ProviderError, ModelError
        )
        runner.success("Exception imports")
    except Exception as e:
        runner.fail("Exception imports", e)


async def test_config_classes(runner):
    """Test configuration classes."""
    runner.section("TEST 2: CONFIGURATION CLASSES")

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
        runner.success("ModelConfig creation")
    except Exception as e:
        runner.fail("ModelConfig creation", e)

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
        runner.success("CascadeConfig creation")
    except Exception as e:
        runner.fail("CascadeConfig creation", e)

    try:
        from cascadeflow import UserTier

        tier = UserTier(
            name="premium",
            max_budget=0.10,
            quality_threshold=0.9
        )
        assert tier.name == "premium"
        assert tier.max_budget == 0.10
        runner.success("UserTier creation")
    except Exception as e:
        runner.fail("UserTier creation", e)


async def test_provider_initialization(runner):
    """Test provider initialization."""
    runner.section("TEST 3: PROVIDER INITIALIZATION")

    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        try:
            from cascadeflow.providers import OpenAIProvider
            provider = OpenAIProvider()
            assert provider.api_key is not None
            await provider.client.aclose()
            runner.success("OpenAI provider initialization")
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
            runner.success("Anthropic provider initialization")
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
            runner.success("Groq provider initialization")
        except Exception as e:
            runner.fail("Groq provider initialization", e)
    else:
        runner.skip("Groq provider (no API key)")

    # Ollama
    try:
        from cascadeflow.providers import OllamaProvider
        provider = OllamaProvider()
        await provider.client.aclose()
        runner.success("Ollama provider initialization")
    except Exception as e:
        runner.fail("Ollama provider initialization", e)


async def test_groq_api(runner):
    """Test Groq API with real call."""
    runner.section("TEST 4: GROQ API (REAL CALL)")

    if not os.getenv("GROQ_API_KEY"):
        runner.skip("Groq API test (no API key)")
        return

    try:
        from cascadeflow.providers import GroqProvider

        provider = GroqProvider()

        result = await provider.complete(
            prompt="Say 'CascadeFlow test successful!' in one sentence.",
            model="llama-3.1-8b-instant",
            max_tokens=50
        )

        assert result.content is not None
        assert len(result.content) > 0
        assert result.model == "llama-3.1-8b-instant"
        assert result.provider == "groq"
        assert result.cost == 0.0
        assert result.tokens_used > 0

        runner.success(f"Groq API call (model: llama-3.1-8b-instant)")
        runner.info(f"Response: {result.content[:60]}...")

        await provider.client.aclose()

    except Exception as e:
        runner.fail("Groq API call", e)


async def test_ollama_connection(runner):
    """Test Ollama connection."""
    runner.section("TEST 5: OLLAMA CONNECTION")

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:11434/api/version", timeout=2.0)
            if response.status_code == 200:
                version_data = response.json()
                runner.success(f"Ollama is running (version: {version_data.get('version', 'unknown')})")

                # Check available models
                tags_response = await client.get("http://localhost:11434/api/tags", timeout=2.0)
                if tags_response.status_code == 200:
                    models = tags_response.json().get("models", [])
                    if models:
                        model_names = [m["name"] for m in models[:3]]
                        runner.info(f"Available models: {', '.join(model_names)}")
                    else:
                        runner.skip("Ollama running but no models installed")
            else:
                runner.skip("Ollama not responding correctly")
    except Exception as e:
        runner.skip(f"Ollama not available: {e}")


async def test_unit_tests(runner):
    """Run pytest unit tests."""
    runner.section("TEST 6: UNIT TESTS (pytest)")

    try:
        import subprocess
        result = subprocess.run(
            ["pytest", "tests/", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            # Count passed tests
            output = result.stdout
            if "passed" in output:
                runner.success("All pytest tests passed")
                runner.info(output.split('\n')[-2])  # Summary line
            else:
                runner.success("Pytest completed")
        else:
            runner.fail("Some pytest tests failed")
            # Show last few lines of output
            lines = result.stdout.split('\n')
            for line in lines[-10:]:
                if line.strip():
                    print(f"   {line}")

    except subprocess.TimeoutExpired:
        runner.fail("Pytest tests timed out")
    except FileNotFoundError:
        runner.skip("pytest not installed")
    except Exception as e:
        runner.fail("Running pytest", e)


async def check_example_syntax(runner):
    """Check example files for syntax errors."""
    runner.section("TEST 7: EXAMPLE FILES SYNTAX")

    import py_compile
    import glob

    example_files = glob.glob("examples/*.py")

    for filepath in example_files:
        filename = os.path.basename(filepath)
        try:
            py_compile.compile(filepath, doraise=True)
            runner.success(f"Syntax OK: {filename}")
        except Exception as e:
            runner.fail(f"Syntax error in {filename}", e)


async def test_api_keys(runner):
    """Check which API keys are configured."""
    runner.section("TEST 8: API KEY CONFIGURATION")

    keys = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
        "HF_TOKEN": os.getenv("HF_TOKEN"),
    }

    for key_name, key_value in keys.items():
        if key_value:
            runner.success(f"{key_name} is set ({key_value[:10]}...)")
        else:
            runner.info(f"{key_name} is NOT set (optional)")


async def main():
    """Run all tests."""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║          🌊 CascadeFlow - Pre-Commit Test Suite 🌊             ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    runner = TestRunner()

    # Run all tests
    await test_imports(runner)
    await test_config_classes(runner)
    await test_api_keys(runner)
    await test_provider_initialization(runner)
    await test_ollama_connection(runner)
    await test_groq_api(runner)
    await test_unit_tests(runner)
    await check_example_syntax(runner)

    # Show summary
    success = runner.summary()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())