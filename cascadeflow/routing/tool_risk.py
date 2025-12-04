"""
Tool Risk Level Classification for CascadeFlow.

Classifies tools by risk/impact level to enable intelligent routing:
- LOW: Read-only, safe tools (search, get_weather)
- MEDIUM: Reversible modifications (update_user, create_draft)
- HIGH: Significant impact (delete_user, send_email)
- CRITICAL: Irreversible, high-impact (delete_all, financial_transaction)

Usage:
    >>> from cascadeflow.routing import ToolRiskLevel, ToolRiskClassifier
    >>>
    >>> classifier = ToolRiskClassifier()
    >>>
    >>> # Classify a tool
    >>> risk = classifier.classify_tool({
    ...     "name": "delete_user",
    ...     "description": "Permanently deletes a user account"
    ... })
    >>> print(risk)  # ToolRiskLevel.HIGH
    >>>
    >>> # Get routing recommendation
    >>> if risk >= ToolRiskLevel.HIGH:
    ...     # Use verifier model for high-risk tools
    ...     model = verifier
"""

import logging
import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ToolRiskLevel(IntEnum):
    """
    Tool risk classification levels.

    Ordered by severity (LOW=1 to CRITICAL=4) for comparison.
    Example: if risk >= ToolRiskLevel.HIGH: use_verifier()
    """

    LOW = 1  # Read-only, safe operations
    MEDIUM = 2  # Reversible modifications
    HIGH = 3  # Significant impact, hard to reverse
    CRITICAL = 4  # Irreversible, high-impact operations


@dataclass
class ToolRiskClassification:
    """Result of tool risk classification."""

    level: ToolRiskLevel
    confidence: float
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.level.name} ({self.confidence:.0%}): {', '.join(self.reasons)}"


# Risk indicators by category
RISK_INDICATORS = {
    # CRITICAL: Irreversible, high-impact
    "critical": {
        "keywords": [
            "delete_all",
            "drop_table",
            "truncate",
            "destroy",
            "financial_transaction",
            "payment",
            "charge",
            "transfer_funds",
            "withdraw",
            "deploy_production",
            "publish_live",
            "send_mass",
            "broadcast",
        ],
        "patterns": [
            r"delete.*all",
            r"remove.*all",
            r"drop.*table",
            r"financial|payment|transaction|charge|withdraw",
            r"deploy.*prod",
            r"publish.*live",
            r"broadcast",
        ],
        "descriptions": [
            "permanently",
            "irreversible",
            "cannot be undone",
            "financial",
            "payment",
            "production",
            "mass",
        ],
    },
    # HIGH: Significant impact
    "high": {
        "keywords": [
            "delete",
            "remove",
            "send_email",
            "send_message",
            "post",
            "publish",
            "submit",
            "execute_query",
            "modify_permissions",
            "change_role",
            "revoke",
            "disable",
            "suspend",
            "ban",
            "terminate",
        ],
        "patterns": [
            r"delete_\w+",
            r"remove_\w+",
            r"send_\w+",
            r"post_\w+",
            r"publish_\w+",
            r"submit_\w+",
            r"execute.*query",
            r"modify.*permission",
            r"disable|suspend|ban|terminate",
        ],
        "descriptions": [
            "delete",
            "remove",
            "send",
            "email",
            "message",
            "post",
            "publish",
            "execute",
            "permission",
            "disable",
            "suspend",
            "terminate",
        ],
    },
    # MEDIUM: Reversible modifications
    "medium": {
        "keywords": [
            "update",
            "edit",
            "modify",
            "create",
            "add",
            "set",
            "change",
            "write",
            "save",
            "upload",
            "insert",
            "append",
            "replace",
        ],
        "patterns": [
            r"update_\w+",
            r"edit_\w+",
            r"modify_\w+",
            r"create_\w+",
            r"add_\w+",
            r"set_\w+",
            r"write_\w+",
            r"save_\w+",
            r"upload_\w+",
        ],
        "descriptions": [
            "update",
            "edit",
            "modify",
            "create",
            "add",
            "change",
            "write",
            "save",
            "upload",
        ],
    },
    # LOW: Read-only, safe operations
    "low": {
        "keywords": [
            "get",
            "read",
            "list",
            "search",
            "query",
            "fetch",
            "retrieve",
            "find",
            "lookup",
            "check",
            "verify",
            "validate",
            "count",
            "calculate",
            "analyze",
            "preview",
        ],
        "patterns": [
            r"get_\w+",
            r"read_\w+",
            r"list_\w+",
            r"search_\w+",
            r"query_\w+",
            r"fetch_\w+",
            r"find_\w+",
            r"lookup_\w+",
            r"check_\w+",
        ],
        "descriptions": [
            "get",
            "read",
            "list",
            "search",
            "query",
            "fetch",
            "find",
            "lookup",
            "check",
            "verify",
            "calculate",
            "analyze",
            "preview",
            "retrieve",
        ],
    },
}


