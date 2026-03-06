#!/usr/bin/env python3
"""
RULER-Style Long Context Benchmark for CascadeFlow.

Implements Needle-in-a-Haystack (NIAH) style tests inspired by the RULER benchmark.
Tests the cascade's ability to:
1. Find single facts in long contexts (Single NIAH)
2. Find multiple facts in long contexts (Multi NIAH)
3. Answer multiple questions about the same context (Multi-Query)
4. Track key-value associations (Multi-Key)

The benchmark uses synthetic test cases with configurable context lengths
to test long-context retrieval while measuring draft acceptance rates.
"""

import argparse
import asyncio
import json
import os
import random
import string
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cascadeflow import CascadeAgent
from cascadeflow.schema.config import ModelConfig

# ============================================================================
# CONFIGURATION
# ============================================================================

DEFAULT_CONFIG = {
    "drafter": "gpt-4o-mini",
    "verifier": "gpt-4o",
    "threshold": 0.6,
    "context_lengths": [1000, 2000, 4000],  # Target word counts
}


# ============================================================================
# HAYSTACK GENERATION
# ============================================================================

FILLER_TOPICS = [
    "The development of renewable energy sources has become increasingly important in recent years. Solar panels are being installed on rooftops across the globe, while wind turbines dot the landscape of many countries. Hydroelectric power continues to be a major source of clean energy in regions with suitable water resources.",
    "Modern transportation systems have evolved significantly over the past century. Electric vehicles are becoming more common on roads, and public transit systems are expanding in major cities. High-speed rail networks connect urban centers in many parts of the world.",
    "The field of medicine has seen remarkable advances in recent decades. New treatments for previously incurable diseases are being developed regularly. Telemedicine has made healthcare more accessible to people in remote areas.",
    "Agriculture has been transformed by technology and innovation. Precision farming techniques allow farmers to optimize their use of water and fertilizers. Vertical farms in urban areas are producing fresh vegetables year-round.",
    "The entertainment industry has undergone dramatic changes with the rise of streaming services. Traditional movie theaters are adapting to new viewing habits. Video games have become one of the largest entertainment sectors.",
    "Education systems around the world are embracing digital tools. Online learning platforms have made knowledge more accessible than ever. Virtual reality is being explored as a way to enhance classroom experiences.",
    "The global economy is increasingly interconnected through trade and finance. International supply chains span multiple continents. Digital currencies and blockchain technology are creating new financial paradigms.",
    "Environmental conservation efforts are expanding worldwide. Protected natural areas are being established in critical ecosystems. Reforestation projects aim to restore degraded landscapes.",
    "Space exploration continues to push the boundaries of human knowledge. Private companies are joining government agencies in the race to explore the cosmos. Satellite technology has revolutionized communications and navigation.",
    "Urban planning is evolving to create more livable cities. Green spaces are being prioritized in new developments. Smart city technologies aim to improve efficiency and quality of life.",
]


def generate_filler_text(target_words: int) -> str:
    """Generate filler text to pad the haystack."""
    paragraphs = []
    current_words = 0

    while current_words < target_words:
        para = random.choice(FILLER_TOPICS)
        paragraphs.append(para)
        current_words += len(para.split())

    return "\n\n".join(paragraphs)


def insert_needle_at_position(haystack: str, needle: str, position: float) -> str:
    """Insert needle at a specific position (0.0 = start, 1.0 = end)."""
    paragraphs = haystack.split("\n\n")
    insert_idx = max(0, min(len(paragraphs) - 1, int(len(paragraphs) * position)))
    paragraphs.insert(insert_idx, needle)
    return "\n\n".join(paragraphs)


# ============================================================================
# TEST CASE GENERATION
# ============================================================================


@dataclass
class RulerTestCase:
    """A RULER benchmark test case."""

    task_id: str
    task_type: str  # single_niah, multi_niah, multi_query, multi_key
    context: str
    question: str
    expected_answer: str
    context_length: int
    needle_position: float  # 0.0 to 1.0
    metadata: dict


