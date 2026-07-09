"""
Eden AI provider implementation for cascadeflow.

Eden AI (https://www.edenai.co) is an OpenAI-compatible aggregator that provides
unified access to 100+ models from multiple providers (OpenAI, Anthropic, Google,
Mistral, DeepSeek, X.AI, Cohere, and more) through a single EU-hosted endpoint and
a single API key.

Key Features:
    - 100+ models from multiple providers via one API key
    - OpenAI-compatible API (``/v3/chat/completions``)
    - EU-hosted infrastructure (data residency); no training on customer data
    - Streaming support
    - Tool calling support
    - Per-request cost returned directly by the API (used for accurate accounting)

Model naming:
    Eden AI uses the ``provider/model`` format, e.g. ``anthropic/claude-sonnet-4-5``,
    ``openai/gpt-5.1``, ``mistral/codestral-latest``.

Example:
    >>> from cascadeflow.providers import EdenAIProvider
    >>>
    >>> provider = EdenAIProvider()  # Uses EDENAI_API_KEY env var
    >>>
    >>> # Basic completion
    >>> response = await provider.complete(
    ...     prompt="What is cascadeflow?",
    ...     model="anthropic/claude-sonnet-4-5",
    ... )
    >>> print(response.content)
    >>>
    >>> # Streaming
    >>> async for chunk in provider.stream(
    ...     prompt="Explain quantum computing",
    ...     model="openai/gpt-5.1",
    ... ):
    ...     print(chunk, end="", flush=True)

See Also:
    - https://docs.edenai.co
    - https://www.edenai.co/product/models
"""

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from ..schema.exceptions import ProviderError
from .base import BaseProvider, HttpConfig, ModelResponse, RetryConfig

# Eden AI pricing per 1M tokens (sample of popular models, USD).
# Eden AI returns the actual per-request cost in each response ("cost" field),
# which this provider uses when available; this table is only a fallback for
# ``estimate_cost()`` and offline cost estimation.
EDENAI_PRICING: dict[str, dict[str, float]] = {
    # Anthropic
    "anthropic/claude-opus-4-5": {"input": 5.0, "output": 25.0},
    "anthropic/claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "anthropic/claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    # OpenAI
    "openai/gpt-5.1": {"input": 1.25, "output": 10.0},
    "openai/gpt-5.1-codex": {"input": 1.25, "output": 10.0},
    # Google
    "google/gemini-3.1-pro-preview": {"input": 1.25, "output": 10.0},
    # Mistral
    "mistral/devstral-medium-latest": {"input": 0.4, "output": 2.0},
    "mistral/codestral-latest": {"input": 0.3, "output": 0.9},
    # DeepSeek
    "deepseek/deepseek-v4-pro": {"input": 0.28, "output": 0.42},
    # X.AI
    "xai/grok-4": {"input": 3.0, "output": 15.0},
}

# Default fallback pricing when a model is unknown (per 1M tokens, USD).
_DEFAULT_PRICING = {"input": 1.0, "output": 3.0}


