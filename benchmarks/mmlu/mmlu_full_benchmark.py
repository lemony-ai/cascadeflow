"""
Full MMLU (Massive Multitask Language Understanding) Benchmark for CascadeFlow.

This script:
1. Downloads the full MMLU test set (14,042 questions across 57 subjects)
2. Validates domain detection on all queries (no API cost)
3. Runs cascade benchmarking with parameter sweeps
4. Reports per-category accuracy (STEM, Humanities, Social Sciences, Other)

MMLU Categories:
- STEM: mathematics, physics, chemistry, biology, computer_science, etc.
- Humanities: history, philosophy, law, ethics, world_religions, etc.
- Social Sciences: economics, psychology, sociology, political_science, etc.
- Other: business, health, marketing, management, etc.

Usage:
    python tests/benchmarks/mmlu_full_benchmark.py --domain-only  # Just domain detection
    python tests/benchmarks/mmlu_full_benchmark.py --sample 100   # Run 100 queries
    python tests/benchmarks/mmlu_full_benchmark.py --full         # Run all queries
    python tests/benchmarks/mmlu_full_benchmark.py --full --sweep # Parameter sweep
"""

import asyncio
import csv
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.request import urlopen, urlretrieve

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cascadeflow import CascadeAgent, DomainConfig, ModelConfig
from cascadeflow.routing.domain import DomainDetector, SemanticDomainDetector

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 30.0  # seconds


async def run_with_retry(agent, query: str, max_tokens: int, max_retries: int = MAX_RETRIES):
    """
    Run agent with exponential backoff retry for transient API errors.

    Args:
        agent: CascadeAgent instance
        query: Query text
        max_tokens: Maximum tokens for response
        max_retries: Maximum number of retry attempts

    Returns:
        Agent result on success

    Raises:
        Exception: If all retries fail
    """
    last_error = None
    backoff = INITIAL_BACKOFF

    for attempt in range(max_retries + 1):
        try:
            return await agent.run(query, max_tokens=max_tokens)
        except Exception as e:
            last_error = e
            error_str = str(e).lower()

            # Check if error is retryable (rate limit, timeout, server error)
            retryable = any(
                keyword in error_str
                for keyword in [
                    "rate_limit",
                    "rate limit",
                    "timeout",
                    "timed out",
                    "429",
                    "500",
                    "502",
                    "503",
                    "504",
                    "overloaded",
                    "capacity",
                    "try again",
                    "connection",
                    "network",
                    "temporary",
                ]
            )

            if not retryable or attempt >= max_retries:
                raise last_error

            # Add jitter to prevent thundering herd
            jitter = random.uniform(0, backoff * 0.1)
            wait_time = min(backoff + jitter, MAX_BACKOFF)

            print(
                f"    ⏳ Retry {attempt + 1}/{max_retries} after {wait_time:.1f}s ({type(e).__name__})"
            )
            await asyncio.sleep(wait_time)

            # Exponential backoff
            backoff = min(backoff * 2, MAX_BACKOFF)

    raise last_error


# MMLU dataset URLs (from hendrycks/test on Hugging Face)
MMLU_BASE_URL = "https://people.eecs.berkeley.edu/~hendrycks/data/test/"
MMLU_CACHE_DIR = Path(__file__).parent / "mmlu_cache"
MMLU_CACHE_FILE = MMLU_CACHE_DIR / "mmlu_test.json"

