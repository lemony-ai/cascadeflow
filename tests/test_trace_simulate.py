"""
Tests for trace export (session.save/load) and offline cascade simulation.
"""

import json
import tempfile
from pathlib import Path

import pytest

from cascadeflow.harness.api import HarnessRunContext
from cascadeflow.harness.simulate import SimulationResult, simulate


class TestSessionSaveLoad:
    """Tests for HarnessRunContext.save() and .load()."""

    def test_save_creates_file(self, tmp_path):
        ctx = HarnessRunContext(mode="observe")
        ctx.record("allow", "test", model="gpt-4o-mini")
        ctx.record("switch_model", "quality too low", model="gpt-4o")

        dest = ctx.save(tmp_path / "trace.jsonl")
        assert dest.exists()
        assert dest.suffix == ".jsonl"

    def test_save_load_roundtrip(self, tmp_path):
        ctx = HarnessRunContext(mode="observe", budget_max=1.0)
        ctx._increment(cost=0.01, steps=1, latency_ms=50.0)
        ctx.record("allow", "observe", model="gpt-4o-mini")
        ctx._increment(cost=0.05, steps=1, latency_ms=200.0)
        ctx.record("switch_model", "escalated", model="gpt-4o")

        path = ctx.save(tmp_path / "session.jsonl")
        loaded = HarnessRunContext.load(path)

        assert loaded["session"] is not None
        assert loaded["session"]["_type"] == "session"
        assert loaded["session"]["run_id"] == ctx.run_id
        assert loaded["session"]["mode"] == "observe"
        assert len(loaded["traces"]) == 2
        assert loaded["traces"][0]["action"] == "allow"
        assert loaded["traces"][1]["action"] == "switch_model"

    def test_save_creates_parent_dirs(self, tmp_path):
        ctx = HarnessRunContext(mode="observe")
        ctx.record("allow", "test")
        dest = ctx.save(tmp_path / "nested" / "deep" / "trace.jsonl")
        assert dest.exists()

    def test_save_jsonl_format(self, tmp_path):
        ctx = HarnessRunContext(mode="observe")
        ctx.record("allow", "test", model="gpt-4o-mini")
        path = ctx.save(tmp_path / "trace.jsonl")

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2  # 1 header + 1 trace entry
        header = json.loads(lines[0])
        assert header["_type"] == "session"
        entry = json.loads(lines[1])
        assert entry["_type"] == "trace"
        assert entry["action"] == "allow"

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            HarnessRunContext.load("/nonexistent/path.jsonl")

    def test_record_with_query(self, tmp_path):
        ctx = HarnessRunContext(mode="observe")
        ctx.record("allow", "test", model="gpt-4o-mini", query="What is Python?")
        path = ctx.save(tmp_path / "trace.jsonl")

        loaded = HarnessRunContext.load(path)
        assert loaded["traces"][0]["query"] == "What is Python?"

    def test_record_without_query_omits_field(self, tmp_path):
        ctx = HarnessRunContext(mode="observe")
        ctx.record("allow", "test", model="gpt-4o-mini")
        path = ctx.save(tmp_path / "trace.jsonl")

        loaded = HarnessRunContext.load(path)
        assert "query" not in loaded["traces"][0]


