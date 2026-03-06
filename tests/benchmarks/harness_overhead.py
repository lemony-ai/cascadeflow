"""Harness decision-path overhead measurement.

Measures the CPU time of ``_evaluate_pre_call_decision`` across a variety of
model / budget / latency / energy / KPI states.  No network calls are made.
"""

from __future__ import annotations

import itertools
import statistics
import time
from dataclasses import dataclass
from typing import Any

from cascadeflow.harness.api import HarnessRunContext
from cascadeflow.harness.instrument import _evaluate_pre_call_decision
from cascadeflow.harness.pricing import OPENAI_MODEL_POOL


@dataclass(frozen=True)
class OverheadReport:
    """Summary of decision-path latency measurements."""

    iterations: int
    p50_us: float
    p95_us: float
    p99_us: float
    mean_us: float
    max_us: float
    p95_under_5ms: bool


# Representative context configurations that exercise different code paths.
_BUDGET_STATES: list[dict[str, Any]] = [
    {},  # no budget
    {"budget_max": 10.0, "cost": 0.0},  # plenty of budget
    {"budget_max": 1.0, "cost": 0.85},  # budget pressure (<20 % remaining)
    {"budget_max": 1.0, "cost": 1.0},  # budget exhausted
]

_LATENCY_STATES: list[dict[str, Any]] = [
    {},
    {"latency_max_ms": 5000.0, "latency_used_ms": 0.0},
    {"latency_max_ms": 5000.0, "latency_used_ms": 5500.0},  # over limit
]

_ENERGY_STATES: list[dict[str, Any]] = [
    {},
    {"energy_max": 100.0, "energy_used": 0.0},
    {"energy_max": 100.0, "energy_used": 110.0},  # over limit
]

_TOOL_FLAGS: list[bool] = [False, True]


def _build_ctx(**overrides: Any) -> HarnessRunContext:
    """Create a lightweight HarnessRunContext for overhead testing."""

    return HarnessRunContext(mode="enforce", **overrides)


def measure_harness_overhead(iterations: int = 1000) -> OverheadReport:
    """Run *iterations* calls to ``_evaluate_pre_call_decision`` and report timing.

    The function cycles through ``OPENAI_MODEL_POOL`` models and various budget /
    latency / energy / tool states to exercise all decision branches.  Timing is
    captured with ``time.perf_counter_ns`` for nanosecond resolution.
    """

    # Build a round-robin of (model, budget, latency, energy, has_tools) combos.
    combos = list(
        itertools.product(
            OPENAI_MODEL_POOL,
            _BUDGET_STATES,
            _LATENCY_STATES,
            _ENERGY_STATES,
            _TOOL_FLAGS,
        )
    )
    combo_cycle = itertools.cycle(combos)

    timings_ns: list[int] = []

    for _ in range(iterations):
        model, budget, latency, energy, has_tools = next(combo_cycle)
        ctx = _build_ctx(**budget, **latency, **energy)

        t0 = time.perf_counter_ns()
        _evaluate_pre_call_decision(ctx, model, has_tools)
        t1 = time.perf_counter_ns()

        timings_ns.append(t1 - t0)

    timings_us = [t / 1_000.0 for t in timings_ns]
    timings_us.sort()

    def _percentile(data: list[float], pct: float) -> float:
        idx = int(len(data) * pct / 100.0)
        idx = min(idx, len(data) - 1)
        return data[idx]

    p50 = _percentile(timings_us, 50)
    p95 = _percentile(timings_us, 95)
    p99 = _percentile(timings_us, 99)
    mean = statistics.mean(timings_us)
    max_val = timings_us[-1]

    return OverheadReport(
        iterations=iterations,
        p50_us=p50,
        p95_us=p95,
        p99_us=p99,
        mean_us=mean,
        max_us=max_val,
        p95_under_5ms=p95 < 5_000.0,
    )