def generate_single_niah(context_length: int, position: float = 0.5) -> RulerTestCase:
    """Generate a Single NIAH test case."""
    # Generate unique needle
    secret_number = random.randint(10000, 99999)
    needle = f"IMPORTANT: The secret code for today is {secret_number}. Remember this number."

    # Generate haystack
    filler = generate_filler_text(context_length)
    context = insert_needle_at_position(filler, needle, position)

    return RulerTestCase(
        task_id=f"single_niah_{context_length}_{int(position*100)}",
        task_type="single_niah",
        context=context,
        question="What is the secret code mentioned in the text?",
        expected_answer=str(secret_number),
        context_length=len(context.split()),
        needle_position=position,
        metadata={"secret_number": secret_number},
    )


def generate_multi_niah(context_length: int, num_needles: int = 3) -> RulerTestCase:
    """Generate a Multi NIAH test case with multiple facts to find."""
    needles = []
    answers = {}

    items = [
        ("color of the car", random.choice(["red", "blue", "green", "silver"])),
        ("name of the city", random.choice(["Tokyo", "London", "Paris", "Sydney"])),
        ("year of the event", random.choice(["2019", "2020", "2021", "2022"])),
        ("price of the item", f"${random.randint(100, 999)}"),
        ("number of attendees", str(random.randint(50, 500))),
    ]

    selected = random.sample(items, num_needles)

    for key, value in selected:
        needles.append(f"NOTE: The {key} is {value}.")
        answers[key] = value

    # Generate haystack and insert needles at different positions
    filler = generate_filler_text(context_length)
    context = filler
    for i, needle in enumerate(needles):
        pos = (i + 1) / (num_needles + 1)
        context = insert_needle_at_position(context, needle, pos)

    question = (
        "List all the specific facts mentioned in the text. What are: "
        + ", ".join([k for k, v in selected])
        + "?"
    )
    expected = ", ".join([f"{k}: {v}" for k, v in selected])

    return RulerTestCase(
        task_id=f"multi_niah_{context_length}_{num_needles}",
        task_type="multi_niah",
        context=context,
        question=question,
        expected_answer=expected,
        context_length=len(context.split()),
        needle_position=0.5,
        metadata={"answers": answers, "num_needles": num_needles},
    )


def generate_multi_key(context_length: int, num_keys: int = 4) -> RulerTestCase:
    """Generate a Multi-Key NIAH test case with key-value pairs to track."""
    keys = ["Project Alpha", "Operation Beta", "Initiative Gamma", "Program Delta", "Task Epsilon"][
        :num_keys
    ]
    values = {}
    needles = []

    for key in keys:
        code = "".join(random.choices(string.ascii_uppercase, k=4))
        values[key] = code
        needles.append(f"ACCESS CODE: {key} requires code {code}.")

    # Generate haystack and insert
    filler = generate_filler_text(context_length)
    context = filler
    for i, needle in enumerate(needles):
        pos = (i + 1) / (num_keys + 1)
        context = insert_needle_at_position(context, needle, pos)

    # Ask about a random key
    query_key = random.choice(keys)

    return RulerTestCase(
        task_id=f"multi_key_{context_length}_{num_keys}",
        task_type="multi_key",
        context=context,
        question=f"What is the access code for {query_key}?",
        expected_answer=values[query_key],
        context_length=len(context.split()),
        needle_position=0.5,
        metadata={"all_values": values, "query_key": query_key},
    )


def generate_test_suite(context_lengths: list[int]) -> list[RulerTestCase]:
    """Generate a full test suite."""
    tests = []

    for length in context_lengths:
        # Single NIAH at different positions
        for pos in [0.1, 0.5, 0.9]:  # Beginning, middle, end
            tests.append(generate_single_niah(length, pos))

        # Multi NIAH
        tests.append(generate_multi_niah(length, num_needles=3))

        # Multi Key
        tests.append(generate_multi_key(length, num_keys=4))

    return tests


