import json
import os
import re
import subprocess
import sys


def parse_stats(output: str) -> dict[str, float]:
    draft_accepted = re.search(r"Draft Accepted:\s+(\d+)", output)
    draft_rejected = re.search(r"Draft Rejected:\s+(\d+)", output)
    total_cost = re.search(r"Total Cost:\s+\$(\d+\.\d+)", output)
    savings_pct = re.search(r"SAVINGS:\s+\$[\d\.]+\s+\(([-\d\.]+)%\)", output)

    if not (draft_accepted and draft_rejected and total_cost and savings_pct):
        raise ValueError("Unable to parse stats from output")

    return {
        "draft_accepted": float(draft_accepted.group(1)),
        "draft_rejected": float(draft_rejected.group(1)),
        "total_cost": float(total_cost.group(1)),
        "savings_pct": float(savings_pct.group(1)),
    }


def run_command(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout


def compare_stats(
    py: dict[str, float], ts: dict[str, float]
) -> dict[str, tuple[float, float, float]]:
    comparisons = {}
    for key in ["draft_accepted", "draft_rejected", "total_cost", "savings_pct"]:
        diff = abs(py[key] - ts[key])
        comparisons[key] = (py[key], ts[key], diff)
    return comparisons


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print(json.dumps({"status": "skipped", "reason": "OPENAI_API_KEY not set"}, indent=2))
        return 0

    py_output = run_command([sys.executable, "examples/basic_usage.py"])
    ts_output = run_command(["npx", "tsx", "packages/core/examples/nodejs/basic-usage.ts"])

    py_stats = parse_stats(py_output)
    ts_stats = parse_stats(ts_output)
    comparisons = compare_stats(py_stats, ts_stats)

    tolerance = 0.05
    failures = []
    for key, (py_val, ts_val, diff) in comparisons.items():
        denom = max(py_val, ts_val, 1.0)
        pct_diff = diff / denom
        if pct_diff > tolerance:
            failures.append(
                {"metric": key, "python": py_val, "typescript": ts_val, "diff": pct_diff}
            )

    result = {
        "python": py_stats,
        "typescript": ts_stats,
        "comparisons": comparisons,
        "failures": failures,
        "tolerance": tolerance,
    }
    print(json.dumps(result, indent=2))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
