"""Base provider interface for all model providers."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging
import math

logger = logging.getLogger(__name__)


@dataclass
class ModelResponse:
    """
    Standardized response from a model provider.

    All providers must return this format.

    Enhanced with logprobs support while maintaining backward compatibility.
    """
    # Original fields (keep exactly as-is)
    content: str
    model: str
    provider: str
    cost: float
    tokens_used: int
    confidence: float  # 0-1 quality score
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = None

    # NEW: Logprobs support for speculative cascading
    tokens: Optional[List[str]] = None
    logprobs: Optional[List[float]] = None
    top_logprobs: Optional[List[Dict[str, float]]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for backward compatibility."""
        result = {
            'content': self.content,
            'model': self.model,
            'provider': self.provider,
            'cost': self.cost,
            'tokens_used': self.tokens_used,
            'confidence': self.confidence,
            'latency_ms': self.latency_ms,
            'metadata': self.metadata,
        }

        # Add logprobs if available
        if self.tokens is not None:
            result['tokens'] = self.tokens
        if self.logprobs is not None:
            result['logprobs'] = self.logprobs
        if self.top_logprobs is not None:
            result['top_logprobs'] = self.top_logprobs

        return result


class BaseProvider(ABC):
    """
    Base class for all model providers.

    All providers (OpenAI, Anthropic, Ollama, etc.) must implement this interface.

    Enhanced with automatic logprobs fallback for providers that don't support it.
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

        # Check logprobs support
        self._supports_logprobs = self._check_logprobs_support()

        if not self._supports_logprobs:
            logger.info(
                f"Provider {self.__class__.__name__} does not support logprobs. "
                f"Using automatic fallback with estimated confidence."
            )

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
                     NEW: logprobs (bool) - Enable logprobs
                          top_logprobs (int) - Get top-k alternatives

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

    # ==========================================
    # NEW: Logprobs Support Methods
    # ==========================================

    def supports_logprobs(self) -> bool:
        """Check if provider supports logprobs."""
        return self._supports_logprobs

    @staticmethod
    def estimate_logprobs_from_temperature(
            tokens: List[str],
            temperature: float,
            base_confidence: float = 0.7
    ) -> tuple[List[float], float]:
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
    def simple_tokenize(text: str) -> List[str]:
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
        tokens = re.findall(r'\w+|[^\w\s]', text)
        return tokens

    def add_logprobs_fallback(
            self,
            response: ModelResponse,
            temperature: float = 0.7,
            base_confidence: float = 0.7
    ) -> ModelResponse:
        """
        Add estimated logprobs to response if not present.

        Call this in your provider's complete() method if logprobs
        weren't returned by the API.

        Args:
            response: ModelResponse to enhance
            temperature: Temperature used for generation
            base_confidence: Base confidence level

        Returns:
            Enhanced ModelResponse with estimated logprobs
        """
        import random

        # Add tokens if missing
        if response.tokens is None:
            response.tokens = self.simple_tokenize(response.content)

        # Add logprobs if missing
        if response.logprobs is None:
            response.logprobs, estimated_conf = self.estimate_logprobs_from_temperature(
                response.tokens,
                temperature,
                base_confidence
            )

            # Update confidence if it was default/low
            if response.confidence < 0.5:
                response.confidence = estimated_conf

        # Generate top_logprobs with alternatives for each token
        if response.top_logprobs is None:
            response.top_logprobs = []

            for i, token in enumerate(response.tokens):
                alternatives = {}

                # Add the actual token as top choice
                alternatives[token] = response.logprobs[i]

                # Generate 4 alternative tokens (total 5 including actual)
                # These are lower probability alternatives
                for j in range(4):
                    # Create variations of the token
                    if len(token) > 2:
                        # Variation: different case, punctuation, etc.
                        alt_variations = [
                            token.lower() if token[0].isupper() else token.capitalize(),
                            token + "s" if not token.endswith("s") else token[:-1],
                            token + ".",
                            " " + token,
                            ]
                        alt_token = alt_variations[j % len(alt_variations)]
                    else:
                        # Short token: use generic alternatives
                        alt_token = f"<alt{j}>"

                    # Alternative has lower probability
                    alt_logprob = response.logprobs[i] - (j + 1) * 0.5 - random.uniform(0, 0.3)
                    alternatives[alt_token] = alt_logprob

                response.top_logprobs.append(alternatives)

        # Add metadata flags
        if 'has_logprobs' not in response.metadata:
            response.metadata['has_logprobs'] = False
        if 'estimated' not in response.metadata:
            response.metadata['estimated'] = True

        return response


# ==========================================
# Provider Capability Matrix
# ==========================================

PROVIDER_CAPABILITIES = {
    'openai': {
        'supports_logprobs': True,
        'supports_streaming': True,
        'max_top_logprobs': 20,
        'has_cost_tracking': True,
    },
    'groq': {
        'supports_logprobs': False,  # Groq doesn't actually support logprobs
        'supports_streaming': True,
        'max_top_logprobs': 0,
        'has_cost_tracking': True,
    },
    'anthropic': {
        'supports_logprobs': False,  # As of Oct 2025
        'supports_streaming': True,
        'max_top_logprobs': 0,
        'has_cost_tracking': True,
    },
    'ollama': {
        'supports_logprobs': False,
        'supports_streaming': True,
        'max_top_logprobs': 0,
        'has_cost_tracking': False,  # Free/local
    },
    'vllm': {
        'supports_logprobs': True,
        'supports_streaming': True,
        'max_top_logprobs': 20,
        'has_cost_tracking': False,  # Self-hosted
    },
    'huggingface': {
        'supports_logprobs': False,  # Depends on model
        'supports_streaming': True,
        'max_top_logprobs': 0,
        'has_cost_tracking': True,
    },
    'together': {
        'supports_logprobs': True,
        'supports_streaming': True,
        'max_top_logprobs': 20,
        'has_cost_tracking': True,
    },
}


def get_provider_capabilities(provider_name: str) -> Dict[str, Any]:
    """
    Get capabilities for a provider.

    Args:
        provider_name: Name of provider

    Returns:
        Dict of capabilities
    """
    return PROVIDER_CAPABILITIES.get(provider_name.lower(), {
        'supports_logprobs': False,
        'supports_streaming': False,
        'max_top_logprobs': 0,
        'has_cost_tracking': False,
    })