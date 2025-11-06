"""Batch processing configuration for cascadeflow."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class BatchStrategy(str, Enum):
    """Batch processing strategy"""

    LITELLM_NATIVE = "litellm_native"  # Use LiteLLM batch API (preferred)
    SEQUENTIAL = "sequential"  # Sequential with concurrency control
    AUTO = "auto"  # Auto-detect best strategy


@dataclass
class BatchConfig:
    """
    Configuration for batch processing.

    Example:
        config = BatchConfig(
            batch_size=10,
            max_parallel=3,
            timeout_per_query=30.0,
            strategy=BatchStrategy.AUTO
        )
    """

    # Batch settings
    batch_size: int = 10
    """Maximum number of queries in a single batch"""

    max_parallel: int = 3
    """Maximum number of parallel requests (fallback mode)"""

    timeout_per_query: float = 30.0
    """Timeout per query in seconds"""

    total_timeout: Optional[float] = None
    """Total timeout for entire batch (default: timeout_per_query * batch_size)"""

    # Strategy
    strategy: BatchStrategy = BatchStrategy.AUTO
    """Batch processing strategy"""

    # Error handling
    stop_on_error: bool = False
    """Stop processing batch if any query fails"""

    retry_failed: bool = True
    """Retry failed queries once"""

    # Cost & quality
    track_cost: bool = True
    """Track cost for each query in batch"""

    validate_quality: bool = True
    """Validate quality for each query in batch"""

    # Advanced
    preserve_order: bool = True
    """Preserve query order in results"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Custom metadata for batch"""

    def __post_init__(self):
        if self.total_timeout is None:
            self.total_timeout = self.timeout_per_query * self.batch_size
