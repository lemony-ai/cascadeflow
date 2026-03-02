"""Tests for the benchmark reproducibility pipeline.

All 15 tests use mocks — no live API calls.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from tests.benchmarks.repro import ReproMetadata, collect_repro_metadata, metadata_to_dict
from tests.benchmarks.baseline import (
    BaselineArtifact,
    BenchmarkDelta,
    ComparisonReport,
    GoNoGoResult,
    save_baseline,
    load_baseline,
    compare_to_baseline,
    check_go_nogo,
)
from tests.benchmarks.harness_overhead import OverheadReport, measure_harness_overhead
from tests.benchmarks.observe_validation import (
    ObserveValidationResult,
    validate_observe_mode,
)
from tests.benchmarks.artifact import SCHEMA_VERSION, bundle_artifact


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def sample_results() -> dict:
    """Minimal results dict matching the existing results JSON format."""
    return {
        "MMLU": {
            "accuracy": 100.0,
            "accept_rate": 30.0,
            "savings_pct": 10.68,
            "effective_savings_pct": 10.68,
            "drafter_accuracy": 100.0,
            "verifier_accuracy": 100.0,
            "total_cascade_cost": 0.017848,
            "total_baseline_cost": 0.019983,
            "avg_latency_ms": 1765.95,
            "n_total": 40,
            "n_correct": 40,
            "n_accepted": 12,
        },
        "TruthfulQA": {
            "accuracy": 86.67,
            "accept_rate": 73.33,
            "savings_pct": 43.45,
            "effective_savings_pct": 30.26,
            "drafter_accuracy": 90.91,
            "verifier_accuracy": 75.0,
            "total_cascade_cost": 0.022044,
            "total_baseline_cost": 0.038982,
            "avg_latency_ms": 4164.96,
            "n_total": 15,
            "n_correct": 13,
            "n_accepted": 11,
        },
    }


@pytest.fixture
def sample_metadata() -> dict:
    return metadata_to_dict(
        collect_repro_metadata(profile="smoke", harness_mode="off")
    )


# ── 1-2: ReproMetadata ───────────────────────────────────────────────────


def test_collect_repro_metadata():
    """All fields populated."""
    meta = collect_repro_metadata(
        profile="standard",
        drafter_model="gpt-4o-mini",
        verifier_model="gpt-4o",
        baseline_model="gpt-4o",
        harness_mode="observe",
    )
    assert isinstance(meta, ReproMetadata)
    assert meta.git_sha  # non-empty
    assert isinstance(meta.git_dirty, bool)
    assert meta.python_version
    assert meta.platform
    assert meta.cascadeflow_version
    assert meta.profile == "standard"
    assert meta.drafter_model == "gpt-4o-mini"
    assert meta.verifier_model == "gpt-4o"
    assert meta.baseline_model == "gpt-4o"
    assert meta.harness_mode == "observe"
    assert isinstance(meta.package_versions, dict)
    assert meta.run_id
    assert meta.timestamp_utc


def test_metadata_round_trip():
    """JSON serializable and round-trips."""
    meta = collect_repro_metadata()
    d = metadata_to_dict(meta)
    raw = json.dumps(d)
    loaded = json.loads(raw)
    assert loaded["run_id"] == meta.run_id
    assert loaded["python_version"] == meta.python_version
    assert loaded["package_versions"] == d["package_versions"]


# ── 3-6: Baseline persistence + comparison ───────────────────────────────


def test_save_load_baseline(tmp_path, sample_results, sample_metadata):
    """Save then load produces identical data."""
    path = tmp_path / "baselines" / "test.json"
    save_baseline(sample_results, sample_metadata, path)
    loaded = load_baseline(path)
    assert isinstance(loaded, BaselineArtifact)
    assert loaded.results == sample_results
    assert loaded.metadata == sample_metadata


def test_compare_no_regression(sample_results):
    """Identical results → zero deltas, no regressions."""
    report = compare_to_baseline(sample_results, sample_results)
    assert isinstance(report, ComparisonReport)
    assert not report.any_accuracy_regression
    assert not report.any_savings_regression
    for d in report.deltas:
        assert d.accuracy_delta == 0.0
        assert d.savings_delta == 0.0
        assert not d.accuracy_regressed
        assert not d.savings_regressed


def test_compare_with_regression(sample_results):
    """Accuracy drop flagged as regression."""
    worse = {
        name: {**vals, "accuracy": vals["accuracy"] - 5.0}
        for name, vals in sample_results.items()
    }
    report = compare_to_baseline(worse, sample_results)
    assert report.any_accuracy_regression
    for d in report.deltas:
        assert d.accuracy_delta == pytest.approx(-5.0)
        assert d.accuracy_regressed


def test_compare_with_improvement(sample_results):
    """Savings increase flagged (but not as regression)."""
    better = {
        name: {**vals, "savings_pct": vals["savings_pct"] + 10.0}
        for name, vals in sample_results.items()
    }
    report = compare_to_baseline(better, sample_results)
    assert not report.any_savings_regression
    for d in report.deltas:
        assert d.savings_delta == pytest.approx(10.0)
        assert not d.savings_regressed


# ── 7-9: Go/No-Go ────────────────────────────────────────────────────────


def test_go_nogo_all_pass(sample_results):
    """All criteria met → overall=True."""
    report = compare_to_baseline(sample_results, sample_results)
    result = check_go_nogo(report, overhead_p95_us=500.0, observe_all_passed=True)
    assert isinstance(result, GoNoGoResult)
    assert result.observe_zero_change is True
    assert result.overhead_under_5ms is True
    assert result.no_accuracy_regression is True
    assert result.no_savings_regression is True
    assert result.overall is True


def test_go_nogo_overhead_fail(sample_results):
    """p95 >5 ms → overall=False."""
    report = compare_to_baseline(sample_results, sample_results)
    result = check_go_nogo(report, overhead_p95_us=6_000.0, observe_all_passed=True)
    assert result.overhead_under_5ms is False
    assert result.overall is False


def test_go_nogo_observe_fail(sample_results):
    """Observe mismatch → overall=False."""
    report = compare_to_baseline(sample_results, sample_results)
    result = check_go_nogo(report, overhead_p95_us=500.0, observe_all_passed=False)
    assert result.observe_zero_change is False
    assert result.overall is False


# ── 10: Harness overhead ─────────────────────────────────────────────────


def test_harness_overhead_measurement():
    """100 iterations, values >0, p95 < p99 <= max."""
    report = measure_harness_overhead(iterations=100)
    assert isinstance(report, OverheadReport)
    assert report.iterations == 100
    assert report.p50_us > 0
    assert report.p95_us > 0
    assert report.p99_us > 0
    assert report.mean_us > 0
    assert report.max_us > 0
    assert report.p95_us <= report.p99_us
    assert report.p99_us <= report.max_us


# ── 11-12: Observe validation ────────────────────────────────────────────


def test_observe_validation_all_pass():
    """Default cases all pass."""
    result = validate_observe_mode()
    assert isinstance(result, ObserveValidationResult)
    assert result.all_passed, f"Failures: {result.failures}"
    assert result.total_cases > 0
    assert result.failed == 0


def test_observe_validation_detects_mutation():
    """Simulated observe-mode bug: if observe mode mutated kwargs, detection would occur.

    We patch _prepare_call_interception to inject a mutation when mode="observe",
    proving the validator catches it.
    """
    from cascadeflow.harness.instrument import _prepare_call_interception as _real

    def _mutating_intercept(*, ctx, mode, kwargs):
        state = _real(ctx=ctx, mode=mode, kwargs=kwargs)
        if mode == "observe":
            # Simulate a bug: observe mode switches the model.
            mutated_kwargs = {**state.kwargs, "model": "MUTATED"}
            from cascadeflow.harness.instrument import _CallInterceptionState

            return _CallInterceptionState(
                kwargs=mutated_kwargs,
                model="MUTATED",
                pre_action=state.pre_action,
                pre_reason=state.pre_reason,
                pre_model=state.pre_model,
                pre_applied=state.pre_applied,
                is_stream=state.is_stream,
                start_time=state.start_time,
            )
        return state

    with patch(
        "tests.benchmarks.observe_validation._prepare_call_interception",
        side_effect=_mutating_intercept,
    ):
        result = validate_observe_mode()

    assert not result.all_passed
    assert result.failed > 0
    assert any("model" in f or "MUTATED" in f for f in result.failures)


# ── 13-15: Artifact bundle ───────────────────────────────────────────────


def _make_bundle(tmp_path, sample_results, sample_metadata) -> dict:
    overhead = {
        "iterations": 100,
        "p50_us": 5.0,
        "p95_us": 12.0,
        "p99_us": 20.0,
        "mean_us": 8.0,
        "max_us": 25.0,
        "p95_under_5ms": True,
    }
    observe = {
        "total_cases": 6,
        "passed": 6,
        "failed": 0,
        "failures": [],
        "all_passed": True,
    }
    path = bundle_artifact(
        results=sample_results,
        metadata=sample_metadata,
        overhead=overhead,
        observe=observe,
        output_dir=tmp_path,
        run_id="test123",
    )
    return json.loads(path.read_text())


def test_artifact_bundle_format(tmp_path, sample_results, sample_metadata):
    """Has schema_version, metadata, results keys."""
    bundle = _make_bundle(tmp_path, sample_results, sample_metadata)
    assert "schema_version" in bundle
    assert "metadata" in bundle
    assert "results" in bundle
    assert "harness_overhead" in bundle
    assert "observe_validation" in bundle


def test_artifact_schema_version(tmp_path, sample_results, sample_metadata):
    """Matches '1.0.0'."""
    bundle = _make_bundle(tmp_path, sample_results, sample_metadata)
    assert bundle["schema_version"] == "1.0.0"
    assert bundle["schema_version"] == SCHEMA_VERSION


def test_artifact_results_compatible(tmp_path, sample_results, sample_metadata):
    """Result keys match existing format."""
    bundle = _make_bundle(tmp_path, sample_results, sample_metadata)
    expected_keys = {
        "accuracy",
        "accept_rate",
        "savings_pct",
        "effective_savings_pct",
        "drafter_accuracy",
        "verifier_accuracy",
        "total_cascade_cost",
        "total_baseline_cost",
        "avg_latency_ms",
        "n_total",
        "n_correct",
        "n_accepted",
    }
    for name, bench in bundle["results"].items():
        assert expected_keys == set(bench.keys()), f"{name} keys mismatch: {set(bench.keys())}"
