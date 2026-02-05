"""
Full HumanEval Benchmark for CascadeFlow Code Generation.

This script:
1. Downloads the HumanEval dataset (164 Python problems)
2. Runs cascade benchmarking with code execution validation
3. Measures pass@1 accuracy and cost savings
4. Outputs detailed results per problem

Usage:
    python tests/benchmarks/humaneval_full_benchmark.py --sample 20    # Run 20 problems
    python tests/benchmarks/humaneval_full_benchmark.py --full         # Run all 164 problems
"""

import asyncio
import json
import os
import re
import sys
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Optional
from urllib.request import urlopen

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cascadeflow import CascadeAgent, DomainConfig, ModelConfig
from tests.benchmarks.utils import resolve_model_cost, resolve_model_pair, resolve_model_provider

# HumanEval dataset URL
HUMANEVAL_URL = "https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz"
HUMANEVAL_CACHE_FILE = Path(__file__).parent / "humaneval_cache.json"


def download_humaneval() -> list[dict]:
    """Download and parse HumanEval dataset."""
    if HUMANEVAL_CACHE_FILE.exists():
        print(f"Loading cached HumanEval from {HUMANEVAL_CACHE_FILE}")
        with open(HUMANEVAL_CACHE_FILE) as f:
            return json.load(f)

    print("Downloading HumanEval dataset...")
    import gzip

    try:
        with urlopen(HUMANEVAL_URL) as response:
            compressed = response.read()

        decompressed = gzip.decompress(compressed).decode("utf-8")
        problems = [json.loads(line) for line in decompressed.strip().split("\n") if line]

        # Cache for future runs
        with open(HUMANEVAL_CACHE_FILE, "w") as f:
            json.dump(problems, f, indent=2)

        print(f"Downloaded and cached {len(problems)} problems")
        return problems
    except Exception as e:
        print(f"Error downloading HumanEval: {e}")
        # Fallback: create a small test set
        return create_fallback_problems()


def create_fallback_problems() -> list[dict]:
    """Create a small fallback test set if download fails."""
    return [
        {
            "task_id": "HumanEval/0",
            "prompt": 'from typing import List\n\n\ndef has_close_elements(numbers: List[float], threshold: float) -> bool:\n    """ Check if in given list of numbers, are any two numbers closer to each other than\n    given threshold.\n    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)\n    False\n    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)\n    True\n    """\n',
            "canonical_solution": "    for idx, elem in enumerate(numbers):\n        for idx2, elem2 in enumerate(numbers):\n            if idx != idx2:\n                distance = abs(elem - elem2)\n                if distance < threshold:\n                    return True\n\n    return False\n",
            "test": "def check(candidate):\n    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) == True\n    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05) == False\n    assert candidate([1.0, 2.0, 5.9, 4.0, 5.0], 0.95) == True\n    assert candidate([1.0, 2.0, 5.9, 4.0, 5.0], 0.8) == False\n    assert candidate([1.0, 2.0, 3.0, 4.0, 5.0], 2.0) == True\n    assert candidate([1.1, 2.2, 3.1, 4.1, 5.1], 1.0) == True\n    assert candidate([1.1, 2.2, 3.1, 4.1, 5.1], 0.5) == False\n",
            "entry_point": "has_close_elements",
        },
        {
            "task_id": "HumanEval/1",
            "prompt": "from typing import List\n\n\ndef separate_paren_groups(paren_string: str) -> List[str]:\n    \"\"\" Input to this function is a string containing multiple groups of nested parentheses. Your goal is to\n    separate those group into separate strings and return the list of those.\n    Separate groups are balanced (each open brace is properly closed) and not nested within each other\n    Ignore any spaces in the input string.\n    >>> separate_paren_groups('( ) (( )) (( )( ))')\n    ['()', '(())', '(()())']\n    \"\"\"\n",
            "canonical_solution": "    result = []\n    current_string = []\n    current_depth = 0\n\n    for c in paren_string:\n        if c == '(':\n            current_depth += 1\n            current_string.append(c)\n        elif c == ')':\n            current_depth -= 1\n            current_string.append(c)\n\n            if current_depth == 0:\n                result.append(''.join(current_string))\n                current_string = []\n\n    return result\n",
            "test": "def check(candidate):\n    assert candidate('(()()) ((())) () ((())()())') == [\n        '(()())', '((()))', '()', '((())()())'\n    ]\n    assert candidate('() (()) ((())) (((())))') == [\n        '()', '(())', '((()))', '(((())))'\n    ]\n    assert candidate('(()(()))') == ['(()(()))']\n",
            "entry_point": "separate_paren_groups",
        },
        {
            "task_id": "HumanEval/2",
            "prompt": '\n\ndef truncate_number(number: float) -> float:\n    """ Given a positive floating point number, it can be decomposed into\n    and integer part (largest integer smaller than given number) and decimals\n    (leftover part always smaller than 1).\n\n    Return the decimal part of the number.\n    >>> truncate_number(3.5)\n    0.5\n    """\n',
            "canonical_solution": "    return number % 1.0\n",
            "test": "def check(candidate):\n    assert candidate(3.5) == 0.5\n    assert abs(candidate(1.33) - 0.33) < 1e-6\n    assert abs(candidate(123.456) - 0.456) < 1e-6\n",
            "entry_point": "truncate_number",
        },
    ]


