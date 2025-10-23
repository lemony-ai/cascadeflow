"""
Interactive Cascade Testing Suite

Test the speculative cascade system with real-time insights.

Usage:
    pytest tests/test_cascade_interactive.py -s -v

Features:
- Interactive prompt input
- All provider support (OpenAI, Anthropic, Groq, Ollama, Together)
- Detailed quality analysis
- Cost and latency metrics
- Complexity detection
- Beautiful formatted output
"""

import os
import sys
from pathlib import Path
from typing import Any, Optional

import pytest
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cascadeflow.config import ModelConfig
from cascadeflow.speculative import WholeResponseCascade

from cascadeflow.providers.anthropic import AnthropicProvider
from cascadeflow.providers.groq import GroqProvider
from cascadeflow.providers.ollama import OllamaProvider
from cascadeflow.providers.openai import OpenAIProvider
from cascadeflow.providers.together import TogetherProvider
from cascadeflow.quality import QualityConfig
from cascadeflow.quality.complexity import ComplexityDetector

# Load environment variables
load_dotenv()


# ANSI color codes for beautiful output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_section(title: str, color: str = Colors.HEADER):
    """Print a section header."""
    print(f"\n{color}{'=' * 80}{Colors.ENDC}")
    print(f"{color}{Colors.BOLD}{title:^80}{Colors.ENDC}")
    print(f"{color}{'=' * 80}{Colors.ENDC}\n")


def print_metric(label: str, value: Any, unit: str = "", good_threshold: Optional[float] = None):
    """Print a metric with color coding."""
    color = Colors.ENDC

    if good_threshold is not None and isinstance(value, (int, float)):
        color = Colors.OKGREEN if value >= good_threshold else Colors.WARNING

    print(f"  {Colors.BOLD}{label:.<40}{Colors.ENDC} {color}{value}{unit}{Colors.ENDC}")


def print_quality_checks(checks: dict[str, bool]):
    """Print quality validation checks."""
    print(f"\n  {Colors.BOLD}Quality Checks:{Colors.ENDC}")
    for check, passed in checks.items():
        symbol = "✓" if passed else "✗"
        color = Colors.OKGREEN if passed else Colors.FAIL
        print(f"    {color}{symbol}{Colors.ENDC} {check.replace('_', ' ').title()}")