class ToolRiskClassifier:
    """
    Classifies tools by risk level based on name and description.

    Uses keyword matching and pattern recognition to determine
    risk level. Supports custom risk overrides for specific tools.

    Example:
        >>> classifier = ToolRiskClassifier()
        >>>
        >>> # Classify single tool
        >>> result = classifier.classify_tool({
        ...     "name": "delete_user",
        ...     "description": "Permanently removes a user"
        ... })
        >>> print(result.level)  # ToolRiskLevel.HIGH
        >>>
        >>> # Classify multiple tools
        >>> tools = [...]
        >>> risks = classifier.classify_tools(tools)
        >>> high_risk = [t for t, r in risks.items() if r.level >= ToolRiskLevel.HIGH]
    """

    def __init__(
        self,
        custom_overrides: Optional[dict[str, ToolRiskLevel]] = None,
        default_level: ToolRiskLevel = ToolRiskLevel.MEDIUM,
    ):
        """
        Initialize risk classifier.

        Args:
            custom_overrides: Dict mapping tool names to risk levels
            default_level: Default risk level when uncertain
        """
        self.overrides = custom_overrides or {}
        self.default_level = default_level

    def classify_tool(
        self,
        tool: dict[str, Any],
    ) -> ToolRiskClassification:
        """
        Classify a single tool by risk level.

        Args:
            tool: Tool definition dict with 'name' and optionally 'description'

        Returns:
            ToolRiskClassification with level, confidence, and reasons
        """
        name = tool.get("name", "").lower()
        description = tool.get("description", "").lower()

        # Check for custom override
        if name in self.overrides:
            return ToolRiskClassification(
                level=self.overrides[name],
                confidence=1.0,
                reasons=["custom_override"],
            )

        # Score each risk level
        scores = {
            ToolRiskLevel.CRITICAL: 0.0,
            ToolRiskLevel.HIGH: 0.0,
            ToolRiskLevel.MEDIUM: 0.0,
            ToolRiskLevel.LOW: 0.0,
        }
        reasons: dict[ToolRiskLevel, list[str]] = {level: [] for level in scores}

        # Check each category
        for category, indicators in RISK_INDICATORS.items():
            level = {
                "critical": ToolRiskLevel.CRITICAL,
                "high": ToolRiskLevel.HIGH,
                "medium": ToolRiskLevel.MEDIUM,
                "low": ToolRiskLevel.LOW,
            }[category]

            # Keyword matches (high weight)
            for keyword in indicators["keywords"]:
                if keyword in name:
                    scores[level] += 2.0
                    reasons[level].append(f"name:{keyword}")

            # Pattern matches (medium weight)
            for pattern in indicators["patterns"]:
                if re.search(pattern, name):
                    scores[level] += 1.5
                    reasons[level].append(f"pattern:{pattern}")

            # Description matches (lower weight)
            for desc_keyword in indicators["descriptions"]:
                if desc_keyword in description:
                    scores[level] += 0.5
                    reasons[level].append(f"desc:{desc_keyword}")

        # Find highest scoring level
        max_score = max(scores.values())

        if max_score == 0:
            # No matches - use default
            return ToolRiskClassification(
                level=self.default_level,
                confidence=0.3,
                reasons=["no_match:using_default"],
            )

        # Find level with highest score
        best_level = max(scores, key=scores.get)

        # Calculate confidence (normalize by total matches)
        total_score = sum(scores.values())
        confidence = max_score / total_score if total_score > 0 else 0.5

        return ToolRiskClassification(
            level=best_level,
            confidence=confidence,
            reasons=reasons[best_level],
            metadata={
                "scores": {l.name: s for l, s in scores.items()},
                "tool_name": name,
            },
        )

    def classify_tools(
        self,
        tools: list[dict[str, Any]],
    ) -> dict[str, ToolRiskClassification]:
        """
        Classify multiple tools.

        Args:
            tools: List of tool definition dicts

        Returns:
            Dict mapping tool names to classifications
        """
        return {
            tool.get("name", f"tool_{i}"): self.classify_tool(tool) for i, tool in enumerate(tools)
        }

    def get_max_risk(
        self,
        tools: list[dict[str, Any]],
    ) -> ToolRiskLevel:
        """
        Get maximum risk level across all tools.

        Args:
            tools: List of tool definition dicts

        Returns:
            Highest risk level found
        """
        if not tools:
            return ToolRiskLevel.LOW

        classifications = self.classify_tools(tools)
        return max(c.level for c in classifications.values())

    def filter_by_risk(
        self,
        tools: list[dict[str, Any]],
        max_level: ToolRiskLevel,
    ) -> list[dict[str, Any]]:
        """
        Filter tools to those at or below a risk level.

        Args:
            tools: List of tool definition dicts
            max_level: Maximum allowed risk level

        Returns:
            Filtered list of tools
        """
        classifications = self.classify_tools(tools)
        return [
            tool
            for tool in tools
            if classifications.get(
                tool.get("name", ""), ToolRiskClassification(ToolRiskLevel.HIGH, 0, [])
            ).level
            <= max_level
        ]

    def requires_verifier(
        self,
        tools: list[dict[str, Any]],
        threshold: ToolRiskLevel = ToolRiskLevel.HIGH,
    ) -> bool:
        """
        Check if any tools require verifier model due to risk.

        Args:
            tools: List of tool definition dicts
            threshold: Risk level that requires verifier

        Returns:
            True if any tool meets or exceeds threshold
        """
        return self.get_max_risk(tools) >= threshold

    def add_override(self, tool_name: str, level: ToolRiskLevel) -> None:
        """Add custom risk level override for a tool."""
        self.overrides[tool_name] = level

    def remove_override(self, tool_name: str) -> bool:
        """Remove custom risk level override."""
        if tool_name in self.overrides:
            del self.overrides[tool_name]
            return True
        return False


# ============================================================================
# ROUTING INTEGRATION
# ============================================================================


def get_tool_risk_routing(
    tools: list[dict[str, Any]],
    classifier: Optional[ToolRiskClassifier] = None,
) -> dict[str, Any]:
    """
    Get routing recommendation based on tool risk.

    Args:
        tools: List of tool definitions
        classifier: Optional custom classifier

    Returns:
        Routing recommendation dict with:
        - max_risk: Maximum risk level
        - use_verifier: Whether to use verifier model
        - classifications: Individual tool classifications
        - high_risk_tools: List of high/critical risk tool names
    """
    classifier = classifier or ToolRiskClassifier()

    classifications = classifier.classify_tools(tools)
    max_risk = (
        max(c.level for c in classifications.values()) if classifications else ToolRiskLevel.LOW
    )

    high_risk_tools = [name for name, c in classifications.items() if c.level >= ToolRiskLevel.HIGH]

    return {
        "max_risk": max_risk,
        "max_risk_name": max_risk.name,
        "use_verifier": max_risk >= ToolRiskLevel.HIGH,
        "classifications": {
            name: {"level": c.level.name, "confidence": c.confidence}
            for name, c in classifications.items()
        },
        "high_risk_tools": high_risk_tools,
    }
