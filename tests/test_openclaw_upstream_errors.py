"""Tests for upstream provider error handling in the OpenClaw OpenAI server.

Verifies that Anthropic 529/500/429 errors are properly surfaced to
OpenClaw users instead of returning empty 200 responses.
"""

import json
from dataclasses import dataclass
from typing import Any

import httpx

from cascadeflow.integrations.openclaw.openai_server import (
    OpenClawOpenAIConfig,
    OpenClawOpenAIServer,
)
from cascadeflow.schema.exceptions import ProviderError


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class _FakeEventType:
    value: str


@dataclass
class _FakeEvent:
    type: _FakeEventType
    content: str = ""
    data: Any = None
    tool_call: Any = None


class _FakeAgentRaisesOnStream:
    """Agent whose stream_events raises a ProviderError."""

    def __init__(self, error: Exception):
        self._error = error

    async def stream_events(self, **_: Any):
        raise self._error
        yield  # make this a generator  # noqa: RET503


class _FakeAgentRaisesOnRun:
    """Agent whose run() raises a ProviderError."""

    def __init__(self, error: Exception):
        self._error = error

    async def run(self, **_: Any):
        raise self._error

    async def stream_events(self, **_: Any):
        raise self._error
        yield  # noqa: RET503


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_sse_json_lines(text: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data: "):
            continue
        payload = line[len("data: "):]
        if payload == "[DONE]":
            break
        chunks.append(json.loads(payload))
    return chunks


def _post_chat(
    port: int,
    stream: bool = False,
) -> httpx.Response:
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": "cascadeflow",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": stream,
    }
    return httpx.post(url, json=payload, timeout=5.0, trust_env=False)


# ---------------------------------------------------------------------------
# Streaming tests
# ---------------------------------------------------------------------------


def test_stream_anthropic_529_returns_error_chunk() -> None:
    """When Anthropic returns 529 (overloaded) during streaming, the client
    should receive an error chunk with finish_reason='error' instead of empty content."""
    error = ProviderError(
        "Anthropic API error: 529 - overloaded",
        provider="anthropic",
        status_code=529,
    )
    server = OpenClawOpenAIServer(
        _FakeAgentRaisesOnStream(error),
        OpenClawOpenAIConfig(host="127.0.0.1", port=0, allow_streaming=True),
    )
    port = server.start()
    try:
        r = _post_chat(port, stream=True)
        assert r.status_code == 200  # SSE stream always starts 200
        chunks = _read_sse_json_lines(r.text)

        # Should have at least the initial role chunk and the error chunk
        assert len(chunks) >= 2

        # Find the error chunk
        error_chunk = None
        for c in chunks:
            if c.get("error"):
                error_chunk = c
                break

        assert error_chunk is not None, f"Expected error chunk in: {chunks}"
        assert error_chunk["error"]["code"] == 503
        assert "overloaded" in error_chunk["error"]["message"].lower()
        assert error_chunk["choices"][0]["finish_reason"] == "error"
    finally:
        server.stop()


def test_stream_anthropic_500_returns_error_chunk() -> None:
    """When Anthropic returns 500 during streaming, the client gets an error chunk."""
    error = ProviderError(
        "Anthropic API error: 500",
        provider="anthropic",
        status_code=500,
    )
    server = OpenClawOpenAIServer(
        _FakeAgentRaisesOnStream(error),
        OpenClawOpenAIConfig(host="127.0.0.1", port=0, allow_streaming=True),
    )
    port = server.start()
    try:
        r = _post_chat(port, stream=True)
        chunks = _read_sse_json_lines(r.text)

        error_chunk = None
        for c in chunks:
            if c.get("error"):
                error_chunk = c
                break

        assert error_chunk is not None, "Missing error chunk for 500"
        assert error_chunk["error"]["code"] == 502  # 502 for upstream 5xx
        assert "anthropic" in error_chunk["error"]["message"].lower()
    finally:
        server.stop()


def test_stream_rate_limit_429_returns_error_chunk() -> None:
    """Rate limit errors should surface in the SSE stream."""
    error = ProviderError(
        "Anthropic rate limit exceeded",
        provider="anthropic",
        status_code=429,
    )
    server = OpenClawOpenAIServer(
        _FakeAgentRaisesOnStream(error),
        OpenClawOpenAIConfig(host="127.0.0.1", port=0, allow_streaming=True),
    )
    port = server.start()
    try:
        r = _post_chat(port, stream=True)
        chunks = _read_sse_json_lines(r.text)

        error_chunk = None
        for c in chunks:
            if c.get("error"):
                error_chunk = c
                break

        assert error_chunk is not None, "Missing error chunk for 429"
        assert error_chunk["error"]["code"] == 429
        assert "rate limit" in error_chunk["error"]["message"].lower()
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# Non-streaming tests
# ---------------------------------------------------------------------------


def test_nonstream_anthropic_529_returns_error_response() -> None:
    """When Anthropic returns 529 in non-streaming mode, the client gets
    an OpenAI-format error response with appropriate HTTP status."""
    error = ProviderError(
        "Anthropic API error: 529 - overloaded",
        provider="anthropic",
        status_code=529,
    )
    server = OpenClawOpenAIServer(
        _FakeAgentRaisesOnRun(error),
        OpenClawOpenAIConfig(host="127.0.0.1", port=0),
    )
    port = server.start()
    try:
        r = _post_chat(port, stream=False)
        assert r.status_code == 503
        body = r.json()
        assert "error" in body
        assert "overloaded" in body["error"]["message"].lower()
        assert body["error"]["type"] == "upstream_error"
    finally:
        server.stop()


def test_nonstream_anthropic_500_returns_error_response() -> None:
    """500 from upstream → 502 to client."""
    error = ProviderError(
        "Anthropic API error: 500",
        provider="anthropic",
        status_code=500,
    )
    server = OpenClawOpenAIServer(
        _FakeAgentRaisesOnRun(error),
        OpenClawOpenAIConfig(host="127.0.0.1", port=0),
    )
    port = server.start()
    try:
        r = _post_chat(port, stream=False)
        assert r.status_code == 502
        body = r.json()
        assert "error" in body
        assert body["error"]["type"] == "upstream_error"
    finally:
        server.stop()


def test_nonstream_generic_exception_returns_500() -> None:
    """Unexpected exceptions from agent.run() should return a 500 error."""
    error = RuntimeError("Something unexpected broke")
    server = OpenClawOpenAIServer(
        _FakeAgentRaisesOnRun(error),
        OpenClawOpenAIConfig(host="127.0.0.1", port=0),
    )
    port = server.start()
    try:
        r = _post_chat(port, stream=False)
        assert r.status_code == 500
        body = r.json()
        assert "error" in body
        assert body["error"]["type"] == "server_error"
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# ProviderError.status_code tests
# ---------------------------------------------------------------------------


def test_provider_error_preserves_status_code() -> None:
    """ProviderError should carry the upstream HTTP status code."""
    err = ProviderError("test", provider="anthropic", status_code=529)
    assert err.status_code == 529
    assert err.provider == "anthropic"


def test_provider_error_default_status_code_is_none() -> None:
    """ProviderError without status_code defaults to None."""
    err = ProviderError("test", provider="openai")
    assert err.status_code is None
