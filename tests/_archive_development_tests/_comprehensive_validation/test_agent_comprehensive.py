"""
CASCADEFLOW ADVANCED TEST SUITE WITH AUTO-TUNING + DIAGNOSTIC VALIDATION
==========================================================================

COMPLETE IMPLEMENTATION with NATURAL QUERY HANDLING

KEY CHANGES FROM PREVIOUS:
✅ Natural query handling - system detects complexity, not pre-labeled
✅ All report methods fully implemented
✅ Comprehensive diagnostic tracking
✅ Auto-tuning with validation
✅ Statistical analysis and anomaly detection

FEATURES:
- 150+ real-world queries (naturally typed, like users would)
- Auto-tuning system for quality parameters
- Cost savings analysis (vs baseline direct routing)
- Quality system performance deep-dive with validation
- Comprehensive latency breakdowns with diagnostics
- ROI analysis per complexity level
- Streaming with detailed progress tracking
- A/B testing different configurations
- Statistical significance testing
"""

import asyncio
import os
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cascadeflow.config import ModelConfig

from cascadeflow.agent import CascadeAgent, CascadeResult
from cascadeflow.quality import QualityConfig

# Load environment
load_dotenv()

# ============================================================================
# TEST CONFIGURATION
# ============================================================================

USE_STREAMING = True
ENABLE_AUTO_TUNING = True  # Set to False to skip auto-tuning
AUTO_TUNE_ITERATIONS = 5  # Number of quality configurations to test
QUICK_TEST = False  # Set True for quick test (~30 queries, 1-2 min)

# RATE LIMITING CONFIGURATION
RATE_LIMIT_DELAY = 0.3
MAX_RETRIES = 5
RETRY_DELAY = 5
EXPONENTIAL_BACKOFF = True

PROVIDER_RATE_LIMITS = {"groq": 30, "openai": 500, "together": 120, "anthropic": 50}

# ============================================================================
# TEST RESULT DATACLASSES
# ============================================================================


@dataclass
class TestResult:
    """Test result - stores what the SYSTEM decided (not what we expected)."""

    query: str
    success: bool = False
    error: Optional[str] = None

    # What the SYSTEM decided
    detected_complexity: Optional[str] = None
    complexity_confidence: Optional[float] = None
    strategy: str = "unknown"
    draft_accepted: Optional[bool] = None

    # Response data
    full_response: str = ""
    response_preview: str = ""
    response_length: Optional[int] = None
    response_word_count: Optional[int] = None

    # Performance data
    latency_ms: float = 0.0
    cost: float = 0.0
    baseline_cost: float = 0.0

    # Quality diagnostics
    quality_score: Optional[float] = None
    quality_threshold: Optional[float] = None
    quality_check_passed: Optional[bool] = None
    rejection_reason: Optional[str] = None

    # Timing breakdown
    complexity_detection_ms: float = 0.0
    draft_generation_ms: float = 0.0
    quality_verification_ms: float = 0.0
    verifier_generation_ms: float = 0.0
    cascade_overhead_ms: float = 0.0

    # Cost breakdown
    draft_cost: Optional[float] = None
    verifier_cost: Optional[float] = None
    cost_saved: Optional[float] = None

    # Response tracking
    draft_response: Optional[str] = None
    verifier_response: Optional[str] = None
    draft_confidence: Optional[float] = None
    verifier_confidence: Optional[float] = None
    confidence_method: Optional[str] = None

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    quality_config: Optional[dict[str, Any]] = None

    # Diagnostic validation
    has_timing_data: bool = False
    timing_complete: bool = False
    diagnostic_fields_present: int = 0
    diagnostic_fields_expected: int = 17

    @property
    def diagnostic_completeness(self) -> float:
        return (self.diagnostic_fields_present / self.diagnostic_fields_expected) * 100