# ============================================================================
# EVALUATION
# ============================================================================


def evaluate_response(test_case: RulerTestCase, response: str) -> bool:
    """Check if the response contains the expected answer."""
    response_lower = response.lower()
    expected_lower = test_case.expected_answer.lower()

    # For single NIAH, check if the number/code is in the response
    if test_case.task_type == "single_niah":
        return expected_lower in response_lower

    # For multi NIAH, check if all answers are present
    if test_case.task_type == "multi_niah":
        answers = test_case.metadata.get("answers", {})
        return all(str(v).lower() in response_lower for v in answers.values())

    # For multi key, check if the correct code is in response
    if test_case.task_type == "multi_key":
        return expected_lower in response_lower

    return False


# ============================================================================
# BENCHMARK RUNNER
# ============================================================================


async def run_test_case(
    agent: CascadeAgent, test_case: RulerTestCase, verbose: bool = False
) -> dict[str, Any]:
    """Run a single test case and return results."""
    start_time = time.time()

    # Build the prompt
    prompt = f"""Document:
{test_case.context}

Question: {test_case.question}

Answer the question based only on the information provided in the document above. Be concise and specific."""

    try:
        result = await agent.run(prompt, max_tokens=200)
        latency_ms = (time.time() - start_time) * 1000

        correct = evaluate_response(test_case, result.content)

        return {
            "task_id": test_case.task_id,
            "task_type": test_case.task_type,
            "context_length": test_case.context_length,
            "needle_position": test_case.needle_position,
            "correct": correct,
            "draft_accepted": result.draft_accepted,
            "model_used": result.model_used,
            "cost": result.total_cost,
            "latency_ms": latency_ms,
            "response": result.content[:200],
            "expected": test_case.expected_answer,
        }
    except Exception as e:
        return {
            "task_id": test_case.task_id,
            "task_type": test_case.task_type,
            "context_length": test_case.context_length,
            "needle_position": test_case.needle_position,
            "correct": False,
            "draft_accepted": False,
            "error": str(e),
            "cost": 0,
            "latency_ms": 0,
        }


