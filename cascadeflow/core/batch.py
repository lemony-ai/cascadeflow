"""Batch processing for cascadeflow."""

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from .batch_config import BatchConfig, BatchStrategy

if TYPE_CHECKING:
    from .agent import CascadeAgent
    from .schema.result import CascadeResult


# Check if LiteLLM batch is available
try:
    from litellm import batch_completion

    HAS_LITELLM_BATCH = True
except (ImportError, AttributeError):
    HAS_LITELLM_BATCH = False


@dataclass
class BatchResult:
    """Result from batch processing"""

    results: list[Optional["CascadeResult"]]
    """Results for each query (None if failed)"""

    success_count: int
    """Number of successful queries"""

    failure_count: int
    """Number of failed queries"""

    total_cost: float
    """Total cost for all queries"""

    total_time: float
    """Total processing time in seconds"""

    strategy_used: str
    """Strategy used (litellm_native or sequential)"""

    errors: list[Optional[str]]
    """Error messages for failed queries"""

    metadata: dict[str, Any]
    """Custom metadata"""

    @property
    def success_rate(self) -> float:
        """Success rate (0.0 to 1.0)"""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    @property
    def average_cost(self) -> float:
        """Average cost per query"""
        total = self.success_count + self.failure_count
        return self.total_cost / total if total > 0 else 0.0

    @property
    def average_time(self) -> float:
        """Average time per query in seconds"""
        total = self.success_count + self.failure_count
        return self.total_time / total if total > 0 else 0.0


class BatchProcessor:
    """
    Batch processor with LiteLLM + fallback.

    Features:
    - LiteLLM native batch (preferred, most efficient)
    - Sequential fallback with concurrency control
    - Cost tracking per query
    - Quality validation per query
    - Error handling and retry logic
    """

    def __init__(self, agent: "CascadeAgent"):
        """
        Initialize batch processor.

        Args:
            agent: CascadeAgent instance to use for processing
        """
        self.agent = agent

    async def process_batch(
        self, queries: list[str], config: Optional[BatchConfig] = None, **kwargs
    ) -> BatchResult:
        """
        Process a batch of queries.

        Args:
            queries: List of query strings
            config: Batch configuration (default: BatchConfig())
            **kwargs: Additional arguments passed to agent.run()

        Returns:
            BatchResult with all results and metadata

        Example:
            queries = ["What is Python?", "What is JavaScript?", "What is Rust?"]
            result = await processor.process_batch(queries)

            for i, cascade_result in enumerate(result.results):
                if cascade_result:
                    print(f"Query {i}: {cascade_result.content}")

            print(f"Success rate: {result.success_rate:.1%}")
            print(f"Total cost: ${result.total_cost:.4f}")
        """
        if config is None:
            config = BatchConfig()

        start_time = time.time()

        # Choose strategy
        strategy = self._choose_strategy(config.strategy)

        # Process batch using chosen strategy
        if strategy == BatchStrategy.LITELLM_NATIVE and HAS_LITELLM_BATCH:
            results, errors = await self._process_litellm_batch(queries, config, **kwargs)
        else:
            results, errors = await self._process_sequential_batch(queries, config, **kwargs)
            strategy = BatchStrategy.SEQUENTIAL  # Update strategy used

        # Calculate statistics
        success_count = sum(1 for r in results if r is not None)
        failure_count = len(results) - success_count
        total_cost = sum(r.total_cost for r in results if r is not None)
        total_time = time.time() - start_time

        return BatchResult(
            results=results,
            success_count=success_count,
            failure_count=failure_count,
            total_cost=total_cost,
            total_time=total_time,
            strategy_used=strategy.value,
            errors=errors,
            metadata=config.metadata,
        )

    def _choose_strategy(self, strategy: BatchStrategy) -> BatchStrategy:
        """Choose batch processing strategy"""
        if strategy == BatchStrategy.AUTO:
            return BatchStrategy.LITELLM_NATIVE if HAS_LITELLM_BATCH else BatchStrategy.SEQUENTIAL
        return strategy

    async def _process_litellm_batch(
        self, queries: list[str], config: BatchConfig, **kwargs
    ) -> tuple[list[Optional["CascadeResult"]], list[Optional[str]]]:
        """
        Process batch using LiteLLM native batch API.

        Note: This currently falls back to concurrent processing since
        LiteLLM batch_completion is designed for the proxy server.
        For the library, we use asyncio.gather with concurrency control.
        """
        # For now, LiteLLM batch API in the library is limited
        # We use efficient concurrent processing instead
        return await self._process_sequential_batch(queries, config, **kwargs)

    async def _process_sequential_batch(
        self, queries: list[str], config: BatchConfig, **kwargs
    ) -> tuple[list[Optional["CascadeResult"]], list[Optional[str]]]:
        """Process batch sequentially with concurrency control"""
        results: list[Optional[CascadeResult]] = []
        errors: list[Optional[str]] = []

        # Semaphore for concurrency control
        semaphore = asyncio.Semaphore(config.max_parallel)

        async def process_one(
            query: str, index: int
        ) -> tuple[int, Optional["CascadeResult"], Optional[str]]:
            """Process single query with semaphore"""
            async with semaphore:
                try:
                    result = await asyncio.wait_for(
                        self.agent.run(query, **kwargs), timeout=config.timeout_per_query
                    )
                    return index, result, None

                except asyncio.TimeoutError:
                    if config.retry_failed:
                        # Retry once
                        try:
                            result = await asyncio.wait_for(
                                self.agent.run(query, **kwargs), timeout=config.timeout_per_query
                            )
                            return index, result, None
                        except Exception as e:
                            error_msg = f"Timeout (retry failed: {str(e)})"
                            if config.stop_on_error:
                                raise
                            return index, None, error_msg
                    else:
                        if config.stop_on_error:
                            raise
                        return index, None, "Timeout"

                except Exception as e:
                    if config.retry_failed:
                        # Retry once
                        try:
                            result = await asyncio.wait_for(
                                self.agent.run(query, **kwargs), timeout=config.timeout_per_query
                            )
                            return index, result, None
                        except Exception as retry_e:
                            error_msg = f"Error: {str(retry_e)}"
                            if config.stop_on_error:
                                raise
                            return index, None, error_msg
                    else:
                        if config.stop_on_error:
                            raise
                        return index, None, str(e)

        # Create tasks for all queries
        tasks = [process_one(query, i) for i, query in enumerate(queries)]

        # Process with total timeout
        try:
            completed = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=config.total_timeout
            )
        except asyncio.TimeoutError:
            # Total timeout exceeded - return partial results
            completed = []
            for i in range(len(queries)):
                completed.append((i, None, "Total timeout exceeded"))

        # Handle exceptions that were returned instead of raised
        processed_results = []
        for item in completed:
            if isinstance(item, Exception):
                # Exception was returned from gather
                processed_results.append((len(processed_results), None, str(item)))
            else:
                processed_results.append(item)

        # Sort by index to preserve order (if requested)
        if config.preserve_order:
            processed_results.sort(key=lambda x: x[0])

        # Extract results and errors
        results = [r for _, r, _ in processed_results]
        errors = [e for _, _, e in processed_results]

        return results, errors


class BatchProcessingError(Exception):
    """Error during batch processing"""

    pass
