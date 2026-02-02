"""Tests for proxy error handling."""

import httpx
import pytest

from cascadeflow.proxy import ProxyHandler, ProxyPlan, ProxyRequest, ProxyRoute
from cascadeflow.proxy.errors import ProxyTransportError, ProxyUpstreamError


@pytest.mark.asyncio
async def test_proxy_upstream_error():
    async def transport_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    route = ProxyRoute(
        name="error-route",
        provider="openai",
        base_url="https://api.openai.test",
    )
    plan = ProxyPlan(
        route=route,
        request=ProxyRequest(
            method="POST",
            path="/v1/chat/completions",
            headers={},
            body={"model": "gpt-4o", "messages": []},
        ),
        model="gpt-4o",
        provider="openai",
    )

    async with ProxyHandler(
        client=httpx.AsyncClient(transport=httpx.MockTransport(transport_handler))
    ) as handler:
        with pytest.raises(ProxyUpstreamError) as excinfo:
            await handler.execute(plan)

    assert excinfo.value.status_code == 500


@pytest.mark.asyncio
async def test_proxy_transport_error():
    async def transport_handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed")

    route = ProxyRoute(
        name="connect-error",
        provider="openai",
        base_url="https://api.openai.test",
    )
    plan = ProxyPlan(
        route=route,
        request=ProxyRequest(
            method="POST",
            path="/v1/chat/completions",
            headers={},
            body={"model": "gpt-4o", "messages": []},
        ),
        model="gpt-4o",
        provider="openai",
    )

    async with ProxyHandler(
        client=httpx.AsyncClient(transport=httpx.MockTransport(transport_handler))
    ) as handler:
        with pytest.raises(ProxyTransportError):
            await handler.execute(plan)
