"""
Rule engine context for routing decisions.

Provides a stable, structured input for rule evaluation without
coupling rule logic to agent internals.
"""

from dataclasses import dataclass
from typing import Any, Optional, Union

from cascadeflow.quality.complexity import QueryComplexity
from cascadeflow.schema.config import UserTier, WorkflowProfile
from cascadeflow.schema.domain_config import DomainConfig


@dataclass(frozen=True)
class RuleContext:
    """Input context for rule evaluation."""

    query: str
    complexity: Optional[Union[QueryComplexity, str]] = None
    complexity_confidence: float = 0.0
    detected_domain: Optional[str] = None
    domain_confidence: float = 0.0
    domain_config: Optional[DomainConfig] = None
    has_tools: bool = False
    has_multi_turn: bool = False
    has_code: bool = False
    has_tool_prompt: bool = False
    user_tier: Optional[str] = None
    tier_config: Optional[UserTier] = None
    workflow_name: Optional[str] = None
    workflow_profile: Optional[WorkflowProfile] = None
    kpi_flags: Optional[dict[str, Any]] = None
    tenant_id: Optional[str] = None
    channel: Optional[str] = None
