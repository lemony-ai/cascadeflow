from __future__ import annotations

import json
import time

import httpx
import pytest

from cascadeflow.integrations.paygentic import (
    PaygenticClient,
    PaygenticConfig,
    PaygenticProxyService,
    PaygenticUsageReporter,
)
from cascadeflow.proxy.models import ProxyRequest, ProxyResult, ProxyUsage


def _config() -> PaygenticConfig:
    return PaygenticConfig(
        api_key="test-key",
        merchant_id="merchant-1",
        billable_metric_id="metric-1",
        base_url="https://api.test.paygentic.local",
        max_retries=2,
        retry_backoff_seconds=0.001,
    )


def test_create_usage_event_builds_expected_payload_and_headers() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["idempotency"] = request.headers.get("Idempotency-Key")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    paygentic = PaygenticClient(_config(), client=client)

    response = paygentic.create_usage_event(
        customer_id="cust-1",
        quantity=42,
        timestamp="2026-02-16T20:00:00Z",
        idempotency_key="idem-123",
        metadata={"source": "test"},
    )

    assert response == {"ok": True}
    assert captured["url"] == "https://api.test.paygentic.local/v0/usage"
    assert captured["auth"] == "Bearer test-key"
    assert captured["idempotency"] == "idem-123"
    assert captured["body"] == {
        "idempotencyKey": "idem-123",
        "customerId": "cust-1",
        "merchantId": "merchant-1",
        "timestamp": "2026-02-16T20:00:00Z",
        "properties": [{"billableMetricId": "metric-1", "quantity": 42}],
        "metadata": {"source": "test"},
    }


def test_request_retries_on_transient_status_code() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(503, json={"error": "temporarily unavailable"})
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    paygentic = PaygenticClient(_config(), client=client)

    response = paygentic.create_customer(
        email="test@example.com",
        name="Test",
        address={
            "line1": "Main Street 1",
            "city": "Zurich",
            "country": "CH",
            "postalCode": "8000",
        },
    )

    assert response == {"ok": True}
    assert calls["count"] == 2


def test_create_customer_requires_valid_address() -> None:
    paygentic = PaygenticClient(
        _config(), client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    )
    with pytest.raises(ValueError, match="Customer address missing required fields"):
        paygentic.create_customer(
            email="test@example.com",
            name="Test",
            address={"line1": "Main Street 1", "city": "Zurich"},
        )


@pytest.mark.asyncio
async def test_usage_reporter_maps_proxy_result_to_usage_event() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"eventId": "evt_1"})

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    paygentic = PaygenticClient(_config(), async_client=async_client)
    reporter = PaygenticUsageReporter(paygentic, quantity_mode="tokens")

    result = ProxyResult(
        status_code=200,
        headers={},
        data={"ok": True},
        provider="openai",
        model="gpt-4o-mini",
        latency_ms=12.3,
        usage=ProxyUsage(input_tokens=100, output_tokens=50, total_tokens=150),
        cost=0.0009,
    )

    response = await reporter.report_proxy_result(
        result=result,
        customer_id="cust_42",
        request_id="req_123",
        timestamp="2026-02-16T20:00:00Z",
        metadata={"tenant": "team-a"},
    )

    assert response == {"eventId": "evt_1"}
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["customerId"] == "cust_42"
    assert body["properties"][0]["quantity"] == 150
    assert body["metadata"]["tenant"] == "team-a"
    assert body["metadata"]["quantity_mode"] == "tokens"

    await async_client.aclose()


@pytest.mark.asyncio
async def test_usage_reporter_cost_mode_scales_to_integer_quantity() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"eventId": "evt_cost"})

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    paygentic = PaygenticClient(_config(), async_client=async_client)
    reporter = PaygenticUsageReporter(paygentic, quantity_mode="cost_usd", cost_scale=1_000_000)

    result = ProxyResult(
        status_code=200,
        headers={},
        data={"ok": True},
        provider="openai",
        model="gpt-5-mini",
        latency_ms=10.0,
        usage=ProxyUsage(input_tokens=10, output_tokens=10, total_tokens=20),
        cost=0.00123,
    )

    response = await reporter.report_proxy_result(
        result=result,
        customer_id="cust_cost_1",
        request_id="req_cost_1",
        timestamp="2026-02-16T20:00:00Z",
    )

    assert response == {"eventId": "evt_cost"}
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["properties"][0]["quantity"] == 1230
    assert body["metadata"]["cost_scale"] == 1_000_000
    assert body["metadata"]["cost_usd_raw"] == 0.00123
    assert body["metadata"]["quantity_mode"] == "cost_usd"

    await async_client.aclose()


