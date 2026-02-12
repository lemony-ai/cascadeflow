"""Base benchmark framework for CascadeFlow evaluations."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from cascadeflow.integrations.litellm import LiteLLMCostProvider
from cascadeflow.utils import estimate_tokens


@dataclass
class BenchmarkResult:
    """Single benchmark test result."""

    # Test identification
    dataset_name: str
    test_id: str
    query: str

    # Cascade decision
    model_used: str  # "drafter" or "verifier"
    accepted: bool  # True if drafter accepted
    quality_score: float  # 0-1 quality score from verifier

    # Cost metrics (in USD)
    drafter_cost: float
    verifier_cost: float  # 0 if drafter accepted
    total_cost: float
    baseline_cost: float  # Cost if always used powerful model

    # Performance metrics
    latency_ms: float
    tokens_input: int
    tokens_output: int

    # Quality metrics (dataset-specific)
    ground_truth: Any
    prediction: Any
    is_correct: bool

    # Metadata
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None

    @property
    def escalated(self) -> bool:
        """True if query was escalated to verifier."""
        return not self.accepted

    @property
    def cost_savings(self) -> float:
        """Savings compared to baseline (USD)."""
        return self.baseline_cost - self.total_cost

    @property
    def cost_savings_pct(self) -> float:
        """Savings percentage compared to baseline."""
        if self.baseline_cost == 0:
            return 0.0
        return (self.cost_savings / self.baseline_cost) * 100

    @property
    def effective_total_cost(self) -> float:
        """
        Quality-adjusted cost.

        If the cascade answer is incorrect, assume you still need to pay the baseline
        (verifier-only) to recover a correct answer.
        """
        return self.total_cost if self.is_correct else (self.total_cost + self.baseline_cost)

    @property
    def effective_savings_pct(self) -> float:
        """
        Quality-adjusted savings percentage.

        This is intentionally harsh: incorrect answers count as requiring a baseline rerun,
        so "savings" will typically go negative.
        """
        if self.baseline_cost == 0:
            return 0.0
        return ((self.baseline_cost - self.effective_total_cost) / self.baseline_cost) * 100


@dataclass
class BenchmarkSummary:
    """Aggregate benchmark results."""

    # Test identification
    dataset_name: str
    total_tests: int
    successful_tests: int
    failed_tests: int

    # Cascade metrics
    drafter_accepted: int
    escalated_to_verifier: int
    acceptance_rate_pct: float
    escalation_rate_pct: float

    # Cost metrics
    total_cost: float
    effective_total_cost: float
    total_baseline_cost: float
    total_savings: float
    avg_savings_pct: float
    effective_avg_savings_pct: float
    avg_cost_per_query: float

    # Performance metrics
    avg_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float

    # Quality metrics
    accuracy: float  # Percentage of correct predictions
    drafter_accuracy: float  # Accuracy when drafter was used
    verifier_accuracy: float  # Accuracy when verifier was used

    # Token usage
    total_input_tokens: int
    total_output_tokens: int
    avg_input_tokens: float
    avg_output_tokens: float


class Benchmark(ABC):
    """Base class for all benchmarks."""

    def __init__(
        self,
        name: Optional[str] = None,
        *,
        drafter_model: str,
        verifier_model: str,
        quality_threshold: float = 0.7,
        max_samples: Optional[int] = None,
        dataset_name: Optional[str] = None,
        baseline_model: Optional[str] = None,
    ):
        """
        Initialize benchmark.

        Args:
            name: Benchmark name (e.g., "HumanEval", "Banking77")
            dataset_name: Optional dataset display name (aliases name)
            drafter_model: Name of drafter model (e.g., "gpt-4o-mini")
            verifier_model: Name of verifier model (e.g., "gpt-4o")
            baseline_model: Optional baseline model name (defaults to verifier)
            quality_threshold: Quality threshold for accepting drafter (0-1)
            max_samples: Maximum number of samples to test (None = all)
        """
        if dataset_name is None and name is None:
            raise ValueError("Benchmark requires name or dataset_name")

        resolved_name = dataset_name or name
        self.name = resolved_name
        self.dataset_name = resolved_name
        self.drafter_model = drafter_model
        self.verifier_model = verifier_model
        self.baseline_model = baseline_model or verifier_model
        self.quality_threshold = quality_threshold
        self.max_samples = max_samples

        self.results: list[BenchmarkResult] = []

    @abstractmethod
    def load_dataset(self) -> list[tuple[str, Any]]:
        """
        Load benchmark dataset.

        Returns:
            List of (query, ground_truth) tuples
        """
        pass

    @abstractmethod
    def evaluate_prediction(self, prediction: str, ground_truth: Any) -> tuple[bool, float]:
        """
        Evaluate if prediction matches ground truth.

        Args:
            prediction: Model's prediction
            ground_truth: Ground truth answer

        Returns:
            (is_correct, confidence_score) tuple
        """
        pass

    @abstractmethod
    async def run_cascade(self, query: str) -> dict[str, Any]:
        """
        Run cascade on a single query.

        Args:
            query: Input query

        Returns:
            Dict containing:
                - prediction: Model's prediction
                - model_used: "drafter" or "verifier"
                - accepted: True if drafter accepted
                - quality_score: 0-1 quality score
                - drafter_cost: Cost in USD
                - verifier_cost: Cost in USD
                - total_cost: Total cost in USD
                - latency_ms: Latency in milliseconds
                - tokens_input: Input tokens
                - tokens_output: Output tokens
        """
        pass

    def get_baseline_cost(self, query: str, prediction: Optional[str] = None) -> float:
        """
        Calculate cost if always using powerful model.

        Override if needed for specific pricing.

        Args:
            query: Input query

        Returns:
            Estimated cost in USD
        """
        input_tokens = estimate_tokens(str(query))
        output_tokens = estimate_tokens(str(prediction)) if prediction else 500

        try:
            provider = LiteLLMCostProvider()
            return provider.calculate_cost(
                model=self.baseline_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception:
            # Default: Estimate ~500 tokens input + 500 tokens output using GPT-4o pricing
            input_tokens = 500
            output_tokens = 500
            input_cost = (input_tokens / 1_000_000) * 2.50
            output_cost = (output_tokens / 1_000_000) * 10.00
            return input_cost + output_cost

    def _calculate_baseline_cost_from_tokens(
        self, input_tokens: int, output_tokens: int, query: str, prediction: Any
    ) -> float:
        try:
            provider = LiteLLMCostProvider()
            return provider.calculate_cost(
                model=self.baseline_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception:
            return self.get_baseline_cost(query, str(prediction))

    async def run(self) -> BenchmarkSummary:
        """
        Run complete benchmark.

        Returns:
            BenchmarkSummary with aggregate results
        """
        print(f"\n{'='*80}")
        print(f"Running {self.name} Benchmark")
        print(f"{'='*80}")
        print(f"Drafter:  {self.drafter_model}")
        print(f"Verifier: {self.verifier_model}")
        print(f"Quality Threshold: {self.quality_threshold}")
        print(f"{'='*80}\n")

        # Load dataset
        dataset = self.load_dataset()
        if self.max_samples:
            dataset = dataset[: self.max_samples]

        print(f"Loaded {len(dataset)} test cases\n")

        # Run tests
        for idx, (query, ground_truth) in enumerate(dataset, 1):
            print(f"Test {idx}/{len(dataset)}: ", end="", flush=True)

            try:
                # Run cascade
                cascade_result = await self.run_cascade(query)

                # Evaluate prediction
                is_correct, confidence = self.evaluate_prediction(
                    cascade_result["prediction"], ground_truth
                )

                tokens_input = cascade_result["tokens_input"]
                tokens_output = cascade_result["tokens_output"]
                if tokens_input == 0:
                    tokens_input = estimate_tokens(str(query))
                if tokens_output == 0:
                    tokens_output = estimate_tokens(str(cascade_result["prediction"]))

                baseline_cost = float(cascade_result.get("baseline_cost") or 0.0)
                if baseline_cost <= 0:
                    # Prefer cascadeflow's own cost semantics if exposed by the benchmark runner.
                    cost_saved = cascade_result.get("cost_saved")
                    if cost_saved is not None:
                        try:
                            baseline_cost = float(cascade_result["total_cost"]) + float(cost_saved)
                        except Exception:
                            baseline_cost = 0.0

                if baseline_cost <= 0:
                    baseline_cost = self._calculate_baseline_cost_from_tokens(
                        tokens_input,
                        tokens_output,
                        query,
                        cascade_result["prediction"],
                    )

                # Create result
                result = BenchmarkResult(
                    dataset_name=self.name,
                    test_id=f"test_{idx}",
                    query=query,
                    model_used=cascade_result["model_used"],
                    accepted=cascade_result["accepted"],
                    quality_score=cascade_result["quality_score"],
                    drafter_cost=cascade_result["drafter_cost"],
                    verifier_cost=cascade_result["verifier_cost"],
                    total_cost=cascade_result["total_cost"],
                    baseline_cost=baseline_cost,
                    latency_ms=cascade_result["latency_ms"],
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    ground_truth=ground_truth,
                    prediction=cascade_result["prediction"],
                    is_correct=is_correct,
                )

                self.results.append(result)

                # Optional per-benchmark hook for additional diagnostics.
                # Kept out of BenchmarkResult to avoid bloating default reports.
                self.on_result(result=result, cascade_result=cascade_result, ground_truth=ground_truth)

                status = "✅ PASS" if is_correct else "❌ FAIL"
                model = "D" if cascade_result["accepted"] else "V"
                # Never claim savings on incorrect results.
                savings = result.cost_savings_pct if is_correct else 0.0
                # Savings can be negative for escalated cases (draft + verifier) vs baseline (verifier only).
                # Display negative values as "overhead" to avoid confusion during benchmark review.
                savings_label = (
                    f"{savings:.1f}% savings" if savings >= 0 else f"{abs(savings):.1f}% overhead"
                )
                print(f"{status} [{model}] (${result.total_cost:.6f}, {savings_label})")

            except Exception as e:
                print(f"❌ ERROR: {e}")
                # Still record error result
                result = BenchmarkResult(
                    dataset_name=self.name,
                    test_id=f"test_{idx}",
                    query=query,
                    model_used="error",
                    accepted=False,
                    quality_score=0.0,
                    drafter_cost=0.0,
                    verifier_cost=0.0,
                    total_cost=0.0,
                    baseline_cost=0.0,
                    latency_ms=0.0,
                    tokens_input=0,
                    tokens_output=0,
                    ground_truth=ground_truth,
                    prediction="",
                    is_correct=False,
                    error=str(e),
                )
                self.results.append(result)

        # Generate summary
        summary = self._generate_summary()
        self._print_summary(summary)

        return summary

    def on_result(
        self,
        *,
        result: BenchmarkResult,
        cascade_result: dict[str, Any],
        ground_truth: Any,
    ) -> None:
        """Optional hook for benchmark-specific diagnostics (default: no-op)."""
        return

    def _generate_summary(self) -> BenchmarkSummary:
        """Generate aggregate summary from results."""
        total = len(self.results)
        failed = sum(1 for r in self.results if r.error is not None)
        successful = total - failed

        # Filter out failed results for metrics
        valid_results = [r for r in self.results if r.error is None]

        if not valid_results:
            # Return empty summary if no valid results
            return BenchmarkSummary(
                dataset_name=self.name,
                total_tests=total,
                successful_tests=0,
                failed_tests=failed,
                drafter_accepted=0,
                escalated_to_verifier=0,
                acceptance_rate_pct=0.0,
                escalation_rate_pct=0.0,
                total_cost=0.0,
                effective_total_cost=0.0,
                total_baseline_cost=0.0,
                total_savings=0.0,
                avg_savings_pct=0.0,
                effective_avg_savings_pct=0.0,
                avg_cost_per_query=0.0,
                avg_latency_ms=0.0,
                median_latency_ms=0.0,
                p95_latency_ms=0.0,
                accuracy=0.0,
                drafter_accuracy=0.0,
                verifier_accuracy=0.0,
                total_input_tokens=0,
                total_output_tokens=0,
                avg_input_tokens=0.0,
                avg_output_tokens=0.0,
            )

        # Re-estimate baseline cost using typical verifier output length.
        verifier_outputs = sorted(
            r.tokens_output for r in valid_results if r.escalated and r.tokens_output > 0
        )
        if verifier_outputs:
            baseline_output_floor = verifier_outputs[len(verifier_outputs) // 2]
            for result in valid_results:
                if not result.accepted:
                    continue
                estimated_output = max(result.tokens_output, baseline_output_floor)
                baseline_cost = self._calculate_baseline_cost_from_tokens(
                    result.tokens_input,
                    estimated_output,
                    result.query,
                    result.prediction,
                )
                result.baseline_cost = max(result.baseline_cost, baseline_cost)

        # Cascade metrics
        drafter_accepted = sum(1 for r in valid_results if r.accepted)
        escalated = sum(1 for r in valid_results if r.escalated)

        # Cost metrics
        total_cost = sum(r.total_cost for r in valid_results)
        effective_total_cost = sum(r.effective_total_cost for r in valid_results)
        total_baseline = sum(r.baseline_cost for r in valid_results)
        total_savings = total_baseline - total_cost
        avg_savings_pct = (total_savings / total_baseline * 100) if total_baseline > 0 else 0.0
        effective_avg_savings_pct = (
            ((total_baseline - effective_total_cost) / total_baseline) * 100
            if total_baseline > 0
            else 0.0
        )

        # Latency metrics
        latencies = sorted([r.latency_ms for r in valid_results])
        avg_latency = sum(latencies) / len(latencies)
        median_latency = latencies[len(latencies) // 2]
        p95_idx = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_idx]

        # Quality metrics
        correct = sum(1 for r in valid_results if r.is_correct)
        accuracy = (correct / len(valid_results) * 100) if valid_results else 0.0

        drafter_results = [r for r in valid_results if r.accepted]
        drafter_correct = sum(1 for r in drafter_results if r.is_correct)
        drafter_accuracy = (
            (drafter_correct / len(drafter_results) * 100) if drafter_results else 0.0
        )

        verifier_results = [r for r in valid_results if r.escalated]
        verifier_correct = sum(1 for r in verifier_results if r.is_correct)
        verifier_accuracy = (
            (verifier_correct / len(verifier_results) * 100) if verifier_results else 0.0
        )

        # Token usage
        total_input = sum(r.tokens_input for r in valid_results)
        total_output = sum(r.tokens_output for r in valid_results)

        return BenchmarkSummary(
            dataset_name=self.name,
            total_tests=total,
            successful_tests=successful,
            failed_tests=failed,
            drafter_accepted=drafter_accepted,
            escalated_to_verifier=escalated,
            acceptance_rate_pct=(drafter_accepted / successful * 100) if successful > 0 else 0.0,
            escalation_rate_pct=(escalated / successful * 100) if successful > 0 else 0.0,
            total_cost=total_cost,
            effective_total_cost=effective_total_cost,
            total_baseline_cost=total_baseline,
            total_savings=total_savings,
            avg_savings_pct=avg_savings_pct,
            effective_avg_savings_pct=effective_avg_savings_pct,
            avg_cost_per_query=total_cost / successful if successful > 0 else 0.0,
            avg_latency_ms=avg_latency,
            median_latency_ms=median_latency,
            p95_latency_ms=p95_latency,
            accuracy=accuracy,
            drafter_accuracy=drafter_accuracy,
            verifier_accuracy=verifier_accuracy,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            avg_input_tokens=total_input / successful if successful > 0 else 0.0,
            avg_output_tokens=total_output / successful if successful > 0 else 0.0,
        )

    def _print_summary(self, summary: BenchmarkSummary) -> None:
        """Print formatted summary to console."""
        print(f"\n{'='*80}")
        print(f"{self.name} Benchmark Results")
        print(f"{'='*80}\n")

        print("TEST EXECUTION:")
        print(f"  Total Tests:         {summary.total_tests}")
        print(f"  Successful:          {summary.successful_tests}")
        print(f"  Failed:              {summary.failed_tests}")

        print("\nCASCADE PERFORMANCE:")
        print(
            f"  Drafter Accepted:    {summary.drafter_accepted} ({summary.acceptance_rate_pct:.1f}%)"
        )
        print(
            f"  Escalated:           {summary.escalated_to_verifier} ({summary.escalation_rate_pct:.1f}%)"
        )

        print("\nCOST ANALYSIS:")
        print(f"  Total Cost:          ${summary.total_cost:.6f}")
        print(f"  Effective Total:     ${summary.effective_total_cost:.6f}")
        print(f"  Baseline Cost:       ${summary.total_baseline_cost:.6f}")
        print(f"  Total Savings:       ${summary.total_savings:.6f}")
        print(f"  Average Savings:     {summary.avg_savings_pct:.1f}%")
        print(f"  Effective Savings:   {summary.effective_avg_savings_pct:.1f}%")
        print(f"  Avg Cost/Query:      ${summary.avg_cost_per_query:.6f}")

        print("\nPERFORMANCE:")
        print(f"  Avg Latency:         {summary.avg_latency_ms:.0f}ms")
        print(f"  Median Latency:      {summary.median_latency_ms:.0f}ms")
        print(f"  P95 Latency:         {summary.p95_latency_ms:.0f}ms")

        print("\nQUALITY:")
        print(f"  Overall Accuracy:    {summary.accuracy:.1f}%")
        print(f"  Drafter Accuracy:    {summary.drafter_accuracy:.1f}%")
        print(f"  Verifier Accuracy:   {summary.verifier_accuracy:.1f}%")

        print("\nTOKEN USAGE:")
        print(f"  Total Input:         {summary.total_input_tokens:,}")
        print(f"  Total Output:        {summary.total_output_tokens:,}")
        print(f"  Avg Input/Query:     {summary.avg_input_tokens:.0f}")
        print(f"  Avg Output/Query:    {summary.avg_output_tokens:.0f}")

        print(f"\n{'='*80}\n")
