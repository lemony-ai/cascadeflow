"""
Full GSM8K Benchmark for CascadeFlow Parameter Optimization.

This script:
1. Downloads the full GSM8K test set (1,319 questions)
2. Validates domain detection on all queries (no API cost)
3. Runs cascade benchmarking with parameter sweeps
4. Outputs optimal parameters for math domain

Usage:
    python tests/benchmarks/gsm8k_full_benchmark.py --domain-only  # Just domain detection
    python tests/benchmarks/gsm8k_full_benchmark.py --sample 100   # Run 100 queries
    python tests/benchmarks/gsm8k_full_benchmark.py --full         # Run all queries
"""

import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.request import urlopen

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cascadeflow import CascadeAgent, DomainConfig, ModelConfig
from tests.benchmarks.utils import resolve_model_cost, resolve_model_pair, resolve_model_provider
from cascadeflow.routing.domain import Domain, DomainDetector, SemanticDomainDetector

# GSM8K test set URL (from OpenAI's grade-school-math repo)
GSM8K_TEST_URL = "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl"
GSM8K_CACHE_FILE = Path(__file__).parent / "gsm8k_test_cache.json"

# Official 8-shot Chain-of-Thought examples for GSM8K
# These are the standard examples used in academic benchmarks
GSM8K_8SHOT_COT = """Solve the following math problems step by step. Show your work and put your final answer after "#### ".

Q: There are 15 trees in the grove. Grove workers will plant trees in the grove today. After they are done, there will be 21 trees. How many trees did the grove workers plant today?
A: There are 15 trees originally. Then there were 21 trees after some more were planted. So there must have been 21 - 15 = 6 trees planted.
#### 6

Q: If there are 3 cars in the parking lot and 2 more cars arrive, how many cars are in the parking lot?
A: There are originally 3 cars. 2 more cars arrive. 3 + 2 = 5.
#### 5

Q: Leah had 32 chocolates and her sister had 42. If they ate 35, how many pieces do they have left in total?
A: Originally, Leah had 32 chocolates. Her sister had 42. So in total they had 32 + 42 = 74. After eating 35, they had 74 - 35 = 39.
#### 39

Q: Jason had 20 lollipops. He gave Denny some lollipops. Now Jason has 12 lollipops. How many lollipops did Jason give to Denny?
A: Jason started with 20 lollipops. Then he had 12 after giving some to Denny. So he gave Denny 20 - 12 = 8 lollipops.
#### 8

Q: Shawn has five toys. For Christmas, he got two toys each from his mom and dad. How many toys does he have now?
A: Shawn started with 5 toys. He got 2 toys from his mom. He got 2 toys from his dad. So he got 2 + 2 = 4 more toys. So he has 5 + 4 = 9 toys now.
#### 9

Q: There were nine computers in the server room. Five more computers were installed each day, from monday to thursday. How many computers are now in the server room?
A: There were originally 9 computers. For each day from monday to thursday, 5 more computers were installed. There are 4 days from monday to thursday. So 5 * 4 = 20 computers were installed. So there are 9 + 20 = 29 computers now.
#### 29

Q: Michael had 58 golf balls. On tuesday, he lost 23 golf balls. On wednesday, he lost 2 more. How many golf balls did he have at the end of wednesday?
A: Michael started with 58 golf balls. On tuesday, he lost 23. So he had 58 - 23 = 35. On wednesday, he lost 2 more. So he had 35 - 2 = 33 golf balls.
#### 33

Q: Olivia has $23. She bought five bagels for $3 each. How much money does she have left?
A: Olivia had 23 dollars. She bought 5 bagels for 3 dollars each. So she spent 5 * 3 = 15 dollars. So she has 23 - 15 = 8 dollars left.
#### 8

Q: """


def format_cot_query(question: str) -> str:
    """Format a question with 8-shot Chain-of-Thought prompt."""
    return GSM8K_8SHOT_COT + question + "\nA:"


@dataclass
class BenchmarkResult:
    """Single query benchmark result."""

    query: str
    answer: str
    predicted: str
    correct: bool
    draft_accepted: bool
    domain_detected: str
    domain_confidence: float
    cost: float
    latency_ms: float
    complexity: str