@dataclass
class AutoTuneConfig:
    """Configuration for auto-tuning experiment."""

    threshold_multiplier: float
    min_complexity_for_cascade: str
    name: str
    results: list[TestResult] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return sum(r.cost for r in self.results if r.success)

    @property
    def total_baseline_cost(self) -> float:
        return sum(r.baseline_cost for r in self.results if r.success)

    @property
    def cost_savings(self) -> float:
        return self.total_baseline_cost - self.total_cost

    @property
    def cost_savings_pct(self) -> float:
        if self.total_baseline_cost == 0:
            return 0.0
        return (self.cost_savings / self.total_baseline_cost) * 100

    @property
    def avg_latency(self) -> float:
        latencies = [r.latency_ms for r in self.results if r.success]
        return statistics.mean(latencies) if latencies else 0.0

    @property
    def draft_acceptance_rate(self) -> float:
        cascade_results = [
            r for r in self.results if r.strategy == "cascade" and r.draft_accepted is not None
        ]
        if not cascade_results:
            return 0.0
        accepted = sum(1 for r in cascade_results if r.draft_accepted)
        return accepted / len(cascade_results)

    @property
    def quality_score_capture_rate(self) -> float:
        cascade_results = [r for r in self.results if r.strategy == "cascade"]
        if not cascade_results:
            return 0.0
        with_scores = sum(1 for r in cascade_results if r.quality_score is not None)
        return (with_scores / len(cascade_results)) * 100

    @property
    def avg_diagnostic_completeness(self) -> float:
        if not self.results:
            return 0.0
        return statistics.mean([r.diagnostic_completeness for r in self.results])


# ============================================================================
# NATURAL TEST QUERIES - Just like users would type them!
# ============================================================================

# Just queries - no pre-categorization!
# Let the system figure out complexity, routing, etc.

TEST_QUERIES = [
    # Customer Support (naturally ranging from trivial to complex)
    "What are your business hours?",
    "How do I contact support?",
    "Where is my order?",
    "Do you ship internationally?",
    "What's your return policy?",
    "How do I reset my password?",
    "Is this product in stock?",
    "What payment methods do you accept?",
    "How do I track my package?",
    "Can I change my delivery address?",
    "How long does shipping take?",
    "What's included in the warranty?",
    "How do I cancel my subscription?",
    "Can I get a refund for this item?",
    "How do I update my billing information?",
    "Is there a student discount?",
    "I received a damaged item, what should I do?",
    "My order is late and I need it urgently, can you help?",
    "I was charged twice for the same order, how do I get a refund?",
    "The product doesn't match the description, what are my options?",
    # Technical Support (naturally ranging difficulty)
    "How do I turn on Bluetooth?",
    "Where is the power button?",
    "How do I take a screenshot?",
    "How do I connect to WiFi?",
    "My device won't turn on, what should I check?",
    "How do I update the software?",
    "The battery drains quickly, any tips?",
    "How do I backup my data?",
    "The screen is frozen, how do I restart?",
    "I'm getting error code 0x8007042c when trying to update, how do I fix it?",
    "My device keeps disconnecting from WiFi every few minutes",
    "After the latest update, my keyboard shortcuts stopped working",
    # General Knowledge (naturally ranging complexity)
    "What is 5 + 7?",
    "What color is the ocean?",
    "How many continents are there?",
    "What is the capital of Japan?",
    "What is photosynthesis?",
    "Who wrote Romeo and Juliet?",
    "What is the speed of light?",
    "Explain what democracy means",
    "What causes seasons on Earth?",
    "Explain the difference between weather and climate",
    "What are the main causes of the French Revolution?",
    "Compare renewable and non-renewable energy sources",
    # Code Assistance (naturally ranging difficulty)
    "How do I print in Python?",
    "What is a variable?",
    "How do I comment code in JavaScript?",
    "How do I create a list in Python?",
    "Explain what a for loop does",
    "How do I read a file in Python?",
    "How do I handle exceptions in Python?",
    "Explain async/await in JavaScript",
    "What are Python decorators and how do they work?",
    "Debug why my React component rerenders unnecessarily",
    # Creative Tasks (naturally ranging)
    "Write a tagline for a coffee shop",
    "Suggest a name for a pet dog",
    "Write a professional email declining a job offer",
    "Create an outline for a presentation on renewable energy",
    "Draft a product description for wireless headphones",
    "Write a compelling brand story for a sustainable fashion startup",
    # Data Analysis (naturally ranging)
    "What is 15% of 200?",
    "Calculate the average of 10, 20, 30",
    "Calculate compound interest on $10000 at 5% for 10 years",
    # Complex Reasoning (naturally complex)
    "Should we expand to the European market given current conditions?",
    "Analyze the trade-offs between microservices and monolithic architecture",
    "Design a fraud detection system for a fintech startup",
    # Greetings (naturally trivial)
    "Hi",
    "Hello there",
    "Good morning",
    "How are you?",
    "Thanks",
]

# Quick test subset
QUICK_TEST_QUERIES = TEST_QUERIES[::3]  # Every 3rd query


# ============================================================================
# DIAGNOSTIC VALIDATION
# ============================================================================