# Category mappings for 57 subjects
SUBJECT_TO_CATEGORY = {
    # STEM (17 subjects)
    "abstract_algebra": "stem",
    "anatomy": "stem",
    "astronomy": "stem",
    "college_biology": "stem",
    "college_chemistry": "stem",
    "college_computer_science": "stem",
    "college_mathematics": "stem",
    "college_physics": "stem",
    "computer_security": "stem",
    "conceptual_physics": "stem",
    "electrical_engineering": "stem",
    "elementary_mathematics": "stem",
    "high_school_biology": "stem",
    "high_school_chemistry": "stem",
    "high_school_computer_science": "stem",
    "high_school_mathematics": "stem",
    "high_school_physics": "stem",
    "high_school_statistics": "stem",
    "machine_learning": "stem",
    # Humanities (13 subjects)
    "formal_logic": "humanities",
    "high_school_european_history": "humanities",
    "high_school_us_history": "humanities",
    "high_school_world_history": "humanities",
    "international_law": "humanities",
    "jurisprudence": "humanities",
    "logical_fallacies": "humanities",
    "moral_disputes": "humanities",
    "moral_scenarios": "humanities",
    "philosophy": "humanities",
    "prehistory": "humanities",
    "professional_law": "humanities",
    "world_religions": "humanities",
    # Social Sciences (12 subjects)
    "econometrics": "social_sciences",
    "high_school_geography": "humanities",  # Often classified as humanities
    "high_school_government_and_politics": "social_sciences",
    "high_school_macroeconomics": "social_sciences",
    "high_school_microeconomics": "social_sciences",
    "high_school_psychology": "social_sciences",
    "human_sexuality": "social_sciences",
    "professional_psychology": "social_sciences",
    "public_relations": "social_sciences",
    "security_studies": "social_sciences",
    "sociology": "social_sciences",
    "us_foreign_policy": "social_sciences",
    # Other (15 subjects)
    "business_ethics": "other",
    "clinical_knowledge": "other",
    "college_medicine": "other",
    "global_facts": "other",
    "human_aging": "other",
    "management": "other",
    "marketing": "other",
    "medical_genetics": "other",
    "miscellaneous": "other",
    "nutrition": "other",
    "professional_accounting": "other",
    "professional_medicine": "other",
    "virology": "other",
}

# Map subjects to expected detected domains
SUBJECT_TO_DOMAIN = {
    # STEM subjects -> science/math domains
    "abstract_algebra": "math",
    "college_mathematics": "math",
    "elementary_mathematics": "math",
    "high_school_mathematics": "math",
    "high_school_statistics": "math",
    "college_physics": "science",
    "high_school_physics": "science",
    "conceptual_physics": "science",
    "college_chemistry": "science",
    "high_school_chemistry": "science",
    "college_biology": "science",
    "high_school_biology": "science",
    "anatomy": "science",
    "astronomy": "science",
    "college_computer_science": "code",
    "high_school_computer_science": "code",
    "computer_security": "code",
    "electrical_engineering": "science",
    "machine_learning": "code",
    # Medical/Health -> medical domain
    "clinical_knowledge": "medical",
    "college_medicine": "medical",
    "medical_genetics": "medical",
    "professional_medicine": "medical",
    "virology": "medical",
    "nutrition": "medical",
    "human_aging": "medical",
    # Business/Finance
    "professional_accounting": "financial",
    "business_ethics": "financial",
    "management": "financial",
    "marketing": "financial",
    "econometrics": "financial",
    "high_school_macroeconomics": "financial",
    "high_school_microeconomics": "financial",
    # Legal
    "international_law": "legal",
    "jurisprudence": "legal",
    "professional_law": "legal",
    # Default to general
}


@dataclass
class BenchmarkResult:
    """Single query benchmark result."""

    query: str
    subject: str
    category: str
    answer: str
    predicted: str
    correct: bool
    draft_accepted: bool
    domain_detected: str
    cost: float
    latency_ms: float


@dataclass
class ParameterConfig:
    """Configuration for parameter sweep."""

    threshold: float = 0.60
    temperature: float = 0.3
    max_tokens: int = 100  # MMLU is multiple choice, short answers


