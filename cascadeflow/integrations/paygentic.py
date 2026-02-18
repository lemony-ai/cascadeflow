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
import collections
import hashlib
import json
import logging
import math
import os
import sqlite3
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
_NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 409, 422}
PAYGENTIC_DELIVERY_MODES = {"sync", "background", "durable_outbox"}


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


class _PaygenticOutbox:
    """Simple SQLite-backed outbox for durable delivery retries."""

    def __init__(self, path: str) -> None:
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paygentic_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at REAL NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                last_error TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paygentic_outbox_dead_letter (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                attempts INTEGER NOT NULL,
                dropped_at REAL NOT NULL,
                reason TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def enqueue(self, payload: dict[str, Any]) -> bool:
        idem = str(payload.get("idempotency_key", "")).strip()
        if not idem:
            raise ValueError("Outbox payload requires idempotency_key")
        now = time.time()
        cursor = self._conn.execute(
            """
            INSERT INTO paygentic_outbox
                (idempotency_key, payload_json, attempts, next_attempt_at, created_at, updated_at)
            VALUES (?, ?, 0, ?, ?, ?)
            ON CONFLICT(idempotency_key) DO NOTHING
            """,
            (idem, json.dumps(payload, sort_keys=True), now, now, now),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def size(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM paygentic_outbox").fetchone()
        return int(row[0] if row else 0)

    def dead_letter_size(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM paygentic_outbox_dead_letter").fetchone()
        return int(row[0] if row else 0)

    def fetch_ready(self, *, now: float, limit: int) -> list[tuple[int, int, dict[str, Any]]]:
        rows = self._conn.execute(
            """
            SELECT id, attempts, payload_json
            FROM paygentic_outbox
            WHERE next_attempt_at <= ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (now, limit),
        ).fetchall()
        events: list[tuple[int, int, dict[str, Any]]] = []
        for row in rows:
            event_id = int(row[0])
            attempts = int(row[1])
            payload = json.loads(row[2])
            events.append((event_id, attempts, payload))
        return events

    def ack(self, event_id: int) -> None:
        self._conn.execute("DELETE FROM paygentic_outbox WHERE id = ?", (event_id,))
        self._conn.commit()

    def dead_letter(self, payload: dict[str, Any], *, attempts: int, reason: str) -> None:
        idem = str(payload.get("idempotency_key", "")).strip()
        payload_json = json.dumps(payload, sort_keys=True)
        payload_sha256 = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO paygentic_outbox_dead_letter
                (idempotency_key, payload_json, payload_sha256, attempts, dropped_at, reason)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                idem or payload_sha256,
                payload_json,
                payload_sha256,
                int(attempts),
                time.time(),
                reason[:200],
            ),
        )
        self._conn.commit()

    def reschedule(
        self, event_id: int, *, attempts: int, next_attempt_at: float, error: str
    ) -> None:
        self._conn.execute(
            """
            UPDATE paygentic_outbox
            SET attempts = ?, next_attempt_at = ?, updated_at = ?, last_error = ?
            WHERE id = ?
            """,
            (attempts, next_attempt_at, time.time(), error[:1000], event_id),
        )
        self._conn.commit()


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

    def is_retryable_error(self, exc: Exception) -> bool:
        if isinstance(exc, PaygenticAPIError):
            if exc.status_code in _NON_RETRYABLE_STATUS_CODES:
                return False
            return exc.status_code in _TRANSIENT_STATUS_CODES or exc.status_code is None
        if isinstance(exc, httpx.RequestError):
            return True
        return True

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
        return await self._arequest(
            "POST", "/v0/customers", payload, idempotency_key=idempotency_key
        )

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
        delivery_mode: str | None = None,
        outbox_path: str | None = None,
        outbox_batch_size: int = 100,
        outbox_poll_interval_seconds: float = 0.5,
        outbox_max_attempts: int = 8,
        outbox_retry_backoff_seconds: float = 1.0,
        outbox_send_concurrency: int = 4,
        sync_timeout_seconds: float = 0.2,
        sync_timeout_fallback_mode: str = "durable_outbox",
        max_concurrent_sends: int = 16,
        max_background_tasks: int = 2048,
        circuit_breaker_failure_threshold: int = 10,
        circuit_breaker_cooldown_seconds: float = 5.0,
    ) -> None:
        self.service = service
        self.reporter = reporter
        self.customer_resolver = customer_resolver
        self.request_id_resolver = request_id_resolver
        resolved_mode = (
            ("background" if report_in_background else "sync")
            if delivery_mode is None
            else delivery_mode
        )
        if resolved_mode not in PAYGENTIC_DELIVERY_MODES:
            allowed = ", ".join(sorted(PAYGENTIC_DELIVERY_MODES))
            raise ValueError(f"delivery_mode must be one of: {allowed}")
        if resolved_mode == "durable_outbox" and not outbox_path:
            raise ValueError("outbox_path is required when delivery_mode='durable_outbox'")
        if sync_timeout_fallback_mode not in {"durable_outbox", "background", "drop"}:
            raise ValueError(
                "sync_timeout_fallback_mode must be one of: durable_outbox, background, drop"
            )

        self.delivery_mode = resolved_mode
        self.report_in_background = self.delivery_mode == "background"
        self.outbox_batch_size = max(1, int(outbox_batch_size))
        self.outbox_poll_interval_seconds = max(0.05, float(outbox_poll_interval_seconds))
        self.outbox_max_attempts = max(1, int(outbox_max_attempts))
        self.outbox_retry_backoff_seconds = max(0.05, float(outbox_retry_backoff_seconds))
        self.outbox_send_concurrency = max(1, int(outbox_send_concurrency))
        self.sync_timeout_seconds = max(0.01, float(sync_timeout_seconds))
        self.max_concurrent_sends = max(1, int(max_concurrent_sends))
        self.max_background_tasks = max(1, int(max_background_tasks))
        self.circuit_breaker_failure_threshold = max(1, int(circuit_breaker_failure_threshold))
        self.circuit_breaker_cooldown_seconds = max(0.5, float(circuit_breaker_cooldown_seconds))
        self._pending_tasks: set[asyncio.Task[Any]] = set()
        self._send_semaphore: asyncio.Semaphore | None = None
        self._recent_send_latencies_ms: collections.deque[float] = collections.deque(maxlen=512)
        self._consecutive_send_failures = 0
        self._circuit_open_until = 0.0

        self._sync_fallback_mode = sync_timeout_fallback_mode
        if (
            self.delivery_mode == "sync"
            and sync_timeout_fallback_mode == "durable_outbox"
            and not outbox_path
        ):
            # Keep backwards compatibility for sync users that do not configure an outbox.
            self._sync_fallback_mode = "background"

        enable_outbox = self.delivery_mode == "durable_outbox" or (
            self.delivery_mode == "sync" and self._sync_fallback_mode == "durable_outbox"
        )
        self._outbox = _PaygenticOutbox(outbox_path) if (enable_outbox and outbox_path) else None
        self._outbox_worker_task: asyncio.Task[None] | None = None
        self._outbox_stop_event: asyncio.Event | None = None
        self._outbox_drain_lock: asyncio.Lock | None = None
        self._delivery_stats: dict[str, int] = {
            "send_attempts": 0,
            "sent_success": 0,
            "sent_failed": 0,
            "outbox_enqueued": 0,
            "outbox_deduplicated": 0,
            "outbox_dropped": 0,
            "outbox_dead_lettered": 0,
            "background_backpressure_dropped": 0,
            "non_retryable_failures": 0,
            "circuit_trips": 0,
            "circuit_short_circuited": 0,
            "sync_timeout_fallbacks": 0,
            "sync_fallback_mode_downgraded": int(
                sync_timeout_fallback_mode == "durable_outbox"
                and self._sync_fallback_mode != "durable_outbox"
            ),
            "sync_fallback_dropped": 0,
        }

    def _track_task(self, task: asyncio.Task[Any]) -> None:
        self._pending_tasks.add(task)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task[Any]) -> None:
        self._pending_tasks.discard(task)
        if task.cancelled():
            return
        try:
            task.result()
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.warning("Paygentic background reporting task failed (ignored): %s", exc)

    def _is_circuit_open(self) -> bool:
        return time.time() < self._circuit_open_until

    def _trip_circuit(self) -> None:
        self._circuit_open_until = time.time() + self.circuit_breaker_cooldown_seconds
        self._delivery_stats["circuit_trips"] += 1

    def _is_retryable_exception(self, exc: Exception) -> bool:
        client = self.reporter.client
        if hasattr(client, "is_retryable_error"):
            try:
                return bool(client.is_retryable_error(exc))
            except Exception:
                return True
        if isinstance(exc, PaygenticAPIError):
            if exc.status_code in _NON_RETRYABLE_STATUS_CODES:
                return False
            return exc.status_code in _TRANSIENT_STATUS_CODES or exc.status_code is None
        if isinstance(exc, httpx.RequestError):
            return True
        return True

    async def _send_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._is_circuit_open():
            self._delivery_stats["circuit_short_circuited"] += 1
            return {"ok": False, "retryable": True, "error": "circuit_open"}

        self._delivery_stats["send_attempts"] += 1
        start = time.perf_counter()
        try:
            if self._send_semaphore is None:
                self._send_semaphore = asyncio.Semaphore(self.max_concurrent_sends)
            async with self._send_semaphore:
                await self.reporter.client.acreate_usage_event(**payload)
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._recent_send_latencies_ms.append(elapsed_ms)
            self._delivery_stats["sent_success"] += 1
            self._consecutive_send_failures = 0
            self._circuit_open_until = 0.0
            return {"ok": True, "retryable": True, "error": None}
        except Exception as exc:  # pragma: no cover - intentionally fail-open
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._recent_send_latencies_ms.append(elapsed_ms)
            retryable = self._is_retryable_exception(exc)
            self._delivery_stats["sent_failed"] += 1
            if not retryable:
                self._delivery_stats["non_retryable_failures"] += 1
            self._consecutive_send_failures += 1
            if self._consecutive_send_failures >= self.circuit_breaker_failure_threshold:
                self._trip_circuit()
            logger.warning("Paygentic usage reporting failed (ignored): %s", exc)
            return {"ok": False, "retryable": retryable, "error": str(exc)}

    def _schedule_background_send(self, payload: dict[str, Any]) -> bool:
        if len(self._pending_tasks) >= self.max_background_tasks:
            self._delivery_stats["background_backpressure_dropped"] += 1
            return False
        task = asyncio.create_task(self._send_payload(payload))
        self._track_task(task)
        return True

    def _enqueue_outbox(self, payload: dict[str, Any]) -> bool:
        inserted = self._outbox.enqueue(payload) if self._outbox is not None else False
        if inserted:
            self._delivery_stats["outbox_enqueued"] += 1
            self._ensure_outbox_worker()
        else:
            self._delivery_stats["outbox_deduplicated"] += 1
        return inserted

    def _enqueue_sync_fallback(self, payload: dict[str, Any]) -> None:
        if self._sync_fallback_mode == "durable_outbox" and self._outbox is not None:
            self._enqueue_outbox(payload)
            return
        if self._sync_fallback_mode == "background":
            if self._schedule_background_send(payload):
                return
        self._delivery_stats["sync_fallback_dropped"] += 1

    def _ensure_outbox_worker(self) -> None:
        if self._outbox is None:
            return
        if self._outbox_worker_task and not self._outbox_worker_task.done():
            return
        if self._outbox_stop_event is None:
            self._outbox_stop_event = asyncio.Event()
        else:
            self._outbox_stop_event.clear()
        self._outbox_worker_task = asyncio.create_task(self._run_outbox_worker())

    async def _run_outbox_worker(self) -> None:
        if self._outbox_stop_event is None:
            return
        while not self._outbox_stop_event.is_set():
            if self._is_circuit_open():
                await asyncio.sleep(self.outbox_poll_interval_seconds)
                continue
            processed = await self._drain_outbox_once(limit=self.outbox_batch_size)
            if processed == 0:
                await asyncio.sleep(self.outbox_poll_interval_seconds)

    async def _process_outbox_event(
        self, event_id: int, attempts: int, payload: dict[str, Any]
    ) -> None:
        if self._outbox is None:
            return
        send_result = await self._send_payload(payload)
        if send_result["ok"]:
            self._outbox.ack(event_id)
            return

        next_attempt = attempts + 1
        retryable = bool(send_result.get("retryable", True))
        if (not retryable) or next_attempt >= self.outbox_max_attempts:
            reason = "non_retryable" if not retryable else "max_attempts_exceeded"
            self._outbox.dead_letter(payload, attempts=next_attempt, reason=reason)
            self._outbox.ack(event_id)
            self._delivery_stats["outbox_dropped"] += 1
            self._delivery_stats["outbox_dead_lettered"] += 1
            return

        delay = self.outbox_retry_backoff_seconds * (2 ** max(0, next_attempt - 1))
        self._outbox.reschedule(
            event_id,
            attempts=next_attempt,
            next_attempt_at=time.time() + delay,
            error=str(send_result.get("error") or "delivery_failed"),
        )

    async def _drain_outbox_once(self, *, limit: int) -> int:
        if self._outbox is None:
            return 0
        if self._is_circuit_open():
            return 0
        if self._outbox_drain_lock is None:
            self._outbox_drain_lock = asyncio.Lock()
        async with self._outbox_drain_lock:
            events = self._outbox.fetch_ready(now=time.time(), limit=limit)
            if not events:
                return 0

            chunk_size = max(1, self.outbox_send_concurrency)
            processed = 0
            for i in range(0, len(events), chunk_size):
                chunk = events[i : i + chunk_size]
                processed += len(chunk)
                await asyncio.gather(
                    *(
                        self._process_outbox_event(event_id, attempts, payload)
                        for event_id, attempts, payload in chunk
                    )
                )
            return processed

    async def flush(self, *, timeout: float | None = None) -> None:
        """Wait for in-flight background reporting tasks.

        This is optional and mainly useful for graceful shutdown and tests.
        """
        deadline = None if timeout is None else time.time() + timeout

        if self._pending_tasks:
            tasks = tuple(self._pending_tasks)
            wait_timeout = None if deadline is None else max(0.0, deadline - time.time())
            done, pending = await asyncio.wait(tasks, timeout=wait_timeout)
            self._pending_tasks.difference_update(done)
            for task in pending:
                task.cancel()
                self._pending_tasks.discard(task)

        if self._outbox is None:
            return

        while self._outbox.size() > 0:
            if deadline is not None and time.time() >= deadline:
                break
            processed = await self._drain_outbox_once(limit=self.outbox_batch_size)
            if processed == 0:
                sleep_for = self.outbox_poll_interval_seconds
                if deadline is not None:
                    sleep_for = min(sleep_for, max(0.0, deadline - time.time()))
                if sleep_for <= 0:
                    break
                await asyncio.sleep(sleep_for)

    async def close(self, *, timeout: float | None = None) -> None:
        """Flush and release outbox resources for graceful shutdown."""
        await self.flush(timeout=timeout)
        if self._outbox_worker_task and not self._outbox_worker_task.done():
            if self._outbox_stop_event is not None:
                self._outbox_stop_event.set()
            wait_timeout = 5.0 if timeout is None else max(0.0, min(5.0, timeout))
            try:
                await asyncio.wait_for(self._outbox_worker_task, timeout=wait_timeout)
            except asyncio.TimeoutError:  # pragma: no cover - shutdown guard
                self._outbox_worker_task.cancel()
        if self._outbox is not None:
            self._outbox.close()
            self._outbox = None

    def get_delivery_stats(self) -> dict[str, Any]:
        """Expose lightweight delivery stats for operational visibility."""
        outbox_size = self._outbox.size() if self._outbox is not None else 0
        dead_letter_size = self._outbox.dead_letter_size() if self._outbox is not None else 0
        recent_lats = list(self._recent_send_latencies_ms)
        avg_latency = sum(recent_lats) / len(recent_lats) if recent_lats else 0.0
        p95_latency = (
            sorted(recent_lats)[max(0, math.ceil(len(recent_lats) * 0.95) - 1)]
            if recent_lats
            else 0.0
        )
        return {
            "delivery_mode": self.delivery_mode,
            "pending_background_tasks": len(self._pending_tasks),
            "outbox_size": outbox_size,
            "dead_letter_size": dead_letter_size,
            "send_latency_ms_avg": avg_latency,
            "send_latency_ms_p95": p95_latency,
            "circuit_open": self._is_circuit_open(),
            "circuit_open_until": self._circuit_open_until,
            "sync_timeout_seconds": self.sync_timeout_seconds,
            "sync_timeout_fallback_mode": self._sync_fallback_mode,
            **self._delivery_stats,
        }

    async def handle(self, request: ProxyRequest) -> ProxyResult:
        if self.delivery_mode == "durable_outbox":
            self._ensure_outbox_worker()

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

        payload = self.reporter.build_usage_event(
            result=result,
            customer_id=customer_id,
            request_id=request_id,
        )
        if not payload:
            return result

        if self.delivery_mode == "sync":
            try:
                send_result = await asyncio.wait_for(
                    self._send_payload(payload),
                    timeout=self.sync_timeout_seconds,
                )
            except asyncio.TimeoutError:
                self._delivery_stats["sync_timeout_fallbacks"] += 1
                self._enqueue_sync_fallback(payload)
                return result
            if not bool(send_result.get("ok", False)):
                self._enqueue_sync_fallback(payload)
            return result

        if self.delivery_mode == "background":
            self._schedule_background_send(payload)
            return result

        self._enqueue_outbox(payload)
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
