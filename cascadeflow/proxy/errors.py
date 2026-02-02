"""Proxy error types."""


class ProxyError(Exception):
    """Base proxy error."""


class ProxyRoutingError(ProxyError):
    """Raised when proxy routing fails."""


class ProxyUpstreamError(ProxyError):
    """Raised when upstream provider returns an error."""

    def __init__(self, message: str, status_code: int | None = None, payload: object | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class ProxyTransportError(ProxyError):
    """Raised when the proxy cannot reach the upstream provider."""
