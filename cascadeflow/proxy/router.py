"""Proxy routing logic for provider selection."""

from __future__ import annotations

from typing import Iterable, Optional

from cascadeflow.schema.model_registry import ModelRegistry

from .errors import ProxyRoutingError
from .models import ProxyPlan, ProxyRequest, ProxyRoute


class ProxyRouter:
    """Route proxy requests to provider-specific routes."""

    def __init__(
        self,
        routes: Iterable[ProxyRoute],
        default_provider: Optional[str] = None,
        registry: Optional[ModelRegistry] = None,
    ) -> None:
        self.routes = list(routes)
        self.default_provider = default_provider
        self.registry = registry or ModelRegistry()
        self._routes_by_provider = {route.provider: route for route in self.routes}

    def plan(self, request: ProxyRequest) -> ProxyPlan:
        """Create a proxy plan for a request."""
        model = request.body.get("model")
        if not model:
            raise ProxyRoutingError("Proxy request is missing a model name.")

        provider, normalized_model = self._parse_model(model)
        route = self._resolve_route(provider, normalized_model)
        if not route:
            raise ProxyRoutingError(f"No proxy route found for model '{model}'.")

        updated_body = dict(request.body)
        updated_body["model"] = normalized_model
        normalized_request = ProxyRequest(
            method=request.method,
            path=request.path,
            headers=dict(request.headers),
            body=updated_body,
        )

        return ProxyPlan(
            route=route,
            request=normalized_request,
            model=normalized_model,
            provider=route.provider,
            metadata={"original_model": model},
        )

    def _parse_model(self, model: str) -> tuple[Optional[str], str]:
        """Parse provider/model prefixes if present."""
        for separator in (":", "/"):
            if separator in model:
                provider, model_name = model.split(separator, 1)
                if provider in self._routes_by_provider:
                    return provider, model_name

        entry = self.registry.get_or_none(model)
        if entry:
            return entry.provider, entry.name

        return self.default_provider, model

    def _resolve_route(self, provider: Optional[str], model: str) -> Optional[ProxyRoute]:
        if provider and provider in self._routes_by_provider:
            route = self._routes_by_provider[provider]
            if route.models and model not in route.models:
                raise ProxyRoutingError(
                    f"Model '{model}' is not configured for provider '{provider}'."
                )
            return route

        for route in self.routes:
            if model in route.models:
                return route

        return None