@dataclass
class ParameterConfig:
    """Configuration for parameter sweep."""

    threshold: float = 0.50
    temperature: float = 0.1
    max_tokens: int = 1000  # Increased for complete math solutions


def download_gsm8k_test_set() -> list[dict]:
    """Download and cache GSM8K test set."""
    if GSM8K_CACHE_FILE.exists():
        print(f"Loading cached GSM8K test set from {GSM8K_CACHE_FILE}")
        with open(GSM8K_CACHE_FILE) as f:
            return json.load(f)

    print(f"Downloading GSM8K test set from {GSM8K_TEST_URL}...")
    problems = []

    try:
        response = urlopen(GSM8K_TEST_URL)
        for line in response:
            data = json.loads(line.decode("utf-8"))
            # Extract numeric answer from solution (format: "#### 42")
            answer_match = re.search(r"####\s*([\d,]+)", data["answer"])
            if answer_match:
                numeric_answer = answer_match.group(1).replace(",", "")
            else:
                numeric_answer = re.sub(r"[^\d]", "", data["answer"].split()[-1])

            problems.append(
                {
                    "question": data["question"],
                    "answer": numeric_answer,
                    "solution": data["answer"],
                }
            )

        # Cache for future use
        GSM8K_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(GSM8K_CACHE_FILE, "w") as f:
            json.dump(problems, f)

        print(f"Downloaded and cached {len(problems)} problems")
        return problems

    except Exception as e:
        print(f"Failed to download GSM8K: {e}")
        print("Using fallback sample data...")
        return get_fallback_problems()


def get_fallback_problems() -> list[dict]:
    """Fallback GSM8K problems if download fails."""
    return [
        {
            "question": "Janet's ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes muffins for her friends every day with four. She sells the remainder at the farmers' market daily for $2 per fresh duck egg. How much in dollars does she make every day at the farmers' market?",
            "answer": "18",
            "solution": "Janet sells 16 - 3 - 4 = 9 duck eggs a day. She makes 9 * 2 = $18 every day at the farmer's market.",
        },
        {
            "question": "A robe takes 2 bolts of blue fiber and half that much white fiber. How many bolts in total does it take?",
            "answer": "3",
            "solution": "It takes 2/2=1 bolt of white fiber. So it takes 2+1=3 bolts in total.",
        },
        {
            "question": "Josh decides to try flipping a house. He buys a house for $80,000 and then puts in $50,000 in repairs. This increased the value of the house by 150%. How much profit did he make?",
            "answer": "70000",
            "solution": "The cost of the house and repairs came out to 80,000+50,000=$130,000. The house increased in value by 80,000*1.5=120,000. So the house is now worth 120,000+80,000=$200,000. That means he made 200,000-130,000=$70,000.",
        },
        # Add more if needed...
    ]


