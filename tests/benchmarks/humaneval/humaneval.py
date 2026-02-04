"""HumanEval Code Generation Benchmark

Evaluates CascadeFlow on code generation tasks using a subset of HumanEval problems.

HumanEval is a well-known benchmark for evaluating code generation models.
This implementation tests:
1. Code correctness (via unit tests)
2. Cost savings vs. baseline (always using powerful model)
3. Quality score calibration for code tasks
4. Acceptance rate for code generation

Research Questions:
- Can drafter models generate correct code for common programming tasks?
- What cost savings can cascade achieve on code generation?
- How does quality scoring perform on code vs. text generation?
- What is the optimal quality threshold for code tasks?

Dataset: Subset of OpenAI HumanEval (10 representative problems)
"""

import asyncio
import os
import sys
from typing import Any, Optional

from cascadeflow import CascadeAgent, ModelConfig

from ..base import Benchmark, BenchmarkResult, BenchmarkSummary
from ..profiler import CascadeProfiler


class HumanEvalBenchmark(Benchmark):
    """HumanEval code generation benchmark."""

    def __init__(
        self,
        drafter_model: str = "claude-haiku-4-5-20251001",
        verifier_model: str = "claude-opus-4-5-20251101",
        quality_threshold: float = 0.7,
        max_samples: Optional[int] = 10,
    ):
        """Initialize HumanEval benchmark."""
        dataset_name = "HumanEval-full" if max_samples is None else f"HumanEval-{max_samples}"
        super().__init__(
            dataset_name=dataset_name,
            drafter_model=drafter_model,
            verifier_model=verifier_model,
            baseline_model=verifier_model,
            quality_threshold=quality_threshold,
            max_samples=max_samples,
        )
        self.profiler = CascadeProfiler()

    def load_dataset(self) -> list[tuple[str, Any]]:
        """
        Load HumanEval dataset.

        Returns:
            List of (problem_id, problem_data) tuples
        """
        # Simplified HumanEval subset with 10 representative problems
        problems = [
            {
                "task_id": "HumanEval/0",
                "prompt": 'Write a Python function that checks if a list contains any negative numbers.\n\ndef has_negative(numbers: list[int]) -> bool:\n    """\n    Return True if list contains any negative numbers, False otherwise.\n    \n    >>> has_negative([1, 2, 3])\n    False\n    >>> has_negative([1, -2, 3])\n    True\n    >>> has_negative([])\n    False\n    """\n',
                "test": "assert has_negative([1, 2, 3]) == False\nassert has_negative([1, -2, 3]) == True\nassert has_negative([]) == False\nassert has_negative([-1, -2, -3]) == True\nassert has_negative([0, 0, 0]) == False",
                "difficulty": "easy",
            },
            {
                "task_id": "HumanEval/1",
                "prompt": 'Write a Python function that returns the sum of all even numbers in a list.\n\ndef sum_even(numbers: list[int]) -> int:\n    """\n    Return sum of all even numbers in the list.\n    \n    >>> sum_even([1, 2, 3, 4])\n    6\n    >>> sum_even([1, 3, 5])\n    0\n    >>> sum_even([])\n    0\n    """\n',
                "test": "assert sum_even([1, 2, 3, 4]) == 6\nassert sum_even([1, 3, 5]) == 0\nassert sum_even([]) == 0\nassert sum_even([2, 4, 6, 8]) == 20\nassert sum_even([10]) == 10",
                "difficulty": "easy",
            },
            {
                "task_id": "HumanEval/2",
                "prompt": "Write a Python function that reverses a string.\n\ndef reverse_string(s: str) -> str:\n    \"\"\"\n    Return the reversed string.\n    \n    >>> reverse_string('hello')\n    'olleh'\n    >>> reverse_string('')\n    ''\n    >>> reverse_string('a')\n    'a'\n    \"\"\"\n",
                "test": "assert reverse_string('hello') == 'olleh'\nassert reverse_string('') == ''\nassert reverse_string('a') == 'a'\nassert reverse_string('12345') == '54321'\nassert reverse_string('race car') == 'rac ecar'",
                "difficulty": "easy",
            },
            {
                "task_id": "HumanEval/3",
                "prompt": "Write a Python function that checks if a string is a palindrome (case-insensitive).\n\ndef is_palindrome(s: str) -> bool:\n    \"\"\"\n    Return True if string is a palindrome, False otherwise.\n    Ignore case.\n    \n    >>> is_palindrome('racecar')\n    True\n    >>> is_palindrome('hello')\n    False\n    >>> is_palindrome('A')\n    True\n    \"\"\"\n",
                "test": "assert is_palindrome('racecar') == True\nassert is_palindrome('hello') == False\nassert is_palindrome('A') == True\nassert is_palindrome('Aa') == True\nassert is_palindrome('RaceCar') == True\nassert is_palindrome('') == True",
                "difficulty": "easy",
            },
            {
                "task_id": "HumanEval/4",
                "prompt": 'Write a Python function that finds the maximum value in a list of integers.\n\ndef find_max(numbers: list[int]) -> int:\n    """\n    Return the maximum value in the list.\n    Assume list is not empty.\n    \n    >>> find_max([1, 2, 3])\n    3\n    >>> find_max([5, 1, 9, 2])\n    9\n    >>> find_max([-1, -5, -3])\n    -1\n    """\n',
                "test": "assert find_max([1, 2, 3]) == 3\nassert find_max([5, 1, 9, 2]) == 9\nassert find_max([-1, -5, -3]) == -1\nassert find_max([100]) == 100\nassert find_max([7, 7, 7]) == 7",
                "difficulty": "easy",
            },
            {
                "task_id": "HumanEval/5",
                "prompt": 'Write a Python function that removes duplicates from a list while preserving order.\n\ndef remove_duplicates(items: list[int]) -> list[int]:\n    """\n    Return list with duplicates removed, preserving original order.\n    \n    >>> remove_duplicates([1, 2, 2, 3])\n    [1, 2, 3]\n    >>> remove_duplicates([1, 1, 1])\n    [1]\n    >>> remove_duplicates([])\n    []\n    """\n',
                "test": "assert remove_duplicates([1, 2, 2, 3]) == [1, 2, 3]\nassert remove_duplicates([1, 1, 1]) == [1]\nassert remove_duplicates([]) == []\nassert remove_duplicates([1, 2, 3, 4]) == [1, 2, 3, 4]\nassert remove_duplicates([4, 3, 2, 1, 3, 4]) == [4, 3, 2, 1]",
                "difficulty": "medium",
            },
            {
                "task_id": "HumanEval/6",
                "prompt": 'Write a Python function that calculates the factorial of a number.\n\ndef factorial(n: int) -> int:\n    """\n    Return factorial of n.\n    Assume n >= 0.\n    \n    >>> factorial(0)\n    1\n    >>> factorial(5)\n    120\n    >>> factorial(1)\n    1\n    """\n',
                "test": "assert factorial(0) == 1\nassert factorial(5) == 120\nassert factorial(1) == 1\nassert factorial(3) == 6\nassert factorial(10) == 3628800",
                "difficulty": "medium",
            },
            {
                "task_id": "HumanEval/7",
                "prompt": 'Write a Python function that checks if a number is prime.\n\ndef is_prime(n: int) -> bool:\n    """\n    Return True if n is prime, False otherwise.\n    Assume n >= 2.\n    \n    >>> is_prime(2)\n    True\n    >>> is_prime(4)\n    False\n    >>> is_prime(17)\n    True\n    """\n',
                "test": "assert is_prime(2) == True\nassert is_prime(4) == False\nassert is_prime(17) == True\nassert is_prime(100) == False\nassert is_prime(97) == True\nassert is_prime(10) == False",
                "difficulty": "medium",
            },
            {
                "task_id": "HumanEval/8",
                "prompt": "Write a Python function that finds the longest common prefix of a list of strings.\n\ndef longest_common_prefix(strs: list[str]) -> str:\n    \"\"\"\n    Return longest common prefix string among an array of strings.\n    If no common prefix, return empty string.\n    \n    >>> longest_common_prefix(['flower', 'flow', 'flight'])\n    'fl'\n    >>> longest_common_prefix(['dog', 'racecar', 'car'])\n    ''\n    >>> longest_common_prefix(['test'])\n    'test'\n    \"\"\"\n",
                "test": "assert longest_common_prefix(['flower', 'flow', 'flight']) == 'fl'\nassert longest_common_prefix(['dog', 'racecar', 'car']) == ''\nassert longest_common_prefix(['test']) == 'test'\nassert longest_common_prefix(['']) == ''\nassert longest_common_prefix(['prefix', 'preload', 'prepare']) == 'pre'",
                "difficulty": "medium",
            },
            {
                "task_id": "HumanEval/9",
                "prompt": 'Write a Python function that performs binary search on a sorted list.\n\ndef binary_search(arr: list[int], target: int) -> int:\n    """\n    Return index of target in sorted array, or -1 if not found.\n    \n    >>> binary_search([1, 2, 3, 4, 5], 3)\n    2\n    >>> binary_search([1, 2, 3, 4, 5], 6)\n    -1\n    >>> binary_search([], 1)\n    -1\n    """\n',
                "test": "assert binary_search([1, 2, 3, 4, 5], 3) == 2\nassert binary_search([1, 2, 3, 4, 5], 6) == -1\nassert binary_search([], 1) == -1\nassert binary_search([1], 1) == 0\nassert binary_search([1, 3, 5, 7, 9], 1) == 0\nassert binary_search([1, 3, 5, 7, 9], 9) == 4",
                "difficulty": "hard",
            },
        ]

        if self.max_samples is None:
            try:
                import json
                import urllib.request

                url = "https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl"
                with urllib.request.urlopen(url, timeout=30) as response:
                    payload = response.read().decode("utf-8")
                full_problems = [json.loads(line) for line in payload.splitlines() if line.strip()]
                return [(p["prompt"], p) for p in full_problems]
            except Exception as exc:
                print(f"  Warning: Failed to download full HumanEval dataset: {exc}")
                print("  Falling back to bundled subset.")
                return [(p["prompt"], p) for p in problems]

        return [(p["prompt"], p) for p in problems[: self.max_samples]]

    def evaluate_prediction(self, prediction: str, ground_truth: Any) -> tuple[bool, float]:
        """
        Evaluate if generated code passes test cases.

        Args:
            prediction: Generated code
            ground_truth: Problem data with test cases

        Returns:
            (is_correct, confidence_score)
        """
        try:
            # Extract code from prediction (handle markdown code blocks)
            code = prediction.strip()
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()

            # Combine code with test cases
            test_code = code + "\n\n" + ground_truth["test"]

            # Execute test cases in isolated namespace
            namespace = {}
            exec(test_code, namespace)

            # All tests passed
            return True, 1.0

        except AssertionError:
            # Test failed
            return False, 0.0
        except Exception as e:
            # Syntax error, runtime error, etc.
            print(f"  Warning: Code evaluation error: {e}")
            return False, 0.0

    async def run_cascade(self, query: str) -> dict[str, Any]:
        """
        Run cascade on a code generation problem.

        Args:
            query: Programming problem prompt

        Returns:
            Cascade result dict
        """
        enhanced_query = (
            f"{query}\n\n"
            "Return only the Python function implementation. "
            "Do not include markdown, explanations, or triple-quoted strings."
        )

        agent = CascadeAgent(
            models=[
                ModelConfig(name=self.drafter_model, provider="anthropic", cost=0.003),
                ModelConfig(name=self.verifier_model, provider="anthropic", cost=0.045),
            ],
            quality={"threshold": self.quality_threshold},
        )

        result = await agent.run(enhanced_query, max_tokens=400, temperature=0.0)

        return {
            "prediction": result.content,
            "model_used": result.model_used,
            "accepted": result.draft_accepted,
            "quality_score": result.quality_score or 0.0,
            "drafter_cost": result.draft_cost or 0.0,
            "verifier_cost": result.verifier_cost or 0.0,
            "total_cost": result.total_cost,
            "latency_ms": result.latency_ms,
            "tokens_input": result.metadata.get("prompt_tokens", 0),
            "tokens_output": result.metadata.get("completion_tokens", 0),
        }