class TestSimulate:
    """Tests for offline cascade simulation."""

    def _make_models(self):
        """Create mock model configs for testing."""
        from cascadeflow.schema.config import ModelConfig

        return [
            ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.000375),
            ModelConfig(name="gpt-4o", provider="openai", cost=0.005),
        ]

    def test_simulate_basic(self):
        models = self._make_models()
        queries = [
            "What is Python?",
            "Hello",
            "Prove the Riemann hypothesis using advanced algebraic topology",
        ]
        result = simulate(queries=queries, models=models)

        assert isinstance(result, SimulationResult)
        assert result.total_queries == 3
        assert result.projected_cost > 0
        assert 0.0 <= result.escalation_rate <= 1.0
        assert len(result.per_query) == 3
        assert sum(result.model_distribution.values()) == 3

    def test_simulate_empty_queries(self):
        models = self._make_models()
        result = simulate(queries=[], models=models)
        assert result.total_queries == 0
        assert result.projected_cost == 0.0
        assert result.escalation_rate == 0.0

    def test_simulate_requires_two_models(self):
        from cascadeflow.schema.config import ModelConfig

        with pytest.raises(ValueError, match="at least 2 models"):
            simulate(
                queries=["test"],
                models=[ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.000375)],
            )

    def test_simulate_from_jsonl(self, tmp_path):
        models = self._make_models()
        jsonl_path = tmp_path / "queries.jsonl"
        queries = ["What is 2+2?", "Explain quantum entanglement in detail"]
        with open(jsonl_path, "w") as f:
            for q in queries:
                f.write(json.dumps({"query": q}) + "\n")

        result = simulate(queries=jsonl_path, models=models)
        assert result.total_queries == 2

    def test_simulate_from_plain_text(self, tmp_path):
        models = self._make_models()
        text_path = tmp_path / "queries.txt"
        text_path.write_text("What is Python?\nHello world\n")

        result = simulate(queries=text_path, models=models)
        assert result.total_queries == 2

    def test_simulate_file_not_found(self):
        models = self._make_models()
        with pytest.raises(FileNotFoundError):
            simulate(queries="/nonexistent.jsonl", models=models)

    def test_simulate_low_threshold_fewer_escalations(self):
        models = self._make_models()
        queries = [
            "What is Python?",
            "Explain the proof of Fermat's Last Theorem",
            "Write a hello world program",
            "Derive the Navier-Stokes equations from first principles",
        ]
        result_low = simulate(queries=queries, models=models, quality_threshold=0.3)
        result_high = simulate(queries=queries, models=models, quality_threshold=0.9)

        assert result_low.escalation_rate <= result_high.escalation_rate

    def test_simulate_summary(self):
        models = self._make_models()
        result = simulate(queries=["What is Python?"], models=models)
        summary = result.summary()

        assert "total_queries" in summary
        assert "projected_cost" in summary
        assert "escalation_rate" in summary
        assert "model_distribution" in summary

    def test_simulate_compare(self):
        models = self._make_models()
        queries = ["What is Python?", "Prove P != NP"]
        result_a = simulate(queries=queries, models=models, quality_threshold=0.5)
        result_b = simulate(queries=queries, models=models, quality_threshold=0.9)
        diff = result_a.compare(result_b)

        assert "cost_change" in diff
        assert "cost_change_pct" in diff
        assert "escalation_rate_change" in diff

    def test_simulate_per_query_details(self):
        models = self._make_models()
        result = simulate(queries=["What is Python?"], models=models)
        entry = result.per_query[0]

        assert entry.query == "What is Python?"
        assert entry.complexity in {"trivial", "simple", "moderate", "hard", "expert"}
        assert entry.routing_decision in {"draft_accepted", "escalated"}
        assert entry.projected_model in {"gpt-4o-mini", "gpt-4o"}
        assert entry.projected_cost >= 0

    def test_simulate_no_domain_detection(self):
        models = self._make_models()
        result = simulate(
            queries=["What is Python?"],
            models=models,
            domain_detection=False,
        )
        assert result.total_queries == 1
        assert result.per_query[0].domain == "general"

    def test_simulate_from_session_save(self, tmp_path):
        """End-to-end: record with query -> save -> load -> simulate."""
        models = self._make_models()
        ctx = HarnessRunContext(mode="observe")
        ctx._increment(cost=0.01, steps=1, latency_ms=50.0)
        ctx.record("allow", "observe", model="gpt-4o-mini", query="What is Python?")
        ctx._increment(cost=0.05, steps=1, latency_ms=200.0)
        ctx.record("allow", "observe", model="gpt-4o", query="Prove the Riemann hypothesis")

        path = ctx.save(tmp_path / "session.jsonl")
        result = simulate(queries=path, models=models)

        assert result.total_queries == 2
        assert result.projected_cost > 0
        assert len(result.per_query) == 2
        assert result.per_query[0].query == "What is Python?"
        assert result.per_query[1].query.startswith("Prove the Riemann")

    def test_simulate_rejects_non_string_query(self, tmp_path):
        """Non-string query values in JSONL are skipped, not crashed on."""
        models = self._make_models()
        jsonl_path = tmp_path / "bad_queries.jsonl"
        with open(jsonl_path, "w") as f:
            f.write(json.dumps({"query": "valid query"}) + "\n")
            f.write(json.dumps({"query": {"nested": "dict"}}) + "\n")
            f.write(json.dumps({"query": "another valid"}) + "\n")

        result = simulate(queries=jsonl_path, models=models)
        assert result.total_queries == 2
