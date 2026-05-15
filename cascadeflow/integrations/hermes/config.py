"""Configuration helpers for Hermes Agent delegation routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .types import VALID_REASONING_EFFORTS

VALID_MODES = {"observe", "route"}


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(frozen=True)
class HermesRouteProfile:
    """Provider/model/reasoning target for a domain, topic, skill, or complexity."""

    provider: Optional[str] = None
    model: Optional[str] = None
    reasoning_effort: Optional[str] = None
    domain: Optional[str] = None
    topic: Optional[str] = None
    confidence: float = 0.8
    description: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> HermesRouteProfile:
        effort = _clean_str(data.get("reasoning_effort"))
        if effort is not None:
            effort = effort.lower()
        if effort is not None and effort not in VALID_REASONING_EFFORTS:
            effort = None
        try:
            confidence = float(data.get("confidence", 0.8))
        except (TypeError, ValueError):
            confidence = 0.8
        return cls(
            provider=_clean_str(data.get("provider")),
            model=_clean_str(data.get("model")),
            reasoning_effort=effort,
            domain=_clean_str(data.get("domain")),
            topic=_clean_str(data.get("topic")),
            confidence=max(0.0, min(1.0, confidence)),
            description=_clean_str(data.get("description")),
        )


@dataclass(frozen=True)
class HermesRoutingConfig:
    """Configuration for CascadeFlow's Hermes delegation router."""

    enabled: bool = False
    mode: str = "observe"
    min_confidence: float = 0.60
    route_reasoning_effort: bool = True
    route_provider_model: bool = True
    log_decisions: bool = True
    routes: Mapping[str, HermesRouteProfile] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> HermesRoutingConfig:
        if not isinstance(data, Mapping):
            return cls()
        mode = str(data.get("mode", "observe") or "observe").strip().lower()
        if mode not in VALID_MODES:
            mode = "observe"
        try:
            min_confidence = float(data.get("min_confidence", 0.60))
        except (TypeError, ValueError):
            min_confidence = 0.60
        raw_routes = data.get("routes") or {}
        routes: dict[str, HermesRouteProfile] = {}
        if isinstance(raw_routes, Mapping):
            for key, value in raw_routes.items():
                route_key = str(key).strip().lower()
                if route_key and isinstance(value, Mapping):
                    routes[route_key] = HermesRouteProfile.from_dict(value)
        return cls(
            enabled=_as_bool(data.get("enabled"), default=False),
            mode=mode,
            min_confidence=max(0.0, min(1.0, min_confidence)),
            route_reasoning_effort=_as_bool(
                data.get("route_reasoning_effort"),
                default=True,
            ),
            route_provider_model=_as_bool(data.get("route_provider_model"), default=True),
            log_decisions=_as_bool(data.get("log_decisions"), default=True),
            routes=routes,
        )
