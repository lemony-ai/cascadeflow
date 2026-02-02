"""Tests for proxy request/response handling."""

import json

import httpx
import pytest

from cascadeflow.proxy import ProxyHandler, ProxyPlan, ProxyRequest, ProxyResult, ProxyRoute


@pytest.mark.asyncio
async def test_proxy_handler_success():
    async def transport_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        assert payload["model"] == "gpt-4o"
        assert request.headers["x-trace"] == "trace-id"
        assert request.headers["authorization"] == "Bearer test-key"

        return httpx.Response(
            200,
            json={
                "id": "resp-1",
                "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
            },
        )

    route = ProxyRoute(
        name="openai-route",
        provider="openai",
        base_url="https://api.openai.test",
        api_key="test-key",
        cost_per_1k_tokens=0.01,
    )
    request = ProxyRequest(
        method="POST",
        path="/v1/chat/completions",
        headers={"x-trace": "trace-id"},
        body={"model": "gpt-4o", "messages": []},
    )
    plan = ProxyPlan(route=route, request=request, model="gpt-4o", provider="openai")

    async with ProxyHandler(
        client=httpx.AsyncClient(transport=httpx.MockTransport(transport_handler))
    ) as handler:
        result = await handler.execute(plan)

    assert isinstance(result, ProxyResult)
    assert result.status_code == 200
    assert result.cost == pytest.approx(0.00025)
    assert result.usage.total_tokens == 25


@pytest.mark.asyncio
async def test_proxy_handler_parses_text_response():
    async def transport_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="plain text")

    route = ProxyRoute(
        name="text-route",
        provider="custom",
        base_url="https://text.example",
    )
    request = ProxyRequest(
        method="GET",
        path="/v1/ping",
        headers={},
        body={"model": "custom-model"},
    )
    plan = ProxyPlan(route=route, request=request, model="custom-model", provider="custom")

    async with ProxyHandler(
        client=httpx.AsyncClient(transport=httpx.MockTransport(transport_handler))
    ) as handler:
        result = await handler.execute(plan)

    assert result.data == "plain text"