def validate_domain_detection(problems: list[dict]) -> dict:
    """
    Validate domain detection on all problems (no API cost).

    Returns statistics on how many are detected as math vs other domains.
    """
    print("\n" + "=" * 70)
    print("DOMAIN DETECTION VALIDATION")
    print("=" * 70)

    rule_detector = DomainDetector()

    # Try semantic detector
    try:
        semantic_detector = SemanticDomainDetector()
        has_semantic = semantic_detector.is_available
    except:
        has_semantic = False
        semantic_detector = None

    stats = {
        "total": len(problems),
        "rule_based": {},
        "semantic": {},
        "both_math": 0,
        "rule_math_semantic_other": 0,
        "rule_other_semantic_math": 0,
        "both_other": 0,
    }

    print(f"\nValidating domain detection on {len(problems)} queries...")
    start_time = time.time()

    for i, problem in enumerate(problems):
        query = problem["question"]

        # Rule-based detection
        rule_domain, rule_confidence = rule_detector.detect(query)
        rule_domain_str = rule_domain.value
        stats["rule_based"][rule_domain_str] = stats["rule_based"].get(rule_domain_str, 0) + 1

        # Semantic detection
        if has_semantic:
            sem_domain, sem_confidence = semantic_detector.detect(query)
            sem_domain_str = sem_domain.value
            stats["semantic"][sem_domain_str] = stats["semantic"].get(sem_domain_str, 0) + 1

            # Cross-compare
            if rule_domain_str == "math" and sem_domain_str == "math":
                stats["both_math"] += 1
            elif rule_domain_str == "math" and sem_domain_str != "math":
                stats["rule_math_semantic_other"] += 1
            elif rule_domain_str != "math" and sem_domain_str == "math":
                stats["rule_other_semantic_math"] += 1
            else:
                stats["both_other"] += 1

        # Progress
        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{len(problems)} queries...")

    elapsed = time.time() - start_time

    # Print results
    print(f"\nDomain Detection Complete ({elapsed:.1f}s)")
    print("-" * 50)

    print("\nRule-Based Detection:")
    for domain, count in sorted(stats["rule_based"].items(), key=lambda x: -x[1]):
        pct = count / stats["total"] * 100
        print(f"  {domain}: {count} ({pct:.1f}%)")

    if has_semantic:
        print("\nSemantic Detection:")
        for domain, count in sorted(stats["semantic"].items(), key=lambda x: -x[1]):
            pct = count / stats["total"] * 100
            print(f"  {domain}: {count} ({pct:.1f}%)")

        print("\nCross-Comparison:")
        print(
            f"  Both detected as math: {stats['both_math']} ({stats['both_math']/stats['total']*100:.1f}%)"
        )
        print(
            f"  Rule=math, Semantic=other: {stats['rule_math_semantic_other']} ({stats['rule_math_semantic_other']/stats['total']*100:.1f}%)"
        )
        print(
            f"  Rule=other, Semantic=math: {stats['rule_other_semantic_math']} ({stats['rule_other_semantic_math']/stats['total']*100:.1f}%)"
        )
        print(
            f"  Both other: {stats['both_other']} ({stats['both_other']/stats['total']*100:.1f}%)"
        )

    # Calculate overall math detection rate
    rule_math_rate = stats["rule_based"].get("math", 0) / stats["total"] * 100
    print(f"\n✅ Rule-based MATH detection rate: {rule_math_rate:.1f}%")

    if has_semantic:
        sem_math_rate = stats["semantic"].get("math", 0) / stats["total"] * 100
        print(f"✅ Semantic MATH detection rate: {sem_math_rate:.1f}%")

    return stats


def extract_numeric_answer(text: str) -> Optional[str]:
    """Extract numeric answer from model response.

    Handles:
    - "The answer is 18"
    - "Therefore, $18"
    - "= $18" or "= 18"
    - LaTeX: "\\boxed{18}" or "$18" in math mode
    - GSM8K format: "#### 18"
    - Markdown bold: "**18**" or "**3 bolts**"
    - Profit calculations: "Profit = $70,000"
    """
    # Remove LaTeX formatting
    text = re.sub(r"\\text\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\boxed\{([^}]*)\}", r"BOXED:\1", text)
    text = re.sub(r"\\\$", "$", text)

    # Remove markdown bold formatting (preserve content)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)

    text_lower = text.lower()

    # Look for common answer patterns (order matters - most specific first)
    patterns = [
        # Boxed answer (LaTeX) - highest priority
        r"boxed:\s*\$?([\d,]+)",
        # GSM8K format - highest priority
        r"####\s*([\d,]+)",
        # Explicit "final answer" patterns
        r"(?:the\s+)?final\s+answer\s*(?:is|=|:)\s*\$?\s*([\d,]+)",
        # Profit/result after calculation - very important for word problems
        r"(?:profit|result|total\s+profit|net\s+profit)\s*(?:is|=|:)?\s*\$?\s*([\d,]+)",
        # "= $X" at end of calculation (after equals sign)
        r"=\s*\$\s*([\d,]+)(?:\s*(?:dollars?|per\s+day)?)?\.?\s*$",
        # "answer is" patterns
        r"(?:the\s+)?answer\s*(?:is|=|:)\s*\$?\s*([\d,]+)",
        # "she/he makes $X" patterns
        r"(?:she|he|they|it)\s+(?:makes?|earns?|gets?|receives?|has)\s*\$?\s*([\d,]+)",
        # Therefore/so patterns with dollar amounts
        r"(?:therefore|so|thus),?\s*(?:she|he|it|they)?\s*(?:makes?|earns?|gets?)?\s*\$\s*([\d,]+)",
        # "makes $X per day/every day"
        r"makes?\s*\$\s*([\d,]+)\s*(?:per\s*day|every\s*day|each\s*day|daily)",
        # Dollar amount at sentence end
        r"\$\s*([\d,]+)\s*\.?\s*$",
        # "in total" patterns
        r"(?:total|altogether|in\s+total)\s*(?:is|of|=|:)?\s*\$?\s*([\d,]+)",
        # Just number patterns for simple answers like "3 bolts"
        r"(?:^|\s)([\d,]+)\s*(?:bolts?|items?|things?|total)?\s*\.?\s*$",
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower, re.MULTILINE)
        if match:
            return match.group(1).replace(",", "")

    # Fallback: look for equations with "= $X" pattern - find the LAST one (final answer)
    equals_matches = list(re.finditer(r"=\s*\$?\s*([\d,]+)", text))
    if equals_matches:
        # Return the last equation result
        return equals_matches[-1].group(1).replace(",", "")

    # Fallback: look for dollar amounts - take the LAST one
    dollar_matches = list(re.finditer(r"\$\s*([\d,]+)", text))
    if dollar_matches:
        return dollar_matches[-1].group(1).replace(",", "")

    # Last fallback: get last standalone number in text
    numbers = re.findall(r"(?:^|\s)([\d,]+)(?:\s|$|\.)", text)
    if numbers:
        return numbers[-1].replace(",", "")

    return None


