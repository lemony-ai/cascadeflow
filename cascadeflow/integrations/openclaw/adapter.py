"""
OpenClaw adapter helpers.

Provides a thin routing adapter that:
- Reads explicit cascadeflow tags from OpenClaw params/payload
- Optionally runs the OpenClaw pre-router classifier
- Returns tags suitable for passing into Cascadeflow routing context
"""

from dataclasses import dataclass
from typing import Any, Optional

from .pre_router import OpenClawRouteHint, classify_openclaw_frame, extract_explicit_tags


@dataclass(frozen=True)
class OpenClawRoutingDecision:
    tags: dict[str, Any]
    hint: Optional[OpenClawRouteHint]
    explicit: bool
    used_classifier: bool


def build_routing_decision(
    method: Optional[str] = None,
    event: Optional[str] = None,
    params: Optional[dict[str, Any]] = None,
    payload: Optional[dict[str, Any]] = None,
    enable_classifier: bool = True,
) -> OpenClawRoutingDecision:
    """Build routing tags for Cascadeflow from OpenClaw frame data."""
    explicit = extract_explicit_tags(params, payload)
    if explicit:
        return OpenClawRoutingDecision(
            tags=explicit,
            hint=None,
            explicit=True,
            used_classifier=False,
        )

    hint = None
    tags: dict[str, Any] = {}
    if enable_classifier:
        hint = classify_openclaw_frame(method=method, event=event, params=params, payload=payload)
        if hint:
            tags["category"] = hint.category
            if hint.cascadeflow_domain:
                tags["domain"] = hint.cascadeflow_domain

    return OpenClawRoutingDecision(
        tags=tags,
        hint=hint,
        explicit=False,
        used_classifier=enable_classifier,
    )


__all__ = ["OpenClawRoutingDecision", "build_routing_decision"]
