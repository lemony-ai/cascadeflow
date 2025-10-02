"""Base provider interface for all model providers."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ModelResponse:
    """
    Standardized response from a model provider.

    All providers must return this format.
    """
    content: str
    model: str
    provider: str
    cost: float
    tokens_used: int
    confidence: float  # 0-1 quality score
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseProvider(ABC):
    """
    Base class for all model providers.

    All providers (OpenAI, Anthropic, Ollama, etc.) must implement this interface.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize provider.

        Args:
            api_key: API key for the provider (if needed)
        """
        # Load API key from parameter or environment
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = self._load_api_key()

    def _load_api_key(self) -> Optional[str]:
        """
        Load API key from environment.

        Override this in subclasses to load from specific env vars.

        Returns:
            API key or None
        """
        return None

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
            prompt: Input prompt
            model: Model name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            **kwargs: Provider-specific options

        Returns:
            ModelResponse with standardized format

        Raises:
            ModelError: If model call fails
        """
        pass

    @abstractmethod
    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for given token count.

        Args:
            tokens: Number of tokens
            model: Model name

        Returns:
            Estimated cost in USD
        """
        pass

    def calculate_confidence(self, response: str, metadata: Optional[Dict[str, Any]] = None) -> float:
        """
        Calculate confidence score for a response.

        Improved heuristic that handles short correct answers better.
        Override in subclasses for provider-specific scoring.

        Args:
            response: Model response text
            metadata: Additional context

        Returns:
            Confidence score (0-1)
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

        # Improved length-based scoring
        # Short answers can still be correct (e.g., "4" for "What is 2+2?")
        length = len(response.strip())

        if length < 20:
            # Very short - could be correct simple answer
            return 0.7  # Increased from 0.4
        elif length < 100:
            # Short but complete
            return 0.8  # Increased from 0.6
        elif length < 300:
            # Medium length - good detail
            return 0.85  # Increased from 0.8
        else:
            # Long, detailed response
            return 0.9