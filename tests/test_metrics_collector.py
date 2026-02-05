import pytest

from cascadeflow.telemetry.collector import MetricsCollector


class _Result:
    def __init__(self):
        self.total_cost = 6.54
        self.latency_ms = 120.0
        self.draft_accepted = True
        self.content = "ok"
        self.model_used = "gpt-4o-mini"
        self.cost_saved = 12.18
        self.metadata = {
            "draft_total_tokens": 400,
            "verifier_total_tokens": 1200,
            "total_tokens": 1600,
        }


def test_metrics_summary_includes_savings_and_tokens():
    collector = MetricsCollector()
    result = _Result()

    collector.record(
        result=result,
        routing_strategy="cascade",
        complexity="simple",
        timing_breakdown=None,
        streaming=False,
        has_tools=False,
    )

    summary = collector.get_summary()

    assert summary["total_cost"] == pytest.approx(6.54)
    assert summary["total_saved"] == pytest.approx(12.18)
    assert summary["baseline_cost"] == pytest.approx(18.72)
    assert summary["savings_percent"] == pytest.approx(65.1)
    assert summary["draft_tokens"] == 400
    assert summary["verifier_tokens"] == 1200
    assert summary["total_tokens"] == 1600
