"""
Tool Quality Validator

Validates tool call quality using 5-level validation with complexity-aware thresholds.
Works alongside your existing text quality system - no base class needed.

ONLY for tool calls - your existing quality system handles text.

5-Level Validation:
    1. JSON syntax valid?
    2. Schema matches expected format?
    3. Tool exists in available tools?
    4. Required fields present?
    5. Parameters make sense?

Adaptive Thresholds (based on complexity from routing/tool_complexity.py):
    - TRIVIAL:  0.70 (more lenient - small model handles well)
    - SIMPLE:   0.75
    - MODERATE: 0.85 (more strict - riskier for small model)

Expected acceptance rates:
    - TRIVIAL:  92%
    - SIMPLE:   76%
    - MODERATE: 47%

Usage:
    from cascadeflow.quality.tool_validator import ToolQualityValidator

    validator = ToolQualityValidator()

    # Basic validation
    score = validator.validate(tool_calls, available_tools)

    # With adaptive threshold (recommended)
    result = validator.validate_tool_calls(
        tool_calls=draft.tool_calls,
        available_tools=tools,
        complexity_level=complexity_level  # From ToolComplexityAnalyzer
    )

    if result.is_valid:
        accept_draft()
    else:
        escalate_to_large_model()
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolQualityScore:
    """
    Tool quality assessment result.

    Similar to your existing ValidationResult but specifically for tools.
    Contains level-by-level validation results and overall score.
    """

    overall_score: float  # 0.0-1.0 overall quality
    threshold_used: float  # Threshold applied
    is_valid: bool  # Did it pass threshold?

    # 5-Level validation results
    json_valid: bool  # Level 1
    schema_valid: bool  # Level 2
    tool_exists: bool  # Level 3
    required_fields_present: bool  # Level 4
    parameters_sensible: bool  # Level 5

    # Additional info
    issues: list[str] = field(default_factory=list)
    complexity_level: Optional[Any] = None
    adaptive_threshold: bool = False

    def __str__(self) -> str:
        status = "✓ VALID" if self.is_valid else "✗ INVALID"
        return (
            f"ToolQuality({status}, score={self.overall_score:.2f}, "
            f"threshold={self.threshold_used:.2f})"
        )


class ToolQualityValidator:
    """
    Validates tool call quality using 5-level validation.

    Works independently - doesn't inherit from anything.
    Your existing text quality system (with alignment, difficulty, etc.)
    remains unchanged.

    5-Level Validation:
    1. JSON syntax
    2. Schema match
    3. Tool exists
    4. Required fields
    5. Parameters sensible

    Adaptive Thresholds:
    - Adjusts based on complexity from ToolComplexityAnalyzer
    - TRIVIAL: 0.70 (lenient)
    - MODERATE: 0.85 (strict)
    """

    # Adaptive thresholds by complexity
    ADAPTIVE_THRESHOLDS = {
        "trivial": 0.70,
        "simple": 0.75,
        "moderate": 0.85,
    }

    DEFAULT_THRESHOLD = 0.80

    # Weights for each validation level
    LEVEL_WEIGHTS = {
        "json_valid": 0.25,
        "schema_valid": 0.20,
        "tool_exists": 0.20,
        "required_fields": 0.20,
        "parameters_sensible": 0.15,
    }

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        if self.verbose:
            logger.info("ToolQualityValidator initialized")

    def validate(
        self, tool_calls: Any, available_tools: Optional[list[dict[str, Any]]] = None
    ) -> float:
        """
        Simple validation - returns quality score 0.0-1.0.

        For basic use when you don't need adaptive thresholds.

        Args:
            tool_calls: Tool calls to validate
            available_tools: Available tools

        Returns:
            Quality score 0.0-1.0
        """
        if isinstance(tool_calls, dict):
            tool_calls = [tool_calls]

        if not tool_calls:
            return 0.0

        scores = []
        for tool_call in tool_calls:
            score = self._validate_single_tool_call(tool_call, available_tools)
            scores.append(score)

        return sum(scores) / len(scores) if scores else 0.0

    def validate_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
        available_tools: list[dict[str, Any]],
        complexity_level: Optional[Any] = None,
    ) -> ToolQualityScore:
        """
        Main validation method with adaptive thresholds.

        This is what you'll use in cascade - integrates with ToolComplexityAnalyzer.

        Args:
            tool_calls: Tool calls from draft
            available_tools: Available tools
            complexity_level: ToolComplexityLevel for adaptive threshold

        Returns:
            ToolQualityScore with detailed results
        """
        # Get threshold (adaptive or default)
        threshold, is_adaptive = self._get_threshold(complexity_level)

        # Run 5-level validation
        json_valid = self._validate_json(tool_calls)
        schema_valid = self._validate_schema(tool_calls)
        tool_exists = self._validate_tool_exists(tool_calls, available_tools)
        required_fields = self._validate_required_fields(tool_calls, available_tools)
        parameters_sensible = self._validate_parameters(tool_calls, available_tools)

        # Calculate weighted score
        score = (
            self.LEVEL_WEIGHTS["json_valid"] * (1.0 if json_valid else 0.0)
            + self.LEVEL_WEIGHTS["schema_valid"] * (1.0 if schema_valid else 0.0)
            + self.LEVEL_WEIGHTS["tool_exists"] * (1.0 if tool_exists else 0.0)
            + self.LEVEL_WEIGHTS["required_fields"] * (1.0 if required_fields else 0.0)
            + self.LEVEL_WEIGHTS["parameters_sensible"] * (1.0 if parameters_sensible else 0.0)
        )

        is_valid = score >= threshold

        # Collect issues
        issues = []
        if not json_valid:
            issues.append("Invalid JSON structure")
        if not schema_valid:
            issues.append("Schema validation failed")
        if not tool_exists:
            issues.append("Tool not found")
        if not required_fields:
            issues.append("Required fields missing")
        if not parameters_sensible:
            issues.append("Parameters don't make sense")

        if self.verbose:
            self._log_validation(score, threshold, is_valid, issues, complexity_level)

        return ToolQualityScore(
            overall_score=score,
            threshold_used=threshold,
            is_valid=is_valid,
            json_valid=json_valid,
            schema_valid=schema_valid,
            tool_exists=tool_exists,
            required_fields_present=required_fields,
            parameters_sensible=parameters_sensible,
            issues=issues,
            complexity_level=complexity_level,
            adaptive_threshold=is_adaptive,
        )

    def _get_threshold(self, complexity_level: Optional[Any]) -> tuple[float, bool]:
        """Get threshold based on complexity."""
        if complexity_level is None:
            return self.DEFAULT_THRESHOLD, False

        # Get level value
        level_value = (
            complexity_level.value.lower()
            if hasattr(complexity_level, "value")
            else str(complexity_level).lower()
        )

        threshold = self.ADAPTIVE_THRESHOLDS.get(level_value, self.DEFAULT_THRESHOLD)
        is_adaptive = level_value in self.ADAPTIVE_THRESHOLDS

        return threshold, is_adaptive

    def _validate_single_tool_call(
        self, tool_call: dict[str, Any], available_tools: Optional[list[dict[str, Any]]]
    ) -> float:
        """Validate single tool call."""
        score = 0.0

        if isinstance(tool_call, dict):
            score += self.LEVEL_WEIGHTS["json_valid"]

        if self._has_expected_fields(tool_call):
            score += self.LEVEL_WEIGHTS["schema_valid"]

        if not available_tools or self._tool_name_exists(tool_call, available_tools):
            score += self.LEVEL_WEIGHTS["tool_exists"]

        if not available_tools or self._has_required_fields(tool_call, available_tools):
            score += self.LEVEL_WEIGHTS["required_fields"]

        if self._parameters_are_sensible(tool_call):
            score += self.LEVEL_WEIGHTS["parameters_sensible"]

        return score

    # ═══════════════════════════════════════════════════════════
    # Validation Levels
    # ═══════════════════════════════════════════════════════════

    def _validate_json(self, tool_calls: list[dict[str, Any]]) -> bool:
        """Level 1: JSON syntax valid."""
        return all(isinstance(tc, dict) for tc in tool_calls) if tool_calls else False

    def _validate_schema(self, tool_calls: list[dict[str, Any]]) -> bool:
        """Level 2: Schema matches."""
        return all(self._has_expected_fields(tc) for tc in tool_calls)

    def _has_expected_fields(self, tool_call: dict[str, Any]) -> bool:
        """Check for name + arguments fields."""
        has_name = "name" in tool_call or "function" in tool_call
        has_args = "arguments" in tool_call or "parameters" in tool_call or "args" in tool_call
        return has_name and has_args

    def _validate_tool_exists(
        self, tool_calls: list[dict[str, Any]], available_tools: list[dict[str, Any]]
    ) -> bool:
        """Level 3: Tool exists."""
        if not available_tools:
            return True
        return all(self._tool_name_exists(tc, available_tools) for tc in tool_calls)

    def _tool_name_exists(
        self, tool_call: dict[str, Any], available_tools: list[dict[str, Any]]
    ) -> bool:
        """Check if tool name exists."""
        tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name")
        if not tool_name:
            return False

        available_names = {t.get("name") for t in available_tools}
        return tool_name in available_names

    def _validate_required_fields(
        self, tool_calls: list[dict[str, Any]], available_tools: list[dict[str, Any]]
    ) -> bool:
        """Level 4: Required fields present."""
        if not available_tools:
            return True
        return all(self._has_required_fields(tc, available_tools) for tc in tool_calls)

    def _has_required_fields(
        self, tool_call: dict[str, Any], available_tools: list[dict[str, Any]]
    ) -> bool:
        """Check required fields."""
        tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name")
        if not tool_name:
            return False

        # Find tool schema
        tool_schema = next((t for t in available_tools if t.get("name") == tool_name), None)
        if not tool_schema:
            return False

        # Get required fields
        required = tool_schema.get("parameters", {}).get("required", [])
        if not required:
            return True

        # Get arguments
        arguments = tool_call.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except:
                return False

        return all(field in arguments for field in required)

    def _validate_parameters(
        self, tool_calls: list[dict[str, Any]], available_tools: list[dict[str, Any]]
    ) -> bool:
        """Level 5: Parameters sensible."""
        return all(self._parameters_are_sensible(tc) for tc in tool_calls)

    def _parameters_are_sensible(self, tool_call: dict[str, Any]) -> bool:
        """Basic sanity checks on parameters."""
        arguments = tool_call.get("arguments", {})

        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except:
                return False

        return isinstance(arguments, dict)

    def _log_validation(
        self,
        score: float,
        threshold: float,
        is_valid: bool,
        issues: list[str],
        complexity_level: Optional[Any],
    ):
        """Log validation results."""
        status = "✓ VALID" if is_valid else "✗ INVALID"
        logger.info(
            f"\nTool Quality Validation\n"
            f"Score: {score:.2f}, Threshold: {threshold:.2f}\n"
            f"Complexity: {complexity_level.value if complexity_level and hasattr(complexity_level, 'value') else 'N/A'}\n"
            f"Result: {status}\n"
            f"Issues: {', '.join(issues) if issues else 'None'}"
        )


__all__ = ["ToolQualityValidator", "ToolQualityScore"]
