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
    tool_call: Any = None


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


def _stream_request(
    events: list[_FakeEvent],
    include_usage: bool = False,
) -> list[dict[str, Any]]:
    server = OpenClawOpenAIServer(
        _FakeAgent(events),
        OpenClawOpenAIConfig(host="127.0.0.1", port=0, allow_streaming=True),
    )
    port = server.start()
    try:
        url = f"http://127.0.0.1:{port}/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": "cascadeflow",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        }
        if include_usage:
            payload["stream_options"] = {"include_usage": True}
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
    # Content must appear as a proper delta chunk (finish_reason=null) so that
    # OpenAI SDKs accumulate it, not only in the stop chunk's delta.
    content_deltas = [
        c["choices"][0]["delta"].get("content", "")
        for c in chunks
        if c["choices"] and c["choices"][0].get("finish_reason") is None
    ]
    assert "from-complete" in content_deltas

    last = chunks[-1]["choices"][0]
    assert last["message"]["content"] == "from-complete"
    assert last["delta"] == {}
    usage = chunks[-1]["usage"]
    assert usage["total_tokens"] == 7
    assert usage["totalTokens"] == 7


def test_openclaw_openai_server_stream_options_include_usage() -> None:
    """When stream_options.include_usage is set, a separate usage-only chunk
    with choices=[] must be sent after the stop chunk (OpenAI spec compliance,
    required by pi-ai / OpenClaw via the OpenAI Node SDK)."""
    chunks = _stream_request(
        [
            _FakeEvent(type=_FakeEventType("chunk"), content="Hi"),
            _FakeEvent(
                type=_FakeEventType("complete"),
                data={"result": {"content": "Hi", "completion_tokens": 5, "total_tokens": 15}},
            ),
        ],
        include_usage=True,
    )
    # Expect: initial, content, stop (with usage), usage-only
    assert len(chunks) >= 3

    # Find the stop chunk (has finish_reason == "stop" and non-empty choices)
    stop_chunk = None
    usage_only_chunk = None
    for c in chunks:
        choices = c.get("choices", [])
        if choices and choices[0].get("finish_reason") == "stop":
            stop_chunk = c
        elif not choices and "usage" in c:
            usage_only_chunk = c

    assert stop_chunk is not None, "Missing stop chunk with finish_reason"
    assert stop_chunk.get("usage", {}).get("total_tokens", 0) >= 1

    # The separate usage-only chunk per OpenAI spec
    assert usage_only_chunk is not None, "Missing separate usage-only chunk (choices=[])"
    assert usage_only_chunk["choices"] == []
    assert usage_only_chunk["usage"]["completion_tokens"] == 5
    assert usage_only_chunk["usage"]["total_tokens"] == 15


def test_openclaw_openai_server_stream_no_usage_chunk_without_stream_options() -> None:
    """Without stream_options.include_usage, no separate usage-only chunk."""
    chunks = _stream_request(
        [
            _FakeEvent(type=_FakeEventType("chunk"), content="Hi"),
        ],
        include_usage=False,
    )
    usage_only_chunks = [c for c in chunks if not c.get("choices")]
    assert len(usage_only_chunks) == 0, "Should not send usage-only chunk without stream_options"


def test_openclaw_openai_server_stream_tool_calls() -> None:
    """Tool call events must appear as OpenAI-format tool_calls in the SSE stream."""
    chunks = _stream_request(
        [
            _FakeEvent(
                type=_FakeEventType("text_chunk"),
                content="I'll check the weather.",
                data={"phase": "direct"},
            ),
            _FakeEvent(
                type=_FakeEventType("tool_call_complete"),
                tool_call={
                    "id": "call_abc",
                    "type": "function",
                    "name": "get_weather",
                    "arguments": {"city": "Zurich"},
                },
            ),
            _FakeEvent(
                type=_FakeEventType("complete"),
                data={
                    "result": {
                        "content": "I'll check the weather.",
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "name": "get_weather",
                                "arguments": {"city": "Zurich"},
                            }
                        ],
                        "total_tokens": 20,
                    }
                },
            ),
        ]
    )
    # Find the tool call delta chunk (finish_reason=null, has tool_calls in delta)
    tc_chunk = None
    for c in chunks:
        choices = c.get("choices", [])
        if choices and choices[0].get("delta", {}).get("tool_calls"):
            tc_chunk = c
            break

    assert tc_chunk is not None, "Missing tool_calls delta chunk"
    tc = tc_chunk["choices"][0]["delta"]["tool_calls"][0]
    assert tc["function"]["name"] == "get_weather"
    assert json.loads(tc["function"]["arguments"]) == {"city": "Zurich"}
    assert tc["id"] == "call_abc"

    # Final stop chunk should have finish_reason="tool_calls"
    last = chunks[-1]["choices"][0]
    assert last["finish_reason"] == "tool_calls"
    assert last["message"]["tool_calls"][0]["function"]["name"] == "get_weather"
