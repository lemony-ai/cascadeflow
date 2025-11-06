"""
Base provider interface for all model providers.


NEW in v2.5 (Oct 20, 2025):
    - estimate_tokens_from_text(): Utility for token estimation
    - estimate_cost_from_text(): Utility for cost estimation
    - Better integration with telemetry.CostCalculator
"""

import asyncio
import logging
import math
import random
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# ERROR CLASSIFICATION FOR RETRY LOGIC
# ============================================================================


class ErrorType(Enum):
    """Categorize errors for appropriate retry strategies."""

    RATE_LIMIT = "rate_limit"  # 429, rate limit messages
    TIMEOUT = "timeout"  # Connection timeout
    SERVER_ERROR = "server_error"  # 500, 502, 503, 504
    AUTH_ERROR = "auth_error"  # 401, 403
    NOT_FOUND = "not_found"  # 404
    BAD_REQUEST = "bad_request"  # 400
    NETWORK_ERROR = "network_error"  # Connection errors
    UNKNOWN = "unknown"  # Other errors


# ============================================================================
# RETRY CONFIGURATION
# ============================================================================


@dataclass
class RetryConfig:
    """
    Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (including first)
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Add randomness to prevent thundering herd
        rate_limit_backoff: Special backoff for rate limits (seconds)
        retryable_errors: Which error types trigger retries
    """

    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    rate_limit_backoff: float = 30.0

    retryable_errors: list[ErrorType] = field(
        default_factory=lambda: [
            ErrorType.RATE_LIMIT,
            ErrorType.TIMEOUT,
            ErrorType.SERVER_ERROR,
            ErrorType.NETWORK_ERROR,
        ]
    )


@dataclass
class RetryMetrics:
    """Track retry statistics for monitoring."""

    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    retries_by_error: dict[str, int] = field(default_factory=dict)
    total_retry_delay: float = 0.0

    def get_summary(self) -> dict[str, Any]:
        """Get human-readable summary."""
        success_rate = (
            self.successful_attempts / self.total_attempts if self.total_attempts > 0 else 0
        )

        return {
            "total_attempts": self.total_attempts,
            "successful": self.successful_attempts,
            "failed": self.failed_attempts,
            "success_rate": f"{success_rate:.1%}",
            "total_retry_delay_sec": round(self.total_retry_delay, 2),
            "retries_by_error": dict(self.retries_by_error),
        }


# ============================================================================
# MODEL RESPONSE
# ============================================================================


