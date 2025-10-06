"""vLLM provider for high-performance local inference."""

import os
import time
import math
from typing import Optional, Dict, Any

import httpx

from .base import BaseProvider, ModelResponse
from ..exceptions import ProviderError, ModelError


class VLLMProvider(BaseProvider):
    """
    vLLM provider for high-performance inference.

    vLLM is an OpenAI-compatible server with:
    - PagedAttention for efficient memory usage
    - Continuous batching for high throughput
    - 24x faster than standard serving
    - Full logprobs support

    Requires vLLM server running locally or remotely.

    Example:
        >>> provider = VLLMProvider(base_url="http://localhost:8000/v1")
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="meta-llama/Llama-3-8B-Instruct"
        ... )

        >>> # With logprobs
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="meta-llama/Llama-3-8B-Instruct",
        ...     logprobs=True,
        ...     top_logprobs=10
        ... )
    """

    def __init__(
            self,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None
    ):
        """
        Initialize vLLM provider.

        Args:
            api_key: Optional API key (usually not needed for local vLLM)
            base_url: vLLM server URL (default: http://localhost:8000/v1)
        """
        super().__init__(api_key)

        # Default to local vLLM server
        self.base_url = base_url or os.getenv(
            "VLLM_BASE_URL",
            "http://localhost:8000/v1"
        )

        # vLLM is OpenAI-compatible, so we use similar headers
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            headers=headers,
            timeout=120.0  # vLLM can be slower for large models
        )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment (optional for vLLM)."""
        return os.getenv("VLLM_API_KEY")

    def _check_logprobs_support(self) -> bool:
        """vLLM supports logprobs (OpenAI-compatible)."""
        return True

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
        Complete a prompt using vLLM server.

        vLLM uses OpenAI-compatible API format.

        Args:
            prompt: User prompt
            model: Model name (must match what's loaded in vLLM)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            **kwargs: Additional parameters
                     NEW: logprobs (bool) - Enable logprobs
                          top_logprobs (int) - Get top-k alternatives (1-20)

        Returns:
            ModelResponse with standardized format (enhanced with logprobs)

        Raises:
            ProviderError: If API call fails
            ModelError: If model execution fails
        """
        start_time = time.time()

        # Extract logprobs parameters
        logprobs_enabled = kwargs.pop('logprobs', False)
        top_logprobs = kwargs.pop('top_logprobs', None)

        # Build messages (OpenAI format)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request payload
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs
        }

        # Add logprobs if requested (OpenAI-compatible)
        if logprobs_enabled:
            payload["logprobs"] = True
            if top_logprobs:
                payload["top_logprobs"] = min(top_logprobs, 20)

        try:
            # Make API request
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload
            )
            response.raise_for_status()

            data = response.json()

            # Extract response (OpenAI format)
            choice = data["choices"][0]
            content = choice["message"]["content"]
            tokens_used = data["usage"]["total_tokens"]

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # vLLM is self-hosted, so cost is 0
            cost = 0.0

            # Calculate confidence
            confidence = self.calculate_confidence(content, data)

            # Build base response
            model_response = ModelResponse(
                content=content,
                model=model,
                provider="vllm",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata={
                    "finish_reason": choice["finish_reason"],
                    "prompt_tokens": data["usage"]["prompt_tokens"],
                    "completion_tokens": data["usage"]["completion_tokens"],
                    "base_url": self.base_url,
                }
            )

            # Parse logprobs if available (OpenAI-compatible format)
            if logprobs_enabled and "logprobs" in choice and choice["logprobs"]:
                logprobs_data = choice["logprobs"]

                if "content" in logprobs_data and logprobs_data["content"]:
                    tokens = []
                    logprobs_list = []
                    top_logprobs_list = []

                    for token_data in logprobs_data["content"]:
                        # Extract token
                        tokens.append(token_data["token"])

                        # Extract logprob
                        logprobs_list.append(token_data["logprob"])

                        # Extract top alternatives
                        if "top_logprobs" in token_data and token_data["top_logprobs"]:
                            top_k = {}
                            for alt in token_data["top_logprobs"]:
                                top_k[alt["token"]] = alt["logprob"]
                            top_logprobs_list.append(top_k)
                        else:
                            top_logprobs_list.append({})

                    # Add to response
                    model_response.tokens = tokens
                    model_response.logprobs = logprobs_list
                    model_response.top_logprobs = top_logprobs_list

                    # Update confidence based on actual probabilities
                    if logprobs_list:
                        avg_prob = sum(math.exp(lp) for lp in logprobs_list) / len(logprobs_list)
                        # Blend with heuristic confidence
                        model_response.confidence = (confidence + avg_prob) / 2

                    # Add metadata
                    model_response.metadata["has_logprobs"] = True
                    model_response.metadata["estimated"] = False
            else:
                # No logprobs available - add estimated values
                if logprobs_enabled:
                    model_response = self.add_logprobs_fallback(
                        model_response,
                        temperature,
                        base_confidence=0.80  # vLLM local models are good
                    )

            return model_response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelError(
                    f"Model '{model}' not found in vLLM server. "
                    f"Available models can be checked at {self.base_url}/models",
                    model=model,
                    provider="vllm"
                )
            elif e.response.status_code == 503:
                raise ProviderError(
                    "vLLM server is overloaded or unavailable",
                    provider="vllm",
                    original_error=e
                )
            else:
                raise ProviderError(
                    f"vLLM API error: {e.response.status_code}",
                    provider="vllm",
                    original_error=e
                )
        except httpx.RequestError as e:
            raise ProviderError(
                f"Failed to connect to vLLM server at {self.base_url}",
                provider="vllm",
                original_error=e
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse vLLM response: {e}",
                model=model,
                provider="vllm"
            )

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for vLLM model.

        vLLM is self-hosted, so cost is always 0.

        Args:
            tokens: Total tokens
            model: Model name

        Returns:
            Cost (always 0.0 for self-hosted)
        """
        return 0.0

    async def list_models(self) -> list:
        """
        List available models on vLLM server.

        Returns:
            List of model names
        """
        try:
            response = await self.client.get(f"{self.base_url}/models")
            response.raise_for_status()
            data = response.json()
            return [model["id"] for model in data.get("data", [])]
        except Exception as e:
            raise ProviderError(
                f"Failed to list models from vLLM server: {e}",
                provider="vllm"
            )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()