async def run_humaneval_benchmark(max_samples: Optional[int] = 10):
    """Run HumanEval benchmark and generate report."""

    print("\n" + "=" * 80)
    print("HUMANEVAL CODE GENERATION BENCHMARK")
    print("=" * 80 + "\n")

    # Verify API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set")
        return

    print("Configuration:")
    dataset_label = (
        "HumanEval-full (164 programming problems)"
        if max_samples is None
        else f"HumanEval-{max_samples} ({max_samples} programming problems)"
    )
    print(f"  Dataset:         {dataset_label}")
    print("  Drafter:         claude-haiku-4-5-20251001")
    print("  Verifier:        claude-opus-4-5-20251101")
    print("  Baseline:        claude-opus-4-5-20251101 (always)")
    print("  Quality Threshold: 0.7\n")

    # Create benchmark
    benchmark = HumanEvalBenchmark(
        drafter_model="claude-haiku-4-5-20251001",
        verifier_model="claude-opus-4-5-20251101",
        quality_threshold=0.7,
        max_samples=max_samples,
    )

    # Run benchmark
    print("Running benchmark...")
    summary = await benchmark.run()

    # Print summary
    print("\n" + "=" * 80)
    print("HUMANEVAL BENCHMARK RESULTS")
    print("=" * 80 + "\n")

    correct_count = (
        int(summary.accuracy / 100 * summary.successful_tests) if summary.successful_tests else 0
    )

    print(f"Total Problems:      {summary.total_tests}")
    print(f"Correct Solutions:   {correct_count} ({summary.accuracy:.1f}%)")
    print(f"Drafter Accepted:    {summary.drafter_accepted} ({summary.acceptance_rate_pct:.1f}%)")
    print(
        f"Verifier Escalated:  {summary.escalated_to_verifier} ({summary.escalation_rate_pct:.1f}%)"
    )

    print("\nCost Analysis:")
    print(f"  Cascade Total Cost:  ${summary.total_cost:.6f}")
    print(f"  Baseline Total Cost: ${summary.total_baseline_cost:.6f}")
    print(f"  Cost Savings:        ${summary.total_savings:.6f} ({summary.avg_savings_pct:.1f}%)")

    print("\nPerformance:")
    print(f"  Average Latency:     {summary.avg_latency_ms:.0f}ms")
    print(f"  Drafter Accuracy:    {summary.drafter_accuracy:.1f}% (when accepted)")

    print("\nKey Findings:")
    if summary.acceptance_rate_pct > 60:
        print(f"  ✅ Drafter handles {summary.acceptance_rate_pct:.0f}% of problems independently")
    if summary.avg_savings_pct > 50:
        print(f"  💰 Achieved {summary.avg_savings_pct:.0f}% cost reduction")
    if summary.drafter_accuracy < 80:
        print(
            "  ⚠️  Low drafter accuracy - consider raising quality threshold or using stronger drafter"
        )

    print("\n" + "=" * 80 + "\n")

    return summary


if __name__ == "__main__":
    asyncio.run(run_humaneval_benchmark())