@dataclass
class BenchmarkResult:
    """Single problem benchmark result."""

    task_id: str
    passed: bool
    draft_accepted: bool
    cost: float
    latency_ms: float
    error: Optional[str] = None
    generated_code: str = ""


@contextmanager
def time_limit(seconds: float):
    """Context manager for execution timeout."""
    import signal

    def signal_handler(signum, frame):
        raise TimeoutError("Execution timed out")

    # Only use signal on Unix
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(int(seconds))
        try:
            yield
        finally:
            signal.alarm(0)
    else:
        # Windows fallback - no timeout
        yield


def extract_code(response: str, prompt: str, entry_point: str) -> str:
    """Extract the function implementation from model response."""
    # Clean response
    response = response.strip()

    # Get imports from prompt
    imports = "\n".join(
        line
        for line in prompt.split("\n")
        if line.startswith("from ") or line.startswith("import ")
    )

    # Strategy 1: Look for code block with full function
    code_block_patterns = [
        r"```python\n(.*?)```",
        r"```\n(.*?)```",
    ]

    for pattern in code_block_patterns:
        match = re.search(pattern, response, re.DOTALL)
        if match:
            code = match.group(1).strip()
            # If code block contains the function definition
            if f"def {entry_point}" in code:
                if imports and not any(code.startswith(imp) for imp in ["from ", "import "]):
                    return imports + "\n\n" + code
                return code

    # Strategy 2: Response contains full function definition
    if f"def {entry_point}" in response:
        # Find the function definition and body
        match = re.search(
            r"(def\s+"
            + re.escape(entry_point)
            + r"\s*\([^)]*\)[^:]*:.*?)(?=\n(?:def\s|class\s|[^\s\n])|\Z)",
            response,
            re.DOTALL,
        )
        if match:
            func_code = match.group(1).rstrip()
            if imports:
                return imports + "\n\n" + func_code
            return func_code

    # Strategy 3: Response is just the function body (indented code)
    # Model was asked to return only the body, need to combine with prompt
    lines = response.split("\n")
    first_non_empty = next((l for l in lines if l.strip()), "")

    if first_non_empty.startswith("    ") or first_non_empty.startswith("\t"):
        # Response is indented - it's function body
        # Ensure prompt ends with newline
        combined = prompt.rstrip("\n") + "\n" + response
        return combined

    # Strategy 4: Response is unindented code that needs the signature prepended
    # This happens when model returns "return x + y" without indentation
    if not first_non_empty.startswith("def "):
        # Extract function signature from prompt
        sig_match = re.search(r"(def\s+" + re.escape(entry_point) + r"\s*\([^)]*\)[^:]*:)", prompt)
        if sig_match:
            signature = sig_match.group(1)
            # Indent the response
            indented_body = "\n".join(
                "    " + line if line.strip() else line for line in response.split("\n")
            )
            if imports:
                return imports + "\n\n" + signature + "\n" + indented_body
            return signature + "\n" + indented_body

    # Fallback: combine prompt and response
    combined = prompt.rstrip("\n") + "\n" + response
    return combined


