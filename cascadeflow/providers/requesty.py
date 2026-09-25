"""
Requesty provider implementation for cascadeflow.

Requesty is an LLM gateway that gives unified access to hundreds of models
from multiple providers through a single OpenAI-compatible endpoint.

Key Features:
    - Models from OpenAI, Anthropic, Google, DeepSeek, xAI, Mistral, and more
    - OpenAI-compatible API
    - Streaming support
    - Tool calling support
    - Dynamic model discovery (managed policies and full catalog)
    - Regional endpoints (e.g. EU: https://router.eu.requesty.ai/v1)

Pricing:
    Requesty returns the request cost in ``usage.cost``. When it is missing,
    cost is estimated from per-1M token pricing below.
    See https://app.requesty.ai for current pricing.

Example:
    >>> from cascadeflow.providers import RequestyProvider
    >>>
    >>> provider = RequestyProvider()  # Uses REQUESTY_API_KEY env var
    >>>
    >>> # Basic completion
    >>> response = await provider.complete(
    ...     prompt="What is cascadeflow?",
    ...     model="openai/gpt-4o-mini"
    ... )
    >>> print(response.content)
    >>>
    >>> # Streaming
    >>> async for chunk in provider.stream(
    ...     prompt="Explain quantum computing",
    ...     model="anthropic/claude-sonnet-4-5"
    ... ):
    ...     print(chunk, end='', flush=True)

See Also:
    - https://docs.requesty.ai
    - https://app.requesty.ai/api-keys
"""

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from ..schema.exceptions import ProviderError
from .base import BaseProvider, HttpConfig, ModelResponse, RetryConfig

# Requesty pricing per 1M tokens (sample of popular models)
# Used only when the response does not include usage.cost.
# Fetch latest pricing from: https://router.requesty.ai/v1/models
REQUESTY_PRICING: dict[str, dict[str, float]] = {
    # OpenAI Models
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "openai/gpt-4o": {"input": 2.5, "output": 10.0},
    "openai/gpt-5-mini": {"input": 0.25, "output": 2.0},
    "openai/gpt-5": {"input": 1.25, "output": 10.0},
    # Anthropic Models
    "anthropic/claude-haiku-4-5": {"input": 1.0, "output": 5.0},
    "anthropic/claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "anthropic/claude-opus-4-5": {"input": 5.0, "output": 25.0},
    # Google Models
    "google/gemini-2.5-flash": {"input": 0.3, "output": 2.5},
    "google/gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    # DeepSeek Models
    "deepseek/deepseek-chat": {"input": 0.14, "output": 0.28},
    # xAI Models
    "xai/grok-4-fast": {"input": 0.2, "output": 0.5},
}


class RequestyProvider(BaseProvider):
    """
    Requesty provider with OpenAI-compatible API.

    Supports:
    - Models from multiple providers through one API key
    - Streaming
    - Tool calling
    - Dynamic model discovery

    Example:
        >>> provider = RequestyProvider()
        >>> response = await provider.complete(
        ...     prompt="Hello!",
        ...     model="openai/gpt-4o-mini"
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
        Initialize Requesty provider with enterprise HTTP support.

        Args:
            api_key: Requesty API key. If None, reads from REQUESTY_API_KEY env var.
            base_url: Base URL for Requesty API. Defaults to https://router.requesty.ai/v1
                (EU: https://router.eu.requesty.ai/v1)
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
                "Requesty API key not found. Please set REQUESTY_API_KEY environment "
                "variable or pass api_key parameter. Get key at: https://app.requesty.ai/api-keys"
            )

        self.base_url = base_url or "https://router.requesty.ai/v1"

        # Get httpx kwargs from http_config (includes verify, proxy, timeout)
        httpx_kwargs = self.http_config.get_httpx_kwargs()
        httpx_kwargs["timeout"] = 120.0  # Requesty-specific timeout

        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                # Optional attribution headers
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
        return os.getenv("REQUESTY_API_KEY")

    def _check_logprobs_support(self) -> bool:
        """Check if provider supports native logprobs."""
        # Requesty supports logprobs for compatible models
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
        pricing = REQUESTY_PRICING.get(model.lower(), {"input": 0.15, "output": 0.6})
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
        Internal implementation of completion using Requesty.

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
            raise ProviderError(
                f"Requesty API error: {e.response.status_code} - {e.response.text}",
                provider="requesty",
                original_error=e,
            )
        except Exception as e:
            raise ProviderError(
                f"Requesty request failed: {str(e)}",
                provider="requesty",
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
        cost = self._resolve_cost(model, usage, prompt_tokens, completion_tokens)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Parse tool calls if present
        tool_calls = self._parse_tool_calls(choice)

        # Estimate confidence (based on response completeness)
        confidence = self._estimate_confidence(content, prompt)

        return ModelResponse(
            content=content,
            model=data.get("model", model),
            provider="requesty",
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
        Internal implementation of streaming from Requesty.

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
                f"Requesty streaming error: {e.response.status_code}",
                provider="requesty",
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
                f"Requesty tool call failed: {str(e)}",
                provider="requesty",
                original_error=e,
            )

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        usage = data.get("usage", {})

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens
        cost = self._resolve_cost(model, usage, prompt_tokens, completion_tokens)
        latency_ms = (time.time() - start_time) * 1000

        tool_calls = self._parse_tool_calls(choice)

        return ModelResponse(
            content=content,
            model=data.get("model", model),
            provider="requesty",
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
        Fetch available models from Requesty API.

        Managed policies (curated, e.g. ``claude-sonnet-4-5``) come first,
        followed by the full ``vendor/model`` catalog. Results are cached for
        1 hour to avoid excessive API calls.

        Returns:
            List of model information dicts

        See Also:
            https://router.requesty.ai/v1/models/managed
            https://router.requesty.ai/v1/models
        """
        now = time.time()

        # Return cached data if still valid
        if self._model_cache and (now - self._cache_timestamp) < self._cache_ttl:
            return list(self._model_cache.values())

        merged: dict[str, Any] = {}
        for path in ("/models/managed", "/models"):
            try:
                response = await self.client.get(f"{self.base_url}{path}")
                response.raise_for_status()
                data = response.json()
            except Exception:
                # If one list fails, keep the other (don't break the provider)
                continue

            for m in data.get("data", []):
                if m.get("id") and m["id"] not in merged:
                    merged[m["id"]] = m

        if not merged:
            return []

        self._model_cache = merged
        self._cache_timestamp = now

        return list(merged.values())

    def _resolve_cost(
        self, model: str, usage: dict[str, Any], prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Use the cost reported by Requesty in usage.cost, else estimate it."""
        reported_cost = usage.get("cost")
        if isinstance(reported_cost, (int, float)):
            return float(reported_cost)
        return self._calculate_cost(model, prompt_tokens, completion_tokens)

    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost based on Requesty pricing.

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
        pricing = REQUESTY_PRICING.get(model_lower)

        # Try prefix matching for versioned models
        if not pricing:
            for key, value in REQUESTY_PRICING.items():
                if model_lower.startswith(key):
                    pricing = value
                    break

        # Fallback to reasonable default (gpt-4o-mini equivalent)
        if not pricing:
            pricing = {"input": 0.15, "output": 0.6}

        # Requesty pricing is per 1M tokens
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
        Parse tool calls from Requesty response.

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
