"""Proxy planning and data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProxyRoute:
    """Configuration for routing proxy requests to a provider."""

    name: str
    provider: str
    base_url: str
    models: set[str] = field(default_factory=set)
    default_headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 60.0
    api_key: str | None = None
    cost_per_1k_tokens: float | None = None


@dataclass
class ProxyRequest:
    """Normalized proxy request payload."""

    method: str
    path: str
    headers: dict[str, str]
    body: dict[str, Any]


@dataclass
class ProxyUsage:
    """Token usage extracted from a provider response."""

    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class ProxyPlan:
    """Execution plan for proxying a request."""

    route: ProxyRoute
    request: ProxyRequest
    model: str
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProxyResult:
    """Proxy execution result with metadata."""

    status_code: int
    headers: dict[str, str]
    data: Any
    provider: str
    model: str
    latency_ms: float
    usage: ProxyUsage | None = None
    cost: float | None = None
