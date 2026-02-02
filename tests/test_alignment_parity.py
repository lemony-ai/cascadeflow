import json
import subprocess
from pathlib import Path

import pytest

from cascadeflow.quality.alignment_scorer import QueryResponseAlignmentScorer


def _build_long_context_question() -> str:
    context = "word " * 310
    return f"{context}\nQuestion: Based on the document, is the answer YES or NO?"


@pytest.mark.parametrize(
    "cases",
    [
        [
            {
                "id": "classification",
                "query": (
                    "Classify the intent. Available intents: billing, tech_support. "
                    "Output the exact intent in the format 'Intent: <intent>'."
                ),
                "response": "Intent: billing",
                "difficulty": 0.3,
            },
            {
                "id": "long_context",
                "query": _build_long_context_question(),
                "response": "YES",
                "difficulty": 0.6,
            },
            {
                "id": "function_call",
                "query": (
                    "You have access to the following tools:\n"
                    "- get_weather: Returns weather for a city.\n"
                    "Call the function when needed. Respond with Tool and Parameters."
                ),
                "response": 'Tool: get_weather\nParameters: {"location": "Paris"}',
                "difficulty": 0.5,
            },
        ]
    ],
)
def test_alignment_parity(cases, tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    tsx_path = repo_root / "node_modules" / ".bin" / "tsx"
    if not tsx_path.exists():
        pytest.skip("tsx not available to run TypeScript parity checks")

    cases_path = tmp_path / "alignment_cases.json"
    cases_path.write_text(json.dumps(cases, indent=2))

    result = subprocess.run(
        [str(tsx_path), "scripts/alignment-parity.ts", str(cases_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    ts_scores = {item["id"]: item["score"] for item in payload["results"]}

    scorer = QueryResponseAlignmentScorer()
    for case in cases:
        py_score = scorer.score(case["query"], case["response"], case.get("difficulty", 0.5))
        ts_score = ts_scores[case["id"]]
        assert abs(py_score - ts_score) <= 0.05
