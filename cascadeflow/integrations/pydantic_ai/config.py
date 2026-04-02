"""Configuration types for the cascadeflow PydanticAI integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, TypedDict


class DomainPolicy(TypedDict, total=False):
    """Per-domain policy overrides for the PydanticAI cascade model.

    Attributes:
        quality_threshold: Optional quality threshold override for this domain
        force_verifier: Always escalate to verifier after drafting
        direct_to_verifier: Skip drafter and route directly to verifier
        metadata: Arbitrary metadata attached to cascade output
    """

    quality_threshold: float
    force_verifier: bool
    direct_to_verifier: bool
    metadata: dict[str, Any]


@dataclass
class CascadeFlowPydanticAIConfig:
    """Configuration for CascadeFlowModel cascade behavior.

    Attributes:
        quality_threshold: Quality threshold for accepting drafter responses (0-1)
        enable_pre_router: Enable pre-routing based on query complexity
        cascade_complexities: Complexity levels that should use cascade
        domain_policies: Per-domain policy overrides
        enable_cost_tracking: Enable automatic cost tracking
        fail_open: If True, integration errors never break the model call
        enable_budget_gate: Enable budget enforcement via harness
    """

    quality_threshold: float = 0.7
    enable_pre_router: bool = True
    cascade_complexities: list[str] = field(
        default_factory=lambda: ["trivial", "simple", "moderate"]
    )
    domain_policies: Optional[dict[str, DomainPolicy]] = None
    enable_cost_tracking: bool = True
    fail_open: bool = True
    enable_budget_gate: bool = True
