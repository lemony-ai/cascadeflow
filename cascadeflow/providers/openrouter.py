"""
OpenRouter provider implementation for cascadeflow.

OpenRouter provides unified access to 400+ AI models from multiple providers
through a single API endpoint. It's OpenAI-compatible and supports all major
models from OpenAI, Anthropic, Google, Meta, Mistral, X.AI, and more.

Key Features:
    - 400+ models from multiple providers (OpenAI, Anthropic, Google, Meta, etc.)
    - OpenAI-compatible API
    - Streaming support
    - Tool calling support
    - Dynamic model discovery
    - Automatic fallbacks

Pricing:
    OpenRouter uses per-1M token pricing. Prices vary by model.
    See https://openrouter.ai/models for current pricing.

Example:
    >>> from cascadeflow.providers import OpenRouterProvider
    >>>
    >>> provider = OpenRouterProvider()  # Uses OPENROUTER_API_KEY env var
    >>>
    >>> # Basic completion
    >>> response = await provider.complete(
    ...     prompt="What is cascadeflow?",
    ...     model="anthropic/claude-3.5-sonnet"
    ... )
    >>> print(response.content)
    >>>
    >>> # Streaming
    >>> async for chunk in provider.stream(
    ...     prompt="Explain quantum computing",
    ...     model="openai/gpt-4o"
    ... ):
    ...     print(chunk, end='', flush=True)

See Also:
    - https://openrouter.ai/docs
    - https://openrouter.ai/models
"""

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from ..schema.exceptions import ProviderError
from .base import BaseProvider, HttpConfig, ModelResponse, RetryConfig

# OpenRouter pricing per 1M tokens (sample of popular models as of 2025)
# Note: OpenRouter has 400+ models with dynamic pricing.
# Fetch latest pricing from: https://openrouter.ai/api/v1/models
OPENROUTER_PRICING: dict[str, dict[str, float]] = {
    # X.AI Models (Top Used)
    "x-ai/grok-beta": {"input": 5.0, "output": 15.0},
    # Anthropic Models (Top Performer for Coding)
    "anthropic/claude-opus-4": {"input": 15.0, "output": 75.0},
    "anthropic/claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
    # OpenAI Models
    "openai/gpt-4o": {"input": 2.5, "output": 10.0},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "openai/o1": {"input": 15.0, "output": 60.0},
    "openai/o1-mini": {"input": 3.0, "output": 12.0},
    # Google Models
    "google/gemini-2.5-flash": {"input": 0.15, "output": 0.6},
    "google/gemini-2.5-pro": {"input": 1.25, "output": 5.0},
    "google/gemini-pro-1.5": {"input": 1.25, "output": 5.0},
    # Meta Models
    "meta-llama/llama-3.1-405b-instruct": {"input": 1.0, "output": 1.0},
    "meta-llama/llama-3.1-70b-instruct": {"input": 0.35, "output": 0.4},
    "meta-llama/llama-3.1-8b-instruct": {"input": 0.05, "output": 0.05},
    # DeepSeek Models (Great Value)
    "deepseek/deepseek-chat": {"input": 0.0, "output": 0.0},
    "deepseek/deepseek-coder-v2": {"input": 0.27, "output": 1.1},
    # Mistral Models
    "mistralai/mistral-large": {"input": 2.0, "output": 6.0},
    "mistralai/mistral-small-3.1": {"input": 0.0, "output": 0.0},
}


