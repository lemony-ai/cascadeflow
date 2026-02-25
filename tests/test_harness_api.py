import pytest

import cascadeflow
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
    monkeypatch.setenv("CASCADEFLOW_HARNESS_KPI_WEIGHTS", '{"cost": 1.0}')

    report = init()
    cfg = get_harness_config()

    assert report.mode == "observe"
    assert cfg.mode == "observe"
    assert cfg.budget == 0.25
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
