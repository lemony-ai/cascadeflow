import json
from dataclasses import dataclass, field

import httpx
import pytest

from cascadeflow.proxy import ProxyConfig, RoutingProxy


class _FakeTelemetry:
    def __init__(self) -> None:
        self._count = 0

    def export_to_dict(self) -> dict:
        self._count += 1
        return {"summary": {"total_queries": self._count}}


class _EventType:
    value = "chunk"


@dataclass
class _FakeEvent:
    content: str
    type: _EventType = field(default_factory=_EventType)


@dataclass
class _FakeResult:
    content: str
    model_used: str = "fake-model"
    metadata: dict = field(default_factory=dict)
    draft_accepted: bool = True
    quality_score: float = 0.9
    complexity: str = "simple"
    cascade_overhead_ms: int = 1


class _FakeAgent:
    def __init__(self) -> None:
        self.telemetry = _FakeTelemetry()

    async def run(self, **kwargs) -> _FakeResult:
        # Provide token metadata so the server can populate usage blocks.
        meta = {
            "prompt_tokens": 5,
            "completion_tokens": 7,
            "total_tokens": 12,
            # Include a tool call to validate Anthropic tool_use shaping.
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "calculator",
                        "arguments": json.dumps({"expression": "2+2"}),
                    },
                }
            ],
        }
        return _FakeResult(content="hello from agent", model_used="fake-model", metadata=meta)

    async def stream_events(self, **kwargs):
        yield _FakeEvent("hello ")
        yield _FakeEvent("stream")


@pytest.fixture
def agent_proxy():
    proxy = RoutingProxy(
        agent=_FakeAgent(),
        config=ProxyConfig(host="127.0.0.1", port=0, allow_streaming=True),
    )
    proxy.start()
    yield proxy
    proxy.stop()


def test_health(agent_proxy):
    url = f"http://{agent_proxy.host}:{agent_proxy.port}/health"
    resp = httpx.get(url, timeout=5.0)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_stats(agent_proxy):
    url = f"http://{agent_proxy.host}:{agent_proxy.port}/stats"
    resp = httpx.get(url, timeout=5.0)
    assert resp.status_code == 200
    assert resp.json()["summary"]["total_queries"] >= 1


def test_openai_agent_response_shape(agent_proxy):
    url = f"http://{agent_proxy.host}:{agent_proxy.port}/v1/chat/completions"
    payload = {"model": "cascadeflow", "messages": [{"role": "user", "content": "hi"}]}
    resp = httpx.post(url, json=payload, timeout=5.0)
    assert resp.status_code == 200
    data = resp.json()

    assert data["object"] == "chat.completion"
    assert data["choices"]
    assert data["choices"][0]["message"]["content"]

    cf = data["cascadeflow"]
    assert cf["model_used"] == "fake-model"

    meta = cf["metadata"]
    for key in ("draft_accepted", "quality_score", "complexity", "cascade_overhead"):
        assert key in meta


def test_anthropic_agent_response_shape(agent_proxy):
    url = f"http://{agent_proxy.host}:{agent_proxy.port}/v1/messages"
    payload = {"model": "claude-any", "messages": [{"role": "user", "content": "hi"}]}
    resp = httpx.post(url, json=payload, timeout=5.0)
    assert resp.status_code == 200
    data = resp.json()

    assert data["type"] == "message"
    assert data["role"] == "assistant"
    assert data["model"] == "claude-any"

    assert isinstance(data["content"], list)
    assert data["content"]
    assert any(block.get("type") == "text" for block in data["content"])
    assert any(block.get("type") == "tool_use" for block in data["content"])

    cf = data["cascadeflow"]
    assert cf["model_used"] == "fake-model"

    meta = cf["metadata"]
    for key in ("draft_accepted", "quality_score", "complexity", "cascade_overhead"):
        assert key in meta


def test_openai_agent_streaming(agent_proxy):
    url = f"http://{agent_proxy.host}:{agent_proxy.port}/v1/chat/completions"
    payload = {
        "model": "cascadeflow",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
    }

    with httpx.stream("POST", url, json=payload, timeout=5.0) as resp:
        assert resp.status_code == 200
        lines = [line for line in resp.iter_lines() if line]

    assert any(line.startswith("data: ") for line in lines)
    assert lines[-1] == "data: [DONE]"


def test_anthropic_agent_streaming(agent_proxy):
    url = f"http://{agent_proxy.host}:{agent_proxy.port}/v1/messages"
    payload = {
        "model": "claude-any",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": True,
    }

    with httpx.stream("POST", url, json=payload, timeout=5.0) as resp:
        assert resp.status_code == 200
        lines = [line for line in resp.iter_lines() if line]

    assert any(line.startswith("event: message_start") for line in lines)
    assert any(line.startswith("event: message_stop") for line in lines)
    assert any(line == "data: [DONE]" for line in lines)