class OpenRouterProvider(BaseProvider):
    """
    OpenRouter provider with OpenAI-compatible API.

    Supports all OpenRouter features:
    - 400+ models from multiple providers
    - Streaming
    - Tool calling
    - Automatic fallbacks
    - Dynamic model discovery

    Example:
        >>> provider = OpenRouterProvider()
        >>> response = await provider.complete(
        ...     prompt="Hello!",
        ...     model="anthropic/claude-3.5-sonnet"
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
        Initialize OpenRouter provider with enterprise HTTP support.

        Args:
            api_key: OpenRouter API key. If None, reads from OPENROUTER_API_KEY env var.
            base_url: Base URL for OpenRouter API. Defaults to https://openrouter.ai/api/v1
            retry_config: Custom retry configuration (optional).
            http_config: Enterprise HTTP configuration (optional). Supports:
                - Custom SSL/TLS certificate verification
                - Corporate proxy configuration (HTTPS_PROXY, HTTP_PROXY)
                - Custom CA bundles (SSL_CERT_FILE, REQUESTS_CA_BUNDLE)
                - Connection timeouts
                If None, auto-detects from environment variables.
        """
        super().__init__(api_key=api_key, retry_config=retry_config, http_config=http_config)

        if not self.api_key:
            raise ValueError(
                "OpenRouter API key not found. Please set OPENROUTER_API_KEY environment "
                "variable or pass api_key parameter. Get key at: https://openrouter.ai"
            )

        self.base_url = base_url or "https://openrouter.ai/api/v1"

        # Get httpx kwargs from http_config (includes verify, proxy, timeout)
        httpx_kwargs = self.http_config.get_httpx_kwargs()
        httpx_kwargs["timeout"] = 120.0  # OpenRouter-specific timeout

        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                # Optional headers for leaderboard rankings
                "HTTP-Referer": "https://github.com/lemony-ai/cascadeflow",
                "X-Title": "CascadeFlow",
            },
            **httpx_kwargs,
        )

        # Model cache for dynamic discovery
        self._model_cache: Optional[dict[str, Any]] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 3600.0  # 1 hour

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment."""
        return os.getenv("OPENROUTER_API_KEY")

    def _check_logprobs_support(self) -> bool:
        """Check if provider supports native logprobs."""
        # OpenRouter supports logprobs for compatible models
        return True

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for given token count (fallback method).

        Args:
            tokens: Number of tokens
            model: Model identifier

        Returns:
            Estimated cost in USD
        """
        pricing = OPENROUTER_PRICING.get(model.lower(), {"input": 0.15, "output": 0.6})
        # Assume 50/50 split between input and output for estimation
        avg_rate = (pricing["input"] + pricing["output"]) / 2
        return (tokens / 1_000_000) * avg_rate

    async def _complete_impl(
        self,
        prompt: str,
        model: str = "openai/gpt-4o-mini",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Internal implementation of completion using OpenRouter.

        Args:
            prompt: User prompt
            model: Model identifier (e.g., 'anthropic/claude-3.5-sonnet')
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
            raise ProviderError(
                f"OpenRouter API error: {e.response.status_code} - {e.response.text}",
                provider="openrouter",
                original_error=e,
            )
        except Exception as e:
            raise ProviderError(
                f"OpenRouter request failed: {str(e)}",
                provider="openrouter",
                original_error=e,
            )

        # Parse response
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        usage = data.get("usage", {})

        # Calculate cost
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Parse tool calls if present
        tool_calls = self._parse_tool_calls(choice)

        # Estimate confidence (based on response completeness)
        confidence = self._estimate_confidence(content, prompt)

        return ModelResponse(
            content=content,
            model=data.get("model", model),
            provider="openrouter",
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
        model: str = "openai/gpt-4o-mini",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Internal implementation of streaming from OpenRouter.

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
                f"OpenRouter streaming error: {e.response.status_code}",
                provider="openrouter",
                original_error=e,
            )

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str = "openai/gpt-4o",
        tool_choice: str = "auto",
        **kwargs,
    ) -> ModelResponse:
        """
        Complete with tool calling support for multi-turn conversations.

        Args:
            messages: Conversation messages
            tools: List of available tools
            model: Model identifier
            tool_choice: Tool choice strategy
            **kwargs: Additional parameters

        Returns:
            ModelResponse with potential tool_calls
        """
        start_time = time.time()

        request_body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": self._convert_tools_to_openai(tools),
            "tool_choice": tool_choice,
            **kwargs,
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=request_body,
            )
            response.raise_for_status()
            data = response.json()

        except Exception as e:
            raise ProviderError(
                f"OpenRouter tool call failed: {str(e)}",
                provider="openrouter",
                original_error=e,
            )

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        usage = data.get("usage", {})

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)
        latency_ms = (time.time() - start_time) * 1000

        tool_calls = self._parse_tool_calls(choice)

        return ModelResponse(
            content=content,
            model=data.get("model", model),
            provider="openrouter",
            cost=cost,
            tokens_used=total_tokens,
            confidence=self._estimate_confidence(content, ""),
            latency_ms=latency_ms,
            tool_calls=tool_calls,
            metadata={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "finish_reason": choice.get("finish_reason"),
            },
        )

    async def fetch_available_models(self) -> list[dict[str, Any]]:
        """
        Fetch available models from OpenRouter API.

        Results are cached for 1 hour to avoid excessive API calls.

        Returns:
            List of model information dicts

        See Also:
            https://openrouter.ai/api/v1/models
        """
        now = time.time()

        # Return cached data if still valid
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
            # If fetch fails, return empty list (don't break the provider)
            return []

    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost based on OpenRouter pricing.

        Note: Pricing is per 1M tokens.

        Args:
            model: Model identifier
            prompt_tokens: Input tokens
            completion_tokens: Output tokens

        Returns:
            Cost in USD
        """
        model_lower = model.lower()

        # Try exact match first
        pricing = OPENROUTER_PRICING.get(model_lower)

        # Try prefix matching for versioned models
        if not pricing:
            for key, value in OPENROUTER_PRICING.items():
                if model_lower.startswith(key):
                    pricing = value
                    break

        # Fallback to reasonable default (gpt-4o-mini equivalent)
        if not pricing:
            pricing = {"input": 0.15, "output": 0.6}

        # OpenRouter pricing is per 1M tokens
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def _convert_tools_to_openai(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert tools from universal format to OpenAI format.

        Args:
            tools: List of tools in universal format

        Returns:
            List of tools in OpenAI format
        """
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
        """
        Parse tool calls from OpenRouter response.

        Args:
            choice: Response choice object

        Returns:
            List of tool calls in universal format, or None
        """
        message = choice.get("message", {})
        raw_tool_calls = message.get("tool_calls")

        if not raw_tool_calls:
            return None

        tool_calls = []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            tool_calls.append(
                {
                    "id": tc.get("id", ""),
                    "name": func.get("name", ""),
                    "arguments": func.get("arguments", "{}"),
                }
            )

        return tool_calls if tool_calls else None

    def _estimate_confidence(self, content: str, prompt: str) -> float:
        """
        Estimate confidence based on response characteristics.

        Args:
            content: Response content
            prompt: Original prompt

        Returns:
            Confidence score between 0 and 1
        """
        if not content:
            return 0.0

        # Base confidence
        confidence = 0.7

        # Adjust based on response length (very short or very long = lower confidence)
        word_count = len(content.split())
        if word_count < 10:
            confidence -= 0.1
        elif word_count > 500:
            confidence += 0.1

        # Adjust based on response structure (code blocks, lists = higher confidence)
        if "```" in content:
            confidence += 0.05
        if any(marker in content for marker in ["1.", "- ", "* "]):
            confidence += 0.05

        return min(max(confidence, 0.0), 1.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