@dataclass
class ModelResponse:
    """
    Standardized response from a model provider.

    All providers must return this format.

    Enhanced with logprobs support and tool calling while maintaining backward compatibility.

    v2.5 (Oct 20, 2025): Better token tracking for CostCalculator integration.
    """

    # Original fields (keep exactly as-is)
    content: str
    model: str
    provider: str
    cost: float
    tokens_used: int
    confidence: float  # 0-1 quality score
    latency_ms: float = 0.0
    metadata: dict[str, Any] = None

    # Logprobs support for speculative cascading
    tokens: Optional[list[str]] = None
    logprobs: Optional[list[float]] = None
    top_logprobs: Optional[list[dict[str, float]]] = None

    # Tool calling support (Oct 11, 2025)
    # If tools were used, this contains list of tool calls
    # If no tools used, this is None
    tool_calls: Optional[list[dict[str, Any]]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for backward compatibility."""
        result = {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "cost": self.cost,
            "tokens_used": self.tokens_used,
            "confidence": self.confidence,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
        }

        # Add logprobs if available
        if self.tokens is not None:
            result["tokens"] = self.tokens
        if self.logprobs is not None:
            result["logprobs"] = self.logprobs
        if self.top_logprobs is not None:
            result["top_logprobs"] = self.top_logprobs

        # Add tool calls if available
        if self.tool_calls is not None:
            result["tool_calls"] = self.tool_calls

        return result


# ============================================================================
# BASE PROVIDER WITH RETRY LOGIC & OPTIONAL TOOL CALLING
# ============================================================================


class BaseProvider(ABC):
    """
    Base class for all model providers with automatic retry logic.

    All providers (OpenAI, Anthropic, Ollama, etc.) must implement this interface.

    Enhanced with:
    - Production-grade confidence estimation
    - Intelligent logprobs defaults
    - Automatic retry logic with exponential backoff
    - Streaming support
    - Optional tool calling support (Oct 11, 2025)
    - Cost estimation utilities (Oct 20, 2025) 🆕

    BACKWARD COMPATIBLE: Tool calling is 100% optional. Existing code works unchanged.

    """

    def __init__(self, api_key: Optional[str] = None, retry_config: Optional[RetryConfig] = None):
        """
        Initialize provider with retry logic.

        Args:
            api_key: API key for the provider (if needed)
            retry_config: Custom retry configuration (optional)
        """
        # Load API key from parameter or environment
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = self._load_api_key()

        # Initialize retry configuration
        self.retry_config = retry_config or RetryConfig()
        self.retry_metrics = RetryMetrics()

        # Check logprobs support
        self._supports_logprobs = self._check_logprobs_support()

        # Check tool calling support
        self._supports_tools = self._check_tool_support()

        if not self._supports_logprobs:
            logger.info(
                f"Provider {self.__class__.__name__} does not support logprobs. "
                f"Using automatic fallback with estimated confidence."
            )

        if self._supports_tools:
            logger.info(f"Provider {self.__class__.__name__} supports tool calling.")

        # Initialize LiteLLM cost provider (auto-detect if installed)
        try:
            from cascadeflow.integrations.litellm import LiteLLMCostProvider

            self._litellm_cost_provider = LiteLLMCostProvider(fallback_enabled=False)
            self._use_litellm_pricing = True

            # Determine if this provider needs a prefix for LiteLLM
            # Providers that match LiteLLM's native format don't need prefixes
            self._litellm_provider_prefix = self._get_litellm_prefix()

            logger.info(f"LiteLLM detected - using accurate pricing for {self.__class__.__name__}")
        except (ImportError, RuntimeError):
            # LiteLLM not installed or not available - use fallback
            self._litellm_cost_provider = None
            self._use_litellm_pricing = False
            self._litellm_provider_prefix = None
            logger.debug(
                f"LiteLLM not available - using fallback pricing for {self.__class__.__name__}"
            )

        # Initialize production confidence estimator
        try:
            from cascadeflow.quality.confidence import ProductionConfidenceEstimator

            provider_name = self.__class__.__name__.replace("Provider", "").lower()
            self._confidence_estimator = ProductionConfidenceEstimator(provider_name)
            logger.debug(f"Initialized production confidence estimator for {provider_name}")
        except ImportError:
            logger.warning(
                "Production confidence system not available. "
                "Using fallback confidence calculation."
            )
            self._confidence_estimator = None

    def _load_api_key(self) -> Optional[str]:
        """
        Load API key from environment.

        Override this in subclasses to load from specific env vars.

        Returns:
            API key or None
        """
        return None

    def _check_logprobs_support(self) -> bool:
        """
        Check if provider supports logprobs.

        Override to indicate if provider supports logprobs.
        Default: False (safe default, providers opt-in)

        Returns:
            True if provider supports logprobs, False otherwise
        """
        return False

    def _check_tool_support(self) -> bool:
        """
        Check if provider supports tool calling.

        Override to indicate if provider supports tool calling.
        Default: False (safe default, providers opt-in)

        Returns:
            True if provider supports tool calling, False otherwise
        """
        return False

    # ========================================================================
    # RETRY LOGIC METHODS
    # ========================================================================

    def _classify_error(self, error: Exception) -> ErrorType:
        """
        Classify error for appropriate retry strategy.

        This is provider-agnostic error classification.
        """
        error_msg = str(error).lower()

        # Rate limiting
        if "429" in error_msg or "rate limit" in error_msg or "too many requests" in error_msg:
            return ErrorType.RATE_LIMIT

        # Timeouts
        if "timeout" in error_msg or "timed out" in error_msg:
            return ErrorType.TIMEOUT

        # Server errors (5xx)
        if any(code in error_msg for code in ["500", "502", "503", "504"]):
            return ErrorType.SERVER_ERROR

        # Auth errors
        if "401" in error_msg or "403" in error_msg or "unauthorized" in error_msg:
            return ErrorType.AUTH_ERROR

        # Not found
        if "404" in error_msg or "not found" in error_msg:
            return ErrorType.NOT_FOUND

        # Bad request
        if "400" in error_msg or "bad request" in error_msg:
            return ErrorType.BAD_REQUEST

        # Network errors
        if any(term in error_msg for term in ["connection", "network", "dns"]):
            return ErrorType.NETWORK_ERROR

        return ErrorType.UNKNOWN

    def _calculate_delay(self, attempt: int, error_type: ErrorType) -> float:
        """
        Calculate delay with exponential backoff and jitter.

        Args:
            attempt: Current attempt number (1-indexed)
            error_type: Type of error that occurred

        Returns:
            Delay in seconds
        """
        # Special handling for rate limits
        if error_type == ErrorType.RATE_LIMIT:
            base_delay = self.retry_config.rate_limit_backoff
        else:
            # Exponential backoff: delay = initial * base^(attempt-1)
            base_delay = self.retry_config.initial_delay * (
                self.retry_config.exponential_base ** (attempt - 1)
            )

        # Cap at max delay
        delay = min(base_delay, self.retry_config.max_delay)

        # Add jitter (±25%) to prevent thundering herd
        if self.retry_config.jitter:
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)

        return max(0, delay)

    def _should_retry(self, error_type: ErrorType, attempt: int) -> bool:
        """
        Determine if error should trigger a retry.

        Args:
            error_type: Type of error that occurred
            attempt: Current attempt number

        Returns:
            True if should retry, False otherwise
        """
        # Exhausted max attempts?
        if attempt >= self.retry_config.max_attempts:
            return False

        # Is this error type retryable?
        return error_type in self.retry_config.retryable_errors

    async def _execute_with_retry(self, func, *args, **kwargs) -> Any:
        """
        Execute function with automatic retry logic.

        This is the core retry mechanism that wraps provider calls.

        Args:
            func: Async function to execute
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result from function

        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        provider_name = self.__class__.__name__.replace("Provider", "")

        for attempt in range(1, self.retry_config.max_attempts + 1):
            self.retry_metrics.total_attempts += 1

            try:
                # Execute the actual provider method
                result = await func(*args, **kwargs)

                # Success!
                self.retry_metrics.successful_attempts += 1

                if attempt > 1:
                    logger.info(
                        f"{provider_name}: ✓ Succeeded on attempt {attempt}/"
                        f"{self.retry_config.max_attempts}"
                    )

                return result

            except Exception as e:
                last_exception = e
                error_type = self._classify_error(e)

                # Update metrics
                self.retry_metrics.failed_attempts += 1
                error_name = error_type.value
                self.retry_metrics.retries_by_error[error_name] = (
                    self.retry_metrics.retries_by_error.get(error_name, 0) + 1
                )

                # Should we retry?
                if not self._should_retry(error_type, attempt):
                    logger.error(
                        f"{provider_name}: ✗ Not retrying {error_type.value} "
                        f"on attempt {attempt}/{self.retry_config.max_attempts}: {e}"
                    )
                    raise

                # Calculate delay
                delay = self._calculate_delay(attempt, error_type)
                self.retry_metrics.total_retry_delay += delay

                logger.warning(
                    f"{provider_name}: ⚠️  Attempt {attempt}/"
                    f"{self.retry_config.max_attempts} failed ({error_type.value}). "
                    f"Retrying in {delay:.2f}s... Error: {e}"
                )

                # Wait before retry
                await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(f"{provider_name}: ✗ All {self.retry_config.max_attempts} attempts failed")
        raise last_exception

    def get_retry_metrics(self) -> dict[str, Any]:
        """Get retry metrics for monitoring."""
        return self.retry_metrics.get_summary()

    # ========================================================================
    # ABSTRACT METHODS (Providers implement these)
    # ========================================================================

    @abstractmethod
    async def _complete_impl(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Provider-specific implementation of complete().

        This is what individual providers override (OpenAI, Anthropic, etc).
        Retry logic is automatic - just implement the API call!

        Args:
            prompt: Input prompt
            model: Model name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            **kwargs: Provider-specific options

        Returns:
            ModelResponse with standardized format

        Raises:
            Exception: If model call fails (will be caught by retry logic)
        """
        pass

    @abstractmethod
    async def _stream_impl(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Provider-specific implementation of stream().

        This is what individual providers override.
        Retry logic is automatic - just implement the streaming!

        Args:
            prompt: Input prompt
            model: Model name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            **kwargs: Provider-specific options

        Yields:
            Content chunks as strings

        Raises:
            Exception: If streaming fails (will be caught by retry logic)
        """
        pass

    async def _complete_with_tools_impl(
        self,
        prompt: Optional[str] = None,
        model: str = "",
        tools: Optional[list[Any]] = None,
        tool_choice: str = "auto",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Provider-specific implementation of complete_with_tools().

        OPTIONAL: Only implement if provider supports tool calling.
        Default implementation raises NotImplementedError.

        Tool calls are included in response.tool_calls field.

        Args:
            prompt: Input prompt (for simple queries)
            model: Model name
            tools: List of tool definitions (optional, OpenAI format)
            tool_choice: Tool choice mode ("auto", "none", or specific tool)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            messages: Conversation history (for multi-turn conversations)
            **kwargs: Provider-specific options

        Returns:
            ModelResponse with tool_calls field populated if model uses tools.

            If tools were called:
                - response.content may be None or empty
                - response.tool_calls will be List[Dict] with tool call details

            If tools were NOT called:
                - response.content will contain the text response
                - response.tool_calls will be None or empty list

        Raises:
            NotImplementedError: If provider doesn't support tool calling
            Exception: If model call fails (will be caught by retry logic)

        Example Implementation:
            >>> async def _complete_with_tools_impl(self, prompt, model, tools=None, ...):
            ...     # Make API call with tools
            ...     api_response = await self.client.post(..., tools=tools)
            ...
            ...     # Parse tool calls from response
            ...     tool_calls = None
            ...     if "tool_calls" in api_response:
            ...         tool_calls = [
            ...             {
            ...                 "id": tc["id"],
            ...                 "name": tc["function"]["name"],
            ...                 "arguments": json.loads(tc["function"]["arguments"])
            ...             }
            ...             for tc in api_response["tool_calls"]
            ...         ]
            ...
            ...     # Return ModelResponse with tool_calls field
            ...     return ModelResponse(
            ...         content=api_response.get("content", ""),
            ...         model=model,
            ...         provider="your_provider",
            ...         cost=cost,
            ...         tokens_used=tokens,
            ...         confidence=confidence,
            ...         latency_ms=latency_ms,
            ...         tool_calls=tool_calls,  # ← Tool calls in response!
            ...         metadata=metadata
            ...     )
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support tool calling. "
            f"Override _complete_with_tools_impl() to add support."
        )

    def _get_litellm_prefix(self) -> Optional[str]:
        """
        Get the LiteLLM provider prefix for this provider.

        LiteLLM expects model names in specific formats:
        - openai: "gpt-4" (no prefix needed)
        - anthropic: "claude-3-opus" (no prefix needed)
        - groq: "groq/llama-3.1-8b-instant"
        - together: "together_ai/..."
        - huggingface: "huggingface/..."

        Returns:
            Provider prefix string or None if not needed
        """
        # Map provider class names to LiteLLM prefixes
        provider_prefixes = {
            "OpenAIProvider": None,  # Native format
            "AnthropicProvider": None,  # Native format
            "GroqProvider": "groq",
            "TogetherProvider": "together_ai",
            "HuggingFaceProvider": "huggingface",
            "OllamaProvider": "ollama",
            "VLLMProvider": "openai",  # vLLM uses OpenAI-compatible format
        }

        return provider_prefixes.get(self.__class__.__name__)

    @abstractmethod
    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for given token count (fallback method).

        This is the fallback pricing used when LiteLLM is not available.
        Each provider must implement this with rough cost estimates.

        Args:
            tokens: Number of tokens
            model: Model name

        Returns:
            Estimated cost in USD
        """
        pass

    def calculate_accurate_cost(
        self,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: Optional[int] = None,
    ) -> float:
        """
        Calculate cost using LiteLLM if available, otherwise fallback.

        This method automatically uses LiteLLM for accurate pricing when installed,
        or falls back to provider-specific estimates.

        Args:
            model: Model name
            prompt_tokens: Input tokens (preferred)
            completion_tokens: Output tokens (preferred)
            total_tokens: Total tokens (fallback if split not available)

        Returns:
            Cost in USD (accurate if LiteLLM installed, estimated otherwise)

        Example:
            >>> # Automatically uses LiteLLM if installed
            >>> cost = provider.calculate_accurate_cost(
            ...     model="gpt-4o-mini",
            ...     prompt_tokens=100,
            ...     completion_tokens=50
            ... )
        """
        if self._use_litellm_pricing and self._litellm_cost_provider:
            try:
                # Prepend provider prefix if needed for LiteLLM
                litellm_model = model
                if self._litellm_provider_prefix:
                    # Only add prefix if model doesn't already have it
                    if not model.startswith(f"{self._litellm_provider_prefix}/"):
                        litellm_model = f"{self._litellm_provider_prefix}/{model}"

                # Use LiteLLM for accurate pricing
                return self._litellm_cost_provider.calculate_cost(
                    model=litellm_model,
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                )
            except Exception as e:
                logger.warning(f"LiteLLM cost calculation failed: {e}. Using fallback pricing.")
                # Fall through to fallback

        # Fallback to provider-specific estimates
        tokens = total_tokens or (prompt_tokens + completion_tokens)
        return self.estimate_cost(tokens, model)

    # ========================================================================
    # PUBLIC API (Automatically includes retry logic)
    # ========================================================================

    async def complete(
        self,
        prompt: Optional[str] = None,
        model: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        tools: Optional[list[Any]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> ModelResponse:
        """
        Complete a prompt with the model (with automatic retry).

        If tools are provided, they will be used automatically.

        Users call this method - retry happens automatically!

        Args:
            prompt: Input prompt (for simple queries)
            model: Model name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            messages: Conversation history (for multi-turn conversations)
            tools: Tool definitions (optional, enables tool calling)
            tool_choice: Tool choice mode ("auto", "none", or specific tool)
            **kwargs: Provider-specific options
                     - logprobs (bool): Enable logprobs (defaults to True if supported)
                     - top_logprobs (int): Get top-k alternatives
                     - parallel_tool_calls (bool): Allow parallel tool execution

        Returns:
            ModelResponse with standardized format.
            If tools were used, response.tool_calls will be populated.

        Raises:
            Exception: If all retry attempts fail

        Example:
            >>> # Simple query (no tools)
            >>> response = await provider.complete(
            ...     prompt="What is Python?",
            ...     model="gpt-4"
            ... )
            >>>
            >>> # With tools
            >>> tools = [{
            ...     "type": "function",
            ...     "function": {
            ...         "name": "get_weather",
            ...         "description": "Get weather",
            ...         "parameters": {...}
            ...     }
            ... }]
            >>>
            >>> response = await provider.complete(
            ...     prompt="What's the weather in Paris?",
            ...     model="gpt-4",
            ...     tools=tools
            ... )
            >>>
            >>> if response.tool_calls:
            ...     for tool_call in response.tool_calls:
            ...         print(f"Tool: {tool_call['name']}")
            ...         print(f"Args: {tool_call['arguments']}")
        """
        # If tools provided and provider supports them, use tool calling path
        if tools and self.supports_tools():
            return await self._execute_with_retry(
                self._complete_with_tools_impl,
                prompt=prompt,
                model=model,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
                messages=messages,
                **kwargs,
            )

        # Otherwise use standard completion
        return await self._execute_with_retry(
            self._complete_impl,
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
            **kwargs,
        )

    async def stream(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream response from the model (with automatic retry for connection).

        Users call this method - retry happens automatically!

        This method enables real-time streaming for better UX. Yields chunks
        as they arrive from the API.

        IMPORTANT: Retry only works for INITIAL CONNECTION failures.
        Once streaming starts (first chunk yielded), mid-stream failures
        cannot be retried because chunks are already sent to the caller.

        NOTE: Streaming mode does NOT include confidence/logprobs in the stream.
        The cascade wrapper will call complete() separately after streaming to
        get the full result with confidence scores and metrics.

        Args:
            prompt: Input prompt
            model: Model name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            **kwargs: Provider-specific options

        Yields:
            Content chunks as strings

        Raises:
            Exception: If all retry attempts fail

        Example:
            >>> provider = OpenAIProvider()
            >>> async for chunk in provider.stream(
            ...     prompt="What is Python?",
            ...     model="gpt-4"
            ... ):
            ...     print(chunk, end='', flush=True)
            Python is a high-level programming language...
        """
        # because it tries to await the async generator, which doesn't work.
        # Instead, we retry the CONNECTION establishment manually.

        last_exception = None
        provider_name = self.__class__.__name__.replace("Provider", "")

        for attempt in range(1, self.retry_config.max_attempts + 1):
            self.retry_metrics.total_attempts += 1

            try:
                # Try to establish streaming connection
                stream_generator = self._stream_impl(
                    prompt=prompt,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system_prompt=system_prompt,
                    **kwargs,
                )

                # Yield all chunks from the stream
                # NOTE: Once we start yielding, we can't retry anymore!
                async for chunk in stream_generator:
                    yield chunk

                # SUCCESS: Stream completed without errors
                self.retry_metrics.successful_attempts += 1

                if attempt > 1:
                    logger.info(
                        f"{provider_name}: ✓ Stream completed on attempt "
                        f"{attempt}/{self.retry_config.max_attempts}"
                    )

                # Stream completed successfully
                return

            except Exception as e:
                last_exception = e
                error_type = self._classify_error(e)

                # Update metrics
                self.retry_metrics.failed_attempts += 1
                error_name = error_type.value
                self.retry_metrics.retries_by_error[error_name] = (
                    self.retry_metrics.retries_by_error.get(error_name, 0) + 1
                )

                # Should we retry?
                if not self._should_retry(error_type, attempt):
                    logger.error(
                        f"{provider_name}: ✗ Not retrying {error_type.value} "
                        f"on attempt {attempt}/{self.retry_config.max_attempts}: {e}"
                    )
                    raise

                # Calculate delay
                delay = self._calculate_delay(attempt, error_type)
                self.retry_metrics.total_retry_delay += delay

                logger.warning(
                    f"{provider_name}: ⚠️  Stream attempt {attempt}/"
                    f"{self.retry_config.max_attempts} failed ({error_type.value}). "
                    f"Retrying in {delay:.2f}s... Error: {e}"
                )

                # Wait before retry
                await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(
            f"{provider_name}: ✗ All {self.retry_config.max_attempts} stream attempts failed"
        )
        raise last_exception

    # ========================================================================
    # COST ESTIMATION UTILITIES (v2.5 - NEW)
    # ========================================================================

    @staticmethod
    def estimate_tokens_from_text(text: str) -> int:
        """
        Estimate token count from text.

        Uses rule of thumb: 1 token ≈ 0.75 words (or 1.3 tokens per word)

        This is the SAME estimation used by CostCalculator for consistency.

        Note: This is an approximation. For exact counts, use tiktoken
        (OpenAI) or the provider's tokenizer.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count

        Example:
            >>> BaseProvider.estimate_tokens_from_text("Hello world!")
            3  # ~2 words * 1.3 = ~3 tokens
        """
        if not text:
            return 0

        word_count = len(text.split())
        token_estimate = int(word_count * 1.3)

        return max(1, token_estimate)  # At least 1 token

    def estimate_cost_from_text(self, text: str, model: str) -> float:
        """
        Estimate cost from text content.

        Combines token estimation with provider-specific pricing.

        Args:
            text: Text to estimate cost for
            model: Model name for pricing

        Returns:
            Estimated cost in USD

        Example:
            >>> provider = OpenAIProvider()
            >>> cost = provider.estimate_cost_from_text(
            ...     "Hello world! How are you?",
            ...     model="gpt-4"
            ... )
            >>> print(f"${cost:.6f}")
            $0.000150
        """
        tokens = self.estimate_tokens_from_text(text)
        return self.estimate_cost(tokens, model)

    # ========================================================================
    # LOGPROBS SUPPORT METHODS
    # ========================================================================

    def should_request_logprobs(self, **kwargs) -> bool:
        """
        Determine if logprobs should be requested for this call.

        INTELLIGENT DEFAULT (Oct 6, 2025): Request logprobs for confidence
        estimation unless explicitly disabled or provider doesn't support them.

        This ensures accurate confidence scores without requiring developers
        to remember to pass logprobs=True on every call.

        Args:
            **kwargs: Call parameters (may contain 'logprobs' override)

        Returns:
            True if logprobs should be requested

        Example:
            # System automatically requests logprobs for OpenAI:
            result = await provider.complete(prompt="Hello", model="gpt-4")
            # result will have logprobs automatically

            # Can explicitly disable if needed:
            result = await provider.complete(
                prompt="Hello",
                model="gpt-4",
                logprobs=False  # Override to disable
            )
        """
        # If explicitly set by caller, respect it
        if "logprobs" in kwargs:
            return kwargs["logprobs"]

        # If provider doesn't support logprobs, don't request
        if not self.supports_logprobs():
            return False

        # Default: YES, request logprobs for better confidence estimation
        return True

    def supports_logprobs(self) -> bool:
        """Check if provider supports logprobs."""
        return self._supports_logprobs

    def supports_tools(self) -> bool:
        """
        Check if provider supports tool calling.

        Returns:
            True if provider supports tool calling, False otherwise
        """
        return self._supports_tools

    def supports_streaming(self) -> bool:
        """Check if provider supports streaming."""
        provider_name = self.__class__.__name__.replace("Provider", "").lower()
        caps = get_provider_capabilities(provider_name)
        return caps.get("supports_streaming", False)

    @staticmethod
    def estimate_logprobs_from_temperature(
        tokens: list[str], temperature: float, base_confidence: float = 0.7
    ) -> tuple[list[float], float]:
        """
        Estimate logprobs when not available from provider.

        Lower temperature = higher confidence:
        - temp 0.0 -> confidence 0.95
        - temp 0.5 -> confidence 0.80
        - temp 1.0 -> confidence 0.60
        - temp 1.5 -> confidence 0.40

        Args:
            tokens: List of tokens
            temperature: Sampling temperature
            base_confidence: Base confidence level (0-1)

        Returns:
            (logprobs_list, average_confidence)
        """
        confidence = max(0.3, min(0.95, base_confidence * (1.5 - temperature)))
        logprob = math.log(confidence)
        logprobs_list = [logprob] * len(tokens)

        return logprobs_list, confidence

    @staticmethod
    def simple_tokenize(text: str) -> list[str]:
        """
        Simple word-based tokenization for fallback.

        Note: This is NOT accurate tokenization. For production,
        use tiktoken (OpenAI) or proper tokenizer.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        import re

        tokens = re.findall(r"\w+|[^\w\s]", text)
        return tokens

    def add_logprobs_fallback(
        self, response: ModelResponse, temperature: float = 0.7, base_confidence: float = 0.7
    ) -> ModelResponse:
        """
        Add estimated logprobs to response if not present.

        Call this in your provider's _complete_impl() method if logprobs
        weren't returned by the API. This uses temperature-based estimation
        as a fallback when native logprobs are unavailable.

        Args:
            response: ModelResponse to enhance
            temperature: Temperature used for generation
            base_confidence: Base confidence level

        Returns:
            Enhanced ModelResponse with estimated logprobs

        Note:
            Estimated logprobs are less accurate than native API logprobs
            but still provide useful confidence signals for routing decisions.
        """
        # Log that we're using estimation (DEBUG level - normal operation)
        logger.debug(
            f"Using estimated logprobs for {response.provider} provider "
            f"(native logprobs not available). Temperature: {temperature:.2f}, "
            f"Base confidence: {base_confidence:.2f}"
        )

        # Add tokens if missing
        if response.tokens is None:
            response.tokens = self.simple_tokenize(response.content)
            logger.debug(f"Tokenized response into {len(response.tokens)} tokens")

        # Add logprobs if missing
        if response.logprobs is None:
            response.logprobs, estimated_conf = self.estimate_logprobs_from_temperature(
                response.tokens, temperature, base_confidence
            )

            # Update confidence if it was default/low
            if response.confidence < 0.5:
                response.confidence = estimated_conf
                logger.debug(
                    f"Updated confidence from <0.5 to {estimated_conf:.3f} "
                    f"based on temperature estimation"
                )

        # Generate top_logprobs with alternatives for each token
        if response.top_logprobs is None:
            response.top_logprobs = []

            for i, token in enumerate(response.tokens):
                alternatives = {}

                # Add the actual token as top choice
                alternatives[token] = response.logprobs[i]

                # Generate 4 alternative tokens (total 5 including actual)
                for j in range(4):
                    if len(token) > 2:
                        alt_variations = [
                            token.lower() if token[0].isupper() else token.capitalize(),
                            token + "s" if not token.endswith("s") else token[:-1],
                            token + ".",
                            " " + token,
                        ]
                        alt_token = alt_variations[j % len(alt_variations)]
                    else:
                        alt_token = f"<alt{j}>"

                    alt_logprob = response.logprobs[i] - (j + 1) * 0.5 - random.uniform(0, 0.3)
                    alternatives[alt_token] = alt_logprob

                response.top_logprobs.append(alternatives)

        if "has_logprobs" not in response.metadata:
            response.metadata["has_logprobs"] = True
        if "estimated" not in response.metadata:
            response.metadata["estimated"] = True

        # Add detailed info for programmatic access and debugging
        avg_logprob = sum(response.logprobs) / len(response.logprobs) if response.logprobs else 0
        response.metadata["logprobs_info"] = {
            "type": "estimated",
            "method": "temperature_based",
            "reason": "Provider does not support native logprobs",
            "base_confidence": base_confidence,
            "temperature": temperature,
            "num_tokens": len(response.tokens),
            "avg_logprob": round(avg_logprob, 3),
        }

        logger.debug(
            f"Added estimated logprobs: {len(response.logprobs)} tokens, "
            f"avg logprob: {avg_logprob:.3f}"
        )

        return response

    # ========================================================================
    # CONFIDENCE ESTIMATION
    # ========================================================================

    def calculate_confidence(
        self, response: str, metadata: Optional[dict[str, Any]] = None
    ) -> float:
        """
        Calculate confidence score using production estimator.

        Now uses:
        - Logprobs (when available) - Most accurate
        - Semantic quality analysis - Always available
        - Provider-specific calibration - Empirical adjustments

        Args:
            response: Model response text
            metadata: Response metadata with optional fields:
                - logprobs: List[float] - Token log probabilities
                - tokens: List[str] - Token list
                - temperature: float - Sampling temperature
                - finish_reason: str - Completion reason
                - query: str - Original query

        Returns:
            Confidence score (0-1)
        """
        if not metadata:
            metadata = {}

        # Use production estimator if available
        if self._confidence_estimator:
            analysis = self._confidence_estimator.estimate(
                response=response,
                query=metadata.get("query"),
                logprobs=metadata.get("logprobs"),
                tokens=metadata.get("tokens"),
                temperature=metadata.get("temperature", 0.7),
                finish_reason=metadata.get("finish_reason"),
                metadata=metadata,
            )
            return analysis.final_confidence

        # Fallback to legacy method if estimator not available
        return self._calculate_confidence_legacy(response, metadata)

    def _calculate_confidence_legacy(
        self, response: str, metadata: Optional[dict[str, Any]] = None
    ) -> float:
        """
        Legacy confidence calculation (fallback).

        Only used if production estimator unavailable.
        """
        if not response or len(response.strip()) < 2:
            return 0.1

        response_lower = response.lower().strip()

        # Check for uncertainty markers
        uncertainty_phrases = [
            "i don't know",
            "i'm not sure",
            "i cannot",
            "unclear",
            "uncertain",
            "not confident",
            "i apologize",
            "i don't have",
            "not able to",
        ]

        if any(phrase in response_lower for phrase in uncertainty_phrases):
            return 0.3

        # Length-based scoring
        length = len(response.strip())
        if length < 20:
            return 0.7
        elif length < 100:
            return 0.8
        elif length < 300:
            return 0.85
        else:
            return 0.9


# ==========================================
# Provider Capability Matrix
# ==========================================

PROVIDER_CAPABILITIES = {
    "openai": {
        "supports_logprobs": True,
        "supports_streaming": True,
        "supports_tools": True,
        "max_top_logprobs": 20,
        "has_cost_tracking": True,
    },
    "groq": {
        "supports_logprobs": False,
        "supports_streaming": True,
        "supports_tools": True,
        "max_top_logprobs": 0,
        "has_cost_tracking": True,
    },
    "anthropic": {
        "supports_logprobs": False,
        "supports_streaming": True,
        "supports_tools": True,
        "max_top_logprobs": 0,
        "has_cost_tracking": True,
    },
    "ollama": {
        "supports_logprobs": False,
        "supports_streaming": True,
        "supports_tools": True,
        "max_top_logprobs": 0,
        "has_cost_tracking": False,
    },
    "vllm": {
        "supports_logprobs": True,
        "supports_streaming": True,
        "supports_tools": True,
        "max_top_logprobs": 20,
        "has_cost_tracking": False,
    },
    "huggingface": {
        "supports_logprobs": False,
        "supports_streaming": True,
        "supports_tools": False,
        "max_top_logprobs": 0,
        "has_cost_tracking": True,
    },
    "together": {
        "supports_logprobs": True,
        "supports_streaming": True,
        "supports_tools": True,
        "max_top_logprobs": 20,
        "has_cost_tracking": True,
    },
}


def get_provider_capabilities(provider_name: str) -> dict[str, Any]:
    """
    Get capabilities for a provider.

    Args:
        provider_name: Name of provider

    Returns:
        Dict of capabilities
    """
    return PROVIDER_CAPABILITIES.get(
        provider_name.lower(),
        {
            "supports_logprobs": False,
            "supports_streaming": False,
            "supports_tools": False,
            "max_top_logprobs": 0,
            "has_cost_tracking": False,
        },
    )