def download_mmlu_test_set() -> list[dict]:
    """Download and cache full MMLU test set using Hugging Face datasets library."""
    if MMLU_CACHE_FILE.exists():
        print(f"Loading cached MMLU from {MMLU_CACHE_FILE}")
        with open(MMLU_CACHE_FILE) as f:
            return json.load(f)

    print("Downloading MMLU test set from Hugging Face...")
    MMLU_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from datasets import load_dataset

        # Load all MMLU subjects using the official dataset
        # Dataset: cais/mmlu (official MMLU benchmark)
        problems = []

        for subject in SUBJECT_TO_CATEGORY.keys():
            try:
                print(f"  Loading {subject}...", end=" ", flush=True)
                dataset = load_dataset("cais/mmlu", subject, split="test", trust_remote_code=True)

                for row in dataset:
                    question = row["question"]
                    choices = [
                        f"A. {row['choices'][0]}",
                        f"B. {row['choices'][1]}",
                        f"C. {row['choices'][2]}",
                        f"D. {row['choices'][3]}",
                    ]
                    # Answer is 0-3, convert to A-D
                    answer = ["A", "B", "C", "D"][row["answer"]]

                    problems.append(
                        {
                            "subject": subject,
                            "category": SUBJECT_TO_CATEGORY.get(subject, "other"),
                            "question": question,
                            "choices": choices,
                            "answer": answer,
                        }
                    )

                print(f"({len(dataset)} questions)")

            except Exception as e:
                print(f"Warning: {e}")

        # Cache for future use
        with open(MMLU_CACHE_FILE, "w") as f:
            json.dump(problems, f)

        print(f"\nDownloaded {len(problems)} problems across {len(SUBJECT_TO_CATEGORY)} subjects")
        return problems

    except ImportError:
        print("Warning: 'datasets' library not installed. Using sample problems.")
        print("Install with: pip install datasets")
        return get_sample_problems()


def get_sample_problems() -> list[dict]:
    """Fallback sample problems if download fails."""
    return [
        {
            "subject": "high_school_mathematics",
            "category": "stem",
            "question": "What is the derivative of x^3?",
            "choices": ["A. 3x^2", "B. x^2", "C. 3x", "D. x^3"],
            "answer": "A",
        },
        {
            "subject": "college_physics",
            "category": "stem",
            "question": "What is the SI unit of force?",
            "choices": ["A. Joule", "B. Newton", "C. Watt", "D. Pascal"],
            "answer": "B",
        },
        {
            "subject": "high_school_us_history",
            "category": "humanities",
            "question": "Who was the first President of the United States?",
            "choices": [
                "A. Thomas Jefferson",
                "B. John Adams",
                "C. George Washington",
                "D. Benjamin Franklin",
            ],
            "answer": "C",
        },
        {
            "subject": "high_school_macroeconomics",
            "category": "social_sciences",
            "question": "What does GDP stand for?",
            "choices": [
                "A. Gross Domestic Product",
                "B. General Domestic Production",
                "C. Gross Development Plan",
                "D. Global Domestic Product",
            ],
            "answer": "A",
        },
        {
            "subject": "professional_medicine",
            "category": "other",
            "question": "What vitamin is produced by the body when exposed to sunlight?",
            "choices": ["A. Vitamin A", "B. Vitamin C", "C. Vitamin D", "D. Vitamin B12"],
            "answer": "C",
        },
    ]


def validate_domain_detection(problems: list[dict]) -> dict:
    """Validate domain detection on all problems (no API cost)."""
    print("\n" + "=" * 70)
    print("DOMAIN DETECTION VALIDATION")
    print("=" * 70)

    rule_detector = DomainDetector()

    try:
        semantic_detector = SemanticDomainDetector()
        has_semantic = semantic_detector.is_available
    except:
        has_semantic = False
        semantic_detector = None

    stats = {
        "total": len(problems),
        "by_category": defaultdict(lambda: {"total": 0, "rule_correct": 0, "semantic_correct": 0}),
        "by_subject": defaultdict(lambda: {"total": 0, "rule_correct": 0, "semantic_correct": 0}),
        "rule_domain_dist": defaultdict(int),
        "semantic_domain_dist": defaultdict(int),
    }

    print(f"\nValidating {len(problems)} queries...")
    start_time = time.time()

    for i, problem in enumerate(problems):
        query = problem["question"]
        subject = problem["subject"]
        category = problem["category"]
        expected_domain = SUBJECT_TO_DOMAIN.get(subject, "general")

        # Rule-based detection
        rule_domain, _ = rule_detector.detect(query)
        rule_domain_str = rule_domain.value
        stats["rule_domain_dist"][rule_domain_str] += 1

        stats["by_category"][category]["total"] += 1
        stats["by_subject"][subject]["total"] += 1

        if rule_domain_str == expected_domain:
            stats["by_category"][category]["rule_correct"] += 1
            stats["by_subject"][subject]["rule_correct"] += 1

        # Semantic detection
        if has_semantic:
            sem_domain, _ = semantic_detector.detect(query)
            sem_domain_str = sem_domain.value
            stats["semantic_domain_dist"][sem_domain_str] += 1

            if sem_domain_str == expected_domain:
                stats["by_category"][category]["semantic_correct"] += 1
                stats["by_subject"][subject]["semantic_correct"] += 1

        if (i + 1) % 500 == 0:
            print(f"  Processed {i+1}/{len(problems)}...")

    elapsed = time.time() - start_time

    # Print results
    print(f"\nDomain Detection Complete ({elapsed:.1f}s)")
    print("-" * 50)

    print("\nRule-Based Domain Distribution:")
    for domain, count in sorted(stats["rule_domain_dist"].items(), key=lambda x: -x[1]):
        pct = count / stats["total"] * 100
        print(f"  {domain}: {count} ({pct:.1f}%)")

    if has_semantic:
        print("\nSemantic Domain Distribution:")
        for domain, count in sorted(stats["semantic_domain_dist"].items(), key=lambda x: -x[1]):
            pct = count / stats["total"] * 100
            print(f"  {domain}: {count} ({pct:.1f}%)")

    print("\nAccuracy by Category:")
    for category, data in stats["by_category"].items():
        rule_acc = data["rule_correct"] / data["total"] * 100 if data["total"] > 0 else 0
        print(f"  {category}: {data['rule_correct']}/{data['total']} ({rule_acc:.1f}%) rule-based")

    return dict(stats)


