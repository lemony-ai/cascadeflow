#!/usr/bin/env python3
"""
Verify test environment setup for CascadeFlow tool calling tests.

Checks:
- API keys in .env
- Required packages installed
- Ollama availability
- Provider connectivity

Run before running tests:
    python verify_test_setup.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text):
    """Print colored header."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")


def print_check(name, status, details=""):
    """Print check result."""
    status_icon = f"{GREEN}✅{RESET}" if status else f"{RED}❌{RESET}"
    print(f"{status_icon} {name:30s} {details}")


def print_warning(message):
    """Print warning message."""
    print(f"{YELLOW}⚠️  {message}{RESET}")


def print_info(message):
    """Print info message."""
    print(f"{BLUE}ℹ️  {message}{RESET}")


# ============================================================================
# CHECK FUNCTIONS
# ============================================================================


def check_dotenv():
    """Check if .env file exists and can be loaded."""
    env_path = Path(".env")
    if not env_path.exists():
        print_check(".env file", False, "Not found")
        print_info("Create .env file with API keys:")
        print(
            """
        OPENAI_API_KEY=sk-...
        ANTHROPIC_API_KEY=sk-ant-...
        GROQ_API_KEY=gsk_...
        TOGETHER_API_KEY=...
        """
        )
        return False

    load_dotenv()
    print_check(".env file", True, "Found and loaded")
    return True


def check_api_keys():
    """Check if API keys are set."""
    keys = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
        "TOGETHER_API_KEY": os.getenv("TOGETHER_API_KEY"),
    }

    print_info("API Keys:")
    available_count = 0
    for key_name, key_value in keys.items():
        has_key = bool(key_value)
        if has_key:
            available_count += 1
            masked = key_value[:8] + "..." if len(key_value) > 8 else "***"
            print_check(f"  {key_name}", True, masked)
        else:
            print_check(f"  {key_name}", False, "Not set")

    if available_count == 0:
        print_warning("No API keys found! Tests will be skipped.")
        return False
    elif available_count < 4:
        print_warning(f"Only {available_count}/4 API keys set. Some tests will be skipped.")
        return True
    else:
        print(f"\n{GREEN}✅ All API keys configured!{RESET}")
        return True


def check_packages():
    """Check if required packages are installed."""
    required = [
        ("pytest", "pytest"),
        ("pytest-asyncio", "pytest_asyncio"),
        ("python-dotenv", "dotenv"),
        ("httpx", "httpx"),
        ("cascadeflow", "cascadeflow"),
    ]

    print_info("Required packages:")
    all_installed = True
    for package_name, import_name in required:
        try:
            __import__(import_name)
            print_check(f"  {package_name}", True)
        except ImportError:
            print_check(f"  {package_name}", False)
            all_installed = False

    if not all_installed:
        print_warning("Install missing packages:")
        print("  pip install pytest pytest-asyncio python-dotenv httpx")
        return False

    return True


async def check_ollama():
    """Check if Ollama is running and has required models."""
    print_info("Ollama:")

    try:
        import httpx

        # Check if Ollama is running
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get("http://localhost:11434/api/tags", timeout=5.0)
                response.raise_for_status()
                print_check("  Ollama server", True, "Running")

                # Check for required models
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]

                required_models = ["gemma3:1b", "gemma3:12b"]
                for model in required_models:
                    has_model = any(model in m for m in models)
                    if has_model:
                        print_check(f"  {model}", True, "Installed")
                    else:
                        print_check(f"  {model}", False, "Not found")
                        print_warning(f"Install with: ollama pull {model}")

                return True

            except (httpx.ConnectError, httpx.TimeoutException):
                print_check("  Ollama server", False, "Not running")
                print_info("Start Ollama:")
                print("    ollama serve")
                return False

    except ImportError:
        print_check("  httpx", False, "Not installed")
        return False


async def check_provider_connectivity():
    """Check if providers can be initialized."""
    print_info("Provider connectivity:")

    providers_to_check = []

    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        providers_to_check.append(("OpenAI", "cascadeflow.providers", "OpenAIProvider"))

    # Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        providers_to_check.append(("Anthropic", "cascadeflow.providers", "AnthropicProvider"))

    # Groq
    if os.getenv("GROQ_API_KEY"):
        providers_to_check.append(("Groq", "cascadeflow.providers", "GroqProvider"))

    # Together
    if os.getenv("TOGETHER_API_KEY"):
        providers_to_check.append(("Together.ai", "cascadeflow.providers", "TogetherProvider"))

    if not providers_to_check:
        print_warning("No API keys set, cannot check connectivity")
        return False

    all_ok = True
    for provider_name, module_name, class_name in providers_to_check:
        try:
            module = __import__(module_name, fromlist=[class_name])
            provider_class = getattr(module, class_name)
            provider_class()
            print_check(f"  {provider_name}", True, "Initialized")
        except Exception as e:
            print_check(f"  {provider_name}", False, str(e)[:40])
            all_ok = False

    return all_ok


def check_test_file():
    """Check if test file exists."""
    test_path = Path("tests/test_tool_calling_comprehensive.py")

    if test_path.exists():
        print_check("Test file", True, str(test_path))
        return True
    else:
        print_check("Test file", False, "Not found")
        print_warning("Expected: tests/test_tool_calling_comprehensive.py")
        return False


# ============================================================================
# MAIN
# ============================================================================


async def main():
    """Run all checks."""
    print_header("CascadeFlow Tool Calling - Setup Verification")

    checks = []

    # 1. Check .env file
    print_header("1. Environment Configuration")
    checks.append(check_dotenv())
    checks.append(check_api_keys())

    # 2. Check packages
    print_header("2. Package Dependencies")
    checks.append(check_packages())

    # 3. Check Ollama
    print_header("3. Ollama Setup (Optional)")
    checks.append(await check_ollama())

    # 4. Check providers
    print_header("4. Provider Connectivity")
    checks.append(await check_provider_connectivity())

    # 5. Check test file
    print_header("5. Test File")
    checks.append(check_test_file())

    # Summary
    print_header("Summary")

    passed = sum(checks)
    total = len(checks)

    if passed == total:
        print(f"\n{GREEN}✅ All checks passed! ({passed}/{total}){RESET}")
        print(f"\n{GREEN}Ready to run tests:{RESET}")
        print("  pytest tests/test_tool_calling_comprehensive.py -v")
    else:
        print(f"\n{YELLOW}⚠️  Some checks failed ({passed}/{total}){RESET}")
        print(f"\n{YELLOW}Tests will run but some may be skipped{RESET}")
        print("\nTo fix issues:")
        print("  1. Check messages above")
        print("  2. Install missing dependencies")
        print("  3. Set API keys in .env")
        print("  4. Run tests with: pytest tests/test_tool_calling_comprehensive.py -v")

    print()


if __name__ == "__main__":
    asyncio.run(main())