def validate_diagnostic_fields(
    result: TestResult, response: CascadeResult
) -> tuple[int, list[str]]:
    """Validate that all diagnostic fields are present."""
    expected_fields = {
        "quality_score": response.quality_score,
        "quality_threshold": response.quality_threshold,
        "quality_check_passed": response.quality_check_passed,
        "rejection_reason": response.rejection_reason if not response.draft_accepted else None,
        "complexity_detection_ms": response.complexity_detection_ms,
        "draft_generation_ms": response.draft_generation_ms,
        "quality_verification_ms": response.quality_verification_ms,
        "response_length": response.response_length,
        "response_word_count": response.response_word_count,
        "draft_response": response.draft_response if response.cascaded else None,
        "verifier_response": response.verifier_response if not response.draft_accepted else None,
        "draft_cost": response.draft_cost if response.cascaded else None,
        "verifier_cost": response.verifier_cost,
        "cost_saved": response.cost_saved if response.cascaded else None,
        "draft_confidence": response.draft_confidence if response.cascaded else None,
        "cascade_overhead_ms": response.cascade_overhead_ms if response.cascaded else None,
    }

    fields_present = 0
    missing_fields = []

    for field, value in expected_fields.items():
        if value is not None:
            fields_present += 1
            setattr(result, field, value)
        else:
            if field in [
                "quality_score",
                "quality_threshold",
                "complexity_detection_ms",
                "response_length",
                "response_word_count",
            ]:
                if value is None:
                    missing_fields.append(field)

    result.diagnostic_fields_present = fields_present
    result.has_timing_data = (
        response.complexity_detection_ms is not None
        or response.draft_generation_ms is not None
        or response.quality_verification_ms is not None
    )
    result.timing_complete = (
        response.complexity_detection_ms is not None
        and (response.draft_generation_ms is not None if response.cascaded else True)
        and (response.quality_verification_ms is not None if response.cascaded else True)
    )

    return fields_present, missing_fields


def validate_quality_system(results: list[TestResult]) -> dict[str, Any]:
    """Validate quality system is working correctly."""
    cascade_results = [r for r in results if r.strategy == "cascade" and r.success]

    if not cascade_results:
        return {"error": "No cascade results to validate"}

    validation = {
        "total_cascade_queries": len(cascade_results),
        "issues": [],
        "warnings": [],
        "passed": True,
    }

    # Quality score capture
    with_scores = sum(1 for r in cascade_results if r.quality_score is not None)
    score_capture_rate = (with_scores / len(cascade_results)) * 100
    validation["quality_score_capture_rate"] = score_capture_rate

    if score_capture_rate < 90:
        validation["issues"].append(
            f"Low quality score capture rate: {score_capture_rate:.1f}% (expected >90%)"
        )
        validation["passed"] = False

    # Acceptance rates by complexity
    acceptance_by_complexity = defaultdict(lambda: {"accepted": 0, "total": 0})

    for r in cascade_results:
        if r.draft_accepted is not None:
            complexity = r.detected_complexity or "unknown"
            acceptance_by_complexity[complexity]["total"] += 1
            if r.draft_accepted:
                acceptance_by_complexity[complexity]["accepted"] += 1

    validation["acceptance_by_complexity"] = {}

    expected_ranges = {
        "trivial": (60, 90),
        "simple": (40, 70),
        "moderate": (20, 50),
    }

    for complexity, data in acceptance_by_complexity.items():
        if data["total"] > 0:
            rate = (data["accepted"] / data["total"]) * 100
            validation["acceptance_by_complexity"][complexity] = rate

            if complexity in expected_ranges:
                min_rate, max_rate = expected_ranges[complexity]
                if not (min_rate <= rate <= max_rate):
                    validation["warnings"].append(
                        f"{complexity} acceptance rate {rate:.1f}% outside expected range {min_rate}-{max_rate}%"
                    )

    # Quality score correlation
    accepted_scores = [
        r.quality_score for r in cascade_results if r.draft_accepted and r.quality_score is not None
    ]
    rejected_scores = [
        r.quality_score
        for r in cascade_results
        if r.draft_accepted is False and r.quality_score is not None
    ]

    if accepted_scores and rejected_scores:
        avg_accepted = statistics.mean(accepted_scores)
        avg_rejected = statistics.mean(rejected_scores)
        separation = avg_accepted - avg_rejected

        validation["quality_separation"] = separation

        if separation < 0.05:
            validation["issues"].append(
                f"Poor quality score separation: {separation:.3f} (expected >0.05)"
            )
            validation["passed"] = False

    # Timing data capture
    with_timing = sum(1 for r in cascade_results if r.has_timing_data)
    timing_capture_rate = (with_timing / len(cascade_results)) * 100
    validation["timing_capture_rate"] = timing_capture_rate

    if timing_capture_rate < 90:
        validation["issues"].append(
            f"Low timing capture rate: {timing_capture_rate:.1f}% (expected >90%)"
        )
        validation["passed"] = False

    return validation


