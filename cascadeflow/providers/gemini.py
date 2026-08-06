"""Google Gemini provider implementation with tool calling support."""

import json
import os
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from .base import BaseProvider, HttpConfig, ModelResponse, RetryConfig


class GeminiProvider(BaseProvider):
    """
    Google Gemini provider for Gemini models with tool calling support.

    Supports Gemini models including:
    - Gemini 2.5 Pro / Flash
    - Gemini 1.5 Pro / Flash
    - Gemini 2.0 Flash (experimental)

    Enhanced with function calling support and automatic retry logic.

                            Gemini-specific retry behavior:
                            - 401 (invalid key): No retry (permanent error)
                            - 429 (rate limit): Retry with exponential backoff
                            - 503 (overloaded): Retry with backoff
                            - Network errors: Retry with backoff

    Example (Basic):
        >>> # Basic usage (automatic retry on failures)
        >>> provider = GeminiProvider(api_key="...")
        >>>
        >>> # Non-streaming:
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="gemini-2.0-flash"
        ... )
        >>> print(f"Response: {response.content}")
        >>> print(f"Confidence: {response.confidence}")

    Example (Tool Calling):
        >>> # Define tools
        >>> tools = [{
        ...     "name": "get_weather",
        ...     "description": "Get weather for a location",
        ...     "parameters": {
        ...         "type": "object",
        ...         "properties": {
        ...             "location": {"type": "string"},
        ...             "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
        ...         },
        ...         "required": ["location"]
        ...     }
        ... }]
        >>>
        >>> # Use with tool-compatible model
        >>> response = await provider.complete(
        ...     prompt="What's the weather in Paris?",
        ...     model="gemini-1.5-pro",
        ...     tools=tools
        ... )
        >>>
        >>> if response.tool_calls:
        ...     for tool_call in response.tool_calls:
        ...         print(f"Tool: {tool_call['name']}")
        ...         print(f"Args: {tool_call['arguments']}")
    """

    # Gemini model pricing (per 1M tokens) - USD
    # Updated: March 2026
    PRICING = {
        # Gemini 3 Series (Latest)
        "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
        "gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
        "gemini-3.1-flash-preview": {"input": 0.50, "output": 3.00},
        "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
        "gemini-3.1-flash-lite-preview": {"input": 0.25, "output": 1.50},
        # Gemini 2.5 Series
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
        "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
        "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
        "gemini-2.5-flash-lite-preview-05-2025": {"input": 0.10, "output": 0.40},
        # Gemini 2.0 Series
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-2.0-flash-lite": {"input": 0.08, "output": 0.30},
        # Gemini 1.5 Series (Legacy)
        "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.5-flash-8b": {"input": 0.0375, "output": 0.15},
    }

    # Default model
    DEFAULT_MODEL = "gemini-2.5-flash"

    # Models supporting tools (function calling)
    TOOL_CAPABLE_MODELS = [
        # Gemini 3 Series
        "gemini-3.1-pro-preview",
        "gemini-3-pro-preview",
        "gemini-3.1-flash-preview",
        "gemini-3-flash-preview",
        # Gemini 2.5 Series
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-2.0-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        http_config: Optional[HttpConfig] = None,
    ):
        """
        Initialize Gemini provider with automatic retry logic and enterprise HTTP support.

        Args:
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY env var.
            retry_config: Custom retry configuration (optional). If None, uses defaults:
                - max_attempts: 3
                - initial_delay: 1.0s
                - rate_limit_backoff: 30.0s
            http_config: Enterprise HTTP configuration (optional). Supports:
                - Custom SSL/TLS certificate verification
                - Corporate proxy configuration (HTTPS_PROXY, HTTP_PROXY)
                - Custom CA bundles (SSL_CERT_FILE, REQUESTS_CA_BUNDLE)
                - Connection timeouts
                If None, auto-detects from environment variables.

        Example:
            # Auto-detect from environment (default)
            provider = GeminiProvider()

            # Corporate environment with custom CA bundle
            provider = GeminiProvider(
                http_config=HttpConfig(verify="/path/to/corporate-ca.pem")
            )

            # With proxy
            provider = GeminiProvider(
                http_config=HttpConfig(proxy="http://proxy.corp.com:8080")
            )
        """
        super().__init__(api_key=api_key, retry_config=retry_config, http_config=http_config)

        if not self.api_key:
            raise ValueError(
                "Gemini API key not found. Please set GEMINI_API_KEY environment "
                "variable or pass api_key parameter."
            )

        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

        httpx_kwargs = self.http_config.get_httpx_kwargs()
        httpx_kwargs["timeout"] = 120.0

        self.client = httpx.AsyncClient(
            headers={"Content-Type": "application/json"},
            **httpx_kwargs,
        )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment."""
        return os.getenv("GEMINI_API_KEY")

    def _check_logprobs_support(self) -> bool:
        """
        Gemini does not have native logprobs like OpenAI.

        Returns:
            False - Gemini doesn't provide logprobs
        """
        return False

    def _check_tool_support(self) -> bool:
        """
        Gemini supports function calling (tool calling).

        Returns:
            True - Gemini has function calling support
        """
        return True

    def _get_model_price(self, model: str) -> tuple[float, float]:
        """
        Get pricing for a Gemini model.

        Args:
            model: Model name

        Returns:
            Tuple of (input_price_per_1m, output_price_per_1m)
        """
        model_base = model.replace("models/", "").strip()

        if model_base in self.PRICING:
            prices = self.PRICING[model_base]
            return prices["input"], prices["output"]

        return 0.0, 0.0

    def _convert_tools_to_gemini(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert tools from universal format to Gemini function calling format.

        Universal format:
        {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {...}  # JSON Schema
        }

        Gemini format:
        {
            "function_declarations": [{
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {...}  # JSON Schema
            }]
        }

        Args:
            tools: List of tools in universal format

        Returns:
            List of tools in Gemini format
        """
        if not tools:
            return []

        gemini_tools = []
        for tool in tools:
            if isinstance(tool, dict):
                gemini_tool = {
                    "function_declarations": [
                        {
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("parameters", {}),
                        }
                    ]
                }
                gemini_tools.append(gemini_tool)

        return gemini_tools

    def _parse_gemini_response(self, response_data: dict[str, Any], model: str) -> ModelResponse:
        """
        Parse Gemini API response into standardized ModelResponse.

        Args:
            response_data: Raw response from Gemini API
            model: Model name used

        Returns:
            Standardized ModelResponse
        """
        content = ""
        tool_calls = None

        if "candidates" in response_data and response_data["candidates"]:
            candidate = response_data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                parts = candidate["content"]["parts"]
                for part in parts:
                    if "text" in part:
                        content += part["text"]
                    elif "functionCall" in part:
                        if tool_calls is None:
                            tool_calls = []
                        tool_calls.append(
                            {
                                "name": part["functionCall"]["name"],
                                "arguments": part["functionCall"].get("args", {}),
                            }
                        )

        usage = response_data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("totalTokenCount", 0)

        input_price, output_price = self._get_model_price(model)
        cost = (prompt_tokens / 1_000_000 * input_price) + (
            completion_tokens / 1_000_000 * output_price
        )

        return ModelResponse(
            content=content,
            model=model,
            provider="gemini",
            cost=cost,
            tokens_used=total_tokens,
            confidence=0.8,  # Gemini doesn't have native logprobs, use default
            latency_ms=response_data.get("modelMetadata", {}).get("promptTokenCount", 0),
            tool_calls=tool_calls,
        )

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for given token count.

        Args:
            tokens: Number of tokens
            model: Model name

        Returns:
            Estimated cost in USD
        """
        input_price, output_price = self._get_model_price(model)
        return tokens / 1_000_000 * (input_price + output_price) / 2

    async def _complete_impl(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Provider-specific implementation of complete().

        Args:
            prompt: Input prompt
            model: Model name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            tools: Optional tools for function calling
            **kwargs: Provider-specific options

        Returns:
            ModelResponse with standardized format
        """
        model_id = model if model.startswith("models/") else f"models/{model}"

        url = f"{self.base_url}/{model_id}:generateContent"

        contents = [{"role": "user", "parts": [{"text": prompt}]}]

        generation_config = {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        }

        if system_prompt:
            generation_config["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        if tools:
            generation_config["tools"] = self._convert_tools_to_gemini(tools)

        request_body = {
            "contents": contents,
            "generationConfig": generation_config,
        }

        params = {"key": self.api_key}

        response = await self.client.post(url, json=request_body, params=params)
        response.raise_for_status()

        response_data = response.json()

        return self._parse_gemini_response(response_data, model)

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

        Args:
            prompt: Input prompt
            model: Model name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            **kwargs: Provider-specific options

        Yields:
            Content chunks as strings
        """
        model_id = model if model.startswith("models/") else f"models/{model}"

        url = f"{self.base_url}/{model_id}:streamGenerateContent"

        contents = [{"role": "user", "parts": [{"text": prompt}]}]

        generation_config = {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }

        if system_prompt:
            generation_config["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        request_body = {
            "contents": contents,
            "generationConfig": generation_config,
        }

        params = {"key": self.api_key}

        async with self.client.stream("POST", url, json=request_body, params=params) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.strip() and line.startswith("data:"):
                    data = line[5:].strip()
                    if data:
                        try:
                            data_obj = json.loads(data)
                            if (
                                "candidates" in data_obj
                                and data_obj["candidates"]
                                and "content" in data_obj["candidates"][0]
                                and "parts" in data_obj["candidates"][0]["content"]
                            ):
                                for part in data_obj["candidates"][0]["content"]["parts"]:
                                    if "text" in part:
                                        yield part["text"]
                        except json.JSONDecodeError:
                            continue
