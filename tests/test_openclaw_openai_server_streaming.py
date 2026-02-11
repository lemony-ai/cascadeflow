import json
from dataclasses import dataclass
from typing import Any

import httpx

from cascadeflow.integrations.openclaw.openai_server import (
    OpenClawOpenAIConfig,
    OpenClawOpenAIServer,
)


@dataclass
class _FakeChunkEventType:
    value: str = "chunk"


@dataclass
class _FakeChunkEvent:
    type: _FakeChunkEventType
    content: str


class _FakeAgent:
    async def stream_events(self, **_: Any):
        yield _FakeChunkEvent(type=_FakeChunkEventType(), content="Hi")
        yield _FakeChunkEvent(type=_FakeChunkEventType(), content="!")


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


def test_openclaw_openai_server_stream_includes_role_and_final_finish_reason() -> None:
    server = OpenClawOpenAIServer(
        _FakeAgent(),
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

        chunks = _read_sse_json_lines(r.text)
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
        assert last["delta"].get("content") == "Hi!"
        assert last["finish_reason"] == "stop"
        assert last["message"]["role"] == "assistant"
        assert last["message"]["content"] == "Hi!"

        usage = chunks[-1].get("usage", {})
        assert usage.get("total_tokens", 0) >= 1
        assert usage.get("totalTokens", 0) >= 1
    finally:
        server.stop()
