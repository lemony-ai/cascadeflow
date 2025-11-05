"""
Example tools for cascadeflow.

Save this as: cascadeflow/tools/examples.py

Provides ready-to-use example tools for testing and documentation.
"""

from typing import Any


def example_calculator(operation: str, x: float, y: float) -> float:
    """
    Perform basic arithmetic operations.

    Args:
        operation: Operation to perform (add, subtract, multiply, divide)
        x: First number
        y: Second number

    Returns:
        Result of the operation

    Raises:
        ValueError: If operation is not recognized
    """
    operations = {
        "add": lambda a, b: a + b,
        "subtract": lambda a, b: a - b,
        "multiply": lambda a, b: a * b,
        "divide": lambda a, b: a / b if b != 0 else float("inf"),
    }

    if operation not in operations:
        raise ValueError(
            f"Unknown operation: {operation}. " f"Valid operations: {', '.join(operations.keys())}"
        )

    return operations[operation](x, y)


def example_get_weather(location: str, unit: str = "celsius") -> dict[str, Any]:
    """
    Get current weather for a location (mock implementation).

    Args:
        location: City name
        unit: Temperature unit (celsius or fahrenheit)

    Returns:
        Weather data dictionary with temperature, condition, and humidity
    """
    # Mock implementation - returns fixed data
    temp = 22 if unit == "celsius" else 72

    return {
        "location": location,
        "temperature": temp,
        "unit": unit,
        "condition": "sunny",
        "humidity": 65,
    }
