"""Proxy error types."""

from __future__ import annotations

from typing import Optional


class ProxyError(Exception):
    """Base proxy error."""


class ProxyRoutingError(ProxyError):
    """Raised when proxy routing fails."""


class ProxyUpstreamError(ProxyError):
    """Raised when upstream provider returns an error."""

    def __init__(self, message: str, status_code: Optional[int] = None, payload: Optional[object] = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class ProxyTransportError(ProxyError):
    """Raised when the proxy cannot reach the upstream provider."""