@pytest.mark.asyncio
async def test_proxy_service_is_fail_open_when_reporting_fails() -> None:
    class FakeService:
        async def handle(self, request: ProxyRequest) -> ProxyResult:
            return ProxyResult(
                status_code=200,
                headers={},
                data={"ok": True},
                provider="openai",
                model="gpt-4o-mini",
                latency_ms=7.0,
                usage=ProxyUsage(input_tokens=10, output_tokens=5, total_tokens=15),
                cost=0.0001,
            )

    class FailingClient:
        async def acreate_usage_event(self, **kwargs):
            raise RuntimeError("network down")

        def create_idempotency_key(self, scope: str, *parts: object) -> str:
            return "fixed-idempotency"

    reporter = PaygenticUsageReporter(FailingClient())
    proxy = PaygenticProxyService(FakeService(), reporter)

    request = ProxyRequest(
        method="POST",
        path="/v1/chat/completions",
        headers={"x-cascadeflow-customer-id": "cust-99", "x-request-id": "req-99"},
        body={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )

    result = await proxy.handle(request)

    assert result.status_code == 200
    assert result.provider == "openai"
    await proxy.flush()


def test_proxy_service_skips_reporting_when_customer_header_missing() -> None:
    class FakeService:
        async def handle(self, request: ProxyRequest) -> ProxyResult:
            return ProxyResult(
                status_code=200,
                headers={},
                data={"ok": True},
                provider="openai",
                model="gpt-4o-mini",
                latency_ms=7.0,
                usage=ProxyUsage(input_tokens=10, output_tokens=5, total_tokens=15),
                cost=0.0001,
            )

    class SpyReporter:
        customer_header = "x-cascadeflow-customer-id"
        request_id_header = "x-request-id"

        def __init__(self):
            self.called = False

        async def report_proxy_result(self, **kwargs):
            self.called = True
            return None

    reporter = SpyReporter()
    proxy = PaygenticProxyService(FakeService(), reporter)

    request = ProxyRequest(
        method="POST",
        path="/v1/chat/completions",
        headers={},
        body={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )

    import asyncio

    result = asyncio.run(proxy.handle(request))

    assert result.status_code == 200
    assert reporter.called is False


@pytest.mark.asyncio
async def test_proxy_service_background_reporting_is_non_blocking_by_default() -> None:
    class FakeService:
        async def handle(self, request: ProxyRequest) -> ProxyResult:
            return ProxyResult(
                status_code=200,
                headers={},
                data={"ok": True},
                provider="openai",
                model="gpt-4o-mini",
                latency_ms=7.0,
                usage=ProxyUsage(input_tokens=10, output_tokens=5, total_tokens=15),
                cost=0.0001,
            )

    class SlowReporter:
        customer_header = "x-cascadeflow-customer-id"
        request_id_header = "x-request-id"

        def __init__(self) -> None:
            self.called = False

        async def report_proxy_result(self, **kwargs):
            await asyncio.sleep(0.1)
            self.called = True
            return {"ok": True}

    import asyncio

    reporter = SlowReporter()
    proxy = PaygenticProxyService(FakeService(), reporter)
    request = ProxyRequest(
        method="POST",
        path="/v1/chat/completions",
        headers={"x-cascadeflow-customer-id": "cust-bg", "x-request-id": "req-bg"},
        body={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )

    start = time.perf_counter()
    result = await proxy.handle(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert result.status_code == 200
    assert elapsed_ms < 80.0
    assert reporter.called is False

    await proxy.flush(timeout=2.0)
    assert reporter.called is True


@pytest.mark.asyncio
async def test_proxy_service_can_run_reporting_in_blocking_mode() -> None:
    class FakeService:
        async def handle(self, request: ProxyRequest) -> ProxyResult:
            return ProxyResult(
                status_code=200,
                headers={},
                data={"ok": True},
                provider="openai",
                model="gpt-4o-mini",
                latency_ms=7.0,
                usage=ProxyUsage(input_tokens=10, output_tokens=5, total_tokens=15),
                cost=0.0001,
            )

    class SlowReporter:
        customer_header = "x-cascadeflow-customer-id"
        request_id_header = "x-request-id"

        def __init__(self) -> None:
            self.called = False

        async def report_proxy_result(self, **kwargs):
            await asyncio.sleep(0.1)
            self.called = True
            return {"ok": True}

    import asyncio

    reporter = SlowReporter()
    proxy = PaygenticProxyService(FakeService(), reporter, report_in_background=False)
    request = ProxyRequest(
        method="POST",
        path="/v1/chat/completions",
        headers={"x-cascadeflow-customer-id": "cust-sync", "x-request-id": "req-sync"},
        body={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )

    start = time.perf_counter()
    result = await proxy.handle(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert result.status_code == 200
    assert elapsed_ms >= 80.0
    assert reporter.called is True