async def run_cascade_benchmark(
    problems: list[dict],
    config: ParameterConfig,
    drafter: str = "gpt-4o-mini",
    verifier: str = "claude-opus-4-5-20251101",
    verbose: bool = False,
) -> list[BenchmarkResult]:
    """Run cascade benchmark with given parameters."""

    default_drafter, default_verifier = resolve_model_pair(drafter, verifier)
    drafter = default_drafter
    verifier = default_verifier

    drafter_provider = resolve_model_provider(drafter)
    verifier_provider = resolve_model_provider(verifier)
    drafter_cost = resolve_model_cost(drafter, 0.000375)
    verifier_cost = resolve_model_cost(verifier, 0.0025)

    agent = CascadeAgent(
        models=[
            ModelConfig(name=drafter, provider=drafter_provider, cost=drafter_cost),
            ModelConfig(name=verifier, provider=verifier_provider, cost=verifier_cost),
        ],
        enable_domain_detection=True,
        use_semantic_domains=True,
        domain_configs={
            "math": DomainConfig(
                drafter=drafter,
                verifier=verifier,
                threshold=config.threshold,
                temperature=config.temperature,
            ),
            "general": DomainConfig(
                drafter=drafter,
                verifier=verifier,
                threshold=config.threshold,
                temperature=config.temperature,
            ),
            "financial": DomainConfig(
                drafter=drafter,
                verifier=verifier,
                threshold=config.threshold,
                temperature=config.temperature,
            ),
        },
        verbose=verbose,
    )

    results = []

    for i, problem in enumerate(problems):
        raw_question = problem["question"]
        correct_answer = problem["answer"]

        # Use official 8-shot Chain-of-Thought prompt format
        query = format_cot_query(raw_question)

        try:
            start = time.time()
            result = await agent.run(query, max_tokens=config.max_tokens)
            latency = (time.time() - start) * 1000

            predicted = extract_numeric_answer(result.content)
            is_correct = predicted == correct_answer

            results.append(
                BenchmarkResult(
                    query=raw_question[:50] + "...",
                    answer=correct_answer,
                    predicted=predicted or "N/A",
                    correct=is_correct,
                    draft_accepted=result.metadata.get("draft_accepted", False),
                    domain_detected=result.metadata.get("detected_domain", "unknown"),
                    domain_confidence=0.0,  # Would need to extract
                    cost=result.total_cost,
                    latency_ms=latency,
                    complexity=result.metadata.get("complexity", "unknown"),
                )
            )

            status = "✅" if is_correct else "❌"
            model_used = "[D]" if result.metadata.get("draft_accepted") else "[V]"
            print(f"  {i+1}/{len(problems)}: {status} {model_used} (${result.total_cost:.4f})")

        except Exception as e:
            print(f"  {i+1}/{len(problems)}: ⚠️ ERROR: {e}")
            results.append(
                BenchmarkResult(
                    query=raw_question[:50] + "...",
                    answer=correct_answer,
                    predicted="ERROR",
                    correct=False,
                    draft_accepted=False,
                    domain_detected="error",
                    domain_confidence=0.0,
                    cost=0.0,
                    latency_ms=0.0,
                    complexity="unknown",
                )
            )

    return results


