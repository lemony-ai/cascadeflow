"""Paygentic billing integration for cascadeflow (opt-in).

This module provides a thin client and reporting helpers for:
- Creating customers
- Creating subscriptions
- Reporting usage events

Design goals:
- Explicit opt-in (nothing is auto-enabled)
- Fail-open reporting (billing errors never block model responses)
- Deterministic idempotency keys for safe retries
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

import httpx

if TYPE_CHECKING:
    from cascadeflow.proxy.models import ProxyRequest, ProxyResult
    from cascadeflow.proxy.service import ProxyService

logger = logging.getLogger(__name__)


DEFAULT_PAYGENTIC_LIVE_URL = "https://api.paygentic.io"
DEFAULT_PAYGENTIC_SANDBOX_URL = "https://api.sandbox.paygentic.io"
_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class PaygenticAPIError(RuntimeError):
    """Raised when Paygentic returns an API error."""

    def __init__(self, message: str, status_code: int | None = None, payload: Any | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass
class PaygenticConfig:
    """Configuration for the Paygentic API client."""

    api_key: str
    merchant_id: str
    billable_metric_id: str
    base_url: str | None = None
    sandbox: bool = False
    timeout: float = 10.0
    max_retries: int = 2
    retry_backoff_seconds: float = 0.25

    @property
    def resolved_base_url(self) -> str:
        if self.base_url:
            return self.base_url.rstrip("/")
        return DEFAULT_PAYGENTIC_SANDBOX_URL if self.sandbox else DEFAULT_PAYGENTIC_LIVE_URL

    @classmethod
    def from_env(cls, *, prefix: str = "PAYGENTIC_") -> PaygenticConfig:
        """Load configuration from environment variables.

        Required:
        - PAYGENTIC_API_KEY
        - PAYGENTIC_MERCHANT_ID
        - PAYGENTIC_BILLABLE_METRIC_ID

        Optional:
        - PAYGENTIC_BASE_URL
        - PAYGENTIC_SANDBOX (true/false)
        - PAYGENTIC_TIMEOUT_SECONDS
        - PAYGENTIC_MAX_RETRIES
        - PAYGENTIC_RETRY_BACKOFF_SECONDS
        """

        import os

        api_key = os.getenv(f"{prefix}API_KEY", "").strip()
        merchant_id = os.getenv(f"{prefix}MERCHANT_ID", "").strip()
        billable_metric_id = os.getenv(f"{prefix}BILLABLE_METRIC_ID", "").strip()

        if not api_key:
            raise ValueError(f"Missing required environment variable: {prefix}API_KEY")
        if not merchant_id:
            raise ValueError(f"Missing required environment variable: {prefix}MERCHANT_ID")
        if not billable_metric_id:
            raise ValueError(f"Missing required environment variable: {prefix}BILLABLE_METRIC_ID")

        base_url = os.getenv(f"{prefix}BASE_URL")
        sandbox_raw = os.getenv(f"{prefix}SANDBOX", "false").strip().lower()
        timeout_raw = os.getenv(f"{prefix}TIMEOUT_SECONDS", "10")
        retries_raw = os.getenv(f"{prefix}MAX_RETRIES", "2")
        backoff_raw = os.getenv(f"{prefix}RETRY_BACKOFF_SECONDS", "0.25")

        return cls(
            api_key=api_key,
            merchant_id=merchant_id,
            billable_metric_id=billable_metric_id,
            base_url=base_url,
            sandbox=sandbox_raw in {"1", "true", "yes", "on"},
            timeout=float(timeout_raw),
            max_retries=int(retries_raw),
            retry_backoff_seconds=float(backoff_raw),
        )


def _iso_timestamp(value: str | None = None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_customer_address(address: dict[str, Any]) -> None:
    required_keys = ("line1", "city", "country", "postalCode")
    missing = [key for key in required_keys if not address.get(key)]
    if missing:
        required = ", ".join(required_keys)
        raise ValueError(
            f"Customer address missing required fields: {', '.join(missing)}. "
            f"Expected keys: {required}"
        )


def _canonical_part(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return str(value)


class PaygenticClient:
    """Thin Paygentic API client with deterministic idempotency support."""

    def __init__(
        self,
        config: PaygenticConfig,
        *,
        client: httpx.Client | None = None,
        async_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = client
        self._async_client = async_client
        self._owns_client = client is None
        self._owns_async_client = async_client is None

    def __enter__(self) -> PaygenticClient:
        if self._client is None:
            self._client = httpx.Client(timeout=self.config.timeout)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    async def __aenter__(self) -> PaygenticClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.config.timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._owns_async_client and self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def create_idempotency_key(self, scope: str, *parts: Any) -> str:
        """Build a deterministic idempotency key for safe retries."""

        joined = "|".join(_canonical_part(p) for p in parts)
        digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24]
        return f"{scope}_{digest}"

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.config.resolved_base_url}{path}"

    def _headers(self, *, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _is_retryable(self, status_code: int) -> bool:
        return status_code in _TRANSIENT_STATUS_CODES

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        client = self._client or httpx.Client(timeout=self.config.timeout)
        if self._client is None:
            self._client = client

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = client.request(
                    method,
                    self._url(path),
                    headers=self._headers(idempotency_key=idempotency_key),
                    json=payload,
                    timeout=self.config.timeout,
                )
            except httpx.RequestError as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
                time.sleep(self.config.retry_backoff_seconds * (2**attempt))
                continue

            if response.status_code >= 400:
                if self._is_retryable(response.status_code) and attempt < self.config.max_retries:
                    time.sleep(self.config.retry_backoff_seconds * (2**attempt))
                    continue
                payload_obj: Any
                try:
                    payload_obj = response.json()
                except ValueError:
                    payload_obj = response.text
                raise PaygenticAPIError(
                    f"Paygentic API request failed with status {response.status_code}",
                    status_code=response.status_code,
                    payload=payload_obj,
                )

            if not response.content:
                return {}
            try:
                return response.json()
            except ValueError:
                return {"raw": response.text}

        raise PaygenticAPIError(f"Paygentic API transport failed after retries: {last_error}")

    async def _arequest(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        client = self._async_client or httpx.AsyncClient(timeout=self.config.timeout)
        if self._async_client is None:
            self._async_client = client

        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = await client.request(
                    method,
                    self._url(path),
                    headers=self._headers(idempotency_key=idempotency_key),
                    json=payload,
                    timeout=self.config.timeout,
                )
            except httpx.RequestError as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
                await asyncio.sleep(self.config.retry_backoff_seconds * (2**attempt))
                continue

            if response.status_code >= 400:
                if self._is_retryable(response.status_code) and attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_backoff_seconds * (2**attempt))
                    continue
                payload_obj: Any
                try:
                    payload_obj = response.json()
                except ValueError:
                    payload_obj = response.text
                raise PaygenticAPIError(
                    f"Paygentic API request failed with status {response.status_code}",
                    status_code=response.status_code,
                    payload=payload_obj,
                )

            if not response.content:
                return {}
            try:
                return response.json()
            except ValueError:
                return {"raw": response.text}

        raise PaygenticAPIError(f"Paygentic API transport failed after retries: {last_error}")

    def create_customer(
        self,
        *,
        email: str,
        name: str,
        address: dict[str, Any],
        phone: str | None = None,
        tax_rates: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _validate_customer_address(address)

        consumer: dict[str, Any] = {
            "email": email,
            "name": name,
            "address": address,
        }
        if phone:
            consumer["phone"] = phone
        if tax_rates:
            consumer["taxRates"] = tax_rates

        payload = {
            "merchantId": self.config.merchant_id,
            "consumer": consumer,
        }
        return self._request("POST", "/v0/customers", payload, idempotency_key=idempotency_key)

    async def acreate_customer(
        self,
        *,
        email: str,
        name: str,
        address: dict[str, Any],
        phone: str | None = None,
        tax_rates: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _validate_customer_address(address)

        consumer: dict[str, Any] = {
            "email": email,
            "name": name,
            "address": address,
        }
        if phone:
            consumer["phone"] = phone
        if tax_rates:
            consumer["taxRates"] = tax_rates

        payload = {
            "merchantId": self.config.merchant_id,
            "consumer": consumer,
        }
        return await self._arequest("POST", "/v0/customers", payload, idempotency_key=idempotency_key)

    def create_subscription(
        self,
        *,
        plan_id: str,
        name: str,
        started_at: str | None = None,
        customer_id: str | None = None,
        customer: dict[str, Any] | None = None,
        auto_charge: bool = False,
        tax_exempt: bool = False,
        ending_at: str | None = None,
        minimum_account_balance: str | None = None,
        redirect_urls: dict[str, Any] | None = None,
        test_clock_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if not customer_id and not customer:
            raise ValueError("Either customer_id or customer payload is required")

        payload: dict[str, Any] = {
            "name": name,
            "planId": plan_id,
            "startedAt": _iso_timestamp(started_at),
            "autoCharge": auto_charge,
            "taxExempt": tax_exempt,
        }

        if customer_id:
            payload["customerId"] = customer_id
        if customer:
            payload["customer"] = customer
        if ending_at:
            payload["endingAt"] = ending_at
        if minimum_account_balance:
            payload["minimumAccountBalance"] = minimum_account_balance
        if redirect_urls:
            payload["redirectUrls"] = redirect_urls
        if test_clock_id:
            payload["testClockId"] = test_clock_id

        return self._request("POST", "/v0/subscriptions", payload, idempotency_key=idempotency_key)

    async def acreate_subscription(
        self,
        *,
        plan_id: str,
        name: str,
        started_at: str | None = None,
        customer_id: str | None = None,
        customer: dict[str, Any] | None = None,
        auto_charge: bool = False,
        tax_exempt: bool = False,
        ending_at: str | None = None,
        minimum_account_balance: str | None = None,
        redirect_urls: dict[str, Any] | None = None,
        test_clock_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if not customer_id and not customer:
            raise ValueError("Either customer_id or customer payload is required")

        payload: dict[str, Any] = {
            "name": name,
            "planId": plan_id,
            "startedAt": _iso_timestamp(started_at),
            "autoCharge": auto_charge,
            "taxExempt": tax_exempt,
        }

        if customer_id:
            payload["customerId"] = customer_id
        if customer:
            payload["customer"] = customer
        if ending_at:
            payload["endingAt"] = ending_at
        if minimum_account_balance:
            payload["minimumAccountBalance"] = minimum_account_balance
        if redirect_urls:
            payload["redirectUrls"] = redirect_urls
        if test_clock_id:
            payload["testClockId"] = test_clock_id

        return await self._arequest(
            "POST", "/v0/subscriptions", payload, idempotency_key=idempotency_key
        )

    def create_usage_event(
        self,
        *,
        customer_id: str,
        quantity: float,
        timestamp: str | None = None,
        idempotency_key: str | None = None,
        billable_metric_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        entitlement_id: str | None = None,
        description: str | None = None,
        price: str | None = None,
    ) -> dict[str, Any]:
        metric_id = billable_metric_id or self.config.billable_metric_id
        if not metric_id:
            raise ValueError("billable_metric_id is required")

        effective_timestamp = _iso_timestamp(timestamp)
        idem = idempotency_key or self.create_idempotency_key(
            "usage",
            self.config.merchant_id,
            customer_id,
            metric_id,
            effective_timestamp,
            quantity,
        )

        usage_property: dict[str, Any] = {
            "billableMetricId": metric_id,
            "quantity": quantity,
        }
        if price is not None:
            usage_property["price"] = price

        payload: dict[str, Any] = {
            "idempotencyKey": idem,
            "customerId": customer_id,
            "merchantId": self.config.merchant_id,
            "timestamp": effective_timestamp,
            "properties": [usage_property],
        }
        if metadata:
            payload["metadata"] = metadata
        if entitlement_id:
            payload["entitlementId"] = entitlement_id
        if description:
            payload["description"] = description

        return self._request("POST", "/v0/usage", payload, idempotency_key=idem)

    async def acreate_usage_event(
        self,
        *,
        customer_id: str,
        quantity: float,
        timestamp: str | None = None,
        idempotency_key: str | None = None,
        billable_metric_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        entitlement_id: str | None = None,
        description: str | None = None,
        price: str | None = None,
    ) -> dict[str, Any]:
        metric_id = billable_metric_id or self.config.billable_metric_id
        if not metric_id:
            raise ValueError("billable_metric_id is required")

        effective_timestamp = _iso_timestamp(timestamp)
        idem = idempotency_key or self.create_idempotency_key(
            "usage",
            self.config.merchant_id,
            customer_id,
            metric_id,
            effective_timestamp,
            quantity,
        )

        usage_property: dict[str, Any] = {
            "billableMetricId": metric_id,
            "quantity": quantity,
        }
        if price is not None:
            usage_property["price"] = price

        payload: dict[str, Any] = {
            "idempotencyKey": idem,
            "customerId": customer_id,
            "merchantId": self.config.merchant_id,
            "timestamp": effective_timestamp,
            "properties": [usage_property],
        }
        if metadata:
            payload["metadata"] = metadata
        if entitlement_id:
            payload["entitlementId"] = entitlement_id
        if description:
            payload["description"] = description

        return await self._arequest("POST", "/v0/usage", payload, idempotency_key=idem)


class PaygenticUsageReporter:
    """Maps cascadeflow proxy results to Paygentic usage events."""

    def __init__(
        self,
        client: PaygenticClient,
        *,
        quantity_mode: str = "tokens",
        cost_scale: int = 1_000_000,
        customer_header: str = "x-cascadeflow-customer-id",
        request_id_header: str = "x-request-id",
    ) -> None:
        if quantity_mode not in {"tokens", "cost_usd", "requests"}:
            raise ValueError("quantity_mode must be one of: tokens, cost_usd, requests")
        if cost_scale <= 0:
            raise ValueError("cost_scale must be a positive integer")
        self.client = client
        self.quantity_mode = quantity_mode
        self.cost_scale = int(cost_scale)
        self.customer_header = customer_header.lower()
        self.request_id_header = request_id_header.lower()

    def _extract_quantity(self, result: ProxyResult) -> int | None:
        if self.quantity_mode == "requests":
            return 1

        if self.quantity_mode == "tokens":
            usage = getattr(result, "usage", None)
            if not usage:
                return None
            tokens = float(getattr(usage, "total_tokens", 0) or 0)
            quantity = int(round(tokens))
            return quantity if quantity > 0 else None

        cost = float(getattr(result, "cost", 0) or 0)
        scaled_cost = int(round(cost * self.cost_scale))
        return scaled_cost if scaled_cost > 0 else None

    def _build_metadata(
        self,
        result: ProxyResult,
        extra_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        usage = getattr(result, "usage", None)
        metadata: dict[str, Any] = {
            "integration": "cascadeflow-paygentic",
            "provider": getattr(result, "provider", "unknown"),
            "model": getattr(result, "model", "unknown"),
            "latency_ms": getattr(result, "latency_ms", None),
            "cost_usd": getattr(result, "cost", None),
            "quantity_mode": self.quantity_mode,
        }
        if usage:
            metadata["input_tokens"] = getattr(usage, "input_tokens", None)
            metadata["output_tokens"] = getattr(usage, "output_tokens", None)
            metadata["total_tokens"] = getattr(usage, "total_tokens", None)
        if self.quantity_mode == "cost_usd":
            metadata["cost_scale"] = self.cost_scale
            metadata["cost_usd_raw"] = getattr(result, "cost", None)

        if extra_metadata:
            metadata.update(extra_metadata)
        return metadata

    def build_usage_event(
        self,
        *,
        result: ProxyResult,
        customer_id: str,
        request_id: str | None = None,
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        quantity = self._extract_quantity(result)
        if quantity is None:
            return None

        ts = _iso_timestamp(timestamp)
        idem = self.client.create_idempotency_key(
            "usage",
            customer_id,
            request_id or "no-request-id",
            getattr(result, "provider", "unknown"),
            getattr(result, "model", "unknown"),
            self.quantity_mode,
            quantity,
            ts,
        )

        return {
            "customer_id": customer_id,
            "quantity": quantity,
            "timestamp": ts,
            "idempotency_key": idem,
            "metadata": self._build_metadata(result, metadata),
        }

    async def report_proxy_result(
        self,
        *,
        result: ProxyResult,
        customer_id: str,
        request_id: str | None = None,
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Report a proxy result to Paygentic. Returns response or None.

        This method is fail-open by design. Any Paygentic failures are logged and
        swallowed to avoid impacting request handling.
        """

        payload = self.build_usage_event(
            result=result,
            customer_id=customer_id,
            request_id=request_id,
            timestamp=timestamp,
            metadata=metadata,
        )
        if not payload:
            return None

        try:
            return await self.client.acreate_usage_event(**payload)
        except Exception as exc:  # pragma: no cover - intentionally fail-open
            logger.warning("Paygentic usage reporting failed (ignored): %s", exc)
            return None


