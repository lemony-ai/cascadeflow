"""Integration tests for proxy routing + execution."""

import json

import httpx
import pytest

from cascadeflow.proxy import ProxyHandler, ProxyRequest, ProxyRoute, ProxyRouter, ProxyService
from cascadeflow.telemetry import CostTracker


@pytest.mark.asyncio
async def test_proxy_service_end_to_end():
    async def transport_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        assert payload["model"] == "gpt-4o"
        assert request.url == httpx.URL("https://api.openai.test/v1/chat/completions")

        return httpx.Response(
            200,
            json={
                "id": "resp-123",
                "usage": {"prompt_tokens": 25, "completion_tokens": 25, "total_tokens": 50},
            },
        )

    tracker = CostTracker()
    route = ProxyRoute(
        name="openai-route",
        provider="openai",
        base_url="https://api.openai.test",
    )
    router = ProxyRouter([route])
    handler = ProxyHandler(
        cost_tracker=tracker, client=httpx.AsyncClient(transport=httpx.MockTransport(transport_handler))
    )
    service = ProxyService(router, handler)

    request = ProxyRequest(
        method="POST",
        path="/v1/chat/completions",
        headers={"x-correlation-id": "abc123"},
        body={"model": "gpt-4o", "messages": []},
    )

    async with handler:
        result = await service.handle(request)

    assert result.provider == "openai"
    assert result.cost == pytest.approx(0.000125)
    assert tracker.total_cost == pytest.approx(0.000125)