def extract_answer(text: str) -> Optional[str]:
    """Extract answer letter (A, B, C, or D) from response.

    Handles various response formats:
    - "The answer is A"
    - "A is correct"
    - "Option B"
    - "The correct option is C"
    - Just "A" or "A."
    - "(A)" or "[A]"
    - "**A**" (markdown bold)
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # Priority 1: Look for explicit answer patterns (most reliable)
    explicit_patterns = [
        # "The answer is A", "Answer: A", "answer is: A"
        r"(?:the\s+)?answer\s*(?:is|:|=)\s*[:\s]*\(?([A-Da-d])\)?",
        # "The correct answer is A", "correct answer: A"
        r"(?:the\s+)?correct\s+answer\s*(?:is|:|=)\s*[:\s]*\(?([A-Da-d])\)?",
        # "The correct option is A", "correct choice is A"
        r"(?:the\s+)?correct\s+(?:option|choice)\s*(?:is|:|=)\s*[:\s]*\(?([A-Da-d])\)?",
        # "Option A is correct", "Choice B is the answer"
        r"(?:option|choice)\s+([A-Da-d])\s+is\s+(?:correct|the\s+answer)",
        # "A is correct", "A is the correct answer"
        r"\b([A-Da-d])\s+is\s+(?:the\s+)?(?:correct|right)(?:\s+answer)?",
        # "I would choose A", "I select B", "My answer is C"
        r"(?:i\s+)?(?:would\s+)?(?:choose|select|pick)\s+\(?([A-Da-d])\)?",
        r"my\s+answer\s+(?:is|would\s+be)\s+\(?([A-Da-d])\)?",
        # "Therefore, A", "Thus, the answer is B", "So, C"
        r"(?:therefore|thus|so|hence),?\s*(?:the\s+answer\s+is\s+)?\(?([A-Da-d])\)?\.?\s*$",
        # "Final answer: A", "Answer = A"
        r"(?:final\s+)?answer\s*[=:]\s*\(?([A-Da-d])\)?",
    ]

    for pattern in explicit_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).upper()

    # Priority 2: Look for formatted answer patterns
    formatted_patterns = [
        # Markdown bold: **A**, **B**
        r"\*\*([A-Da-d])\*\*",
        # Parentheses at end: (A), (B)
        r"\(([A-Da-d])\)\s*\.?\s*$",
        # Brackets: [A], [B]
        r"\[([A-Da-d])\]",
        # "Option A", "Choice B" (standalone)
        r"(?:option|choice)\s+([A-Da-d])\b(?!\s+(?:is|and|or|,))",
    ]

    for pattern in formatted_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).upper()

    # Priority 3: Look for letter at the very start of response
    # This catches responses like "A. The mitochondria..." or just "A"
    start_patterns = [
        r"^\s*\(?([A-Da-d])\)?[\.\)\:\s]",  # A. or A) or A: or A followed by space
        r"^\s*([A-Da-d])\s*$",  # Just the letter alone
    ]

    for pattern in start_patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

    # Priority 4: Look for letter at the very end of response
    # This catches responses that conclude with just the letter
    end_patterns = [
        r"[\.\s]\(?([A-Da-d])\)?\s*\.?\s*$",  # ends with " A" or " (A)" or " A."
        r":\s*\(?([A-Da-d])\)?\s*\.?\s*$",  # ends with ": A"
    ]

    for pattern in end_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

    # Priority 5: Last resort - find the last standalone letter A-D
    # This is less reliable but catches edge cases
    # Look for pattern like "...so the answer would be A." where A is isolated
    letters = re.findall(r"(?<![A-Za-z])([A-Da-d])(?![A-Za-z])", text)
    if letters:
        # Return the last one found (most likely the conclusion)
        return letters[-1].upper()

    return None


def format_question(problem: dict) -> str:
    """Format a multiple-choice question for the model.

    Uses a clear prompt that encourages models to state their answer explicitly.
    """
    question = problem["question"]
    choices = "\n".join(problem["choices"])

    return f"""Answer the following multiple-choice question.

