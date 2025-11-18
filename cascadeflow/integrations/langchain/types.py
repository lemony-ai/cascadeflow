"""Type definitions for CascadeFlow LangChain integration."""

from typing import Optional, TypedDict


class TokenUsage(TypedDict):
    """Token usage tracking."""

    input: int
    output: int


class CostMetadata(TypedDict, total=False):
    """Cost tracking metadata for cascade execution.

    Attributes:
        drafter_tokens: Token usage for drafter model
        verifier_tokens: Token usage for verifier model (optional)
        drafter_cost: Cost of drafter execution in USD
        verifier_cost: Cost of verifier execution in USD
        total_cost: Total cost in USD
        savings_percentage: Savings percentage vs. always using verifier
        model_used: Which model was used ('drafter' or 'verifier')
        accepted: Whether drafter response was accepted
        drafter_quality: Quality score of drafter response (0-1)
    """

    drafter_tokens: TokenUsage
    verifier_tokens: Optional[TokenUsage]
    drafter_cost: float
    verifier_cost: float
    total_cost: float
    savings_percentage: float
    model_used: str
    accepted: bool
    drafter_quality: float


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


class CascadeConfig(TypedDict, total=False):
    """Configuration for cascade behavior.

    Attributes:
        quality_threshold: Quality threshold for accepting drafter responses (0-1)
        enable_cost_tracking: Enable automatic cost tracking
        cost_tracking_provider: Cost tracking provider ('langsmith' or 'cascadeflow')
        enable_pre_router: Enable pre-routing based on query complexity
        cascade_complexities: Complexity levels that should use cascade
    """

    quality_threshold: float
    enable_cost_tracking: bool
    cost_tracking_provider: str
    enable_pre_router: bool
    cascade_complexities: list[str]