def execute_test(
    code: str, test: str, entry_point: str, timeout: float = 5.0
) -> tuple[bool, Optional[str]]:
    """Execute code with test cases and return (passed, error_message)."""
    # Prepare full code
    full_code = code + "\n\n" + test + f"\n\ncheck({entry_point})"

    # Create isolated namespace
    namespace = {}

    try:
        with time_limit(timeout):
            exec(full_code, namespace)
        return True, None
    except TimeoutError:
        return False, "Execution timed out"
    except AssertionError as e:
        return False, f"Assertion failed: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


class HumanEvalBenchmark:
    """HumanEval benchmark runner with CascadeFlow integration."""

    def __init__(
        self,
        drafter_model: str = "gpt-4o-mini",
        verifier_model: str = "claude-opus-4-5-20251101",
        quality_threshold: float = 0.50,
    ):
        self.drafter_model = drafter_model
        self.verifier_model = verifier_model
        self.quality_threshold = quality_threshold
        self.problems = download_humaneval()
        self.results: list[BenchmarkResult] = []

    def create_prompt(self, problem: dict) -> str:
        """Create a code generation prompt."""
        prompt = problem["prompt"]
        entry_point = problem["entry_point"]

        return f"""Complete the following Python function. Return the COMPLETE function including the signature and imports.

{prompt}

Important:
- Return the COMPLETE function starting with the 'def' statement
- Include any necessary imports at the top
- Do not include any explanation, markdown code blocks, or extra text
- Just return the Python code directly
- The function should handle all edge cases from the docstring examples"""

    async def run_single(self, problem: dict) -> BenchmarkResult:
        """Run benchmark on a single problem."""
        task_id = problem["task_id"]
        prompt = self.create_prompt(problem)
        entry_point = problem["entry_point"]
        test = problem["test"]
        original_prompt = problem["prompt"]

        # Create CascadeFlow agent with code domain config
        drafter_provider = resolve_model_provider(self.drafter_model)
        verifier_provider = resolve_model_provider(self.verifier_model)
        drafter_cost = resolve_model_cost(self.drafter_model, 0.00015)
        verifier_cost = resolve_model_cost(self.verifier_model, 0.015)

        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name=self.drafter_model,
                    provider=drafter_provider,
                    cost=drafter_cost,
                ),
                ModelConfig(
                    name=self.verifier_model,
                    provider=verifier_provider,
                    cost=verifier_cost,
                ),
            ],
            enable_domain_detection=True,
            use_semantic_domains=True,
            domain_configs={
                "code": DomainConfig(
                    drafter=self.drafter_model,
                    verifier=self.verifier_model,
                    threshold=self.quality_threshold,
                    temperature=0.2,
                    cascade_complexities=["trivial", "simple", "moderate", "hard", "expert"],
                ),
            },
        )

        start_time = time.time()

        try:
            result = await agent.run(prompt, max_tokens=1000)
            latency_ms = (time.time() - start_time) * 1000

            # Extract code from response
            code = extract_code(result.content, original_prompt, entry_point)

            # Execute tests
            passed, error = execute_test(code, test, entry_point)

            draft_accepted = result.metadata.get("draft_accepted", False)

            return BenchmarkResult(
                task_id=task_id,
                passed=passed,
                draft_accepted=draft_accepted,
                cost=result.total_cost,
                latency_ms=latency_ms,
                error=error,
                generated_code=code[:500],  # Truncate for storage
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return BenchmarkResult(
                task_id=task_id,
                passed=False,
                draft_accepted=False,
                cost=0.0,
                latency_ms=latency_ms,
                error=f"Generation error: {e}",
            )

    async def run_benchmark(
        self,
        max_problems: Optional[int] = None,
        verbose: bool = True,
    ) -> dict:
        """Run full benchmark."""
        problems = self.problems[:max_problems] if max_problems else self.problems

        print("=" * 70)
        print("HUMANEVAL BENCHMARK")
        print("=" * 70)
        print("\nConfiguration:")
        print(f"  Drafter:  {self.drafter_model}")
        print(f"  Verifier: {self.verifier_model}")
        print(f"  Threshold: {self.quality_threshold}")
        print(f"  Problems: {len(problems)}")
        print()
        print("Running benchmark...\n")

        self.results = []

        for i, problem in enumerate(problems):
            task_id = problem["task_id"]
            short_id = task_id.split("/")[-1]

            result = await self.run_single(problem)
            self.results.append(result)

            # Progress output
            status = "✓" if result.passed else "✗"
            route = "[D]" if result.draft_accepted else "[V]"

            if verbose:
                print(
                    f"[{i+1}/{len(problems)}] {short_id}: {status} {route} | Cost: ${result.cost:.4f} | {result.latency_ms:.0f}ms",
                    end="",
                )
                if result.error and not result.passed:
                    print(f" | {result.error[:50]}")
                else:
                    print()

        # Calculate metrics
        return self._calculate_metrics(problems)

    def _calculate_metrics(self, problems: list) -> dict:
        """Calculate benchmark metrics."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        draft_accepted = sum(1 for r in self.results if r.draft_accepted)
        total_cost = sum(r.cost for r in self.results)

        # Baseline cost (verifier only)
        baseline_cost = total * 0.02  # Rough estimate

        pass_rate = passed / total if total > 0 else 0
        draft_rate = draft_accepted / total if total > 0 else 0
        savings = (baseline_cost - total_cost) / baseline_cost if baseline_cost > 0 else 0

        metrics = {
            "total_problems": total,
            "passed": passed,
            "pass_rate": pass_rate,
            "draft_acceptance": draft_rate,
            "total_cost": total_cost,
            "baseline_cost": baseline_cost,
            "cost_savings": savings,
        }

        # Print summary
        print("\n" + "=" * 70)
        print("BENCHMARK SUMMARY")
        print("=" * 70)
        print("\nAccuracy:")
        print(f"  Pass@1: {pass_rate:.1%} ({passed}/{total})")
        print("\nCascade Performance:")
        print(f"  Draft Acceptance: {draft_rate:.1%}")
        print(f"  Total Cost: ${total_cost:.4f}")
        print(f"  Baseline Cost: ${baseline_cost:.4f}")
        print(f"  Cost Savings: {savings:.1%}")
        print()

        # Breakdown by pass/fail
        passed_results = [r for r in self.results if r.passed]
        failed_results = [r for r in self.results if not r.passed]

        if passed_results:
            passed_draft = sum(1 for r in passed_results if r.draft_accepted) / len(passed_results)
            print(f"Passed problems ({len(passed_results)}):")
            print(f"  Draft acceptance: {passed_draft:.1%}")

        if failed_results:
            failed_draft = sum(1 for r in failed_results if r.draft_accepted) / len(failed_results)
            print(f"Failed problems ({len(failed_results)}):")
            print(f"  Draft acceptance: {failed_draft:.1%}")
            print("  Common errors:")
            errors = {}
            for r in failed_results:
                err_type = r.error.split(":")[0] if r.error else "Unknown"
                errors[err_type] = errors.get(err_type, 0) + 1
            for err, count in sorted(errors.items(), key=lambda x: -x[1])[:5]:
                print(f"    {err}: {count}")

        print("=" * 70)

        return metrics


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="HumanEval Benchmark for CascadeFlow")
    parser.add_argument("--sample", type=int, help="Run on N problems (default: all)")
    parser.add_argument("--full", action="store_true", help="Run all 164 problems")
    default_drafter, default_verifier = resolve_model_pair(
        "gpt-4o-mini", "claude-opus-4-5-20251101"
    )
    parser.add_argument("--drafter", type=str, default=default_drafter, help="Drafter model")
    parser.add_argument("--verifier", type=str, default=default_verifier, help="Verifier model")
    parser.add_argument("--threshold", type=float, default=0.50, help="Quality threshold")

    args = parser.parse_args()

    max_problems = None
    if args.sample:
        max_problems = args.sample
    elif not args.full:
        max_problems = 20  # Default to 20 for quick test

    benchmark = HumanEvalBenchmark(
        drafter_model=args.drafter,
        verifier_model=args.verifier,
        quality_threshold=args.threshold,
    )

    results = await benchmark.run_benchmark(max_problems=max_problems)

    # Save results
    output_dir = Path(__file__).parent / "humaneval_results"
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "results.json", "w") as f:
        json.dump(
            {
                "config": {
                    "drafter": args.drafter,
                    "verifier": args.verifier,
                    "threshold": args.threshold,
                },
                "metrics": results,
                "results": [
                    {
                        "task_id": r.task_id,
                        "passed": r.passed,
                        "draft_accepted": r.draft_accepted,
                        "cost": r.cost,
                        "latency_ms": r.latency_ms,
                        "error": r.error,
                    }
                    for r in benchmark.results
                ],
            },
            f,
            indent=2,
        )

    print(f"\nResults saved to: {output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
