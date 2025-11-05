"""Utility functions for cascadeflow."""

import logging
import os
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

# Global console for rich output
console = Console()


def setup_logging(level: Optional[str] = None) -> None:
    """
    Setup rich logging with color and formatting.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               If None, reads from LOG_LEVEL env var, defaults to INFO.

    Example:
        >>> setup_logging("DEBUG")
        >>> logging.info("This is a test")
    """
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")

    logging.basicConfig(
        level=level.upper(),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(rich_tracebacks=True, console=console, show_time=True, show_path=False)
        ],
    )


def format_cost(cost: float) -> str:
    """
    Format cost in USD with 4 decimal places.

    Args:
        cost: Cost in USD

    Returns:
        Formatted string like "$0.0042"

    Example:
        >>> format_cost(0.00425)
        '$0.0043'
        >>> format_cost(1.5)
        '$1.5000'
        >>> format_cost(0.0)
        '$0.0000'
    """
    return f"${cost:.4f}"


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation for text.

    Uses OpenAI-style estimation: 1 token ≈ 4 characters.
    This is a rough approximation and should not be used for exact billing.

    Args:
        text: Input text

    Returns:
        Estimated token count

    Example:
        >>> estimate_tokens("Hello, world!")
        3
        >>> estimate_tokens("This is a longer sentence with more words.")
        11
    """
    # Simple approximation: 1 token ≈ 4 characters
    return max(1, len(text) // 4)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text for display with ellipsis.

    Args:
        text: Input text
        max_length: Maximum length before truncation
        suffix: Suffix to add when truncated (default: "...")

    Returns:
        Truncated text with suffix if needed

    Example:
        >>> truncate_text("This is a very long text", max_length=10)
        'This is...'
        >>> truncate_text("Short", max_length=10)
        'Short'
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def calculate_cosine_similarity(vec1: list, vec2: list) -> float:
    """
    Calculate cosine similarity between two vectors.

    Used for semantic routing and quality estimation.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score (0-1)

    Example:
        >>> calculate_cosine_similarity([1, 0, 0], [1, 0, 0])
        1.0
        >>> calculate_cosine_similarity([1, 0, 0], [0, 1, 0])
        0.0
    """
    import numpy as np

    vec1 = np.array(vec1)
    vec2 = np.array(vec2)

    # Handle zero vectors
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    # Cosine similarity
    similarity = np.dot(vec1, vec2) / (norm1 * norm2)

    # Clamp to [0, 1] range
    return float(max(0.0, min(1.0, similarity)))


def get_env_or_raise(key: str, default: Optional[str] = None) -> str:
    """
    Get environment variable or raise error.

    Args:
        key: Environment variable key
        default: Default value if not set (optional)

    Returns:
        Environment variable value

    Raises:
        ValueError: If key not set and no default provided

    Example:
        >>> os.environ["TEST_VAR"] = "test_value"
        >>> get_env_or_raise("TEST_VAR")
        'test_value'
    """
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"Environment variable {key} not set and no default provided")
    return value


def parse_model_identifier(identifier: str) -> tuple[str, str]:
    """
    Parse model identifier into provider and model name.

    Args:
        identifier: Model identifier (e.g., "openai:gpt-4" or "gpt-4")

    Returns:
        Tuple of (provider, model_name)

    Example:
        >>> parse_model_identifier("openai:gpt-4")
        ('openai', 'gpt-4')
        >>> parse_model_identifier("gpt-4")
        ('', 'gpt-4')
    """
    if ":" in identifier:
        provider, model = identifier.split(":", 1)
        return provider, model
    return "", identifier