def analyze_results(results: list[BenchmarkResult], config: ParameterConfig) -> dict:
    """Analyze benchmark results and compute metrics."""
    total = len(results)
    correct = sum(1 for r in results if r.correct)
    draft_accepted = sum(1 for r in results if r.draft_accepted)
    draft_correct = sum(1 for r in results if r.draft_accepted and r.correct)
    verifier_used = total - draft_accepted
    verifier_correct = sum(1 for r in results if not r.draft_accepted and r.correct)

    total_cost = sum(r.cost for r in results)
    avg_latency = sum(r.latency_ms for r in results) / total if total > 0 else 0

    # Calculate baseline cost (all verifier)
    # Cost ratio: Claude Opus 4.5 ($15/1K avg) vs GPT-4o-mini ($0.375/1K avg) = 40x
    # For OpenAI-only: GPT-4o ($10/1K avg) vs GPT-4o-mini ($0.375/1K avg) = 26.7x
    verifier_drafter_ratio = 40.0  # Opus 4.5 vs GPT-4o-mini
    baseline_cost = (
        total_cost
        * (1.0 / (draft_accepted / total + (1 - draft_accepted / total) * verifier_drafter_ratio))
        if draft_accepted > 0
        else total_cost
    )

    return {
        "config": {
            "threshold": config.threshold,
            "temperature": config.temperature,
        },
        "accuracy": {
            "total": total,
            "correct": correct,
            "accuracy_pct": correct / total * 100 if total > 0 else 0,
            "draft_correct": draft_correct,
            "draft_correct_pct": draft_correct / draft_accepted * 100 if draft_accepted > 0 else 0,
            "verifier_correct": verifier_correct,
            "verifier_correct_pct": (
                verifier_correct / verifier_used * 100 if verifier_used > 0 else 0
            ),
        },
        "cascade": {
            "draft_accepted": draft_accepted,
            "draft_accepted_pct": draft_accepted / total * 100 if total > 0 else 0,
            "verifier_used": verifier_used,
        },
        "cost": {
            "total_cost": total_cost,
            "avg_cost_per_query": total_cost / total if total > 0 else 0,
            "estimated_baseline": baseline_cost,
            "savings_pct": (1 - total_cost / baseline_cost) * 100 if baseline_cost > 0 else 0,
        },
        "latency": {
            "avg_ms": avg_latency,
        },
    }


async def parameter_sweep(
    problems: list[dict],
    thresholds: list[float] = [0.40, 0.50, 0.60, 0.70],
    temperatures: list[float] = [0.1],
) -> list[dict]:
    """Run parameter sweep to find optimal configuration."""

    print("\n" + "=" * 70)
    print("PARAMETER SWEEP (Official 8-shot Chain-of-Thought)")
    print("=" * 70)
    print("Prompting: 8-shot CoT (standard GSM8K benchmark)")
    print(f"Thresholds: {thresholds}")
    print(f"Temperatures: {temperatures}")
    print(f"Queries: {len(problems)}")

    all_results = []

    for threshold in thresholds:
        for temperature in temperatures:
            config = ParameterConfig(
                threshold=threshold,
                temperature=temperature,
            )

            print(f"\n--- Testing threshold={threshold}, temp={temperature} ---")

            results = await run_cascade_benchmark(problems, config)
            analysis = analyze_results(results, config)
            all_results.append(analysis)

            print("\nResults:")
            print(f"  Accuracy: {analysis['accuracy']['accuracy_pct']:.1f}%")
            print(f"  Draft Accepted: {analysis['cascade']['draft_accepted_pct']:.1f}%")
            print(f"  Cost Savings: {analysis['cost']['savings_pct']:.1f}%")

    return all_results


