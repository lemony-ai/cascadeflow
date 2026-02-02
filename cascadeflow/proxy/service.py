"""High-level proxy service that combines routing and execution."""

from __future__ import annotations

from .handler import ProxyHandler
from .models import ProxyRequest, ProxyResult
from .router import ProxyRouter


class ProxyService:
    """End-to-end proxy service for handling requests."""

    def __init__(self, router: ProxyRouter, handler: ProxyHandler) -> None:
        self.router = router
        self.handler = handler

    async def handle(self, request: ProxyRequest) -> ProxyResult:
        """Route and execute a proxy request."""
        plan = self.router.plan(request)
        return await self.handler.execute(plan)