class EdenAIProvider(BaseProvider):
    """
    Eden AI provider with OpenAI-compatible API.

    Supports:
    - 100+ models from multiple providers via a single API key
    - Streaming
    - Tool calling
    - Accurate per-request cost (read from the API response when present)

    Example:
        >>> provider = EdenAIProvider()
        >>> response = await provider.complete(
        ...     prompt="Hello!",
        ...     model="anthropic/claude-sonnet-4-5",
        ... )
        >>> print(response.content)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        http_config: Optional[HttpConfig] = None,
    ):
        """
        Initialize Eden AI provider with enterprise HTTP support.

        Args:
            api_key: Eden AI API key. If None, reads from EDENAI_API_KEY env var.
            base_url: Base URL for the Eden AI API. Defaults to
                https://api.edenai.run/v3 (use https://api.eu.edenai.run/v3 for the
                EU-only endpoint).
            retry_config: Custom retry configuration (optional).
            http_config: Enterprise HTTP configuration (optional). Supports custom
                SSL/TLS verification, corporate proxies, custom CA bundles, and
                connection timeouts. If None, auto-detects from environment variables.
        """
        super().__init__(api_key=api_key, retry_config=retry_config, http_config=http_config)

        if not self.api_key:
            raise ValueError(
                "Eden AI API key not found. Please set the EDENAI_API_KEY environment "
                "variable or pass api_key parameter. Get a key at: https://app.edenai.run"
            )

        self.base_url = base_url or "https://api.edenai.run/v3"

        # Get httpx kwargs from http_config (includes verify, proxy, timeout)
        httpx_kwargs = self.http_config.get_httpx_kwargs()
        httpx_kwargs["timeout"] = 120.0

        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            **httpx_kwargs,
        )

        # Model cache for dynamic discovery
        self._model_cache: Optional[dict[str, Any]] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 3600.0  # 1 hour

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment."""
        return os.getenv("EDENAI_API_KEY")

    def _check_logprobs_support(self) -> bool:
        """Check if provider supports native logprobs."""
        # Support varies per underlying model; conservatively report False.
        return False

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for a given token count (fallback method).

        Args:
            tokens: Number of tokens
            model: Model identifier (``provider/model`` format)

        Returns:
            Estimated cost in USD
        """
        pricing = EDENAI_PRICING.get(model.lower(), _DEFAULT_PRICING)
        # Assume 50/50 split between input and output for estimation.
        avg_rate = (pricing["input"] + pricing["output"]) / 2
        return (tokens / 1_000_000) * avg_rate

    async def _complete_impl(
        self,
        prompt: str,
        model: str = "anthropic/claude-haiku-4-5",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Internal implementation of completion using Eden AI.

        Args:
            prompt: User prompt
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            tools: Optional list of tools for function calling
            tool_choice: Tool choice strategy ('auto', 'none', or specific tool)
            **kwargs: Additional parameters passed to the API

        Returns:
            ModelResponse with content, cost, and metadata
        """
        start_time = time.time()

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request body
        request_body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }

        # Add tools if provided
        if tools:
            request_body["tools"] = self._convert_tools_to_openai(tools)
            if tool_choice:
                request_body["tool_choice"] = tool_choice

        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=request_body,
            )
            response.raise_for_status()
            data = response.json()

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 401:
                raise ProviderError(
                    "Invalid Eden AI API key (401). Check your EDENAI_API_KEY.",
                    provider="edenai",
                    original_error=e,
                )
            if status == 429:
                raise ProviderError(
                    "Eden AI rate limit exceeded (429). Please retry later.",
                    provider="edenai",
                    original_error=e,
                )
            raise ProviderError(
                f"Eden AI API error: {status} - {e.response.text}",
                provider="edenai",
                original_error=e,
            )
        except Exception as e:
            raise ProviderError(
                f"Eden AI request failed: {str(e)}",
                provider="edenai",
                original_error=e,
            )

        # Parse response
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        usage = data.get("usage", {})

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens

        # Eden AI returns the actual per-request cost; prefer it when present,
        # otherwise fall back to the local pricing estimate.
        cost = self._resolve_cost(data, model, prompt_tokens, completion_tokens)

        latency_ms = (time.time() - start_time) * 1000
        tool_calls = self._parse_tool_calls(choice)
        confidence = self._estimate_confidence(content, prompt)

        return ModelResponse(
            content=content,
            model=data.get("model", model),
            provider="edenai",
            cost=cost,
            tokens_used=total_tokens,
            confidence=confidence,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
            metadata={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "finish_reason": choice.get("finish_reason"),
            },
        )

    async def _stream_impl(
        self,
        prompt: str,
        model: str = "anthropic/claude-haiku-4-5",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Internal implementation of streaming from Eden AI.

        Args:
            prompt: User prompt
            model: Model identifier
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Yields:
            String chunks of the response
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request_body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            **kwargs,
        }

        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=request_body,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or line.startswith(":"):
                        continue

                    if line.startswith("data: "):
                        data = line[6:]

                        if data == "[DONE]":
                            break

                        try:
                            parsed = json.loads(data)
                            delta = parsed.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPStatusError as e:
            raise ProviderError(
                f"Eden AI streaming error: {e.response.status_code}",
                provider="edenai",
                original_error=e,
            )

    async def fetch_available_models(self) -> list[dict[str, Any]]:
        """
        Fetch available models from the Eden AI API.

        Results are cached for 1 hour to avoid excessive API calls.

        Returns:
            List of model information dicts

        See Also:
            https://api.edenai.run/v3/models
        """
        now = time.time()

        if self._model_cache and (now - self._cache_timestamp) < self._cache_ttl:
            return list(self._model_cache.values())

        try:
            response = await self.client.get(f"{self.base_url}/models")
            response.raise_for_status()
            data = response.json()

            models = data.get("data", [])
            self._model_cache = {m["id"]: m for m in models}
            self._cache_timestamp = now

            return models

        except Exception:
            # If fetch fails, return empty list (don't break the provider).
            return []

    def _resolve_cost(
        self, data: dict[str, Any], model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """
        Resolve the request cost.

        Prefers the ``cost`` value returned by the Eden AI API; falls back to the
        local pricing table when it is missing or invalid.
        """
        api_cost = data.get("cost")
        if isinstance(api_cost, (int, float)) and api_cost >= 0:
            return float(api_cost)
        return self._calculate_cost(model, prompt_tokens, completion_tokens)

    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost from the local pricing table (per 1M tokens).

        Args:
            model: Model identifier
            prompt_tokens: Input tokens
            completion_tokens: Output tokens

        Returns:
            Cost in USD
        """
        model_lower = model.lower()
        pricing = EDENAI_PRICING.get(model_lower)

        if not pricing:
            for key, value in EDENAI_PRICING.items():
                if model_lower.startswith(key):
                    pricing = value
                    break

        if not pricing:
            pricing = _DEFAULT_PRICING

        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def _convert_tools_to_openai(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert tools from universal format to OpenAI format."""
        if not tools:
            return []

        openai_tools = []
        for tool in tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.get("name", tool.get("function", {}).get("name", "")),
                    "description": tool.get(
                        "description", tool.get("function", {}).get("description", "")
                    ),
                    "parameters": tool.get(
                        "parameters", tool.get("function", {}).get("parameters", {})
                    ),
                },
            }
            openai_tools.append(openai_tool)

        return openai_tools

    def _parse_tool_calls(self, choice: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
        """Parse tool calls from an Eden AI response into the universal format."""
        message = choice.get("message", {})
        raw_tool_calls = message.get("tool_calls")

        if not raw_tool_calls:
            return None

        tool_calls = []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            raw_args = func.get("arguments", "{}")
            if isinstance(raw_args, str):
                try:
                    parsed_args = json.loads(raw_args)
                except (json.JSONDecodeError, TypeError):
                    parsed_args = raw_args
            else:
                parsed_args = raw_args
            tool_calls.append(
                {
                    "id": tc.get("id", ""),
                    "name": func.get("name", ""),
                    "arguments": parsed_args,
                }
            )

        return tool_calls if tool_calls else None

    def _estimate_confidence(self, content: str, prompt: str) -> float:
        """Estimate confidence based on response characteristics."""
        if not content:
            return 0.0

        confidence = 0.7

        word_count = len(content.split())
        if word_count < 10:
            confidence -= 0.1
        elif word_count > 500:
            confidence += 0.1

        if "```" in content:
            confidence += 0.05
        if any(marker in content for marker in ["1.", "- ", "* "]):
            confidence += 0.05

        return min(max(confidence, 0.0), 1.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