def _header_value(headers: dict[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


class PaygenticProxyService:
    """Wrap ProxyService and report usage events to Paygentic (opt-in)."""

    def __init__(
        self,
        service: ProxyService,
        reporter: PaygenticUsageReporter,
        *,
        customer_resolver: Callable[[ProxyRequest, ProxyResult], str | None] | None = None,
        request_id_resolver: Callable[[ProxyRequest, ProxyResult], str | None] | None = None,
        report_in_background: bool = True,
    ) -> None:
        self.service = service
        self.reporter = reporter
        self.customer_resolver = customer_resolver
        self.request_id_resolver = request_id_resolver
        self.report_in_background = report_in_background
        self._pending_tasks: set[asyncio.Task[dict[str, Any] | None]] = set()

    def _track_task(self, task: asyncio.Task[dict[str, Any] | None]) -> None:
        self._pending_tasks.add(task)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task[dict[str, Any] | None]) -> None:
        self._pending_tasks.discard(task)
        if task.cancelled():
            return
        try:
            task.result()
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.warning("Paygentic background reporting task failed (ignored): %s", exc)

    async def flush(self, *, timeout: float | None = None) -> None:
        """Wait for in-flight background reporting tasks.

        This is optional and mainly useful for graceful shutdown and tests.
        """
        if not self._pending_tasks:
            return
        tasks = tuple(self._pending_tasks)
        done, pending = await asyncio.wait(tasks, timeout=timeout)
        self._pending_tasks.difference_update(done)
        for task in pending:
            task.cancel()
            self._pending_tasks.discard(task)

    async def handle(self, request: ProxyRequest) -> ProxyResult:
        result = await self.service.handle(request)

        customer_id: str | None
        if self.customer_resolver:
            customer_id = self.customer_resolver(request, result)
        else:
            customer_id = _header_value(request.headers, self.reporter.customer_header)

        if not customer_id:
            return result

        if self.request_id_resolver:
            request_id = self.request_id_resolver(request, result)
        else:
            request_id = _header_value(request.headers, self.reporter.request_id_header)

        if self.report_in_background:
            task = asyncio.create_task(
                self.reporter.report_proxy_result(
                    result=result,
                    customer_id=customer_id,
                    request_id=request_id,
                )
            )
            self._track_task(task)
        else:
            await self.reporter.report_proxy_result(
                result=result,
                customer_id=customer_id,
                request_id=request_id,
            )
        return result


__all__ = [
    "DEFAULT_PAYGENTIC_LIVE_URL",
    "DEFAULT_PAYGENTIC_SANDBOX_URL",
    "PaygenticAPIError",
    "PaygenticConfig",
    "PaygenticClient",
    "PaygenticUsageReporter",
    "PaygenticProxyService",
]
