"""Type definitions for CascadeFlow LangChain integration."""

from typing import Any, Callable, Literal, Optional, TypedDict, Union
from typing_extensions import NotRequired


class CascadeConfig(TypedDict):
    """Configuration for the CascadeFlow wrapper.

    Attributes:
        drafter: The drafter model (cheap, fast) - tries first
        verifier: The verifier model (expensive, accurate) - used when quality is insufficient
        quality_threshold: Quality threshold for accepting drafter responses (0-1). Default: 0.7
        enable_cost_tracking: Enable automatic cost tracking. Default: True
        cost_tracking_provider: Cost tracking provider ('langsmith' or 'cascadeflow'). Default: 'langsmith'
        quality_validator: Custom quality validator function that returns confidence score (0-1)
        enable_pre_router: Enable pre-routing based on query complexity. Default: False
        pre_router: Custom PreRouter instance for advanced routing control
        cascade_complexities: Complexity levels that should use cascade (try drafter first).
                            Default: ['trivial', 'simple', 'moderate']
    """

    drafter: Any  # BaseChatModel from langchain
    verifier: Any  # BaseChatModel from langchain
    quality_threshold: NotRequired[float]
    enable_cost_tracking: NotRequired[bool]
    cost_tracking_provider: NotRequired[Literal['langsmith', 'cascadeflow']]
    quality_validator: NotRequired[Callable[[Any], Union[float, Any]]]  # Can return Promise or number
    enable_pre_router: NotRequired[bool]
    pre_router: NotRequired[Any]  # PreRouter type
    cascade_complexities: NotRequired[list[str]]  # QueryComplexity list


class TokenUsage(TypedDict):
    """Token usage for a model call."""

    input: int
    output: int


class CascadeResult(TypedDict):
    """Cascade execution result with cost metadata.

    Attributes:
        content: The final response content
        model_used: Model that provided the final response ('drafter' or 'verifier')
        drafter_quality: Quality score of the drafter response (0-1)
        accepted: Whether the drafter response was accepted
        drafter_cost: Cost of the drafter call
        verifier_cost: Cost of the verifier call (0 if not used)
        total_cost: Total cost of the cascade
        savings_percentage: Cost savings percentage (0-100)
        latency_ms: Latency in milliseconds
    """

    content: str
    model_used: Literal['drafter', 'verifier']
    drafter_quality: NotRequired[float]
    accepted: bool
    drafter_cost: float
    verifier_cost: float
    total_cost: float
    savings_percentage: float
    latency_ms: float


class CostMetadata(TypedDict):
    """Internal cost calculation metadata.

    Attributes:
        drafter_tokens: Token usage for drafter call
        verifier_tokens: Token usage for verifier call (if used)
        drafter_cost: Cost of the drafter call
        verifier_cost: Cost of the verifier call
        total_cost: Total cost of the cascade
        savings_percentage: Cost savings percentage (0-100)
        model_used: Model that provided the final response
        accepted: Whether the drafter response was accepted
        drafter_quality: Quality score of the drafter response (0-1)
    """

    drafter_tokens: TokenUsage
    verifier_tokens: NotRequired[TokenUsage]
    drafter_cost: float
    verifier_cost: float
    total_cost: float
    savings_percentage: float
    model_used: Literal['drafter', 'verifier']
    accepted: bool
    drafter_quality: NotRequired[float]