class CascadeTestSuite:
    """Interactive cascade testing suite."""

    def __init__(self):
        self.providers = {}
        self.cascade_configs = {}
        self.complexity_detector = ComplexityDetector()
        self.session_stats = {
            "total_queries": 0,
            "total_accepted": 0,
            "total_cost_saved": 0.0,
            "total_time_saved": 0.0,
        }

    def setup_providers(self):
        """Initialize all providers."""
        print_section("Initializing Providers", Colors.OKCYAN)

        # OpenAI
        if os.getenv("OPENAI_API_KEY"):
            try:
                self.providers["openai"] = OpenAIProvider()
                print(f"  {Colors.OKGREEN}✓{Colors.ENDC} OpenAI initialized")
            except Exception as e:
                print(f"  {Colors.FAIL}✗{Colors.ENDC} OpenAI failed: {e}")

        # Anthropic
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                self.providers["anthropic"] = AnthropicProvider()
                print(f"  {Colors.OKGREEN}✓{Colors.ENDC} Anthropic initialized")
            except Exception as e:
                print(f"  {Colors.FAIL}✗{Colors.ENDC} Anthropic failed: {e}")

        # Groq
        if os.getenv("GROQ_API_KEY"):
            try:
                self.providers["groq"] = GroqProvider()
                print(f"  {Colors.OKGREEN}✓{Colors.ENDC} Groq initialized")
            except Exception as e:
                print(f"  {Colors.FAIL}✗{Colors.ENDC} Groq failed: {e}")

        # Together
        if os.getenv("TOGETHER_API_KEY"):
            try:
                self.providers["together"] = TogetherProvider()
                print(f"  {Colors.OKGREEN}✓{Colors.ENDC} Together initialized")
            except Exception as e:
                print(f"  {Colors.FAIL}✗{Colors.ENDC} Together failed: {e}")

        # Ollama (local, no API key needed)
        try:
            self.providers["ollama"] = OllamaProvider()
            print(f"  {Colors.OKGREEN}✓{Colors.ENDC} Ollama initialized")
        except Exception as e:
            print(f"  {Colors.FAIL}✗{Colors.ENDC} Ollama failed: {e}")

        if not self.providers:
            print(f"\n  {Colors.FAIL}ERROR: No providers available!{Colors.ENDC}")
            print("  Please check your .env file and API keys.")
            sys.exit(1)

    def setup_cascade_configs(self):
        """Setup cascade configurations for different providers."""
        print_section("Available Cascade Configurations", Colors.OKCYAN)

        configs = [
            # OpenAI cascades
            {
                "name": "OpenAI: GPT-4o-mini → GPT-4o",
                "drafter": ModelConfig(
                    name="gpt-4o-mini", provider="openai", cost=0.15, speed_ms=200
                ),
                "verifier": ModelConfig(name="gpt-4o", provider="openai", cost=5.0, speed_ms=800),
                "available": "openai" in self.providers,
            },
            {
                "name": "OpenAI: GPT-3.5 → GPT-4o",
                "drafter": ModelConfig(
                    name="gpt-3.5-turbo", provider="openai", cost=0.5, speed_ms=150
                ),
                "verifier": ModelConfig(name="gpt-4o", provider="openai", cost=5.0, speed_ms=800),
                "available": "openai" in self.providers,
            },
            # Anthropic cascades
            {
                "name": "Anthropic: Haiku → Sonnet",
                "drafter": ModelConfig(
                    name="claude-3-haiku-20240307", provider="anthropic", cost=0.25, speed_ms=200
                ),
                "verifier": ModelConfig(
                    name="claude-3-5-sonnet-20241022", provider="anthropic", cost=3.0, speed_ms=600
                ),
                "available": "anthropic" in self.providers,
            },
            # Groq cascades
            {
                "name": "Groq: Llama 3.1 8B → 70B",
                "drafter": ModelConfig(
                    name="llama-3.1-8b-instant", provider="groq", cost=0.05, speed_ms=100
                ),
                "verifier": ModelConfig(
                    name="llama-3.1-70b-versatile", provider="groq", cost=0.59, speed_ms=400
                ),
                "available": "groq" in self.providers,
            },
            {
                "name": "Groq: Gemma 7B → Llama 70B",
                "drafter": ModelConfig(
                    name="gemma2-9b-it", provider="groq", cost=0.20, speed_ms=120
                ),
                "verifier": ModelConfig(
                    name="llama-3.1-70b-versatile", provider="groq", cost=0.59, speed_ms=400
                ),
                "available": "groq" in self.providers,
            },
            # Together cascades
            {
                "name": "Together: Llama 8B → 70B",
                "drafter": ModelConfig(
                    name="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                    provider="together",
                    cost=0.18,
                    speed_ms=150,
                ),
                "verifier": ModelConfig(
                    name="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                    provider="together",
                    cost=0.88,
                    speed_ms=500,
                ),
                "available": "together" in self.providers,
            },
            # Ollama cascades
            {
                "name": "Ollama: Gemma3 1B → 12B",
                "drafter": ModelConfig(name="gemma3:1b", provider="ollama", cost=0.0, speed_ms=50),
                "verifier": ModelConfig(
                    name="gemma3:12b", provider="ollama", cost=0.0, speed_ms=300
                ),
                "available": "ollama" in self.providers,
            },
            # Cross-provider cascades
            {
                "name": "Cross: Groq 8B → OpenAI GPT-4o",
                "drafter": ModelConfig(
                    name="llama-3.1-8b-instant", provider="groq", cost=0.05, speed_ms=100
                ),
                "verifier": ModelConfig(name="gpt-4o", provider="openai", cost=5.0, speed_ms=800),
                "available": "groq" in self.providers and "openai" in self.providers,
            },
            {
                "name": "Cross: Ollama → Anthropic Sonnet",
                "drafter": ModelConfig(
                    name="gemma3:12b", provider="ollama", cost=0.0, speed_ms=300
                ),
                "verifier": ModelConfig(
                    name="claude-3-5-sonnet-20241022", provider="anthropic", cost=3.0, speed_ms=600
                ),
                "available": "ollama" in self.providers and "anthropic" in self.providers,
            },
        ]

        # Filter to available configs
        available_configs = [c for c in configs if c["available"]]

        for i, config in enumerate(available_configs, 1):
            self.cascade_configs[i] = config
            print(f"  {Colors.OKGREEN}[{i}]{Colors.ENDC} {config['name']}")

        if not self.cascade_configs:
            print(f"\n  {Colors.FAIL}ERROR: No cascade configs available!{Colors.ENDC}")
            sys.exit(1)

    def select_cascade_config(self) -> dict[str, Any]:
        """Let user select a cascade configuration."""
        print(
            f"\n{Colors.BOLD}Select cascade configuration (1-{len(self.cascade_configs)}):{Colors.ENDC} ",
            end="",
        )

        while True:
            try:
                choice = int(input().strip())
                if choice in self.cascade_configs:
                    return self.cascade_configs[choice]
                else:
                    print(f"{Colors.FAIL}Invalid choice. Try again:{Colors.ENDC} ", end="")
            except ValueError:
                print(f"{Colors.FAIL}Please enter a number:{Colors.ENDC} ", end="")

    def select_quality_config(self) -> QualityConfig:
        """Let user select quality configuration."""
        print_section("Quality Configuration", Colors.OKCYAN)

        configs = {
            1: ("CASCADE (Recommended)", QualityConfig.for_cascade()),
            2: ("Production", QualityConfig.for_production()),
            3: ("Development", QualityConfig.for_development()),
            4: ("Strict", QualityConfig.strict()),
        }

        for num, (name, _) in configs.items():
            print(f"  {Colors.OKGREEN}[{num}]{Colors.ENDC} {name}")

        print(f"\n{Colors.BOLD}Select quality config (1-4) [default: 1]:{Colors.ENDC} ", end="")

        choice_str = input().strip()
        choice = int(choice_str) if choice_str else 1

        if choice not in configs:
            choice = 1

        name, config = configs[choice]
        print(f"\n  Using: {Colors.OKGREEN}{name}{Colors.ENDC}")

        return config

    async def run_cascade_test(
        self, query: str, cascade_config: dict, quality_config: QualityConfig
    ):
        """Run a cascade test and display results."""
        print_section(f"Testing Query: {query[:60]}...", Colors.HEADER)

        # Detect complexity
        complexity, score = self.complexity_detector.detect(query)
        print_metric("Query Complexity", f"{complexity.value.upper()} (score: {score:.2f})")
        print_metric(
            "Complexity Threshold", quality_config.confidence_thresholds.get(complexity.value, 0.70)
        )

        # Create cascade
        cascade = WholeResponseCascade(
            drafter=cascade_config["drafter"],
            verifier=cascade_config["verifier"],
            providers=self.providers,
            quality_config=quality_config,
            verbose=False,
        )

        # Run cascade
        print(f"\n  {Colors.OKCYAN}Running cascade...{Colors.ENDC}")
        result = await cascade.execute(query, max_tokens=200, temperature=0.7)

        # Display results
        self._display_cascade_results(result, cascade_config, complexity)

        # Update session stats
        self._update_session_stats(result)

        return result

    def _display_cascade_results(self, result, cascade_config, complexity):
        """Display detailed cascade results."""

        # ============ MODEL DECISION ============
        print_section("Model Decision", Colors.OKBLUE)

        if result.draft_accepted:
            print(f"  {Colors.OKGREEN}✓ DRAFT ACCEPTED{Colors.ENDC}")
            print(f"  Used: {Colors.BOLD}{result.drafter_model}{Colors.ENDC}")
        else:
            print(f"  {Colors.WARNING}✗ DRAFT REJECTED{Colors.ENDC}")
            print(f"  Used: {Colors.BOLD}{result.verifier_model}{Colors.ENDC}")

        print_metric("Decision Reason", result.metadata.get("reason", "unknown"))

        # ============ CONFIDENCE SCORES ============
        print_section("Confidence Analysis", Colors.OKBLUE)

        print_metric("Draft Confidence", f"{result.draft_confidence:.1%}", good_threshold=0.50)

        if not result.draft_accepted:
            print_metric(
                "Verifier Confidence", f"{result.verifier_confidence:.1%}", good_threshold=0.70
            )

        # Show confidence method
        conf_method = result.metadata.get("confidence_method", "unknown")
        draft_method = result.metadata.get("draft_method", "unknown")

        if result.draft_accepted:
            print_metric("Confidence Method", conf_method)
        else:
            print_metric("Draft Method", draft_method)
            print_metric("Verifier Method", conf_method)

        # ============ QUALITY VALIDATION ============
        if "validation_checks" in result.metadata:
            print_section("Quality Validation", Colors.OKBLUE)
            print_quality_checks(result.metadata["validation_checks"])

        # ============ PERFORMANCE METRICS ============
        print_section("Performance Metrics", Colors.OKBLUE)

        # Cost analysis
        print(f"\n  {Colors.BOLD}Cost Analysis:{Colors.ENDC}")
        print_metric("Total Cost", f"${result.total_cost:.6f}")

        if result.draft_accepted:
            drafter_cost = result.total_cost
            verifier_cost = cascade_config["verifier"].cost * 0.1  # Estimate
            savings = verifier_cost - drafter_cost
            savings_pct = (savings / verifier_cost * 100) if verifier_cost > 0 else 0

            print_metric("Verifier Cost (avoided)", f"${verifier_cost:.6f}")
            print_metric("Cost Saved", f"${savings:.6f} ({savings_pct:.1f}%)", good_threshold=0.0)
        else:
            print_metric("Extra Draft Cost", f"${result.metadata.get('cost_saved', 0.0):.6f}")

        # Latency analysis
        print(f"\n  {Colors.BOLD}Latency Analysis:{Colors.ENDC}")
        print_metric("Total Latency", f"{result.latency_ms:.0f}", "ms")

        if result.draft_accepted:
            estimated_verifier = cascade_config["verifier"].speed_ms
            time_saved = estimated_verifier - result.latency_ms

            print_metric("Verifier Latency (estimated)", f"{estimated_verifier:.0f}", "ms")
            print_metric("Time Saved", f"{time_saved:.0f}", "ms", good_threshold=0.0)
            print_metric("Speedup", f"{result.speedup:.2f}x", good_threshold=1.0)
        else:
            print_metric("Speedup", "1.0x (no speedup)")

        # ============ RESPONSE CONTENT ============
        print_section("Response Content", Colors.OKBLUE)

        content_preview = result.content[:300]
        if len(result.content) > 300:
            content_preview += "..."

        print(f"  {content_preview}\n")

        print_metric("Response Length", f"{len(result.content)} chars")
        print_metric("Word Count", len(result.content.split()))

        # ============ CASCADE STATISTICS ============
        stats = cascade.get_stats()

        print_section("Cascade Statistics", Colors.OKBLUE)

        print_metric("Total Executions", stats["total_executions"])
        print_metric("Drafts Accepted", stats["drafts_accepted"])
        print_metric("Drafts Rejected", stats["drafts_rejected"])
        print_metric("Acceptance Rate", f"{stats['acceptance_rate']:.1%}", good_threshold=0.50)

        if stats["total_executions"] > 0:
            print_metric("Avg Speedup", f"{stats['avg_speedup']:.2f}x", good_threshold=1.5)
            print_metric("Avg Cost Saved", f"${stats['avg_cost_saved']:.6f}", good_threshold=0.0)

        # Complexity breakdown
        if "complexity_breakdown" in stats and stats["complexity_breakdown"]:
            print(f"\n  {Colors.BOLD}By Complexity:{Colors.ENDC}")
            for comp, comp_stats in stats["complexity_breakdown"].items():
                rate = comp_stats["acceptance_rate"]
                color = Colors.OKGREEN if rate >= 0.5 else Colors.WARNING
                print(
                    f"    {comp:10s}: {color}{rate:6.1%}{Colors.ENDC} "
                    f"({comp_stats['accepted']}/{comp_stats['total']})"
                )

    def _update_session_stats(self, result):
        """Update session-wide statistics."""
        self.session_stats["total_queries"] += 1

        if result.draft_accepted:
            self.session_stats["total_accepted"] += 1
            self.session_stats["total_cost_saved"] += result.metadata.get("cost_saved", 0.0)
            self.session_stats["total_time_saved"] += (
                result.metadata.get("speedup", 1.0) - 1.0
            ) * result.latency_ms

    def display_session_summary(self):
        """Display summary of entire session."""
        if self.session_stats["total_queries"] == 0:
            return

        print_section("Session Summary", Colors.HEADER)

        acceptance_rate = self.session_stats["total_accepted"] / self.session_stats["total_queries"]

        print_metric("Total Queries", self.session_stats["total_queries"])
        print_metric("Drafts Accepted", self.session_stats["total_accepted"])
        print_metric("Acceptance Rate", f"{acceptance_rate:.1%}", good_threshold=0.50)
        print_metric(
            "Total Cost Saved", f"${self.session_stats['total_cost_saved']:.4f}", good_threshold=0.0
        )
        print_metric(
            "Total Time Saved",
            f"{self.session_stats['total_time_saved']:.0f}",
            "ms",
            good_threshold=0.0,
        )


