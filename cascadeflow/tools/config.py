"""
Tool configuration for cascadeflow.

Defines tools that can be called by language models.
"""

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolConfig:
    """
    Universal tool configuration that works across all providers.

    Example:
        def get_weather(location: str, unit: str = "celsius") -> dict:
            return {"temp": 22, "condition": "sunny"}

        tool = ToolConfig(
            name="get_weather",
            description="Get current weather for a location",
            parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                },
                "required": ["location"]
            },
            function=get_weather
        )
    """

    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema format
    function: Optional[Callable] = None  # Actual function to execute

    def __post_init__(self):
        """Validate tool configuration."""
        if not self.name:
            raise ValueError("Tool name cannot be empty")
        if not self.description:
            raise ValueError("Tool description cannot be empty")
        if not isinstance(self.parameters, dict):
            raise ValueError("Tool parameters must be a dictionary (JSON schema)")

        # Validate JSON schema structure
        if self.parameters.get("type") != "object":
            raise ValueError("Tool parameters must be a JSON schema with type='object'")

    @classmethod
    def from_function(cls, func: Callable, description: Optional[str] = None) -> "ToolConfig":
        """
        Create ToolConfig from a Python function with type hints.

        Example:
            def calculate(x: int, y: int) -> int:
                '''Add two numbers.'''
                return x + y

            tool = ToolConfig.from_function(calculate)
        """
        # Get function signature
        sig = inspect.signature(func)

        # Extract description from docstring if not provided
        if description is None:
            description = func.__doc__ or f"Call function {func.__name__}"
            description = description.strip()

        # Build parameters schema from type hints
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            param_schema = {"type": "string"}  # Default type

            # Infer type from annotation
            if param.annotation != inspect.Parameter.empty:
                annotation = param.annotation
                param_schema["type"] = _infer_json_type(annotation)

            properties[param_name] = param_schema

            # Add to required if no default value
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        parameters = {"type": "object", "properties": properties, "required": required}

        return cls(
            name=func.__name__, description=description, parameters=parameters, function=func
        )


def _infer_json_type(python_type: type) -> str:
    """
    Infer JSON schema type from Python type annotation.

    Args:
        python_type: Python type annotation

    Returns:
        JSON schema type string
    """
    type_map = {
        int: "integer",
        float: "number",
        str: "string",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    # Handle basic types
    if python_type in type_map:
        return type_map[python_type]

    # Handle typing module types
    type_str = str(python_type)
    if "List" in type_str or "list" in type_str:
        return "array"
    elif "Dict" in type_str or "dict" in type_str:
        return "object"

    # Default to string
    return "string"


def tool(func: Callable) -> ToolConfig:
    """
    Decorator to create a tool from a function.

    Example:
        @tool
        def get_weather(city: str) -> dict:
            '''Get weather for a city.'''
            return {"temp": 22, "condition": "sunny"}
    """
    return ToolConfig.from_function(func)


def create_tool_from_function(func: Callable, description: Optional[str] = None) -> ToolConfig:
    """
    Convenience function to create a tool from a Python function.

    Example:
        def add(x: int, y: int) -> int:
            '''Add two numbers.'''
            return x + y

        tool = create_tool_from_function(add)
    """
    return ToolConfig.from_function(func, description)
