"""Router framework for CascadeFlow LangChain integration.

This module contains the PreRouter and base router classes for
intelligent query routing based on complexity detection.
"""

from .base import (
    Router,
    RouterChain,
    RoutingDecision,
    RoutingDecisionHelper,
    RoutingStrategy,
)
from .pre_router import (
    PreRouter,
    PreRouterConfig,
    PreRouterStats,
    create_pre_router,
)

__all__ = [
    # Base router framework
    "Router",
    "RouterChain",
    "RoutingDecision",
    "RoutingDecisionHelper",
    "RoutingStrategy",
    # PreRouter
    "PreRouter",
    "PreRouterConfig",
    "PreRouterStats",
    "create_pre_router",
]
