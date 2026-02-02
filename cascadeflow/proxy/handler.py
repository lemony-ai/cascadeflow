"""Proxy request execution and response handling."""

from __future__ import annotations

import json
import time

import httpx

from cascadeflow.schema.model_registry import ModelRegistry
from cascadeflow.telemetry.cost_tracker import CostTracker

from .costs import calculate_cost, extract_usage
from .errors import ProxyTransportError, ProxyUpstreamError
from .models import ProxyPlan, ProxyResult


class ProxyHandler:
    """Execute proxy plans against upstream providers."""

    def __init__(
        self,
        cost_tracker: CostTracker | None = None,
        registry: ModelRegistry | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.cost_tracker = cost_tracker
        self.registry = registry or ModelRegistry()
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> ProxyHandler:
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def execute(self, plan: ProxyPlan) -> ProxyResult:
        """Execute a proxy plan and return a structured result."""
        client = self._client or httpx.AsyncClient()
        if self._client is None:
            self._client = client

        headers = dict(plan.route.default_headers)
        headers.update(plan.request.headers)
        if plan.route.api_key and "authorization" not in {k.lower(): v for k, v in headers.items()}:
            headers["Authorization"] = f"Bearer {plan.route.api_key}"

        url = f"{plan.route.base_url}{plan.request.path}"

        start = time.monotonic()
        try:
            response = await client.request(
                plan.request.method,
                url,
                headers=headers,
                json=plan.request.body,
                timeout=plan.route.timeout,
            )
        except httpx.RequestError as exc:
            raise ProxyTransportError(f"Proxy transport error: {exc}") from exc
        latency_ms = (time.monotonic() - start) * 1000

        data = self._parse_response(response)
        if response.status_code >= 400:
            raise ProxyUpstreamError(
                message=f"Upstream error ({response.status_code})",
                status_code=response.status_code,
                payload=data,
            )

        usage = extract_usage(data)
        cost = calculate_cost(plan.model, usage, plan.route, self.registry)

        if self.cost_tracker and usage and cost is not None:
            self.cost_tracker.add_cost(
                model=plan.model,
                provider=plan.provider,
                tokens=usage.total_tokens,
                cost=cost,
                metadata={"proxy": True, "route": plan.route.name},
            )

        return ProxyResult(
            status_code=response.status_code,
            headers=dict(response.headers),
            data=data,
            provider=plan.provider,
            model=plan.model,
            latency_ms=latency_ms,
            usage=usage,
            cost=cost,
        )

    @staticmethod
    def _parse_response(response: httpx.Response):
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        try:
            return response.json()
        except json.JSONDecodeError:
            return response.text