Question: {question}

{choices}

Think through this step-by-step, then conclude with "The answer is X" where X is A, B, C, or D."""


async def run_cascade_benchmark(
    problems: list[dict],
    config: ParameterConfig,
    drafter: str = "gpt-4o-mini",
    verifier: str = "claude-sonnet-4-20250514",
) -> list[BenchmarkResult]:
    """Run cascade benchmark with given parameters.

    Uses domain detection to route queries to appropriate domain configs.
    MMLU covers: math, science, code, medical, financial, legal, general.
    """

    verifier_provider = "anthropic" if "claude" in verifier.lower() else "openai"
    drafter_cost = 0.000375  # GPT-4o-mini avg ($0.15/$0.60 per 1M)
    verifier_cost = (
        0.015 if "opus" in verifier.lower() else 0.003 if "sonnet" in verifier.lower() else 0.0025
    )

    # Configure all domains expected in MMLU
    # Each domain gets same drafter/verifier but optimized thresholds
    domain_configs = {
        # STEM domains
        "math": DomainConfig(
            drafter=drafter,
            verifier=verifier,
            threshold=config.threshold,
            temperature=0.1,  # Low temp for precise math
            cascade_complexities=["trivial", "simple", "moderate", "hard", "expert"],
        ),
        "science": DomainConfig(
            drafter=drafter,
            verifier=verifier,
            threshold=config.threshold,
            temperature=0.2,
            cascade_complexities=["trivial", "simple", "moderate", "hard"],
        ),
        "code": DomainConfig(
            drafter=drafter,
            verifier=verifier,
            threshold=config.threshold,
            temperature=0.2,
            cascade_complexities=["trivial", "simple", "moderate", "hard", "expert"],
        ),
        # High-stakes domains (higher accuracy needed)
        "medical": DomainConfig(
            drafter=drafter,
            verifier=verifier,
            threshold=min(config.threshold + 0.1, 0.9),  # Higher threshold for medical
            temperature=0.1,
            cascade_complexities=["trivial", "simple", "moderate"],
        ),
        "legal": DomainConfig(
            drafter=drafter,
            verifier=verifier,
            threshold=min(config.threshold + 0.1, 0.9),  # Higher threshold for legal
            temperature=0.2,
            cascade_complexities=["trivial", "simple", "moderate"],
        ),
        "financial": DomainConfig(
            drafter=drafter,
            verifier=verifier,
            threshold=config.threshold,
            temperature=0.2,
            cascade_complexities=["trivial", "simple", "moderate", "hard"],
        ),
        # General domain (catch-all)
        "general": DomainConfig(
            drafter=drafter,
            verifier=verifier,
            threshold=config.threshold,
            temperature=config.temperature,
            cascade_complexities=["trivial", "simple", "moderate"],
        ),
    }

    agent = CascadeAgent(
        models=[
            ModelConfig(name=drafter, provider="openai", cost=drafter_cost),
            ModelConfig(name=verifier, provider=verifier_provider, cost=verifier_cost),
        ],
        enable_domain_detection=True,
        use_semantic_domains=True,
        domain_configs=domain_configs,
    )

    results = []

    for i, problem in enumerate(problems):
        query = format_question(problem)
        correct_answer = problem["answer"]

        try:
            start = time.time()
            result = await run_with_retry(agent, query, config.max_tokens)
            latency = (time.time() - start) * 1000

            predicted = extract_answer(result.content)
            is_correct = predicted == correct_answer

            results.append(
                BenchmarkResult(
                    query=problem["question"][:50] + "...",
                    subject=problem["subject"],
                    category=problem["category"],
                    answer=correct_answer,
                    predicted=predicted or "N/A",
                    correct=is_correct,
                    draft_accepted=result.metadata.get("draft_accepted", False),
                    domain_detected=result.metadata.get("detected_domain", "unknown"),
                    cost=result.total_cost,
                    latency_ms=latency,
                )
            )

            status = "✓" if is_correct else "✗"
            model_used = "[D]" if result.metadata.get("draft_accepted") else "[V]"
            print(
                f"[{i+1}/{len(problems)}] {problem['subject'][:20]:20s}: {status} {model_used} | Cost: ${result.total_cost:.4f}"
            )

        except Exception as e:
            print(f"[{i+1}/{len(problems)}] {problem['subject'][:20]:20s}: ⚠️ ERROR: {e}")
            results.append(
                BenchmarkResult(
                    query=problem["question"][:50] + "...",
                    subject=problem["subject"],
                    category=problem["category"],
                    answer=correct_answer,
                    predicted="ERROR",
                    correct=False,
                    draft_accepted=False,
                    domain_detected="error",
                    cost=0.0,
                    latency_ms=0.0,
                )
            )

    return results


def analyze_results(results: list[BenchmarkResult], config: ParameterConfig) -> dict:
    """Analyze benchmark results."""
    total = len(results)
    correct = sum(1 for r in results if r.correct)
    draft_accepted = sum(1 for r in results if r.draft_accepted)
    total_cost = sum(r.cost for r in results)

    # Per-category breakdown
    category_stats = defaultdict(
        lambda: {"total": 0, "correct": 0, "draft_accepted": 0, "cost": 0.0}
    )
    for r in results:
        category_stats[r.category]["total"] += 1
        if r.correct:
            category_stats[r.category]["correct"] += 1
        if r.draft_accepted:
            category_stats[r.category]["draft_accepted"] += 1
        category_stats[r.category]["cost"] += r.cost

    # Baseline cost (all verifier)
    verifier_drafter_ratio = 40.0
    baseline_cost = (
        total_cost
        * (1.0 / (draft_accepted / total + (1 - draft_accepted / total) * verifier_drafter_ratio))
        if draft_accepted > 0
        else total_cost
    )

    return {
        "config": {"threshold": config.threshold, "temperature": config.temperature},
        "accuracy": {
            "total": total,
            "correct": correct,
            "accuracy_pct": correct / total * 100 if total > 0 else 0,
        },
        "cascade": {
            "draft_accepted": draft_accepted,
            "draft_accepted_pct": draft_accepted / total * 100 if total > 0 else 0,
        },
        "cost": {
            "total_cost": total_cost,
            "baseline_cost": baseline_cost,
            "savings_pct": (1 - total_cost / baseline_cost) * 100 if baseline_cost > 0 else 0,
        },
        "by_category": {
            cat: {
                "accuracy": stats["correct"] / stats["total"] * 100 if stats["total"] > 0 else 0,
                "draft_pct": (
                    stats["draft_accepted"] / stats["total"] * 100 if stats["total"] > 0 else 0
                ),
                "total": stats["total"],
            }
            for cat, stats in category_stats.items()
        },
    }


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="MMLU Full Benchmark")
    parser.add_argument("--domain-only", action="store_true", help="Only run domain detection")
    parser.add_argument("--sample", type=int, default=0, help="Number of samples (0=all)")
    parser.add_argument("--full", action="store_true", help="Run full benchmark")
    parser.add_argument("--sweep", action="store_true", help="Run parameter sweep")

    args = parser.parse_args()

    # Download/load dataset
    try:
        problems = download_mmlu_test_set()
    except Exception as e:
        print(f"Failed to download MMLU: {e}")
        print("Using sample problems...")
        problems = get_sample_problems()

    print(f"\nLoaded {len(problems)} MMLU problems")

    # Domain detection validation
    domain_stats = validate_domain_detection(problems)

    if args.domain_only:
        print("\nDomain-only mode complete.")
        return

    # Determine sample size
    if args.sample > 0:
        sample_size = min(args.sample, len(problems))
    elif args.full:
        sample_size = len(problems)
    else:
        sample_size = 50  # Default sample

    sample_problems = problems[:sample_size]

    print("\n" + "=" * 70)
    print("MMLU BENCHMARK")
    print("=" * 70)
    print("\nConfiguration:")
    print("  Drafter:  gpt-4o-mini")
    print("  Verifier: claude-sonnet-4-20250514")
    print(f"  Problems: {sample_size}")

    if args.sweep:
        thresholds = [0.50, 0.60, 0.70]
        all_results = []

        for threshold in thresholds:
            config = ParameterConfig(threshold=threshold)
            print(f"\n--- Threshold: {threshold} ---")
            results = await run_cascade_benchmark(sample_problems, config)
            analysis = analyze_results(results, config)
            all_results.append(analysis)

            print("\nResults:")
            print(f"  Accuracy: {analysis['accuracy']['accuracy_pct']:.1f}%")
            print(f"  Draft Accepted: {analysis['cascade']['draft_accepted_pct']:.1f}%")
            print(f"  Cost Savings: {analysis['cost']['savings_pct']:.1f}%")

        # Find best config
        best = max(
            all_results,
            key=lambda x: x["accuracy"]["accuracy_pct"] * 0.5 + x["cost"]["savings_pct"] * 0.5,
        )
        print("\n" + "=" * 70)
        print("OPTIMAL CONFIGURATION")
        print("=" * 70)
        print(f"Threshold: {best['config']['threshold']}")
        print(f"Accuracy: {best['accuracy']['accuracy_pct']:.1f}%")
        print(f"Cost Savings: {best['cost']['savings_pct']:.1f}%")
    else:
        config = ParameterConfig(threshold=0.60)
        results = await run_cascade_benchmark(sample_problems, config)
        analysis = analyze_results(results, config)

        print("\n" + "=" * 70)
        print("BENCHMARK SUMMARY")
        print("=" * 70)
        print("\nAccuracy:")
        print(
            f"  Overall: {analysis['accuracy']['accuracy_pct']:.1f}% ({analysis['accuracy']['correct']}/{analysis['accuracy']['total']})"
        )

        print("\nCascade Performance:")
        print(f"  Draft Acceptance: {analysis['cascade']['draft_accepted_pct']:.1f}%")
        print(f"  Total Cost: ${analysis['cost']['total_cost']:.4f}")
        print(f"  Baseline Cost: ${analysis['cost']['baseline_cost']:.4f}")
        print(f"  Cost Savings: {analysis['cost']['savings_pct']:.1f}%")

        print("\nBy Category:")
        for cat, stats in analysis["by_category"].items():
            print(
                f"  {cat}: {stats['accuracy']:.1f}% accuracy, {stats['draft_pct']:.1f}% draft ({stats['total']} q)"
            )

        # Save results for publication
        results_dir = Path(__file__).parent / "mmlu_results"
        results_dir.mkdir(exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        results_file = results_dir / f"mmlu_results_{timestamp}.json"

        results_data = {
            "benchmark": "MMLU",
            "timestamp": timestamp,
            "configuration": {
                "drafter": "gpt-4o-mini",
                "verifier": "claude-sonnet-4-20250514",
                "threshold": config.threshold,
                "temperature": config.temperature,
                "total_problems": sample_size,
                "domain_detection": True,
                "semantic_domains": True,
            },
            "results": {
                "accuracy": analysis["accuracy"],
                "cascade": analysis["cascade"],
                "cost": analysis["cost"],
                "by_category": analysis["by_category"],
            },
            "per_query_results": [
                {
                    "subject": r.subject,
                    "category": r.category,
                    "correct": r.correct,
                    "draft_accepted": r.draft_accepted,
                    "domain_detected": r.domain_detected,
                    "cost": r.cost,
                }
                for r in results
            ],
        }

        with open(results_file, "w") as f:
            json.dump(results_data, f, indent=2)

        print(f"\nResults saved to: {results_file}")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
