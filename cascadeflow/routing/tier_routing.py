"""
Tier-aware routing for user tier management.

This module provides tier-based model filtering and budget enforcement.
It's OPTIONAL - only activated when users provide 'tiers' parameter.

Usage:
    >>> from cascadeflow import CascadeAgent
    >>> from cascadeflow.schema.config import DEFAULT_TIERS
    >>>
    >>> # OPTIONAL: Enable tier routing
    >>> agent = CascadeAgent(models=[...], tiers=DEFAULT_TIERS)
    >>>
    >>> # Use tier-aware routing
    >>> result = await agent.run("query", user_tier="free")
    >>>
    >>> # Or ignore tiers - works without them
    >>> agent = CascadeAgent(models=[...])  # No tiers = no tier routing
    >>> result = await agent.run("query")  # Works fine
"""

import logging
from typing import Optional

from ..schema.config import ModelConfig, UserTier

logger = logging.getLogger(__name__)


class TierAwareRouter:
    """
    Routes model selection based on user tiers.

    This router is OPTIONAL and only used when:
    1. User provides 'tiers' parameter to CascadeAgent
    2. User specifies 'user_tier' parameter in agent.run()

    Features:
    - Model filtering based on tier's allowed_models
    - Budget constraint awareness
    - Optimization weight application
    - Quality threshold enforcement

    Example:
        >>> router = TierAwareRouter(
        ...     tiers={"free": free_tier, "pro": pro_tier},
        ...     models=[cheap_model, expensive_model],
        ...     verbose=True
        ... )
        >>>
        >>> # Filter models for free tier
        >>> free_models = router.filter_models("free", all_models)
        >>> # Returns only models allowed for free tier
    """

    def __init__(
        self,
        tiers: dict[str, UserTier],
        models: list[ModelConfig],
        verbose: bool = False,
    ):
        """
        Initialize tier-aware router.

        Args:
            tiers: Dictionary of tier name -> UserTier configuration
            models: All available models in the agent
            verbose: Enable verbose logging
        """
        self.tiers = tiers
        self.all_models = models
        self.verbose = verbose

        # Statistics
        self.stats = {
            "total_filters": 0,
            "by_tier": dict.fromkeys(tiers.keys(), 0),
            "models_filtered_out": 0,
        }

        if verbose:
            logger.info(
                f"TierAwareRouter initialized:\n"
                f"  Tiers: {list(tiers.keys())}\n"
                f"  Total models: {len(models)}\n"
                f"  Model names: {[m.name for m in models]}"
            )

    def filter_models(
        self, tier_name: str, available_models: Optional[list[ModelConfig]] = None
    ) -> list[ModelConfig]:
        """
        Filter models based on user tier constraints.

        This is the core tier routing function. It:
        1. Checks if tier exists
        2. Filters models based on tier's allowed_models
        3. Excludes models in tier's exclude_models
        4. Returns filtered list

        Args:
            tier_name: Name of the user tier (e.g., "free", "pro")
            available_models: Models to filter (defaults to all models)

        Returns:
            Filtered list of models allowed for this tier

        Example:
            >>> free_models = router.filter_models("free")
            >>> # Returns only cheap models allowed for free tier
        """
        if available_models is None:
            available_models = self.all_models

        # Update stats
        self.stats["total_filters"] += 1

        # Check if tier exists
        if tier_name not in self.tiers:
            logger.warning(
                f"Tier '{tier_name}' not found. Available tiers: {list(self.tiers.keys())}. "
                f"Returning all models."
            )
            return available_models

        tier = self.tiers[tier_name]
        self.stats["by_tier"][tier_name] += 1

        # Filter models based on tier's allowed_models
        filtered = []
        for model in available_models:
            # Check if model is allowed
            if tier.allows_model(model.name):
                filtered.append(model)
            else:
                self.stats["models_filtered_out"] += 1
                if self.verbose:
                    logger.debug(f"Model '{model.name}' filtered out by tier '{tier_name}'")

        if self.verbose:
            logger.info(
                f"Tier '{tier_name}' filtering: {len(available_models)} → {len(filtered)} models\n"
                f"  Allowed: {[m.name for m in filtered]}\n"
                f"  Filtered out: {len(available_models) - len(filtered)}"
            )

        # Fallback: If no models remain, return cheapest model
        if not filtered:
            logger.warning(
                f"Tier '{tier_name}' filtered out ALL models. "
                f"Returning cheapest model as fallback."
            )
            # Sort by cost and return cheapest
            cheapest = sorted(available_models, key=lambda m: m.cost)[0]
            return [cheapest]

        return filtered

    def get_tier(self, tier_name: str) -> Optional[UserTier]:
        """
        Get tier configuration by name.

        Args:
            tier_name: Name of the tier

        Returns:
            UserTier configuration or None if not found
        """
        return self.tiers.get(tier_name)

    def get_tier_constraints(self, tier_name: str) -> dict:
        """
        Get tier constraints for display/logging.

        Args:
            tier_name: Name of the tier

        Returns:
            Dictionary of tier constraints
        """
        tier = self.get_tier(tier_name)
        if not tier:
            return {}

        return {
            "max_budget": tier.max_budget,
            "quality_threshold": tier.quality_threshold,
            "optimization": {
                "cost": tier.optimization.cost,
                "speed": tier.optimization.speed,
                "quality": tier.optimization.quality,
            },
            "latency": {
                "max_total_ms": tier.latency.max_total_ms,
                "max_per_model_ms": tier.latency.max_per_model_ms,
            },
            "allowed_models": tier.allowed_models,
            "exclude_models": tier.exclude_models,
        }

    def get_stats(self) -> dict:
        """
        Get routing statistics.

        Returns:
            Dictionary of statistics
        """
        avg_filtered = self.stats["models_filtered_out"] / max(self.stats["total_filters"], 1)

        return {
            **self.stats,
            "avg_filtered_per_query": round(avg_filtered, 2),
        }

    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            "total_filters": 0,
            "by_tier": dict.fromkeys(self.tiers.keys(), 0),
            "models_filtered_out": 0,
        }

        if self.verbose:
            logger.info("TierAwareRouter stats reset")


__all__ = ["TierAwareRouter"]
