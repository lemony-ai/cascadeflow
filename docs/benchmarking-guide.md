# CascadeFlow Benchmarking Guide

Comprehensive guide to using and creating benchmarks for CascadeFlow cascade systems.

## Table of Contents

1. [Overview](#overview)
2. [Available Benchmarks](#available-benchmarks)
3. [Running Benchmarks](#running-benchmarks)
4. [Understanding Results](#understanding-results)
5. [Creating Custom Benchmarks](#creating-custom-benchmarks)
6. [Best Practices](#best-practices)

## Overview

CascadeFlow includes a comprehensive benchmarking suite to evaluate cascade system performance across multiple dimensions:

- **Code Generation** (HumanEval)
- **Math Reasoning** (GSM8K)
- **Multi-Turn Conversations** (MT-Bench)
- **Factual Accuracy** (TruthfulQA)
- **Customer Support** (Real-world ROI)
- **Provider Comparison** (OpenAI vs Anthropic)

### Why Benchmark?

Benchmarks help you:

1. **Validate Quality**: Ensure cascade maintains accuracy
2. **Measure Cost Savings**: Quantify actual ROI
3. **Tune Thresholds**: Find optimal quality thresholds
4. **Compare Providers**: Understand provider-specific behavior
5. **Track Performance**: Monitor improvements over time

## Available Benchmarks

### 1. HumanEval: Code Generation

**Purpose**: Tests code generation capabilities

**Dataset**: 10 programming problems from HumanEval

**Metrics**:
- Code correctness (passes unit tests)
- Acceptance rate (drafter usage)
- Cost reduction vs always using powerful model

**Usage**:
```bash
cd tests/benchmarks
python -m benchmarks.humaneval
```

**Expected Results**:
- Accuracy: 70-85%
- Acceptance Rate: 50-70%
- Cost Reduction: 40-60%

### 2. GSM8K: Math Reasoning

**Purpose**: Evaluates multi-step mathematical reasoning

**Dataset**: 10 grade school math word problems

**Metrics**:
- Answer correctness (numerical accuracy)
- Drafter accuracy on accepted problems
- Cost savings on math tasks

**Usage**:
```bash
python -m benchmarks.gsm8k
```

**Expected Results**:
- Accuracy: 75-90%
- Acceptance Rate: 40-60%
- Cost Reduction: 35-55%

### 3. MT-Bench: Multi-Turn Conversations

**Purpose**: Tests context retention and dialogue coherence

**Dataset**: 10 multi-turn conversations across 8 categories

**Categories**: Writing, Roleplay, Reasoning, Math, Coding, Extraction, STEM, Humanities

**Metrics**:
- All-turns-pass rate (conversation success)
- Per-turn quality scores
- Context retention across turns

**Usage**:
```bash
python -m benchmarks.mtbench
```

**Expected Results**:
- Accuracy: 70-80% (all turns pass)
- Acceptance Rate: 50-70%
- Cost Reduction: 40-60%

### 4. TruthfulQA: Factual Accuracy

**Purpose**: Evaluates truthfulness and avoids misinformation

**Dataset**: 15 questions across 10 categories (misconceptions, science, history, health, etc.)

**Metrics**:
- Truthful answer rate
- Misinformation detection
- Verifier escalation effectiveness

**Usage**:
```bash
python -m benchmarks.truthfulqa
```

**Expected Results**:
- Accuracy: 70-85% truthful
- Acceptance Rate: 55-70%
- Cost Reduction: 40-60%

### 5. Customer Support: Real-World ROI

**Purpose**: Demonstrates practical business value

**Dataset**: 20 realistic support scenarios

**Distribution**:
- 60% Simple FAQs
- 20% Moderate complexity
- 20% Complex escalations

**Metrics**:
- Response helpfulness
- Professional tone
- Monthly/annual ROI projections

**Usage**:
```bash
python -m benchmarks.customer_support
```

**Expected Results**:
- Accuracy: 85%+ helpful
- Acceptance Rate: 60-70%
- Annual Savings: $5K-$15K (at 10K queries/month)

### 6. Provider Comparison

**Purpose**: Compares quality scoring across providers

**Tests**: OpenAI vs Anthropic verifiers with same drafter

**Metrics**:
- Quality score agreement
- Latency differences
- Cost differences
- Optimal thresholds per provider

**Usage**:
```bash
python -m benchmarks.provider_comparison
```

**Key Findings**:
- Agreement rate: 70-85%
- Score variance: ±0.1-0.15
- Provider-specific thresholds may be needed

## Running Benchmarks

### Single Benchmark

Run individual benchmarks:

```bash
cd tests/benchmarks

# HumanEval
python -m benchmarks.humaneval

# GSM8K
python -m benchmarks.gsm8k

# MT-Bench
python -m benchmarks.mtbench

# TruthfulQA
python -m benchmarks.truthfulqa

# Customer Support
python -m benchmarks.customer_support

# Provider Comparison
python -m benchmarks.provider_comparison
```

### All Benchmarks

Run the complete suite:

```bash
python -m benchmarks.run_all --output-dir results --format md,json,csv
```

**Output**:
- `results/comparison.md` - Comparison table
- `results/results.json` - Raw data
- `results/*.csv` - Per-benchmark CSVs (if implemented)

### With Custom Configuration

```python
from benchmarks.humaneval import HumanEvalBenchmark

benchmark = HumanEvalBenchmark(
    drafter_model="gpt-4o-mini",
    verifier_model="gpt-4o",
    quality_threshold=0.75,  # Custom threshold
    max_samples=20,           # More samples
)

summary = await benchmark.run()
```

## Understanding Results

### Key Metrics

#### Accuracy
Percentage of correct/helpful responses
- **High (>85%)**: Production-ready quality
- **Medium (70-85%)**: Consider raising threshold
- **Low (<70%)**: Quality issues, investigate further

#### Acceptance Rate
Percentage of queries handled by drafter
- **High (>70%)**: Excellent cost savings
- **Medium (50-70%)**: Good balance
- **Low (<50%)**: Threshold may be too strict

#### Cost Reduction
Percentage savings vs always using verifier
- **Calculation**: `(baseline_cost - cascade_cost) / baseline_cost * 100`
- **Target**: 40-65% for most use cases

#### Drafter Accuracy
Accuracy when drafter is accepted
- **High (>80%)**: Drafter reliable on simple tasks
- **Low (<70%)**: Quality threshold may be too lenient

### Sample Output

```
==================== CUSTOMER SUPPORT BENCHMARK RESULTS ====================

Total Queries:       20
Helpful Responses:   17 (85.0%)
Drafter Accepted:    12 (60.0%)
Verifier Escalated:  8 (40.0%)

Cost Analysis:
  Cascade Total Cost:  $0.003450
  Baseline Total Cost: $0.008900
  Cost Savings:        $0.005450 (61.2%)

  💰 Projected ROI (10K queries/month):
     Monthly Savings:  $272.50
     Annual Savings:   $3,270.00

Performance:
  Average Latency:     1250ms
  Average Quality:     0.823
  Drafter Accuracy:    91.7% (when accepted)

Key Findings:
  ✅ Drafter handles 60% of queries (meets 60% target)
  ✅ High response quality: 85% helpful
  💰 Significant cost savings: 61% reduction
  ✅ Drafter maintains quality: 92% accurate on simple queries

📊 Business Impact:
  - Cascade pattern saves $3,270/year at 10K queries/month
  - Drafter handles 60% of queries at 10x lower cost
  - Verifier escalation ensures complex queries get premium responses
  - ✅ Ready for production deployment in customer support use cases
```

### Interpreting Trade-offs

#### High Accuracy, Low Acceptance
- Quality threshold too strict
- Missing cost savings opportunity
- **Action**: Lower threshold slightly (e.g., 0.7 → 0.65)

#### High Acceptance, Low Accuracy
- Quality threshold too lenient
- Drafter producing low-quality responses
- **Action**: Raise threshold (e.g., 0.7 → 0.75)

#### Optimal Balance
- Accuracy: 80-90%
- Acceptance: 50-70%
- Cost Reduction: 45-65%

## Creating Custom Benchmarks

### Step 1: Extend Base Class

```python
from benchmarks.base import Benchmark, BenchmarkResult, BenchmarkSummary
from typing import Any

class MyBenchmark(Benchmark):
    def __init__(
        self,
        drafter_model: str = "gpt-4o-mini",
        verifier_model: str = "gpt-4o",
        quality_threshold: float = 0.7,
        max_samples: int = 10,
    ):
        super().__init__(
            dataset_name="MyBenchmark-10",
            drafter_model=drafter_model,
            verifier_model=verifier_model,
            baseline_model=verifier_model,
            quality_threshold=quality_threshold,
            max_samples=max_samples,
        )
```

### Step 2: Load Dataset

```python
def load_dataset(self) -> list[tuple[str, Any]]:
    """Load your benchmark data."""

    problems = [
        {
            "problem_id": "BENCH/1",
            "query": "Your test query here",
            "expected_answer": "The correct answer",
            "category": "category_name",
        },
        # ... more problems
    ]

    return [(p["problem_id"], p) for p in problems[:self.max_samples]]
```

### Step 3: Implement Evaluation

```python
def evaluate_prediction(
    self, prediction: str, ground_truth: Any
) -> tuple[bool, float]:
    """
    Evaluate if prediction is correct.

    Args:
        prediction: Model's response
        ground_truth: Problem data with expected answer

    Returns:
        (is_correct, quality_score)
    """
    # Your evaluation logic here
    expected = ground_truth["expected_answer"]
    is_correct = expected.lower() in prediction.lower()

    # Calculate quality score (0.0 to 1.0)
    quality_score = 1.0 if is_correct else 0.0

    return is_correct, quality_score
```

### Step 4: Run Cascade (Optional Override)

```python
async def run_cascade(self, query: str) -> dict[str, Any]:
    """Run cascade on a query (optional override)."""

    from cascadeflow.agent import CascadeAgent

    agent = CascadeAgent(
        models=[
            {"name": self.drafter_model, "provider": "openai"},
            {"name": self.verifier_model, "provider": "openai"},
        ],
        quality={"threshold": self.quality_threshold},
    )

    result = await agent.arun(query)
    return result
```

### Step 5: Create Runner Function

```python
async def run_my_benchmark() -> BenchmarkSummary:
    """Run benchmark and print results."""

    print("\\n" + "=" * 80)
    print("MY CUSTOM BENCHMARK")
    print("=" * 80 + "\\n")

    benchmark = MyBenchmark(
        drafter_model="gpt-4o-mini",
        verifier_model="gpt-4o",
        quality_threshold=0.7,
        max_samples=10,
    )

    summary = await benchmark.run()

    # Print results
    print(f"Accuracy: {summary.accuracy*100:.1f}%")
    print(f"Cost Savings: ${summary.cost_savings:.6f}")

    return summary


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_my_benchmark())
```

## Best Practices

### 1. API Key Management

Always set API keys before running benchmarks:

```bash
export OPENAI_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"  # For provider comparison
```

### 2. Start Small

Test with `max_samples=5` before running full benchmarks:

```python
benchmark = MyBenchmark(max_samples=5)  # Quick test
```

### 3. Monitor Costs

Track costs during benchmark runs:

```python
print(f"Total Cost: ${summary.total_cost:.6f}")
print(f"Cost per Query: ${summary.total_cost / summary.total_tests:.6f}")
```

### 4. Iterate on Thresholds

Test multiple thresholds to find optimal:

```python
for threshold in [0.6, 0.65, 0.7, 0.75, 0.8]:
    benchmark = MyBenchmark(quality_threshold=threshold)
    summary = await benchmark.run()
    print(f"Threshold {threshold}: Accuracy={summary.accuracy:.2f}, "
          f"Acceptance={summary.acceptance_rate:.2f}")
```

### 5. Compare Providers

Test both OpenAI and Anthropic to find best fit:

```python
# OpenAI verifier
openai_bench = MyBenchmark(verifier_model="gpt-4o")

# Anthropic verifier
anthropic_bench = MyBenchmark(verifier_model="claude-sonnet-4-5-20250929")
```

### 6. Track Over Time

Save results to compare improvements:

```python
results_history = []

summary = await benchmark.run()
results_history.append({
    "date": datetime.now().isoformat(),
    "accuracy": summary.accuracy,
    "cost_reduction": summary.cost_reduction_pct,
})
```

### 7. Category Analysis

Analyze performance by category:

```python
# In your benchmark
category_stats = {}
for result in self.results:
    cat = result.category
    if cat not in category_stats:
        category_stats[cat] = {"correct": 0, "total": 0}
    category_stats[cat]["total"] += 1
    if result.correct:
        category_stats[cat]["correct"] += 1

for cat, stats in category_stats.items():
    accuracy = stats["correct"] / stats["total"]
    print(f"{cat}: {accuracy*100:.1f}% ({stats['correct']}/{stats['total']})")
```

## Troubleshooting

### Low Accuracy

**Symptoms**: Accuracy <70%

**Possible Causes**:
1. Quality threshold too low
2. Drafter model insufficient for task
3. Evaluation criteria too strict

**Solutions**:
- Raise quality threshold to 0.75-0.8
- Use stronger drafter (e.g., gpt-4o instead of gpt-4o-mini)
- Review evaluation logic

### Low Acceptance Rate

**Symptoms**: Acceptance <40%

**Possible Causes**:
1. Quality threshold too high
2. Drafter model overly conservative
3. Domain mismatch

**Solutions**:
- Lower threshold to 0.6-0.65
- Check drafter model capabilities
- Use domain-specific prompting

### High Costs

**Symptoms**: Cost reduction <30%

**Possible Causes**:
1. Too many verifier escalations
2. Expensive baseline model
3. Large context windows

**Solutions**:
- Lower quality threshold
- Use cheaper baseline for comparison
- Optimize prompt length

### Inconsistent Results

**Symptoms**: Results vary significantly between runs

**Possible Causes**:
1. Model randomness (temperature)
2. Small sample size
3. Edge cases in dataset

**Solutions**:
- Increase `max_samples` for stability
- Set temperature=0 for deterministic results
- Review dataset for outliers

## Additional Resources

- **Source Code**: `tests/benchmarks/`
- **Examples**: Each benchmark file includes usage examples
- **API Documentation**: See `cascadeflow.agent.CascadeAgent` docs

For questions or issues, please open an issue on GitHub.

---

**Happy Benchmarking! 🎯**
