import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from cascadeflow.quality.alignment_scorer import QueryResponseAlignmentScorer


@dataclass
class TestCase:
    id: str
    query: str
    response: str


def build_long_context(words: int = 320) -> str:
    base = (
        "Cascadeflow is a system that routes queries across models based on quality. "
        "It tracks costs, alignment, and confidence across providers. "
        "The goal is to minimize spend while preserving accuracy. "
    )
    tokens = base.split()
    repeated = (tokens * ((words // len(tokens)) + 1))[:words]
    return " ".join(repeated)


def build_cases() -> List[TestCase]:
    long_context = build_long_context()
    return [
        TestCase(
            id="basic_fact",
            query="What is 2+2?",
            response="4",
        ),
        TestCase(
            id="mcq",
            query="Answer the following multiple-choice question: What is 2+2? A) 3 B) 4 C) 5 D) 6",
            response="B",
        ),
        TestCase(
            id="v11_classification",
            query=(
                "You are an intent classifier. Choose the correct label from the list: "
                "[transfer, balance, card]. Return only the label."
            ),
            response="transfer",
        ),
        TestCase(
            id="v12_long_context",
            query=(
                f"Context: {long_context}\n\nQuestion: Based on the text, what is the goal of cascadeflow?"
            ),
            response="The goal is to minimize spend while preserving accuracy.",
        ),
        TestCase(
            id="v13_function_call",
            query=(
                "Call the weather tool. Return a function call for get_weather with parameters: "
                "city=Boston."
            ),
            response='{"name":"get_weather","parameters":{"city":"Boston"}}',
        ),
        TestCase(
            id="v14_long_context_short_answer",
            query=(
                f"Context: {long_context}\n\nQuestion: According to the text, what is the primary goal?"
            ),
            response="accuracy",
        ),
    ]


def score_python(cases: List[TestCase]) -> Dict[str, Dict[str, Any]]:
    scorer = QueryResponseAlignmentScorer()
    results: Dict[str, Dict[str, Any]] = {}
    for test_case in cases:
        analysis = scorer.score(test_case.query, test_case.response, query_difficulty=0.5, verbose=True)
        results[test_case.id] = {
            "alignmentScore": analysis.alignment_score,
            "reasoning": analysis.reasoning,
            "features": analysis.features,
            "baselineUsed": analysis.baseline_used,
            "isTrivial": analysis.is_trivial,
        }
    return results


def score_typescript(cases: List[TestCase]) -> Dict[str, Dict[str, Any]]:
    input_path = Path("tests/e2e/_alignment_cases.json")
    payload = [
        {"id": test_case.id, "query": test_case.query, "response": test_case.response}
        for test_case in cases
    ]
    input_path.write_text(json.dumps(payload, indent=2))

    try:
        result = subprocess.run(
            ["npx", "tsx", "tests/e2e/alignment_parity.ts", str(input_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(exc.stdout)
        print(exc.stderr, file=sys.stderr)
        raise
    finally:
        if input_path.exists():
            input_path.unlink()

    parsed = json.loads(result.stdout)
    return {entry["id"]: entry for entry in parsed}


def compare_results(
    python_results: Dict[str, Dict[str, Any]],
    ts_results: Dict[str, Dict[str, Any]],
    tolerance: float = 0.05,
) -> Dict[str, Any]:
    mismatches = []
    for test_id, py_result in python_results.items():
        ts_result = ts_results.get(test_id)
        if not ts_result:
            mismatches.append({"id": test_id, "error": "missing_ts_result"})
            continue
        diff = abs(py_result["alignmentScore"] - ts_result["alignmentScore"])
        if diff > tolerance:
            mismatches.append(
                {
                    "id": test_id,
                    "python": py_result["alignmentScore"],
                    "typescript": ts_result["alignmentScore"],
                    "diff": diff,
                }
            )

    return {
        "tolerance": tolerance,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def main() -> int:
    cases = build_cases()
    python_results = score_python(cases)

    try:
        ts_results = score_typescript(cases)
    except Exception as exc:  # pragma: no cover - used in e2e script
        print(json.dumps({"error": str(exc), "stage": "typescript"}, indent=2))
        return 2

    comparison = compare_results(python_results, ts_results)
    output = {
        "cases": [case.__dict__ for case in cases],
        "python": python_results,
        "typescript": ts_results,
        "comparison": comparison,
    }
    print(json.dumps(output, indent=2))

    return 1 if comparison["mismatch_count"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
