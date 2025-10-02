"""Base provider interface for all model providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, AsyncIterator
from datetime import datetime


@dataclass
class ModelResponse:
    """
    Standardized response from a model provider.

    All providers must return this format to ensure consistency.

    Attributes:
        content: Generated text content
        model: Model name that generated the response
        provider: Provider name (e.g., 'openai', 'anthropic')
        cost: Cost of this request in USD
        tokens_used: Total tokens used (prompt + completion)
        confidence: Quality/confidence score (0-1)
        latency_ms: Response latency in milliseconds
        metadata: Provider-specific metadata

    Example:
        >>> response = ModelResponse(
        ...     content="Hello, world!",
        ...     model="gpt-3.5-turbo",
        ...     provider="openai",
        ...     cost=0.002,
        ...     tokens_used=100,
        ...     confidence=0.95
        ... )
        >>> print(response.content)
        'Hello, world!'
    """

    content: str
    model: str
    provider: str
    cost: float
    tokens_used: int
    confidence: float
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}

        # Add timestamp
        if "timestamp" not in self.metadata:
            self.metadata["timestamp"] = datetime.now().isoformat()


class BaseProvider(ABC):
    """
    Base class for all model providers.

    All providers (OpenAI, Anthropic, Ollama, etc.) must implement this interface
    to ensure consistency and allow swapping providers seamlessly.

    Example:
        >>> class MyProvider(BaseProvider):
        ...     async def complete(self, prompt, model, **kwargs):
        ...         # Implementation here
        ...         return ModelResponse(...)
        ...
        ...     def estimate_cost(self, tokens, model):
        ...         return tokens / 1000 * 0.002
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize provider.

        Args:
            api_key: API key for the provider (if needed)
        """
        self.api_key = api_key

    @abstractmethod
    async def complete(
            self,
            prompt: str,
            model: str,
            max_tokens: int = 4096,
            temperature: float = 0.7,
            system_prompt: Optional[str] = None,
            **kwargs
    ) -> ModelResponse:
        """
        Complete a prompt with the model.

        Args:
            prompt: Input prompt text
            model: Model name to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            **kwargs: Provider-specific options

        Returns:
            ModelResponse with standardized format

        Raises:
            ModelError: If model call fails
            ProviderError: If provider is unavailable

        Example:
            >>> provider = OpenAIProvider(api_key="sk-...")
            >>> response = await provider.complete(
            ...     prompt="What is AI?",
            ...     model="gpt-3.5-turbo"
            ... )
            >>> print(response.content)
        """
        pass

    @abstractmethod
    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for given token count.

        Args:
            tokens: Number of tokens (prompt + completion)
            model: Model name

        Returns:
            Estimated cost in USD

        Example:
            >>> provider = OpenAIProvider()
            >>> cost = provider.estimate_cost(1000, "gpt-3.5-turbo")
            >>> print(f"${cost:.4f}")
            '$0.0020'
        """
        pass

    def calculate_confidence(
            self,
            response: str,
            metadata: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate confidence score for a response.

        This is a simple heuristic by default. Subclasses should override
        with better scoring methods (e.g., using logprobs, embeddings).

        Args:
            response: Model response text
            metadata: Additional context (e.g., logprobs)

        Returns:
            Confidence score (0-1)

        Example:
            >>> provider = BaseProvider()
            >>> confidence = provider.calculate_confidence("Hello world")
            >>> 0.0 <= confidence <= 1.0
            True
        """
        metadata = metadata or {}

        # Empty or very short responses are low confidence
        if not response or len(response.strip()) < 10:
            return 0.1

        # Check for uncertainty markers
        uncertainty_phrases = [
            "i don't know",
            "i'm not sure",
            "i cannot",
            "unclear",
            "uncertain",
            "not confident",
            "i apologize",
            "i'm unable to",
        ]

        response_lower = response.lower()
        if any(phrase in response_lower for phrase in uncertainty_phrases):
            return 0.3

        # Length-based scoring (simple heuristic)
        length = len(response)
        if length < 50:
            return 0.4
        elif length < 200:
            return 0.6
        elif length < 500:
            return 0.8
        else:
            return 0.9

    async def stream_complete(
            self,
            prompt: str,
            model: str,
            max_tokens: int = 4096,
            temperature: float = 0.7,
            **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream completion tokens (optional, not all providers support).

        Args:
            prompt: Input prompt
            model: Model name
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
            **kwargs: Provider-specific options

        Yields:
            Tokens as they're generated

        Example:
            >>> async for token in provider.stream_complete("Write a story"):
            ...     print(token, end="")
        """
        # Default: not implemented, just return complete response
        response = await self.complete(prompt, model, max_tokens, temperature, **kwargs)
        yield response.content

    def __repr__(self) -> str:
        """String representation of provider."""
        return f"{self.__class__.__name__}()"