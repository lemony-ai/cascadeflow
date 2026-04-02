"""Result types for the cascadeflow PydanticAI integration."""

from __future__ import annotations

from typing import Optional, TypedDict


class CascadeResult(TypedDict):
    """Result of cascade execution.

    Attributes:
        content: Final response content
        model_used: Which model was used ('drafter' or 'verifier')
        accepted: Whether drafter response was accepted
        drafter_quality: Quality score of drafter response (0-1)
        drafter_cost: Cost of drafter execution in USD
        verifier_cost: Cost of verifier execution in USD
        total_cost: Total cost in USD
        savings_percentage: Savings percentage vs. always using verifier
        latency_ms: Total latency in milliseconds
        complexity: Detected query complexity
        domain: Detected domain (if any)
    """

    content: str
    model_used: str
    accepted: bool
    drafter_quality: float
    drafter_cost: float
    verifier_cost: float
    total_cost: float
    savings_percentage: float
    latency_ms: float
    complexity: Optional[str]
    domain: Optional[str]


class CostMetadata(TypedDict, total=False):
    """Cost tracking metadata for cascade execution.

    Attributes:
        drafter_tokens: Token usage for drafter model {input, output}
        verifier_tokens: Token usage for verifier model (optional)
        drafter_cost: Cost of drafter execution in USD
        verifier_cost: Cost of verifier execution in USD
        total_cost: Total cost in USD
        savings_percentage: Savings percentage vs. always using verifier
        model_used: Which model was used ('drafter' or 'verifier')
        accepted: Whether drafter response was accepted
        drafter_quality: Quality score of drafter response (0-1)
    """

    drafter_tokens: dict[str, int]
    verifier_tokens: Optional[dict[str, int]]
    drafter_cost: float
    verifier_cost: float
    total_cost: float
    savings_percentage: float
    model_used: str
    accepted: bool
    drafter_quality: float
