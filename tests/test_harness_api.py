import sys

import pytest

import cascadeflow
import cascadeflow.harness.api as harness_api
from cascadeflow.harness import agent, get_current_run, get_harness_config, init, reset, run


def setup_function() -> None:
    reset()


def test_init_sets_mode_and_returns_report():
    report = init(mode="observe", budget=1.5, max_tool_calls=7)

    cfg = get_harness_config()
    assert cfg.mode == "observe"
    assert cfg.budget == 1.5
    assert cfg.max_tool_calls == 7
    assert report.mode == "observe"
    assert isinstance(report.instrumented, list)
    assert isinstance(report.detected_but_not_instrumented, list)
    assert report.config_sources["mode"] == "code"


def test_init_rejects_invalid_mode():
    with pytest.raises(ValueError):
        init(mode="invalid")  # type: ignore[arg-type]


def test_init_idempotent_logs(monkeypatch, caplog):
    monkeypatch.setattr(harness_api, "find_spec", lambda _: None)
    with caplog.at_level("DEBUG", logger="cascadeflow.harness"):
        init(mode="observe")
        init(mode="observe")
    assert any("idempotent" in rec.message for rec in caplog.records)


def test_env_aliases_and_false_bool(monkeypatch):
    monkeypatch.setenv("CASCADEFLOW_MODE", "observe")
    monkeypatch.setenv("CASCADEFLOW_BUDGET", "0.33")
    monkeypatch.setenv("CASCADEFLOW_HARNESS_VERBOSE", "off")
    monkeypatch.setenv("CASCADEFLOW_HARNESS_MAX_TOOL_CALLS", "4")
    monkeypatch.setenv("CASCADEFLOW_HARNESS_MAX_LATENCY_MS", "1200")
    monkeypatch.setenv("CASCADEFLOW_HARNESS_MAX_ENERGY", "0.01")
    monkeypatch.setenv("CASCADEFLOW_HARNESS_COMPLIANCE", "gdpr")

    report = init()
    cfg = get_harness_config()

    assert report.mode == "observe"
    assert cfg.mode == "observe"
    assert cfg.budget == 0.33
    assert cfg.verbose is False
    assert cfg.max_tool_calls == 4
    assert cfg.max_latency_ms == 1200
    assert cfg.max_energy == 0.01
    assert cfg.compliance == "gdpr"


def test_init_invalid_json_env_raises(monkeypatch):
    monkeypatch.setenv("CASCADEFLOW_HARNESS_KPI_WEIGHTS", "[1,2,3]")
    with pytest.raises(ValueError):
        init()


def test_init_non_numeric_env_raises(monkeypatch):
    monkeypatch.setenv("CASCADEFLOW_HARNESS_BUDGET", "abc")
    with pytest.raises(ValueError):
        init()


def test_run_uses_global_defaults_and_overrides():
    init(mode="enforce", budget=2.0, max_tool_calls=5)

    default_ctx = run()
    assert default_ctx.mode == "enforce"
    assert default_ctx.budget_max == 2.0
    assert default_ctx.tool_calls_max == 5
    assert default_ctx.budget_remaining == 2.0

    override_ctx = run(budget=0.5, max_tool_calls=3)
    assert override_ctx.budget_max == 0.5
    assert override_ctx.tool_calls_max == 3
    assert override_ctx.budget_remaining == 0.5


def test_run_without_enter_exit_is_safe():
    ctx = run()
    ctx.__exit__(None, None, None)


@pytest.mark.asyncio
async def test_nested_run_context_is_isolated():
    init(mode="enforce", budget=1.0)

    async with run(budget=0.7) as outer:
        assert get_current_run() is outer
        assert outer.budget_max == 0.7

        async with run(budget=0.2) as inner:
            assert get_current_run() is inner
            assert inner.budget_max == 0.2

        assert get_current_run() is outer

    assert get_current_run() is None


def test_sync_run_context_isolated():
    init(mode="enforce", budget=1.0)
    with run(budget=0.6) as outer:
        assert get_current_run() is outer
        with run(budget=0.1) as inner:
            assert get_current_run() is inner
            assert inner.budget_max == 0.1
        assert get_current_run() is outer
    assert get_current_run() is None


def test_agent_decorator_keeps_sync_behavior_and_attaches_metadata():
    @agent(
        budget=0.9,
        kpi_targets={"quality_min": 0.9},
        kpi_weights={"cost": 0.5, "quality": 0.5},
        compliance="gdpr",
    )
    def fn(x: int) -> int:
        return x + 1

    assert fn(2) == 3
    policy = fn.__cascadeflow_agent_policy__
    assert policy["budget"] == 0.9
    assert policy["kpi_targets"] == {"quality_min": 0.9}
    assert policy["compliance"] == "gdpr"


@pytest.mark.asyncio
async def test_agent_decorator_keeps_async_behavior_and_attaches_metadata():
    @agent(budget=0.4, kpi_weights={"cost": 1.0})
    async def fn(x: int) -> int:
        return x * 2

    assert await fn(4) == 8
    policy = fn.__cascadeflow_agent_policy__
    assert policy["budget"] == 0.4
    assert policy["kpi_weights"] == {"cost": 1.0}


def test_top_level_exports_exist():
    assert callable(cascadeflow.init)
    assert callable(cascadeflow.reset)
    assert callable(cascadeflow.run)
    assert callable(cascadeflow.agent)
    report = cascadeflow.init(mode="off")
    assert report.mode == "off"


