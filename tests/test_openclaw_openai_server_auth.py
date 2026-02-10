import json
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from cascadeflow.integrations.openclaw.openai_server import (
    OpenClawOpenAIConfig,
    OpenClawOpenAIServer,
)


@dataclass
class _FakeResult:
    content: str = "ok"
    model_used: str = "fake-model"
    metadata: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}


class _FakeAgent:
    async def run(self, **_: Any) -> _FakeResult:
        return _FakeResult()


def test_openclaw_openai_server_requires_auth_when_configured() -> None:
    server = OpenClawOpenAIServer(
        _FakeAgent(),
        OpenClawOpenAIConfig(host="127.0.0.1", port=0, auth_token="secret", allow_streaming=False),
    )
    port = server.start()
    try:
        url = f"http://127.0.0.1:{port}/v1/chat/completions"
        payload = {"model": "cascadeflow", "messages": [{"role": "user", "content": "hi"}]}

        # No auth -> 401
        r = httpx.post(url, json=payload, timeout=5.0, trust_env=False)
        assert r.status_code == 401
        body = json.loads(r.text)
        assert "error" in body

        # Wrong auth -> 401
        r = httpx.post(
            url, json=payload, headers={"Authorization": "Bearer nope"}, timeout=5.0, trust_env=False
        )
        assert r.status_code == 401

        # Correct auth -> 200
        r = httpx.post(
            url,
            json=payload,
            headers={"Authorization": "Bearer secret"},
            timeout=5.0,
            trust_env=False,
        )
        assert r.status_code == 200
        body = json.loads(r.text)
        assert body["choices"][0]["message"]["content"] == "ok"
    finally:
        server.stop()


def test_openclaw_openai_server_stats_can_use_separate_token() -> None:
    class _FakeTelemetry:
        def export_to_dict(self) -> dict[str, Any]:
            return {"summary": {"total_queries": 0}}

    class _AgentWithTelemetry(_FakeAgent):
        telemetry = _FakeTelemetry()

    server = OpenClawOpenAIServer(
        _AgentWithTelemetry(),
        OpenClawOpenAIConfig(
            host="127.0.0.1",
            port=0,
            auth_token="main",
            stats_auth_token="stats",
            allow_streaming=False,
        ),
    )
    port = server.start()
    try:
        url = f"http://127.0.0.1:{port}/stats"

        r = httpx.get(url, timeout=5.0, trust_env=False)
        assert r.status_code == 401

        r = httpx.get(url, headers={"Authorization": "Bearer main"}, timeout=5.0, trust_env=False)
        assert r.status_code == 401

        r = httpx.get(url, headers={"Authorization": "Bearer stats"}, timeout=5.0, trust_env=False)
        assert r.status_code == 200
        assert json.loads(r.text)["summary"]["total_queries"] == 0
    finally:
        server.stop()
