"""Baseline management and Go/No-Go gate evaluation.

Saves and loads benchmark baselines as JSON, computes per-benchmark deltas,
and evaluates the four V2 Go/No-Go criteria.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Tolerance constants (module-level so tests can inspect / override)
# ---------------------------------------------------------------------------

ACCURACY_REGRESSION_TOLERANCE: float = 2.0  # percentage points
SAVINGS_REGRESSION_TOLERANCE: float = 5.0  # percentage points


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BaselineArtifact:
    """A persisted baseline snapshot."""

    metadata: dict[str, Any]
    results: dict[str, Any]


@dataclass(frozen=True)
class BenchmarkDelta:
    """Per-benchmark comparison between current and baseline."""

    benchmark: str
    accuracy_delta: float  # positive = improvement
    savings_delta: float
    accept_rate_delta: float
    latency_delta_ms: float  # positive = slower
    accuracy_regressed: bool
    savings_regressed: bool


@dataclass(frozen=True)
class ComparisonReport:
    """Aggregated comparison across all benchmarks."""

    deltas: list[BenchmarkDelta]
    any_accuracy_regression: bool
    any_savings_regression: bool


@dataclass(frozen=True)
class GoNoGoResult:
    """Result of the four-gate V2 readiness check."""

    observe_zero_change: bool
    overhead_under_5ms: bool
    no_accuracy_regression: bool
    no_savings_regression: bool
    overall: bool
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_baseline(
    results: dict[str, Any],
    metadata: dict[str, Any],
    path: Path,
) -> Path:
    """Write *results* + *metadata* as a baseline JSON file."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"metadata": metadata, "results": results}
    path.write_text(json.dumps(payload, indent=2))
    return path


def load_baseline(path: Path) -> BaselineArtifact:
    """Load a previously saved baseline."""

    raw = json.loads(Path(path).read_text())
    return BaselineArtifact(metadata=raw["metadata"], results=raw["results"])


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

_RESULT_KEYS = ("accuracy", "savings_pct", "accept_rate", "avg_latency_ms")


def compare_to_baseline(
    current: dict[str, Any],
    baseline: dict[str, Any],
) -> ComparisonReport:
    """Compute per-benchmark deltas between *current* and *baseline*."""

    deltas: list[BenchmarkDelta] = []

    all_benchmarks = set(current) | set(baseline)
    for name in sorted(all_benchmarks):
        cur = current.get(name, {})
        base = baseline.get(name, {})
        if not cur or not base:
            continue

        acc_delta = cur.get("accuracy", 0.0) - base.get("accuracy", 0.0)
        sav_delta = cur.get("savings_pct", 0.0) - base.get("savings_pct", 0.0)
        ar_delta = cur.get("accept_rate", 0.0) - base.get("accept_rate", 0.0)
        lat_delta = cur.get("avg_latency_ms", 0.0) - base.get("avg_latency_ms", 0.0)

        deltas.append(
            BenchmarkDelta(
                benchmark=name,
                accuracy_delta=acc_delta,
                savings_delta=sav_delta,
                accept_rate_delta=ar_delta,
                latency_delta_ms=lat_delta,
                accuracy_regressed=acc_delta < -ACCURACY_REGRESSION_TOLERANCE,
                savings_regressed=sav_delta < -SAVINGS_REGRESSION_TOLERANCE,
            )
        )

    return ComparisonReport(
        deltas=deltas,
        any_accuracy_regression=any(d.accuracy_regressed for d in deltas),
        any_savings_regression=any(d.savings_regressed for d in deltas),
    )


# ---------------------------------------------------------------------------
# Go / No-Go
# ---------------------------------------------------------------------------


def check_go_nogo(
    comparison: Optional[ComparisonReport],
    overhead_p95_us: float,
    observe_all_passed: bool,
) -> GoNoGoResult:
    """Evaluate the four V2 readiness gates.

    Args:
        comparison: Baseline comparison (may be ``None`` when no baseline exists).
        overhead_p95_us: Harness decision overhead p95 in *microseconds*.
        observe_all_passed: Whether observe-mode validation passed all cases.

    Returns:
        A ``GoNoGoResult`` with individual gate flags and ``overall``.
    """

    observe_ok = observe_all_passed
    overhead_ok = overhead_p95_us < 5_000.0  # 5 ms = 5 000 us

    if comparison is not None:
        acc_ok = not comparison.any_accuracy_regression
        sav_ok = not comparison.any_savings_regression
    else:
        # No baseline → cannot fail these gates.
        acc_ok = True
        sav_ok = True

    overall = observe_ok and overhead_ok and acc_ok and sav_ok

    return GoNoGoResult(
        observe_zero_change=observe_ok,
        overhead_under_5ms=overhead_ok,
        no_accuracy_regression=acc_ok,
        no_savings_regression=sav_ok,
        overall=overall,
        details={
            "overhead_p95_us": overhead_p95_us,
            "accuracy_tolerance": ACCURACY_REGRESSION_TOLERANCE,
            "savings_tolerance": SAVINGS_REGRESSION_TOLERANCE,
        },
    )
