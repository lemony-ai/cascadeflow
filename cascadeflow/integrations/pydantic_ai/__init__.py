"""cascadeflow PydanticAI integration — full cascade Model for PydanticAI agents.

Provides ``CascadeFlowModel``, a drop-in PydanticAI ``Model`` that performs
speculative cascading: a cheap drafter model runs first and its response is
quality-gated before optionally escalating to a more powerful verifier.

Quick start::

    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIModel
    from cascadeflow.integrations.pydantic_ai import create_cascade_model

    drafter = OpenAIModel("gpt-4o-mini")
    verifier = OpenAIModel("gpt-4o")
    cascade = create_cascade_model(drafter, verifier, quality_threshold=0.7)

    agent = Agent(model=cascade)
    result = await agent.run("What is quantum computing?")
"""

from __future__ import annotations

from importlib.util import find_spec

from .config import CascadeFlowPydanticAIConfig, DomainPolicy
from .model import CascadeFlowModel, create_cascade_model
from .types import CascadeResult, CostMetadata

PYDANTIC_AI_AVAILABLE = find_spec("pydantic_ai") is not None


def is_pydantic_ai_available() -> bool:
    """Return True if pydantic-ai is installed."""
    return PYDANTIC_AI_AVAILABLE


__all__ = [
    "PYDANTIC_AI_AVAILABLE",
    "CascadeFlowModel",
    "CascadeFlowPydanticAIConfig",
    "CascadeResult",
    "CostMetadata",
    "DomainPolicy",
    "create_cascade_model",
    "is_pydantic_ai_available",
]
