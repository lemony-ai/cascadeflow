"""
Tool Router - Phase 3: Tool Capability Filtering and Routing
===========================================================

The ToolRouter handles tool-specific routing logic:
- Filters models by tool support capability
- Validates tool schemas
- Tracks tool usage statistics
- Separate from PreRouter (complexity-based routing)

Architecture:
    PreRouter → Complexity-based routing
    ToolRouter → Tool capability filtering
    Agent → Orchestrates both

Example:
    >>> tool_router = ToolRouter(models=all_models)
    >>> result = tool_router.filter_tool_capable_models(
    ...     tools=[{...}],
    ...     available_models=all_models
    ... )
    >>> capable_models = result['models']  # Only tool-capable models
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

from ..config import ModelConfig
from ..exceptions import cascadeflowError

logger = logging.getLogger(__name__)


@dataclass
class ToolFilterResult:
    """Result from tool capability filtering."""

    models: list[ModelConfig]  # Models that support tools
    filtered_count: int  # Number of models filtered out
    has_capable_models: bool  # Whether any capable models found
    reason: str  # Explanation


class ToolRouter:
    """
    Router for tool capability filtering.

    Responsibilities:
    - Filter models by tool support capability
    - Validate tool configurations
    - Track tool routing statistics
    - Provide insights on tool-capable models

    Separate from PreRouter to maintain clean separation of concerns:
    - PreRouter: Complexity-based routing (HARD → direct, SIMPLE → cascade)
    - ToolRouter: Capability-based filtering (tools → only tool-capable models)

    Example:
        >>> router = ToolRouter(models=models, verbose=True)
        >>> result = router.filter_tool_capable_models(
        ...     tools=[weather_tool],
        ...     available_models=models
        ... )
        >>> print(f"Capable models: {len(result['models'])}")
    """

    def __init__(self, models: list[ModelConfig], verbose: bool = False):
        """
        Initialize tool router.

        Args:
            models: List of all available models
            verbose: Enable verbose logging
        """
        self.models = models
        self.verbose = verbose

        # Statistics tracking
        self.stats = {
            "total_filters": 0,
            "models_before_filter": [],
            "models_after_filter": [],
            "filter_hits": 0,  # Times filtering was needed
            "no_capable_models": 0,  # Times no capable models found
        }

        # Count tool-capable models
        self.tool_capable_models = [m for m in models if getattr(m, "supports_tools", False)]

        if self.verbose:
            logger.info(
                f"ToolRouter initialized: "
                f"{len(self.tool_capable_models)}/{len(models)} models support tools"
            )
            if self.tool_capable_models:
                logger.info(
                    f"Tool-capable models: "
                    f"{', '.join(m.name for m in self.tool_capable_models)}"
                )

    def filter_tool_capable_models(
        self, tools: Optional[list[dict[str, Any]]], available_models: list[ModelConfig]
    ) -> dict[str, Any]:
        """
        Filter models to only those that support tool calling.

        Args:
            tools: List of tools (if None, returns all models)
            available_models: Models to filter from

        Returns:
            Dict with:
                - models: List of tool-capable models
                - filtered_count: Number filtered out
                - has_capable_models: bool
                - reason: Explanation

        Raises:
            cascadeflowError: If tools provided but no capable models
        """
        # Update statistics
        self.stats["total_filters"] += 1
        self.stats["models_before_filter"].append(len(available_models))

        # If no tools, return all models
        if not tools:
            self.stats["models_after_filter"].append(len(available_models))
            return {
                "models": available_models,
                "filtered_count": 0,
                "has_capable_models": True,
                "reason": "No tools provided, all models available",
            }

        # Filter to tool-capable models
        capable_models = [m for m in available_models if getattr(m, "supports_tools", False)]

        filtered_count = len(available_models) - len(capable_models)
        self.stats["filter_hits"] += 1
        self.stats["models_after_filter"].append(len(capable_models))

        # Check if we have any capable models
        if not capable_models:
            self.stats["no_capable_models"] += 1

            # Get names of models that don't support tools
            non_capable = [m.name for m in available_models]

            error_msg = (
                f"No tool-capable models available. "
                f"Tools provided: {len(tools)}, "
                f"Models available: {non_capable}. "
                f"Please add tool-capable models to your configuration."
            )

            if self.verbose:
                logger.error(error_msg)

            raise cascadeflowError(error_msg)

        reason = (
            f"Filtered to {len(capable_models)}/{len(available_models)} "
            f"tool-capable models for {len(tools)} tools"
        )

        if self.verbose:
            logger.info(reason)
            logger.info(f"Tool-capable models: " f"{', '.join(m.name for m in capable_models)}")

        return {
            "models": capable_models,
            "filtered_count": filtered_count,
            "has_capable_models": True,
            "reason": reason,
        }

    def validate_tools(self, tools: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Validate tool configurations.

        Checks:
        - Required fields present (name, description, parameters)
        - Parameters is valid JSON Schema
        - No duplicate tool names

        Args:
            tools: List of tools to validate

        Returns:
            Dict with:
                - valid: bool
                - errors: List of validation errors
                - warnings: List of warnings
        """
        errors = []
        warnings = []

        if not tools:
            return {"valid": True, "errors": [], "warnings": []}

        # Check for duplicate names
        names = [tool.get("name") for tool in tools]
        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            errors.append(f"Duplicate tool names: {duplicates}")

        # Validate each tool
        for i, tool in enumerate(tools):
            tool_id = tool.get("name", f"tool_{i}")

            # Check required fields
            if "name" not in tool:
                errors.append(f"{tool_id}: Missing 'name' field")

            if "description" not in tool:
                warnings.append(f"{tool_id}: Missing 'description' (recommended)")

            if "parameters" not in tool:
                errors.append(f"{tool_id}: Missing 'parameters' field")
            else:
                # Validate parameters is object-like
                params = tool["parameters"]
                if not isinstance(params, dict):
                    errors.append(f"{tool_id}: 'parameters' must be a dict")
                else:
                    # Check for JSON Schema structure
                    if "type" not in params:
                        warnings.append(f"{tool_id}: 'parameters' missing 'type' field")
                    if "properties" not in params:
                        warnings.append(f"{tool_id}: 'parameters' missing 'properties' field")

        valid = len(errors) == 0

        if not valid and self.verbose:
            logger.warning(f"Tool validation failed: {errors}")

        if warnings and self.verbose:
            logger.info(f"Tool validation warnings: {warnings}")

        return {"valid": valid, "errors": errors, "warnings": warnings}

    def suggest_models_for_tools(
        self, tools: list[dict[str, Any]], max_cost: Optional[float] = None
    ) -> list[ModelConfig]:
        """
        Suggest best models for given tools.

        Considers:
        - Tool support capability
        - Cost constraints
        - Model quality for tool calling

        Args:
            tools: List of tools
            max_cost: Maximum cost per 1K tokens

        Returns:
            List of suggested models (sorted by quality/cost)
        """
        # Start with tool-capable models
        candidates = self.tool_capable_models.copy()

        # Filter by cost if specified
        if max_cost is not None:
            candidates = [m for m in candidates if m.cost <= max_cost]

        # Sort by tool quality (if available) and cost
        def sort_key(model: ModelConfig) -> tuple:
            # Higher quality first, then lower cost
            tool_quality = getattr(model, "tool_quality", 0.5)
            return (-tool_quality, model.cost)

        candidates.sort(key=sort_key)

        if self.verbose and candidates:
            logger.info(
                f"Suggested models for {len(tools)} tools: "
                f"{', '.join(m.name for m in candidates[:3])}"
            )

        return candidates

    def get_stats(self) -> dict[str, Any]:
        """
        Get tool router statistics.

        Returns:
            Dict with filtering and usage statistics
        """
        # Calculate averages
        avg_before = (
            sum(self.stats["models_before_filter"]) / len(self.stats["models_before_filter"])
            if self.stats["models_before_filter"]
            else 0
        )
        avg_after = (
            sum(self.stats["models_after_filter"]) / len(self.stats["models_after_filter"])
            if self.stats["models_after_filter"]
            else 0
        )

        return {
            "total_filters": self.stats["total_filters"],
            "filter_hits": self.stats["filter_hits"],
            "no_capable_models": self.stats["no_capable_models"],
            "avg_models_before_filter": avg_before,
            "avg_models_after_filter": avg_after,
            "tool_capable_models": len(self.tool_capable_models),
            "total_models": len(self.models),
            "tool_capability_rate": (
                len(self.tool_capable_models) / len(self.models) * 100 if self.models else 0
            ),
        }

    def reset_stats(self):
        """Reset statistics tracking."""
        self.stats = {
            "total_filters": 0,
            "models_before_filter": [],
            "models_after_filter": [],
            "filter_hits": 0,
            "no_capable_models": 0,
        }

        if self.verbose:
            logger.info("ToolRouter statistics reset")


__all__ = ["ToolRouter", "ToolFilterResult"]