def find_optimal_config(sweep_results: list[dict]) -> dict:
    """Find optimal configuration from sweep results."""

    # Score each config: maximize (accuracy * draft_acceptance * savings)
    # With minimum accuracy constraint of 85%

    best_config = None
    best_score = -1

    for result in sweep_results:
        accuracy = result["accuracy"]["accuracy_pct"]
        draft_pct = result["cascade"]["draft_accepted_pct"]
        savings = result["cost"]["savings_pct"]

        # Minimum accuracy constraint
        if accuracy < 85:
            score = 0
        else:
            # Weighted score: accuracy matters most, then savings, then draft acceptance
            score = accuracy * 0.4 + savings * 0.35 + draft_pct * 0.25

        if score > best_score:
            best_score = score
            best_config = result

    return best_config


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="GSM8K Full Benchmark")
    parser.add_argument(
        "--domain-only", action="store_true", help="Only run domain detection validation"
    )
    parser.add_argument("--sample", type=int, default=0, help="Number of samples to run (0=all)")
    parser.add_argument("--full", action="store_true", help="Run full benchmark")
    parser.add_argument("--sweep", action="store_true", help="Run parameter sweep")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Download/load dataset
    problems = download_gsm8k_test_set()
    print(f"\nLoaded {len(problems)} GSM8K problems", flush=True)

    # 1. Domain detection validation (always run, no cost)
    domain_stats = validate_domain_detection(problems)

    if args.domain_only:
        print("\nDomain-only mode complete.")
        return

    # 2. Determine sample size
    if args.sample > 0:
        sample_size = min(args.sample, len(problems))
    elif args.full:
        sample_size = len(problems)
    else:
        sample_size = 20  # Default small sample

    sample_problems = problems[:sample_size]

    # 3. Run benchmark or sweep
    print("\n📊 Using models:")
    print("  Drafter:  gpt-4o-mini ($0.15/$0.60 per 1M)")
    print("  Verifier: claude-opus-4-5-20251101 ($5/$25 per 1M)")

    if args.sweep:
        sweep_results = await parameter_sweep(
            sample_problems,
            thresholds=[0.50, 0.60],  # Official benchmark: test 0.5 vs 0.6
            temperatures=[0.1],
        )

        optimal = find_optimal_config(sweep_results)
        print("\n" + "=" * 70)
        print("OPTIMAL CONFIGURATION")
        print("=" * 70)
        print(f"Threshold: {optimal['config']['threshold']}")
        print(f"Temperature: {optimal['config']['temperature']}")
        print(f"Accuracy: {optimal['accuracy']['accuracy_pct']:.1f}%")
        print(f"Draft Acceptance: {optimal['cascade']['draft_accepted_pct']:.1f}%")
        print(f"Cost Savings: {optimal['cost']['savings_pct']:.1f}%")
    else:
        # Single run with default config
        config = ParameterConfig(threshold=0.50, temperature=0.1)
        results = await run_cascade_benchmark(sample_problems, config, verbose=args.verbose)
        analysis = analyze_results(results, config)

        print("\n" + "=" * 70)
        print("BENCHMARK RESULTS")
        print("=" * 70)
        print(f"Total Queries: {analysis['accuracy']['total']}")
        print(f"Accuracy: {analysis['accuracy']['accuracy_pct']:.1f}%")
        print(f"Draft Accepted: {analysis['cascade']['draft_accepted_pct']:.1f}%")
        print(f"Draft Accuracy: {analysis['accuracy']['draft_correct_pct']:.1f}%")
        print(f"Verifier Accuracy: {analysis['accuracy']['verifier_correct_pct']:.1f}%")
        print(f"Total Cost: ${analysis['cost']['total_cost']:.4f}")
        print(f"Cost Savings: {analysis['cost']['savings_pct']:.1f}%")
        print(f"Avg Latency: {analysis['latency']['avg_ms']:.0f}ms")


if __name__ == "__main__":
    asyncio.run(main())