@pytest.fixture
def test_suite():
    """Create test suite fixture."""
    suite = CascadeTestSuite()
    suite.setup_providers()
    suite.setup_cascade_configs()
    return suite


@pytest.mark.asyncio
async def test_interactive_cascade(test_suite):
    """
    Interactive cascade testing.

    Run with: pytest tests/test_cascade_interactive.py -s -v
    """

    print_section("Interactive Cascade Testing Suite", Colors.HEADER)
    print(f"\n  {Colors.BOLD}Welcome to the Cascade Testing Suite!{Colors.ENDC}")
    print("  Test your cascade system with real-time insights.\n")

    # Select cascade configuration (once)
    cascade_config = test_suite.select_cascade_config()

    # Select quality configuration (once)
    quality_config = test_suite.select_quality_config()

    # Main testing loop
    while True:
        print_section("Enter Test Query", Colors.OKCYAN)
        print(f"  {Colors.BOLD}Enter your query (or 'quit' to exit):{Colors.ENDC}")
        print(f"  {Colors.BOLD}  - 'config' to change cascade config{Colors.ENDC}")
        print(f"  {Colors.BOLD}  - 'quality' to change quality config{Colors.ENDC}")
        print(f"  {Colors.BOLD}  - 'summary' to see session summary{Colors.ENDC}\n")
        print("  > ", end="")

        query = input().strip()

        if not query:
            continue

        if query.lower() == "quit":
            test_suite.display_session_summary()
            print(f"\n  {Colors.OKGREEN}Thanks for testing!{Colors.ENDC}\n")
            break

        if query.lower() == "config":
            cascade_config = test_suite.select_cascade_config()
            continue

        if query.lower() == "quality":
            quality_config = test_suite.select_quality_config()
            continue

        if query.lower() == "summary":
            test_suite.display_session_summary()
            continue

        # Run the test
        try:
            await test_suite.run_cascade_test(query, cascade_config, quality_config)
        except Exception as e:
            print(f"\n  {Colors.FAIL}ERROR: {e}{Colors.ENDC}\n")
            import traceback

            traceback.print_exc()

        # Ask if user wants to continue
        print(f"\n{Colors.BOLD}Press Enter to test another query...{Colors.ENDC}")
        input()


if __name__ == "__main__":
    # Run directly
    import sys

    sys.exit(pytest.main([__file__, "-s", "-v"]))
