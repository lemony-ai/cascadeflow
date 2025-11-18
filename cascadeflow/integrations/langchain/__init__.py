"""CascadeFlow LangChain Integration.

Transparent wrapper for LangChain chat models with intelligent cascade logic
for cost optimization.

Example:
    >>> from langchain_openai import ChatOpenAI
    >>> from cascadeflow.langchain import CascadeFlow
    >>>
    >>> drafter = ChatOpenAI(model='gpt-4o-mini')
    >>> verifier = ChatOpenAI(model='gpt-4o')
    >>>
    >>> cascade = CascadeFlow(
    ...     drafter=drafter,
    ...     verifier=verifier,
    ...     quality_threshold=0.7
    ... )
    >>>
    >>> result = await cascade.ainvoke("What is TypeScript?")
"""

from .wrapper import CascadeFlow, with_cascade
from .types import CascadeConfig, CascadeResult, CostMetadata, TokenUsage
from .utils import (
    calculate_quality,
    calculate_cost,
    calculate_savings,
    create_cost_metadata,
    extract_token_usage,
    MODEL_PRICING,
)

# Model discovery utilities - optional feature
# TODO: Implement models.py module
# from .models import (
#     MODEL_PRICING_REFERENCE,
#     analyze_cascade_pair,
#     suggest_cascade_pairs,
#     discover_cascade_pairs,
#     analyze_model,
#     compare_models,
#     find_best_cascade_pair,
#     validate_cascade_pair,
#     extract_model_name,
#     get_provider,
# )
from .cost_tracking import (
    BudgetTracker,
    CostHistory,
    CostEntry,
    track_costs,
)
from .langchain_callbacks import (
    CascadeFlowCallbackHandler,
    get_cascade_callback,
)

__all__ = [
    # Main classes
    "CascadeFlow",
    "with_cascade",
    # Types
    "CascadeConfig",
    "CascadeResult",
    "CostMetadata",
    "TokenUsage",
    # Utilities
    "calculate_quality",
    "calculate_cost",
    "calculate_savings",
    "create_cost_metadata",
    "extract_token_usage",
    "MODEL_PRICING",
    # Model discovery (TODO: implement models.py module)
    # "MODEL_PRICING_REFERENCE",
    # "analyze_cascade_pair",
    # "suggest_cascade_pairs",
    # "discover_cascade_pairs",
    # "analyze_model",
    # "compare_models",
    # "find_best_cascade_pair",
    # "validate_cascade_pair",
    # "extract_model_name",
    # "get_provider",
    # Cost tracking (Python-specific features)
    "BudgetTracker",
    "CostHistory",
    "CostEntry",
    "track_costs",
    # LangChain callback handlers
    "CascadeFlowCallbackHandler",
    "get_cascade_callback",
]
