import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from typing import Optional


METRIC_THRESHOLDS: dict[str, dict[str, float]] = {
    # Count metrics are discrete and naturally noisy with stochastic model routing.
    "draft_accepted": {"max_abs_diff": 2.0, "blocking": 1.0},
    "draft_rejected": {"max_abs_diff": 2.0, "blocking": 1.0},
    # Cost should be directionally close, but token variance can be meaningful.
    "total_cost": {"max_abs_diff": 0.005, "max_rel_diff": 0.35, "blocking": 1.0},
    # Savings % is the noisiest due response-length/token variance across providers/runs.
    # Keep this as diagnostic-only, not merge-blocking.
    "savings_pct": {"max_abs_diff": 25.0, "blocking": 0.0},
}

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_DIST_ENTRY = REPO_ROOT / "packages" / "core" / "dist" / "index.mjs"


def _extract_last_float(pattern: str, output: str) -> Optional[float]:
    matches = re.findall(pattern, output, flags=re.MULTILINE)
    if not matches:
        return None
    return float(matches[-1])


def parse_stats(output: str) -> dict[str, float]:
    draft_accepted = _extract_last_float(r"Draft Accepted:\s+(\d+)", output)
    draft_rejected = _extract_last_float(r"Draft Rejected:\s+(\d+)", output)
    total_cost = _extract_last_float(r"Total Cost:\s+\$([+-]?\d+(?:\.\d+)?)", output)
    savings_pct = _extract_last_float(
        r"SAVINGS:\s+\$[+-]?\d+(?:\.\d+)?\s+\(([+-]?\d+(?:\.\d+)?)%\)",
        output,
    )

    # Fallback parser for variants that only print the "You achieved X% savings" summary line.
    if savings_pct is None:
        savings_pct = _extract_last_float(r"You achieved\s+([+-]?\d+(?:\.\d+)?)%\s+savings", output)

    if (
        draft_accepted is None
        or draft_rejected is None
        or total_cost is None
        or savings_pct is None
    ):
        raise ValueError("Unable to parse stats from output")

    return {
        "draft_accepted": draft_accepted,
        "draft_rejected": draft_rejected,
        "total_cost": total_cost,
        "savings_pct": savings_pct,
    }


def run_command(cmd: list[str]) -> str:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{REPO_ROOT}:{existing_pythonpath}" if existing_pythonpath else str(REPO_ROOT)
    )

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=900,
            cwd=str(REPO_ROOT),
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        details = {
            "status": "command_failed",
            "command": cmd,
            "returncode": exc.returncode,
            "stdout_tail": exc.stdout[-4000:] if exc.stdout else "",
            "stderr_tail": exc.stderr[-4000:] if exc.stderr else "",
        }
        raise RuntimeError(json.dumps(details, indent=2)) from exc
    except subprocess.TimeoutExpired as exc:
        details = {
            "status": "command_timeout",
            "command": cmd,
            "timeout_seconds": 900,
            "stdout_tail": (exc.stdout or "")[-4000:],
            "stderr_tail": (exc.stderr or "")[-4000:] if exc.stderr else "",
        }
        raise RuntimeError(json.dumps(details, indent=2)) from exc

    # Some scripts/loggers emit warnings to stderr; include both streams for resilient parsing.
    return f"{result.stdout}\n{result.stderr}".strip()


def ensure_typescript_build() -> None:
    if CORE_DIST_ENTRY.exists():
        return
    run_command(["pnpm", "--filter", "@cascadeflow/core", "build"])


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

    ensure_typescript_build()

    py_output = run_command([sys.executable, "examples/basic_usage.py"])
    ts_output = run_command(["npx", "tsx", "packages/core/examples/nodejs/basic-usage.ts"])

    py_stats = parse_stats(py_output)
    ts_stats = parse_stats(ts_output)
    comparisons = compare_stats(py_stats, ts_stats)

    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for key, (py_val, ts_val, abs_diff) in comparisons.items():
        metric_limits = METRIC_THRESHOLDS.get(key, {})
        max_abs = metric_limits.get("max_abs_diff")
        max_rel = metric_limits.get("max_rel_diff")
        blocking = bool(metric_limits.get("blocking", 1.0))
        rel_diff = abs_diff / max(abs(py_val), abs(ts_val), 1.0)

        exceeded = False
        reasons: list[str] = []
        if max_abs is not None and abs_diff > max_abs:
            exceeded = True
            reasons.append(f"abs_diff {abs_diff:.6f} > max_abs_diff {max_abs:.6f}")
        if max_rel is not None and rel_diff > max_rel:
            exceeded = True
            reasons.append(f"rel_diff {rel_diff:.6f} > max_rel_diff {max_rel:.6f}")

        if exceeded:
            record = {
                "metric": key,
                "python": py_val,
                "typescript": ts_val,
                "abs_diff": abs_diff,
                "rel_diff": rel_diff,
                "thresholds": metric_limits,
                "reasons": reasons,
            }
            if blocking:
                failures.append(record)
            else:
                warnings.append(record)

    result = {
        "python": py_stats,
        "typescript": ts_stats,
        "comparisons": comparisons,
        "failures": failures,
        "warnings": warnings,
        "thresholds": METRIC_THRESHOLDS,
    }
    print(json.dumps(result, indent=2))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