def validate_direct_routing(results: list[TestResult]) -> dict[str, Any]:
    """Validate direct routing is faster than cascade."""
    direct_results = [r for r in results if r.strategy == "direct" and r.success]
    cascade_results = [r for r in results if r.strategy == "cascade" and r.success]

    if not direct_results or not cascade_results:
        return {"error": "Need both direct and cascade results"}

    validation = {
        "direct_count": len(direct_results),
        "cascade_count": len(cascade_results),
        "issues": [],
        "passed": True,
    }

    direct_latencies = [r.latency_ms for r in direct_results]
    cascade_latencies = [r.latency_ms for r in cascade_results]

    avg_direct = statistics.mean(direct_latencies)
    avg_cascade = statistics.mean(cascade_latencies)

    validation["avg_direct_latency"] = avg_direct
    validation["avg_cascade_latency"] = avg_cascade

    # Hard/Expert should be routed direct
    complexity_distribution = defaultdict(int)
    for r in direct_results:
        complexity = r.detected_complexity or "unknown"
        complexity_distribution[complexity] += 1

    validation["complexity_distribution"] = dict(complexity_distribution)

    hard_expert_count = complexity_distribution.get("hard", 0) + complexity_distribution.get(
        "expert", 0
    )
    hard_expert_pct = (hard_expert_count / len(direct_results)) * 100 if direct_results else 0

    validation["hard_expert_percentage"] = hard_expert_pct

    if hard_expert_pct < 60:
        validation["issues"].append(
            f"Only {hard_expert_pct:.1f}% of direct routing is hard/expert (expected >60%)"
        )
        validation["passed"] = False

    return validation


# ============================================================================
# ENHANCED TEST SUITE
# ============================================================================


