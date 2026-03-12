from argparse import Namespace

from cascadeflow.harness import HarnessConfig
from cascadeflow.integrations.openclaw.openai_server import _configure_harness


def _args(**overrides):
    base = {
        "harness_mode": None,
        "harness_budget": None,
        "harness_max_tool_calls": None,
        "harness_max_latency_ms": None,
        "harness_max_energy": None,
        "harness_compliance": None,
    }
    base.update(overrides)
    return Namespace(**base)


def test_configure_harness_passes_cli_values(monkeypatch, capsys):
    captured = {}

    def fake_init(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("cascadeflow.harness.init", fake_init)
    monkeypatch.setattr(
        "cascadeflow.harness.get_harness_config",
        lambda: HarnessConfig(
            mode="observe",
            budget=1.0,
            max_tool_calls=12,
            max_latency_ms=3500,
            compliance="strict",
        ),
    )

    _configure_harness(
        _args(
            harness_mode="observe",
            harness_budget=1.0,
            harness_max_tool_calls=12,
            harness_max_latency_ms=3500,
            harness_compliance="strict",
        )
    )

    assert captured == {
        "mode": "observe",
        "budget": 1.0,
        "max_tool_calls": 12,
        "max_latency_ms": 3500,
        "max_energy": None,
        "compliance": "strict",
    }
    output = capsys.readouterr().out
    assert "Harness mode=observe" in output
    assert "budget=1.0" in output
    assert "max_tool_calls=12" in output


def test_configure_harness_no_flags_off_mode_is_quiet(monkeypatch, capsys):
    monkeypatch.setattr("cascadeflow.harness.init", lambda **_: None)
    monkeypatch.setattr(
        "cascadeflow.harness.get_harness_config",
        lambda: HarnessConfig(mode="off"),
    )

    _configure_harness(_args())

    assert capsys.readouterr().out == ""


def test_configure_harness_explicit_off_prints_status(monkeypatch, capsys):
    monkeypatch.setattr("cascadeflow.harness.init", lambda **_: None)
    monkeypatch.setattr(
        "cascadeflow.harness.get_harness_config",
        lambda: HarnessConfig(mode="off"),
    )

    _configure_harness(_args(harness_mode="off"))

    output = capsys.readouterr().out
    assert "Harness mode=off" in output
