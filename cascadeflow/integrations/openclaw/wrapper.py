"""
OpenClaw -> Cascadeflow adapter wrapper.

This is a lightweight bridge that:
- extracts prompt/messages from OpenClaw frames
- applies explicit tags or pre-router classifier
- forwards routing hints to CascadeAgent
"""

from dataclasses import dataclass
from typing import Any, Optional

from cascadeflow.agent import CascadeAgent

from .adapter import OpenClawRoutingDecision, build_routing_decision
from .pre_router import CATEGORY_TO_DOMAIN


@dataclass
class OpenClawAdapterConfig:
    enable_classifier: bool = True
    default_domain_confidence: float = 0.8


class OpenClawAdapter:
    """Thin adapter for routing OpenClaw frames through CascadeAgent."""

    def __init__(self, agent: CascadeAgent, config: Optional[OpenClawAdapterConfig] = None):
        self.agent = agent
        self.config = config or OpenClawAdapterConfig()

    async def run_frame(
        self,
        method: Optional[str] = None,
        event: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
        query: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        **kwargs,
    ):
        """Route a single OpenClaw frame through CascadeAgent."""
        routing = build_routing_decision(
            method=method,
            event=event,
            params=params,
            payload=payload,
            enable_classifier=self.config.enable_classifier,
        )

        prompt, extracted_messages = _extract_prompt(query, messages, params, payload)
        tenant_id = _extract_value(params, payload, keys=("tenant_id", "tenantId", "accountId"))
        channel = _extract_value(params, payload, keys=("channel", "lane", "replyChannel"))
        if not channel and routing.tags.get("category"):
            channel = routing.tags.get("category")

        kpi_flags = kwargs.pop("kpi_flags", None) or {}
        if routing.tags.get("category"):
            kpi_flags["openclaw_category"] = routing.tags.get("category")
        if routing.explicit:
            kpi_flags["openclaw_routing"] = "explicit"
        elif routing.used_classifier:
            kpi_flags["openclaw_routing"] = "classifier"

        domain_hint = routing.tags.get("domain")
        if not domain_hint and routing.tags.get("category"):
            domain_hint = CATEGORY_TO_DOMAIN.get(routing.tags.get("category"))

        domain_confidence_hint = (
            routing.hint.confidence
            if routing.hint
            else self.config.default_domain_confidence
        )

        return await self.agent.run(
            prompt,
            messages=extracted_messages,
            domain_hint=domain_hint,
            domain_confidence_hint=domain_confidence_hint,
            kpi_flags=kpi_flags,
            tenant_id=tenant_id,
            channel=channel,
            **kwargs,
        )


def _extract_prompt(
    query: Optional[str],
    messages: Optional[list[dict[str, Any]]],
    params: Optional[dict[str, Any]],
    payload: Optional[dict[str, Any]],
) -> tuple[str, Optional[list[dict[str, Any]]]]:
    if query:
        return query, messages

    for source in (params, payload):
        if not isinstance(source, dict):
            continue
        if source.get("messages"):
            return "", source.get("messages")
        for key in ("message", "text", "prompt", "question"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value, messages

    raise ValueError("OpenClaw frame missing prompt/message data")


def _extract_value(
    params: Optional[dict[str, Any]],
    payload: Optional[dict[str, Any]],
    keys: tuple[str, ...],
) -> Optional[str]:
    for source in (params, payload):
        if not isinstance(source, dict):
            continue
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


__all__ = ["OpenClawAdapter", "OpenClawAdapterConfig", "OpenClawRoutingDecision"]
