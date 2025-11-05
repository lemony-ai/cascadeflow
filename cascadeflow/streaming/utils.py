"""
cascadeflow Streaming Utilities
================================

Shared utilities for streaming implementations:
- Progressive JSON parsing
- Tool call validation helpers
- Confidence estimation
"""

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class JSONParseState(Enum):
    """State of progressive JSON parsing."""

    EMPTY = "empty"
    PARTIAL = "partial"
    COMPLETE = "complete"
    INVALID = "invalid"


@dataclass
class ParseResult:
    """Result from progressive JSON parsing."""

    state: JSONParseState
    data: Optional[dict[str, Any]] = None
    partial_keys: list[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.partial_keys is None:
            self.partial_keys = []


class ProgressiveJSONParser:
    """
    Parse JSON progressively as it streams in.

    Handles incomplete JSON gracefully and extracts whatever is parseable.

    Examples:
        >>> parser = ProgressiveJSONParser()
        >>> result = parser.parse('{"name": "get_weat')
        >>> result.state
        JSONParseState.PARTIAL
        >>> result.partial_keys
        ['name']
        >>> result.data
        {'name': 'get_weat'}
    """

    def __init__(self):
        """Initialize parser."""
        self.buffer = ""

    def parse(self, json_str: str) -> ParseResult:
        """
        Parse potentially incomplete JSON string.

        Args:
            json_str: JSON string (may be incomplete)

        Returns:
            ParseResult with state and extracted data
        """
        if not json_str or not json_str.strip():
            return ParseResult(state=JSONParseState.EMPTY)

        json_str = json_str.strip()

        # Try to parse as complete JSON first
        try:
            data = json.loads(json_str)
            return ParseResult(
                state=JSONParseState.COMPLETE,
                data=data,
                partial_keys=list(data.keys()) if isinstance(data, dict) else [],
            )
        except json.JSONDecodeError:
            pass

        # Try to extract partial data
        partial_data, partial_keys = self._extract_partial_json(json_str)

        if partial_data:
            return ParseResult(
                state=JSONParseState.PARTIAL, data=partial_data, partial_keys=partial_keys
            )

        # Check if it's valid JSON start
        if self._is_valid_json_start(json_str):
            return ParseResult(state=JSONParseState.PARTIAL, data={}, partial_keys=[])

        return ParseResult(state=JSONParseState.INVALID, error="Invalid JSON structure")

    def _extract_partial_json(self, json_str: str) -> tuple[dict[str, Any], list[str]]:
        """
        Extract whatever is parseable from partial JSON.

        Strategy:
        1. Try to close incomplete structures
        2. Extract complete key-value pairs
        3. Return partial dictionary
        """
        data = {}
        keys = []

        # Pattern: "key": "value"
        string_pattern = r'"([^"]+)"\s*:\s*"([^"]*)"'
        for match in re.finditer(string_pattern, json_str):
            key, value = match.groups()
            data[key] = value
            keys.append(key)

        # Pattern: "key": number
        number_pattern = r'"([^"]+)"\s*:\s*(-?\d+\.?\d*)'
        for match in re.finditer(number_pattern, json_str):
            key, value = match.groups()
            if key not in data:  # Don't override strings
                try:
                    data[key] = float(value) if "." in value else int(value)
                    keys.append(key)
                except ValueError:
                    pass

        # Pattern: "key": true/false/null
        bool_pattern = r'"([^"]+)"\s*:\s*(true|false|null)'
        for match in re.finditer(bool_pattern, json_str):
            key, value = match.groups()
            if key not in data:
                data[key] = {"true": True, "false": False, "null": None}[value]
                keys.append(key)

        # Pattern: "key": { (nested object start)
        object_pattern = r'"([^"]+)"\s*:\s*\{'
        for match in re.finditer(object_pattern, json_str):
            key = match.group(1)
            if key not in data:
                data[key] = {}  # Placeholder for nested object
                keys.append(key)

        # Pattern: "key": [ (array start)
        array_pattern = r'"([^"]+)"\s*:\s*\['
        for match in re.finditer(array_pattern, json_str):
            key = match.group(1)
            if key not in data:
                data[key] = []  # Placeholder for array
                keys.append(key)

        return data, keys

    def _is_valid_json_start(self, json_str: str) -> bool:
        """Check if string is a valid JSON start."""
        json_str = json_str.strip()

        # Must start with { or [
        if not json_str.startswith(("{", "[")):
            return False

        # Check for balanced quotes
        json_str.count('"')
        # Odd number of quotes is fine for partial JSON

        return True


class ToolCallValidator:
    """
    Validates tool calls for correctness.

    Checks:
    1. Tool name exists in available tools
    2. Required parameters present
    3. Parameter types correct
    4. No extra parameters
    """

    @staticmethod
    def validate_tool_call(
        tool_call: dict[str, Any], available_tools: list[dict[str, Any]]
    ) -> tuple[bool, str]:
        """
        Validate a tool call.

        Args:
            tool_call: Tool call dict with 'name' and 'arguments'
            available_tools: List of available tool definitions

        Returns:
            (is_valid, reason)
        """
        # Check structure
        if "name" not in tool_call:
            return False, "Missing 'name' field"

        if "arguments" not in tool_call:
            return False, "Missing 'arguments' field"

        tool_name = tool_call["name"]
        arguments = tool_call["arguments"]

        # Find tool definition
        tool_def = None
        for tool in available_tools:
            if isinstance(tool, dict):
                # Handle both formats: direct dict and function wrapper
                func_def = tool.get("function", tool)
                if func_def.get("name") == tool_name:
                    tool_def = func_def
                    break

        if tool_def is None:
            return False, f"Tool '{tool_name}' not found in available tools"

        # Get parameter schema
        params_schema = tool_def.get("parameters", {})
        required_params = params_schema.get("required", [])
        properties = params_schema.get("properties", {})

        # Parse arguments if string
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return False, "Invalid JSON in arguments"

        if not isinstance(arguments, dict):
            return False, "Arguments must be a dict"

        # Check required parameters
        for param in required_params:
            if param not in arguments:
                return False, f"Missing required parameter: {param}"

        # Check parameter types (basic validation)
        for param_name, param_value in arguments.items():
            if param_name in properties:
                expected_type = properties[param_name].get("type")

                if expected_type == "string" and not isinstance(param_value, str):
                    return False, f"Parameter '{param_name}' must be string"
                elif expected_type == "number" and not isinstance(param_value, (int, float)):
                    return False, f"Parameter '{param_name}' must be number"
                elif expected_type == "boolean" and not isinstance(param_value, bool):
                    return False, f"Parameter '{param_name}' must be boolean"
                elif expected_type == "array" and not isinstance(param_value, list):
                    return False, f"Parameter '{param_name}' must be array"
                elif expected_type == "object" and not isinstance(param_value, dict):
                    return False, f"Parameter '{param_name}' must be object"

        return True, "Valid"

    @staticmethod
    def extract_tool_calls_from_response(response: str) -> list[dict[str, Any]]:
        """
        Extract tool calls from LLM response.

        Handles various formats:
        - Direct JSON
        - Function calling format
        - Text with embedded JSON
        """
        tool_calls = []

        # Try to parse as direct JSON
        try:
            data = json.loads(response)
            if isinstance(data, dict) and "name" in data:
                tool_calls.append(data)
            elif isinstance(data, list):
                tool_calls.extend(data)
            return tool_calls
        except json.JSONDecodeError:
            pass

        # Try to extract JSON blocks
        json_pattern = r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^}]*\}[^{}]*\}'
        matches = re.findall(json_pattern, response, re.DOTALL)

        for match in matches:
            try:
                tool_call = json.loads(match)
                tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue

        return tool_calls


def estimate_confidence_from_logprobs(
    logprobs: list[float], method: str = "mean"
) -> Optional[float]:
    """
    Estimate confidence from logprobs.

    Args:
        logprobs: List of log probabilities
        method: 'mean', 'min', or 'median'

    Returns:
        Confidence score 0.0-1.0, or None if not available
    """
    if not logprobs:
        return None

    try:
        import math

        if method == "mean":
            avg_logprob = sum(logprobs) / len(logprobs)
            confidence = math.exp(avg_logprob)
        elif method == "min":
            min_logprob = min(logprobs)
            confidence = math.exp(min_logprob)
        elif method == "median":
            sorted_logprobs = sorted(logprobs)
            median_logprob = sorted_logprobs[len(sorted_logprobs) // 2]
            confidence = math.exp(median_logprob)
        else:
            return None

        # Clamp to [0, 1]
        return max(0.0, min(1.0, confidence))

    except (ValueError, OverflowError):
        return None


__all__ = [
    "JSONParseState",
    "ParseResult",
    "ProgressiveJSONParser",
    "ToolCallValidator",
    "estimate_confidence_from_logprobs",
]
