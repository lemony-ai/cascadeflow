from __future__ import annotations

import sys
from unittest.mock import Mock, patch

import pytest

from cascadeflow.mcp_server import _is_local_host, _load_callable, main


def test_load_callable_and_local_host_validation() -> None:
    assert _load_callable("math:sqrt")(9) == 3
    assert _is_local_host("127.0.0.1") is True
    assert _is_local_host("::1") is True
    assert _is_local_host("0.0.0.0") is False

    with pytest.raises(SystemExit, match="module.path:callable"):
        _load_callable("invalid")
    with pytest.raises(SystemExit, match="not callable"):
        _load_callable("math:pi")


def test_mcp_cli_loads_config_and_runs_stdio_without_stdout(capsys) -> None:
    agent = object()
    resolver = Mock()
    server = Mock()
    argv = [
        "cascadeflow-mcp",
        "--config",
        "cascadeflow.yaml",
        "--knowledge-resolver",
        "app.knowledge:resolve",
    ]

    with (
        patch.object(sys, "argv", argv),
        patch("cascadeflow.config_loader.load_agent", return_value=agent) as load_agent,
        patch("cascadeflow.mcp_server._load_callable", return_value=resolver),
        patch("cascadeflow.integrations.mcp.create_mcp_server", return_value=server) as create,
    ):
        main()

    load_agent.assert_called_once_with("cascadeflow.yaml", verbose=False)
    create.assert_called_once_with(
        agent,
        knowledge_resolver=resolver,
        include_ui=True,
        host="127.0.0.1",
        port=8000,
        streamable_http_path="/mcp",
    )
    server.run.assert_called_once_with(transport="stdio")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_mcp_cli_loads_preset_and_warns_for_public_http(capsys) -> None:
    agent = object()
    server = Mock()
    argv = [
        "cascadeflow-mcp",
        "--preset",
        "cost_optimized",
        "--transport",
        "streamable-http",
        "--host",
        "0.0.0.0",
        "--port",
        "9000",
        "--path",
        "/cascade",
        "--no-ui",
    ]

    with (
        patch.object(sys, "argv", argv),
        patch("cascadeflow.utils.presets.auto_agent", return_value=agent) as auto_agent,
        patch("cascadeflow.integrations.mcp.create_mcp_server", return_value=server) as create,
    ):
        main()

    auto_agent.assert_called_once_with("cost_optimized", verbose=False, enable_cascade=True)
    create.assert_called_once_with(
        agent,
        knowledge_resolver=None,
        include_ui=False,
        host="0.0.0.0",
        port=9000,
        streamable_http_path="/cascade",
    )
    server.run.assert_called_once_with(transport="streamable-http")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "does not add authentication or TLS" in captured.err