def test_run_record_and_trace_copy():
    ctx = run(budget=1.0)
    ctx.record(action="switch_model", reason="cost_pressure", model="gpt-4o-mini")
    trace_a = ctx.trace()
    trace_b = ctx.trace()
    assert trace_a == trace_b
    assert trace_a[0]["action"] == "switch_model"
    trace_a.append({"action": "mutated"})
    assert len(ctx.trace()) == 1


def test_init_reads_from_env(monkeypatch):
    monkeypatch.setenv("CASCADEFLOW_HARNESS_MODE", "observe")
    monkeypatch.setenv("CASCADEFLOW_HARNESS_BUDGET", "0.25")
    monkeypatch.setenv("CASCADEFLOW_HARNESS_KPI_TARGETS", '{"quality_min": 0.9}')
    monkeypatch.setenv("CASCADEFLOW_HARNESS_KPI_WEIGHTS", '{"cost": 1.0}')

    report = init()
    cfg = get_harness_config()

    assert report.mode == "observe"
    assert cfg.mode == "observe"
    assert cfg.budget == 0.25
    assert cfg.kpi_targets == {"quality_min": 0.9}
    assert cfg.kpi_weights == {"cost": 1.0}
    assert report.config_sources["mode"] == "env"
    assert report.config_sources["budget"] == "env"


def test_init_reads_from_config_file(tmp_path, monkeypatch):
    config = tmp_path / "cascadeflow.json"
    config.write_text(
        '{"harness":{"mode":"observe","budget":0.75,"max_tool_calls":11,"kpi_targets":{"quality_min":0.9}}}'
    )
    monkeypatch.setenv("CASCADEFLOW_CONFIG", str(config))

    report = init()
    cfg = get_harness_config()

    assert cfg.mode == "observe"
    assert cfg.budget == 0.75
    assert cfg.max_tool_calls == 11
    assert cfg.kpi_targets == {"quality_min": 0.9}
    assert report.config_sources["mode"] == "file"
    assert report.config_sources["budget"] == "file"


def test_init_reads_top_level_config_file_keys(tmp_path, monkeypatch):
    config = tmp_path / "cascadeflow.json"
    config.write_text('{"mode":"observe","budget":0.4,"max_tool_calls":2}')
    monkeypatch.setenv("CASCADEFLOW_CONFIG", str(config))

    report = init()
    cfg = get_harness_config()

    assert cfg.mode == "observe"
    assert cfg.budget == 0.4
    assert cfg.max_tool_calls == 2
    assert report.config_sources["mode"] == "file"


def test_init_non_dict_config_file_ignored(tmp_path, monkeypatch):
    config = tmp_path / "cascadeflow.json"
    config.write_text('["not-a-dict"]')
    monkeypatch.setenv("CASCADEFLOW_CONFIG", str(config))

    report = init()
    cfg = get_harness_config()

    assert cfg.mode == "off"
    assert cfg.budget is None
    assert report.config_sources["mode"] == "default"


def test_init_file_loader_exception_falls_back_defaults(monkeypatch):
    import cascadeflow.config_loader as cl

    monkeypatch.setattr(cl, "find_config", lambda: "broken.json")

    def _raise(_path):
        raise RuntimeError("boom")

    monkeypatch.setattr(cl, "load_config", _raise)

    report = init()
    cfg = get_harness_config()
    assert cfg.mode == "off"
    assert report.config_sources["mode"] == "default"


def test_init_config_loader_import_failure_falls_back(monkeypatch):
    monkeypatch.setitem(sys.modules, "cascadeflow.config_loader", object())
    report = init(mode="observe")
    assert report.mode == "observe"
    assert report.config_sources["mode"] == "code"


def test_precedence_code_over_env_over_file(tmp_path, monkeypatch):
    config = tmp_path / "cascadeflow.json"
    config.write_text('{"harness":{"mode":"off","budget":9.9}}')
    monkeypatch.setenv("CASCADEFLOW_CONFIG", str(config))
    monkeypatch.setenv("CASCADEFLOW_HARNESS_MODE", "observe")
    monkeypatch.setenv("CASCADEFLOW_HARNESS_BUDGET", "0.5")

    # env overrides file
    report_env = init()
    cfg_env = get_harness_config()
    assert cfg_env.mode == "observe"
    assert cfg_env.budget == 0.5
    assert report_env.config_sources["mode"] == "env"
    assert report_env.config_sources["budget"] == "env"

    # code overrides env
    report_code = init(mode="enforce", budget=0.2)
    cfg_code = get_harness_config()
    assert cfg_code.mode == "enforce"
    assert cfg_code.budget == 0.2
    assert report_code.config_sources["mode"] == "code"
    assert report_code.config_sources["budget"] == "code"


def test_reset_clears_state():
    init(mode="enforce", budget=0.9)
    with run() as ctx:
        assert get_current_run() is ctx
    reset()
    cfg = get_harness_config()
    assert cfg.mode == "off"
    assert cfg.budget is None
    assert get_current_run() is None


def test_init_without_detected_sdks(monkeypatch):
    monkeypatch.setattr(harness_api, "find_spec", lambda _: None)
    report = init(mode="observe")
    assert report.instrumented == []
    assert report.detected_but_not_instrumented == []


def test_init_reports_openai_instrumented_when_patch_succeeds(monkeypatch):
    monkeypatch.setattr(
        harness_api,
        "find_spec",
        lambda name: object() if name == "openai" else None,
    )

    import cascadeflow.harness.instrument as instrument

    monkeypatch.setattr(instrument, "patch_openai", lambda: True)
    report = init(mode="observe")
    assert report.instrumented == ["openai"]
