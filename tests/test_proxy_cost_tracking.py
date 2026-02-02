"""Tests for cost tracking through proxy."""

import httpx
import pytest

from cascadeflow.proxy import ProxyHandler, ProxyPlan, ProxyRequest, ProxyRoute
from cascadeflow.telemetry import CostTracker


@pytest.mark.asyncio
async def test_proxy_cost_tracking_updates_tracker():
    async def transport_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "resp-1",
                "usage": {"prompt_tokens": 500, "completion_tokens": 500, "total_tokens": 1000},
            },
        )

    tracker = CostTracker()
    route = ProxyRoute(
        name="openai-route",
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
        cost_tracker=tracker,
        client=httpx.AsyncClient(transport=httpx.MockTransport(transport_handler)),
    ) as handler:
        result = await handler.execute(plan)

    assert result.cost == pytest.approx(0.0025)
    assert tracker.total_cost == pytest.approx(0.0025)
    assert tracker.by_model["gpt-4o"] == pytest.approx(0.0025)
    assert tracker.by_provider["openai"] == pytest.approx(0.0025)
    assert tracker.entries[0].tokens == 1000
