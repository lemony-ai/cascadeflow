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

__all__ = [
    # Main classes
    'CascadeFlow',
    'with_cascade',

    # Types
    'CascadeConfig',
    'CascadeResult',
    'CostMetadata',
    'TokenUsage',

    # Utilities
    'calculate_quality',
    'calculate_cost',
    'calculate_savings',
    'create_cost_metadata',
    'extract_token_usage',
    'MODEL_PRICING',
]