async def run_benchmark(
    config: dict = None, sample_size: int = None, full: bool = False, verbose: bool = False
) -> dict[str, Any]:
    """Run the RULER benchmark."""
    config = config or DEFAULT_CONFIG

    # Determine context lengths
    if full:
        context_lengths = [1000, 2000, 4000, 8000]
    elif sample_size:
        context_lengths = [1000, 2000][:sample_size]
    else:
        context_lengths = config.get("context_lengths", [1000, 2000])

    # Generate test cases
    test_cases = generate_test_suite(context_lengths)

    if sample_size and sample_size < len(test_cases):
        test_cases = random.sample(test_cases, sample_size)

    print("=" * 70)
    print("RULER-STYLE LONG CONTEXT BENCHMARK")
    print("=" * 70)
    print("\nConfiguration:")
    print(f"  Drafter:  {config['drafter']}")
    print(f"  Verifier: {config['verifier']}")
    print(f"  Threshold: {config['threshold']}")
    print(f"  Context Lengths: {context_lengths}")
    print(f"  Tasks: {len(test_cases)}")
    print()

    # Create agent
    agent = CascadeAgent(
        models=[
            ModelConfig(name=config["drafter"], provider="openai", cost=0.00015),
            ModelConfig(name=config["verifier"], provider="openai", cost=0.0025),
        ],
        enable_domain_detection=True,
        use_semantic_domains=True,
    )

    # Run tests
    results = []
    for i, test_case in enumerate(test_cases, 1):
        result = await run_test_case(agent, test_case, verbose)
        results.append(result)

        # Progress indicator
        status = "✓" if result["correct"] else "✗"
        model_ind = "[D]" if result.get("draft_accepted") else "[V]"
        print(
            f"[{i}/{len(test_cases)}] {test_case.task_id}: {status} {model_ind} | "
            f"{test_case.context_length} words | "
            f"pos={test_case.needle_position:.1f} | "
            f"${result.get('cost', 0):.4f}"
        )

    # Calculate metrics
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    drafts_accepted = sum(1 for r in results if r.get("draft_accepted", False))
    total_cost = sum(r.get("cost", 0) for r in results)

    # By task type
    by_type = {}
    for r in results:
        t = r["task_type"]
        if t not in by_type:
            by_type[t] = {"correct": 0, "total": 0, "draft_accepted": 0}
        by_type[t]["total"] += 1
        by_type[t]["correct"] += 1 if r["correct"] else 0
        by_type[t]["draft_accepted"] += 1 if r.get("draft_accepted") else 0

    # By context length
    by_length = {}
    for r in results:
        length = r["context_length"]
        bucket = f"{length//1000}K" if length >= 1000 else "<1K"
        if bucket not in by_length:
            by_length[bucket] = {"correct": 0, "total": 0, "draft_accepted": 0}
        by_length[bucket]["total"] += 1
        by_length[bucket]["correct"] += 1 if r["correct"] else 0
        by_length[bucket]["draft_accepted"] += 1 if r.get("draft_accepted") else 0

    # By needle position
    by_position = {
        "start": {"correct": 0, "total": 0},
        "middle": {"correct": 0, "total": 0},
        "end": {"correct": 0, "total": 0},
    }
    for r in results:
        pos = r.get("needle_position", 0.5)
        if pos < 0.3:
            key = "start"
        elif pos > 0.7:
            key = "end"
        else:
            key = "middle"
        by_position[key]["total"] += 1
        by_position[key]["correct"] += 1 if r["correct"] else 0

    # Print summary
    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    print("\nOverall Performance:")
    print(f"  Accuracy:         {correct/total*100:.1f}% ({correct}/{total})")
    print(f"  Draft Acceptance: {drafts_accepted/total*100:.1f}%")
    print(f"  Total Cost:       ${total_cost:.4f}")

    print("\nBy Task Type:")
    for t, stats in sorted(by_type.items()):
        acc = stats["correct"] / stats["total"] * 100
        draft = stats["draft_accepted"] / stats["total"] * 100
        print(f"  {t:15s} {acc:5.1f}% acc | {draft:5.1f}% draft | {stats['total']} tasks")

    print("\nBy Context Length:")
    for length, stats in sorted(by_length.items()):
        acc = stats["correct"] / stats["total"] * 100
        draft = stats["draft_accepted"] / stats["total"] * 100
        print(f"  {length:6s} {acc:5.1f}% acc | {draft:5.1f}% draft | {stats['total']} tasks")

    print("\nBy Needle Position:")
    for pos, stats in by_position.items():
        if stats["total"] > 0:
            acc = stats["correct"] / stats["total"] * 100
            print(f"  {pos:8s} {acc:5.1f}% acc | {stats['total']} tasks")

    print("=" * 70)

    # Save results
    output_dir = Path(__file__).parent / "ruler_results"
    output_dir.mkdir(exist_ok=True)

    summary = {
        "config": config,
        "metrics": {
            "total_tasks": total,
            "correct": correct,
            "accuracy": correct / total,
            "draft_acceptance": drafts_accepted / total,
            "total_cost": total_cost,
        },
        "by_type": {t: {"accuracy": s["correct"] / s["total"], **s} for t, s in by_type.items()},
        "by_length": {
            l: {"accuracy": s["correct"] / s["total"], **s} for l, s in by_length.items()
        },
        "results": results,
    }

    with open(output_dir / "results.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nResults saved to: {output_dir}/")

    return summary


# ============================================================================
# MAIN
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="RULER-style Long Context Benchmark")
    parser.add_argument("--sample", type=int, help="Run with N samples")
    parser.add_argument("--full", action="store_true", help="Run full benchmark")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    asyncio.run(run_benchmark(sample_size=args.sample, full=args.full, verbose=args.verbose))


if __name__ == "__main__":
    main()
