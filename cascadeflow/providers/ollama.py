"""Ollama provider implementation for local LLM serving."""

import os
import time
from typing import Optional, Dict, Any

import httpx

from .base import BaseProvider, ModelResponse
from ..exceptions import ProviderError, ModelError


class OllamaProvider(BaseProvider):
    """
    Ollama provider for local LLM serving.

    Supports: Llama 3, Mistral, CodeLlama, Phi-3, Gemma, and 100+ other models.

    Benefits:
    - 100% FREE (no API costs)
    - Unlimited requests (no rate limits)
    - Privacy (runs locally)
    - Fast (no network latency)
    - Works with speculative cascading (automatic logprobs estimation)

    Requirements:
    - Ollama installed: https://ollama.com/download
    - Model pulled: `ollama pull llama3:8b`

    Example:
        >>> provider = OllamaProvider()
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="llama3:8b"
        ... )
        >>> print(response.content)
        >>> print(f"Cost: ${response.cost}")  # Always $0.00!

        >>> # With logprobs (automatically estimated)
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="llama3:8b",
        ...     logprobs=True  # Works via automatic fallback!
        ... )
        >>> print(response.logprobs)  # Estimated from temperature
    """

    def __init__(
            self,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None
    ):
        """
        Initialize Ollama provider.

        Args:
            api_key: Not needed for Ollama (kept for interface compatibility)
            base_url: Ollama server URL. Defaults to http://localhost:11434
        """
        super().__init__(api_key)
        self.base_url = base_url or os.getenv("OLLAMA_HOST", "http://localhost:11434")

        # Initialize HTTP client (no auth needed for Ollama)
        self.client = httpx.AsyncClient(
            timeout=120.0  # Longer timeout for local inference
        )

    def _check_logprobs_support(self) -> bool:
        """Ollama does NOT support logprobs - uses automatic fallback."""
        return False

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
        Complete a prompt using Ollama.

        Args:
            prompt: User prompt
            model: Model name (e.g., 'llama3:8b', 'mistral:7b', 'codellama:7b')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            **kwargs: Additional Ollama parameters
                     NEW: logprobs (bool) - Enable estimated logprobs (automatic fallback)

        Returns:
            ModelResponse with standardized format (with estimated logprobs if requested)

        Raises:
            ProviderError: If Ollama server not reachable
            ModelError: If model not found or execution fails
        """
        start_time = time.time()

        # Extract logprobs parameter (for automatic fallback)
        logprobs_enabled = kwargs.pop('logprobs', False)
        kwargs.pop('top_logprobs', None)  # Not used, but remove if present

        # Build request payload (Ollama format)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,  # We'll add streaming later
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,  # Ollama's name for max_tokens
            }
        }

        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt

        # Add any additional options
        if kwargs:
            payload["options"].update(kwargs)

        try:
            # Make API request to Ollama
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()

            data = response.json()

            # Extract response
            content = data.get("response", "")

            # Ollama doesn't return token counts, estimate them
            prompt_tokens = len(prompt) // 4
            completion_tokens = len(content) // 4
            tokens_used = prompt_tokens + completion_tokens

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate cost (always $0 for Ollama!)
            cost = 0.0

            # Calculate confidence
            confidence = self.calculate_confidence(content, data)

            # Build base response
            model_response = ModelResponse(
                content=content,
                model=model,
                provider="ollama",
                cost=cost,  # FREE!
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata={
                    "done": data.get("done"),
                    "total_duration": data.get("total_duration"),
                    "load_duration": data.get("load_duration"),
                    "prompt_eval_count": data.get("prompt_eval_count"),
                    "eval_count": data.get("eval_count"),
                }
            )

            # Add estimated logprobs if requested
            # Ollama doesn't support real logprobs, so we ALWAYS use fallback
            if logprobs_enabled:
                model_response = self.add_logprobs_fallback(
                    model_response,
                    temperature,
                    base_confidence=0.75  # Local models slightly lower than API models
                )

            return model_response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelError(
                    f"Model '{model}' not found. Did you run 'ollama pull {model}'?",
                    model=model,
                    provider="ollama"
                )
            else:
                raise ProviderError(
                    f"Ollama API error: {e.response.status_code}",
                    provider="ollama",
                    original_error=e
                )
        except httpx.ConnectError as e:
            raise ProviderError(
                "Cannot connect to Ollama. Is it running? Try: 'ollama serve'",
                provider="ollama",
                original_error=e
            )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to Ollama server",
                provider="ollama",
                original_error=e
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse Ollama response: {e}",
                model=model,
                provider="ollama"
            )

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for Ollama model.

        Ollama is always FREE!

        Args:
            tokens: Total tokens (not used)
            model: Model name (not used)

        Returns:
            Always 0.0 (FREE!)
        """
        return 0.0  # Ollama is free!

    def calculate_confidence(
            self,
            response: str,
            metadata: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate confidence score for Ollama response.

        Uses response length and completion status as heuristics.

        Args:
            response: Model response text
            metadata: Response metadata from Ollama

        Returns:
            Confidence score (0-1)
        """
        # Start with base confidence
        confidence = super().calculate_confidence(response)

        if metadata:
            # Check if generation completed successfully
            if metadata.get("done") == True:
                confidence = min(1.0, confidence + 0.05)

            # Ollama doesn't provide confidence scores,
            # so we rely on response quality heuristics

        return confidence

    async def list_models(self) -> list[str]:
        """
        List available models in Ollama.

        Returns:
            List of model names
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            raise ProviderError(
                f"Failed to list Ollama models: {e}",
                provider="ollama"
            )

    async def pull_model(self, model: str) -> None:
        """
        Pull a model from Ollama library.

        Args:
            model: Model name to pull (e.g., 'llama3:8b')
        """
        try:
            response = await self.client.post(
                f"{self.base_url}/api/pull",
                json={"name": model}
            )
            response.raise_for_status()
        except Exception as e:
            raise ProviderError(
                f"Failed to pull model '{model}': {e}",
                provider="ollama"
            )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()