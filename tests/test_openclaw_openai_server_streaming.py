import json
from dataclasses import dataclass
from typing import Any

import httpx

from cascadeflow.integrations.openclaw.openai_server import (
    OpenClawOpenAIConfig,
    OpenClawOpenAIServer,
)


@dataclass
class _FakeEventType:
    value: str


@dataclass
class _FakeEvent:
    type: _FakeEventType
    content: str = ""
    data: Any = None


class _FakeAgent:
    def __init__(self, events: list[_FakeEvent]):
        self._events = events

    async def stream_events(self, **_: Any):
        for event in self._events:
            yield event


def _read_sse_json_lines(text: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data: "):
            continue
        payload = line[len("data: ") :]
        if payload == "[DONE]":
            break
        chunks.append(json.loads(payload))
    return chunks


def _stream_request(events: list[_FakeEvent]) -> list[dict[str, Any]]:
    server = OpenClawOpenAIServer(
        _FakeAgent(events),
        OpenClawOpenAIConfig(host="127.0.0.1", port=0, allow_streaming=True),
    )
    port = server.start()
    try:
        url = f"http://127.0.0.1:{port}/v1/chat/completions"
        payload = {
            "model": "cascadeflow",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        }
        r = httpx.post(url, json=payload, timeout=5.0, trust_env=False)
        assert r.status_code == 200
        return _read_sse_json_lines(r.text)
    finally:
        server.stop()


def test_openclaw_openai_server_stream_includes_role_and_final_finish_reason() -> None:
    chunks = _stream_request(
        [
            _FakeEvent(type=_FakeEventType("chunk"), content="Hi"),
            _FakeEvent(type=_FakeEventType("chunk"), content="!"),
        ]
    )
    assert len(chunks) >= 3

    first = chunks[0]["choices"][0]
    assert first["delta"]["role"] == "assistant"
    assert first["delta"]["content"] == ""
    assert first["finish_reason"] is None

    for middle in chunks[1:-1]:
        choice = middle["choices"][0]
        assert "content" in choice["delta"]
        assert choice["finish_reason"] is None

    last = chunks[-1]["choices"][0]
    assert last["delta"] == {}
    assert last["finish_reason"] == "stop"
    assert last["message"]["role"] == "assistant"
    assert last["message"]["content"] == "Hi!"

    usage = chunks[-1].get("usage", {})
    assert usage.get("total_tokens", 0) >= 1
    assert usage.get("totalTokens", 0) >= 1


def test_openclaw_openai_server_stream_handles_text_chunk_events() -> None:
    chunks = _stream_request(
        [
            _FakeEvent(
                type=_FakeEventType("routing"),
                data={"strategy": "cascade"},
            ),
            _FakeEvent(
                type=_FakeEventType("text_chunk"),
                content="Hello ",
                data={"phase": "draft"},
            ),
            _FakeEvent(type=_FakeEventType("draft_decision"), data={"accepted": True}),
            _FakeEvent(
                type=_FakeEventType("text_chunk"),
                content="world",
                data={"phase": "draft"},
            ),
        ]
    )
    middle_contents = [c["choices"][0]["delta"].get("content", "") for c in chunks[1:-1]]
    assert "".join(middle_contents) == "Hello world"
    assert chunks[-1]["choices"][0]["message"]["content"] == "Hello world"


def test_openclaw_openai_server_stream_drops_draft_after_switch() -> None:
    chunks = _stream_request(
        [
            _FakeEvent(
                type=_FakeEventType("routing"),
                data={"strategy": "cascade"},
            ),
            _FakeEvent(
                type=_FakeEventType("text_chunk"),
                content="wrong ",
                data={"phase": "draft"},
            ),
            _FakeEvent(
                type=_FakeEventType("text_chunk"),
                content="draft",
                data={"phase": "draft"},
            ),
            _FakeEvent(type=_FakeEventType("draft_decision"), data={"accepted": False}),
            _FakeEvent(type=_FakeEventType("switch"), content="cascading"),
            _FakeEvent(
                type=_FakeEventType("text_chunk"),
                content="right ",
                data={"phase": "verifier"},
            ),
            _FakeEvent(
                type=_FakeEventType("text_chunk"),
                content="answer",
                data={"phase": "verifier"},
            ),
        ]
    )
    middle_contents = [c["choices"][0]["delta"].get("content", "") for c in chunks[1:-1]]
    assert "".join(middle_contents) == "right answer"
    assert chunks[-1]["choices"][0]["message"]["content"] == "right answer"


def test_openclaw_openai_server_stream_uses_complete_content_when_no_chunks() -> None:
    chunks = _stream_request(
        [
            _FakeEvent(
                type=_FakeEventType("complete"),
                data={"result": {"content": "from-complete", "total_tokens": 7}},
            )
        ]
    )
    last = chunks[-1]["choices"][0]
    assert last["message"]["content"] == "from-complete"
    assert last["delta"] == {"content": "from-complete"}
    usage = chunks[-1]["usage"]
    assert usage["total_tokens"] == 7
    assert usage["totalTokens"] == 7
