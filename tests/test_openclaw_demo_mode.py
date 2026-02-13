"""End-to-end tests for OpenClaw server --demo-mode."""

from __future__ import annotations

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


CHAT_PAYLOAD = {"model": "cascadeflow", "messages": [{"role": "user", "content": "hi"}]}


def _make_server(
    *,
    demo_mode: bool = True,
    demo_max_queries: int = 3,
    demo_window_seconds: int = 3600,
    auth_token: Optional[str] = None,
) -> OpenClawOpenAIServer:
    return OpenClawOpenAIServer(
        _FakeAgent(),
        OpenClawOpenAIConfig(
            host="127.0.0.1",
            port=0,
            allow_streaming=False,
            demo_mode=demo_mode,
            demo_max_queries=demo_max_queries,
            demo_window_seconds=demo_window_seconds,
            auth_token=auth_token,
        ),
    )


def test_demo_mode_allows_unauthenticated_requests() -> None:
    """Requests with no auth header should succeed in demo mode."""
    server = _make_server()
    port = server.start()
    try:
        url = f"http://127.0.0.1:{port}/v1/chat/completions"
        r = httpx.post(url, json=CHAT_PAYLOAD, timeout=5.0, trust_env=False)
        assert r.status_code == 200
        body = r.json()
        assert body["choices"][0]["message"]["content"] == "ok"
    finally:
        server.stop()


def test_demo_mode_response_includes_remaining_count() -> None:
    """Response metadata should include demo_queries_remaining and demo_queries_limit."""
    server = _make_server(demo_max_queries=5)
    port = server.start()
    try:
        url = f"http://127.0.0.1:{port}/v1/chat/completions"
        r = httpx.post(url, json=CHAT_PAYLOAD, timeout=5.0, trust_env=False)
        assert r.status_code == 200
        body = r.json()
        meta = body["cascadeflow"]["metadata"]
        assert meta["demo_queries_limit"] == 5
        assert meta["demo_queries_remaining"] == 4  # 5 - 1

        # Second request
        r = httpx.post(url, json=CHAT_PAYLOAD, timeout=5.0, trust_env=False)
        body = r.json()
        meta = body["cascadeflow"]["metadata"]
        assert meta["demo_queries_remaining"] == 3  # 5 - 2
    finally:
        server.stop()


def test_demo_mode_rate_limit_returns_429() -> None:
    """After exceeding the demo query limit, server returns 429."""
    server = _make_server(demo_max_queries=3)
    port = server.start()
    try:
        url = f"http://127.0.0.1:{port}/v1/chat/completions"

        # Send 3 requests (should all succeed)
        for i in range(3):
            r = httpx.post(url, json=CHAT_PAYLOAD, timeout=5.0, trust_env=False)
            assert r.status_code == 200, f"Request {i+1} failed with {r.status_code}"
            body = r.json()
            remaining = body["cascadeflow"]["metadata"]["demo_queries_remaining"]
            assert remaining == 2 - i  # 2, 1, 0

        # 4th request should be rate-limited
        r = httpx.post(url, json=CHAT_PAYLOAD, timeout=5.0, trust_env=False)
        assert r.status_code == 429
        body = r.json()
        assert "error" in body
        assert "Demo limit reached" in body["error"]["message"]
    finally:
        server.stop()


def test_demo_mode_authenticated_requests_bypass_limit() -> None:
    """Requests with a valid auth token bypass demo rate limiting."""
    server = _make_server(demo_max_queries=2, auth_token="secret")
    port = server.start()
    try:
        url = f"http://127.0.0.1:{port}/v1/chat/completions"
        auth_headers = {"Authorization": "Bearer secret"}

        # Exhaust demo limit with unauthenticated requests
        for _ in range(2):
            r = httpx.post(url, json=CHAT_PAYLOAD, timeout=5.0, trust_env=False)
            assert r.status_code == 200

        # Unauthenticated -> 429
        r = httpx.post(url, json=CHAT_PAYLOAD, timeout=5.0, trust_env=False)
        assert r.status_code == 429

        # Authenticated -> still 200 (no rate limit)
        r = httpx.post(url, json=CHAT_PAYLOAD, headers=auth_headers, timeout=5.0, trust_env=False)
        assert r.status_code == 200
        body = r.json()
        assert body["choices"][0]["message"]["content"] == "ok"
        # Authenticated responses should NOT have demo metadata
        meta = body["cascadeflow"]["metadata"]
        assert "demo_queries_remaining" not in meta
    finally:
        server.stop()


def test_demo_mode_invalid_token_treated_as_demo() -> None:
    """In demo mode, an invalid token is treated as a demo request (not 401)."""
    server = _make_server(demo_max_queries=5, auth_token="real-secret")
    port = server.start()
    try:
        url = f"http://127.0.0.1:{port}/v1/chat/completions"

        # Invalid token -> allowed through as demo (transition period for old clients)
        r = httpx.post(
            url,
            json=CHAT_PAYLOAD,
            headers={"Authorization": "Bearer wrong-key"},
            timeout=5.0,
            trust_env=False,
        )
        assert r.status_code == 200
        body = r.json()
        meta = body["cascadeflow"]["metadata"]
        assert "demo_queries_remaining" in meta
        assert meta["demo_queries_limit"] == 5
    finally:
        server.stop()


def test_demo_mode_no_demo_metadata_when_disabled() -> None:
    """When demo_mode is off, responses should not contain demo metadata."""
    server = _make_server(demo_mode=False)
    port = server.start()
    try:
        url = f"http://127.0.0.1:{port}/v1/chat/completions"
        r = httpx.post(url, json=CHAT_PAYLOAD, timeout=5.0, trust_env=False)
        assert r.status_code == 200
        body = r.json()
        meta = body["cascadeflow"]["metadata"]
        assert "demo_queries_remaining" not in meta
        assert "demo_queries_limit" not in meta
    finally:
        server.stop()