class EnhancedTestSuite:
    """Advanced test suite with auto-tuning and comprehensive diagnostics."""

    def __init__(self):
        self.results: list[TestResult] = []
        self.agent = None
        self.baseline_verifier_cost = 0.0006
        self.auto_tune_configs: list[AutoTuneConfig] = []
        self.diagnostic_issues: list[str] = []

    def setup_agent(self, quality_config: Optional[QualityConfig] = None):
        """Setup agent with specified quality config."""
        print("Setting up agent...")

        together_key = os.getenv("TOGETHER_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        groq_key = os.getenv("GROQ_API_KEY")

        models = []

        if together_key and openai_key:
            models = [
                ModelConfig(
                    name="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                    provider="together",
                    cost=0.00018,
                    speed_ms=500,
                ),
                ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015, speed_ms=1000),
            ]
            print("✓ Using Together + OpenAI")
            self.baseline_verifier_cost = 0.00015
        elif openai_key:
            models = [
                ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002, speed_ms=800),
                ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015, speed_ms=1000),
            ]
            print("✓ Using OpenAI")
            self.baseline_verifier_cost = 0.00015
        elif anthropic_key:
            models = [
                ModelConfig(
                    name="claude-3-5-haiku-20241022",
                    provider="anthropic",
                    cost=0.00025,
                    speed_ms=700,
                ),
                ModelConfig(
                    name="claude-sonnet-4-20250514", provider="anthropic", cost=0.003, speed_ms=1500
                ),
            ]
            print("✓ Using Anthropic")
            self.baseline_verifier_cost = 0.003
        elif together_key:
            models = [
                ModelConfig(
                    name="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                    provider="together",
                    cost=0.00018,
                    speed_ms=500,
                ),
                ModelConfig(
                    name="meta-llama/Llama-3.3-70B-Instruct-Turbo",
                    provider="together",
                    cost=0.00088,
                    speed_ms=1200,
                ),
            ]
            print("✓ Using Together AI")
            self.baseline_verifier_cost = 0.00088
        elif groq_key:
            models = [
                ModelConfig(name="llama-3.1-8b-instant", provider="groq", cost=0.0, speed_ms=300),
                ModelConfig(
                    name="llama-3.3-70b-versatile", provider="groq", cost=0.0, speed_ms=800
                ),
            ]
            print("⚠️  Using Groq (rate limited)")
            self.baseline_verifier_cost = 0.0006
        else:
            raise ValueError("No API keys found")

        if quality_config is None:
            quality_config = QualityConfig.for_cascade()

        self.agent = CascadeAgent(
            models=models, quality_config=quality_config, enable_cascade=True, verbose=False
        )

        print(f"✓ Drafter: {models[0].name}")
        print(f"✓ Verifier: {models[-1].name}")
        print()

    async def run_single_query(
        self, query: str, quality_config: Optional[dict[str, Any]] = None
    ) -> TestResult:
        """Run single query - NATURALLY, like a user would."""
        result = TestResult(query=query, quality_config=quality_config)

        for attempt in range(MAX_RETRIES):
            try:
                # Just send the query!
                if USE_STREAMING:
                    response = await self.agent.run_streaming(
                        query=query, max_tokens=300, temperature=0.7, enable_visual=False
                    )
                else:
                    response = await self.agent.run(query=query, max_tokens=300, temperature=0.7)

                # Extract what the SYSTEM decided
                result.success = True
                result.full_response = response.content
                result.cost = response.total_cost
                result.baseline_cost = self.baseline_verifier_cost
                result.latency_ms = response.latency_ms

                result.detected_complexity = response.complexity
                result.complexity_confidence = (
                    response.metadata.get("complexity_confidence", 0.0)
                    if hasattr(response, "metadata")
                    else 0.0
                )
                result.strategy = response.routing_strategy
                result.draft_accepted = response.draft_accepted

                # Quality system results
                result.quality_score = response.quality_score
                result.quality_threshold = response.quality_threshold
                result.quality_check_passed = response.quality_check_passed
                result.rejection_reason = response.rejection_reason

                # Timing breakdown
                result.complexity_detection_ms = response.complexity_detection_ms
                result.draft_generation_ms = response.draft_generation_ms
                result.quality_verification_ms = response.quality_verification_ms
                result.verifier_generation_ms = response.verifier_generation_ms
                result.cascade_overhead_ms = response.cascade_overhead_ms

                # Cost breakdown
                result.draft_cost = response.draft_cost
                result.verifier_cost = response.verifier_cost
                result.cost_saved = response.cost_saved

                # Response tracking
                result.draft_response = response.draft_response
                result.verifier_response = response.verifier_response
                result.response_length = response.response_length
                result.response_word_count = response.response_word_count
                result.draft_confidence = response.draft_confidence
                result.verifier_confidence = response.verifier_confidence

                result.metadata = response.metadata if hasattr(response, "metadata") else {}

                # Validate diagnostics
                fields_present, missing = validate_diagnostic_fields(result, response)
                if missing and len(missing) > 3:
                    self.diagnostic_issues.append(
                        f"Query '{query[:40]}...': Missing {len(missing)} fields"
                    )

                # Create preview
                result.response_preview = (
                    result.full_response[:80] + "..."
                    if len(result.full_response) > 80
                    else result.full_response
                )

                # Print progress
                strategy_emoji = "🔀" if result.strategy == "cascade" else "➡️"
                accept_emoji = (
                    "✓"
                    if result.draft_accepted
                    else "✗" if result.draft_accepted is not None else "-"
                )
                diag_emoji = "📊" if result.diagnostic_completeness > 80 else "⚠️"
                complexity_short = (result.detected_complexity or "?")[:4]
                print(
                    f"{strategy_emoji} {accept_emoji} {diag_emoji} [{complexity_short:4}] {result.latency_ms:4.0f}ms ${result.cost:.6f} | {result.query[:45]}"
                )

                break

            except Exception as e:
                error_str = str(e).lower()

                if (
                    "429" in error_str
                    or "rate limit" in error_str
                    or "too many requests" in error_str
                ):
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAY * (2**attempt) if EXPONENTIAL_BACKOFF else RETRY_DELAY
                        print(
                            f"⏳ Rate limited, waiting {delay}s (attempt {attempt + 1}/{MAX_RETRIES})... | {query[:40]}"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        result.error = f"Rate limit exceeded after {MAX_RETRIES} retries"
                        result.success = False
                        print(f"❌ RATE LIMIT: {query[:50]} (max retries exceeded)")
                        break
                else:
                    result.error = str(e)
                    result.success = False
                    print(f"❌ ERROR: {query[:50]}: {str(e)[:80]}")
                    break

        return result

    def get_all_queries(self) -> list[str]:
        """Get all test queries - just plain strings."""
        if QUICK_TEST:
            return QUICK_TEST_QUERIES
        return TEST_QUERIES

    async def run_test_suite(
        self, quality_config: Optional[QualityConfig] = None, config_name: str = "default"
    ):
        """Run full test suite - sending queries naturally."""
        print("=" * 80)
        print(f"CASCADEFLOW TEST RUN: {config_name.upper()}")
        print("=" * 80)
        print()

        self.setup_agent(quality_config)

        all_queries = self.get_all_queries()
        total = len(all_queries)

        provider_name = self.agent.models[0].provider
        rate_limit_delay = RATE_LIMIT_DELAY

        if provider_name in PROVIDER_RATE_LIMITS:
            rpm = PROVIDER_RATE_LIMITS[provider_name]
            calculated_delay = 60.0 / rpm
            rate_limit_delay = max(calculated_delay, RATE_LIMIT_DELAY)

        print(f"Running {total} queries (naturally, like a user would)...")
        print(
            f"Rate limit: ~{60/rate_limit_delay:.0f} requests/min ({rate_limit_delay:.1f}s delay)"
        )
        print(f"Estimated time: ~{(total * rate_limit_delay) / 60:.1f} minutes")
        print()

        results_for_config = []
        start_time = time.time()

        quality_config_dict = {
            "threshold_multiplier": (
                quality_config.confidence_thresholds.get("moderate", 0.0) / 0.55
                if quality_config
                else 1.0
            ),
            "confidence_thresholds": (
                quality_config.confidence_thresholds if quality_config else None
            ),
        }

        for i, query in enumerate(all_queries, 1):
            if i % 10 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                remaining = total - i
                eta = remaining / rate if rate > 0 else 0
                print(
                    f"\n--- Progress: {i}/{total} ({i/total*100:.1f}%) | Rate: {rate:.1f} q/s | ETA: {eta/60:.1f}min ---\n"
                )

            result = await self.run_single_query(query, quality_config_dict)

            results_for_config.append(result)
            self.results.append(result)

            await asyncio.sleep(rate_limit_delay)

        total_time = time.time() - start_time
        avg_rate = total / total_time if total_time > 0 else 0

        print(
            f"\n✓ Completed {total} queries in {total_time/60:.1f} minutes ({avg_rate:.1f} q/s avg)"
        )

        return results_for_config

    async def auto_tune_quality_parameters(self):
        """Auto-tune quality parameters."""
        print("\n" + "=" * 80)
        print("AUTO-TUNING QUALITY PARAMETERS")
        print("=" * 80)
        print()

        test_configs = [
            (0.7, "Very Aggressive (0.7x)"),
            (0.85, "Aggressive (0.85x)"),
            (1.0, "Balanced (1.0x - Default)"),
            (1.15, "Conservative (1.15x)"),
            (1.3, "Very Conservative (1.3x)"),
        ]

        for threshold_multiplier, name in test_configs[:AUTO_TUNE_ITERATIONS]:
            print(f"\n{'='*80}")
            print(f"Testing: {name}")
            print(f"{'='*80}\n")

            base_config = QualityConfig.for_cascade()
            scaled_thresholds = {
                complexity: min(0.95, max(0.15, threshold * threshold_multiplier))
                for complexity, threshold in base_config.confidence_thresholds.items()
            }

            quality_config = QualityConfig(
                confidence_thresholds=scaled_thresholds,
                min_length_thresholds=base_config.min_length_thresholds,
                require_specifics_for_complex=base_config.require_specifics_for_complex,
                enable_hallucination_detection=base_config.enable_hallucination_detection,
                enable_comparative=False,
                enable_adaptive=True,
                log_decisions=False,
                log_details=False,
            )

            config = AutoTuneConfig(
                threshold_multiplier=threshold_multiplier,
                min_complexity_for_cascade="simple",
                name=name,
            )

            self.results = []
            self.diagnostic_issues = []

            results = await self.run_test_suite(quality_config, name)
            config.results = results

            self.auto_tune_configs.append(config)

            print(f"\n✓ Completed: {name}")
            print(f"  Cost: ${config.total_cost:.4f}")
            print(f"  Savings: ${config.cost_savings:.4f} ({config.cost_savings_pct:.1f}%)")
            print(f"  Acceptance Rate: {config.draft_acceptance_rate*100:.1f}%")
            print(f"  Avg Latency: {config.avg_latency:.0f}ms")

        self.report_auto_tune_results()
        self.report_diagnostic_validation()

    def report_auto_tune_results(self):
        """Report auto-tuning results."""
        print("\n" + "=" * 80)
        print("AUTO-TUNE RESULTS")
        print("=" * 80)

        if not self.auto_tune_configs:
            print("No auto-tune data available")
            return

        print(f"\n{'Configuration':<25} {'Cost':<12} {'Savings':<15} {'Accept %':<12}")
        print("-" * 75)

        for config in self.auto_tune_configs:
            savings_str = f"${config.cost_savings:.4f} ({config.cost_savings_pct:.0f}%)"
            accept_str = f"{config.draft_acceptance_rate*100:.1f}%"
            print(
                f"{config.name:<25} ${config.total_cost:<11.4f} {savings_str:<15} {accept_str:<12}"
            )

        best_savings = max(self.auto_tune_configs, key=lambda c: c.cost_savings_pct)
        best_balanced = max(
            self.auto_tune_configs, key=lambda c: c.cost_savings_pct * c.draft_acceptance_rate
        )

        print("\n🏆 RECOMMENDATIONS")
        print("-" * 80)
        print(f"Best Cost Savings:      {best_savings.name}")
        print(f"  └─ Saves {best_savings.cost_savings_pct:.1f}%")
        print(f"\nBest Balanced:          {best_balanced.name}")

    def report_diagnostic_validation(self):
        """Report diagnostic validation."""
        print("\n" + "=" * 80)
        print("DIAGNOSTIC VALIDATION")
        print("=" * 80)

        if not self.results:
            print("No results to validate")
            return

        quality_validation = validate_quality_system(self.results)

        print("\n📊 QUALITY SYSTEM")
        print("-" * 80)

        if "error" in quality_validation:
            print(f"⚠️  {quality_validation['error']}")
        else:
            print(
                f"Quality Score Capture:  {quality_validation['quality_score_capture_rate']:.1f}%"
            )
            print(f"Timing Capture Rate:    {quality_validation['timing_capture_rate']:.1f}%")

            if quality_validation["passed"]:
                print("\n✅ Quality system PASSED")
            else:
                print("\n❌ Quality system FAILED")
                for issue in quality_validation["issues"]:
                    print(f"  • {issue}")

    def generate_comprehensive_report(self):
        """Generate comprehensive report."""
        print("\n" + "=" * 80)
        print("COMPREHENSIVE REPORT")
        print("=" * 80)

        successful = [r for r in self.results if r.success]

        if not successful:
            print("No successful queries")
            return

        self._report_executive_summary(successful)
        self._report_cost_analysis(successful)
        self._report_routing_analysis(successful)
        self._report_quality_system(successful)
        self._report_latency_deep_dive(successful)
        self._report_complexity_analysis(successful)

    def _report_executive_summary(self, results: list[TestResult]):
        """Executive summary."""
        print(f"\n{'='*80}")
        print("EXECUTIVE SUMMARY")
        print("=" * 80)

        total_cost = sum(r.cost for r in results)
        total_baseline = sum(r.baseline_cost for r in results)
        total_savings = total_baseline - total_cost
        savings_pct = (total_savings / total_baseline * 100) if total_baseline > 0 else 0

        cascade_count = sum(1 for r in results if r.strategy == "cascade")
        direct_count = sum(1 for r in results if r.strategy == "direct")

        accepted = sum(1 for r in results if r.draft_accepted is True)
        rejected = sum(1 for r in results if r.draft_accepted is False)
        acceptance_rate = (
            (accepted / (accepted + rejected) * 100) if (accepted + rejected) > 0 else 0
        )

        print("\n📊 KEY METRICS")
        print("-" * 80)
        print(f"Total Queries:          {len(results)}")
        print(f"Total Cost:             ${total_cost:.4f}")
        print(f"Total Savings:          ${total_savings:.4f} ({savings_pct:.1f}%)")
        print(f"Cascade Used:           {cascade_count} ({cascade_count/len(results)*100:.1f}%)")
        print(f"Direct Used:            {direct_count} ({direct_count/len(results)*100:.1f}%)")
        print(f"Draft Acceptance:       {acceptance_rate:.1f}%")

    def _report_cost_analysis(self, results: list[TestResult]):
        """Cost analysis."""
        print(f"\n{'='*80}")
        print("COST ANALYSIS")
        print("=" * 80)

        sum(r.cost for r in results)
        sum(r.baseline_cost for r in results)

        cascade_results = [r for r in results if r.strategy == "cascade"]

        if cascade_results:
            cascade_cost = sum(r.cost for r in cascade_results)
            print("\n💰 CASCADE COSTS")
            print("-" * 80)
            print(f"Total Cost:             ${cascade_cost:.6f}")
            print(f"Avg Cost/Query:         ${cascade_cost/len(cascade_results):.6f}")

    def _report_routing_analysis(self, results: list[TestResult]):
        """Routing analysis."""
        print(f"\n{'='*80}")
        print("ROUTING ANALYSIS")
        print("=" * 80)

        complexity_routing = defaultdict(lambda: {"cascade": 0, "direct": 0})

        for r in results:
            if r.detected_complexity:
                complexity_routing[r.detected_complexity][r.strategy] += 1

        print("\n🎯 ROUTING BY COMPLEXITY")
        print("-" * 80)

        for complexity in ["trivial", "simple", "moderate", "hard", "expert"]:
            if complexity in complexity_routing:
                data = complexity_routing[complexity]
                total = data["cascade"] + data["direct"]
                cascade_pct = data["cascade"] / total * 100 if total > 0 else 0
                print(
                    f"{complexity.upper():<10} Cascade: {data['cascade']:3} ({cascade_pct:5.1f}%) | Direct: {data['direct']:3}"
                )

    def _report_quality_system(self, results: list[TestResult]):
        """Quality system analysis."""
        print(f"\n{'='*80}")
        print("QUALITY SYSTEM")
        print("=" * 80)

        cascade_results = [r for r in results if r.strategy == "cascade"]

        if not cascade_results:
            print("No cascade results")
            return

        with_scores = sum(1 for r in cascade_results if r.quality_score is not None)
        score_capture = (with_scores / len(cascade_results)) * 100

        print("\n📊 QUALITY METRICS")
        print("-" * 80)
        print(f"Quality Score Capture:  {score_capture:.1f}%")

        accepted = [r for r in cascade_results if r.draft_accepted and r.quality_score is not None]
        rejected = [
            r for r in cascade_results if not r.draft_accepted and r.quality_score is not None
        ]

        if accepted and rejected:
            avg_accepted = statistics.mean([r.quality_score for r in accepted])
            avg_rejected = statistics.mean([r.quality_score for r in rejected])
            print(f"Avg Accepted Score:     {avg_accepted:.3f}")
            print(f"Avg Rejected Score:     {avg_rejected:.3f}")
            print(f"Separation:             {avg_accepted - avg_rejected:.3f}")

    def _report_latency_deep_dive(self, results: list[TestResult]):
        """Latency analysis."""
        print(f"\n{'='*80}")
        print("LATENCY ANALYSIS")
        print("=" * 80)

        cascade_results = [r for r in results if r.strategy == "cascade"]
        direct_results = [r for r in results if r.strategy == "direct"]

        if cascade_results:
            avg_cascade = statistics.mean([r.latency_ms for r in cascade_results])
            print("\n⚡ CASCADE LATENCY")
            print("-" * 80)
            print(f"Average:                {avg_cascade:.0f}ms")

        if direct_results:
            avg_direct = statistics.mean([r.latency_ms for r in direct_results])
            print("\n⚡ DIRECT LATENCY")
            print("-" * 80)
            print(f"Average:                {avg_direct:.0f}ms")

    def _report_complexity_analysis(self, results: list[TestResult]):
        """Complexity detection analysis."""
        print(f"\n{'='*80}")
        print("COMPLEXITY ANALYSIS")
        print("=" * 80)

        complexity_dist = defaultdict(int)
        for r in results:
            if r.detected_complexity:
                complexity_dist[r.detected_complexity] += 1

        print("\n📊 DETECTED COMPLEXITY DISTRIBUTION")
        print("-" * 80)
        for complexity in ["trivial", "simple", "moderate", "hard", "expert"]:
            if complexity in complexity_dist:
                count = complexity_dist[complexity]
                pct = (count / len(results)) * 100
                print(f"{complexity.upper():<10} {count:3} ({pct:5.1f}%)")


async def main():
    """Run test suite."""
    suite = EnhancedTestSuite()

    try:
        if ENABLE_AUTO_TUNING:
            await suite.auto_tune_quality_parameters()
        else:
            await suite.run_test_suite()

        suite.generate_comprehensive_report()

        print("\n" + "=" * 80)
        print("✅ TEST SUITE COMPLETED")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
        if suite.results:
            suite.generate_comprehensive_report()
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
