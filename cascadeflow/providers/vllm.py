"""vLLM provider for high-performance local inference with tool calling support."""

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from ..exceptions import ModelError, ProviderError
from .base import BaseProvider, ModelResponse, RetryConfig


class ReasoningModelInfo:
    """
    Information about reasoning model capabilities and limitations.

    Used for auto-detection and configuration across all providers.
    Unified type that matches TypeScript ReasoningModelInfo interface.
    """

    def __init__(
        self,
        is_reasoning: bool = False,
        provider: str = "vllm",
        supports_streaming: bool = True,
        supports_tools: bool = True,
        supports_system_messages: bool = True,
        supports_reasoning_effort: bool = False,
        supports_extended_thinking: bool = False,
        requires_max_completion_tokens: bool = False,
        requires_thinking_budget: bool = False,
    ):
        self.is_reasoning = is_reasoning
        self.provider = provider
        self.supports_streaming = supports_streaming
        self.supports_tools = supports_tools
        self.supports_system_messages = supports_system_messages
        self.supports_reasoning_effort = supports_reasoning_effort  # OpenAI o1/o3
        self.supports_extended_thinking = supports_extended_thinking  # Anthropic Claude 3.7
        self.requires_max_completion_tokens = requires_max_completion_tokens  # OpenAI specific
        self.requires_thinking_budget = requires_thinking_budget  # Anthropic specific


def get_reasoning_model_info(model_name: str) -> ReasoningModelInfo:
    """
    Detect if model is DeepSeek-R1 reasoning model.

    Args:
        model_name: Model name to check

    Returns:
        Model capabilities
    """
    name = model_name.lower()

    # DeepSeek-R1 - Chain-of-thought reasoning model
    # Variations: deepseek-r1, deepseek-r1-distill, etc.
    if "deepseek-r1" in name or "deepseek_r1" in name:
        return ReasoningModelInfo(
            is_reasoning=True,
            provider="vllm",
            supports_streaming=True,
            supports_tools=True,
            supports_system_messages=True,
            supports_extended_thinking=False,
            requires_thinking_budget=False,
        )

    # Standard models (no reasoning)
    return ReasoningModelInfo(
        is_reasoning=False,
        provider="vllm",
        supports_streaming=True,
        supports_tools=True,
        supports_system_messages=True,
        supports_extended_thinking=False,
        requires_thinking_budget=False,
    )


class VLLMProvider(BaseProvider):
    """
    vLLM provider for high-performance inference with tool calling.

    vLLM is an OpenAI-compatible server with:
    - PagedAttention for efficient memory usage
    - Continuous batching for high throughput
    - 24x faster than standard serving
    - Full logprobs support (OpenAI-compatible format)
    - Tool/function calling support (OpenAI-compatible!)
    - Self-hosted (zero API costs)

    Enhanced with full logprobs support, intelligent defaults for token-level confidence,
    complete tool calling capabilities, and confidence_method tracking.

                           tool calling API, so we can leverage the same format as OpenAI/Groq.
                           Supports parallel tool calls, multi-turn conversations, and automatic
                           tool result handling.

    Requires vLLM server running locally or remotely.

    Example (Basic):
        >>> provider = VLLMProvider(base_url="http://localhost:8000/v1")
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="meta-llama/Llama-3-8B-Instruct"
        ... )

    Example (Tool Calling):
        >>> # Define tools (OpenAI-compatible format)
        >>> tools = [{
        ...     "type": "function",
        ...     "function": {
        ...         "name": "get_weather",
        ...         "description": "Get weather for a location",
        ...         "parameters": {
        ...             "type": "object",
        ...             "properties": {
        ...                 "location": {"type": "string"},
        ...                 "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
        ...             },
        ...             "required": ["location"]
        ...         }
        ...     }
        ... }]
        >>>
        >>> # Use tools automatically
        >>> response = await provider.complete(
        ...     prompt="What's the weather in Paris?",
        ...     model="meta-llama/Meta-Llama-3.1-70B-Instruct",
        ...     tools=tools
        ... )
        >>>
        >>> # Check for tool calls
        >>> if response.tool_calls:
        ...     for tool_call in response.tool_calls:
        ...         print(f"Tool: {tool_call['name']}")
        ...         print(f"Args: {tool_call['arguments']}")
        >>>
        >>> # Multi-turn with tool results (conversation format)
        >>> messages = [
        ...     {"role": "user", "content": "What's the weather in Paris?"},
        ...     {"role": "assistant", "content": None, "tool_calls": response.tool_calls},
        ...     {"role": "tool", "tool_call_id": "call_123", "content": '{"temp": 22, "condition": "sunny"}'}
        ... ]
        >>> response = await provider.complete(
        ...     messages=messages,
        ...     model="meta-llama/Meta-Llama-3.1-70B-Instruct",
        ...     tools=tools
        ... )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 300.0,
    ):
        """
        Initialize vLLM provider with tool calling support.

        Args:
            api_key: Optional API key for remote vLLM servers with authentication.
                     Not needed for local installations. Can also be set via VLLM_API_KEY env var.
            base_url: vLLM server URL. Defaults to http://localhost:8000/v1.
                      Can also be set via VLLM_BASE_URL env var.
                      Examples:
                        - Local: http://localhost:8000/v1
                        - Network: http://192.168.1.200:8000/v1
                        - Remote: https://vllm.yourdomain.com/v1
            retry_config: Custom retry configuration (optional)
            timeout: Request timeout in seconds (default: 300s for large models, reasoning models need more time)
        """
        super().__init__(api_key=api_key, retry_config=retry_config)

        self.base_url = base_url or os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        self.timeout = timeout

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.AsyncClient(headers=headers, timeout=self.timeout)

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment (optional for vLLM)."""
        return os.getenv("VLLM_API_KEY")

    def _check_logprobs_support(self) -> bool:
        """
        vLLM supports native logprobs for confidence analysis.

        Returns:
            True - vLLM provides native logprobs (OpenAI-compatible format)
        """
        return True

    async def _complete_impl(
        self,
        prompt: Optional[str] = None,
        model: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> ModelResponse:
        """
        Complete a prompt using vLLM server with optional tool calling.

        confidence estimation. Set logprobs=False to disable.

        vLLM uses OpenAI-compatible API format with full logprobs and tool support.

        Args:
            prompt: User prompt (for simple queries)
            model: Model name (must match what's loaded in vLLM)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            messages: Conversation history (OpenAI format) - for multi-turn or tool use
            tools: Tool definitions (OpenAI format) - enables tool calling
            tool_choice: Tool selection strategy ("auto", "none", or {"type": "function", "function": {"name": "..."}})
            **kwargs: Additional parameters including:
                - logprobs (bool): Enable logprobs (default: True for accurate confidence)
                - top_logprobs (int): Get top-k alternatives (default: 5)
                - parallel_tool_calls (bool): Allow parallel tool calls (default: True)

        Returns:
            ModelResponse with standardized format (enhanced with logprobs, tool_calls, and confidence_method)

        Raises:
            ProviderError: If API call fails (will be caught by retry logic)
            ModelError: If model execution fails (will be caught by retry logic)
        """
        start_time = time.time()

        # Intelligent default for logprobs
        if "logprobs" not in kwargs:
            kwargs["logprobs"] = self.should_request_logprobs(**kwargs)

        # Extract parameters
        logprobs_enabled = kwargs.pop("logprobs", False)
        top_logprobs = kwargs.pop("top_logprobs", 5)
        parallel_tool_calls = kwargs.pop("parallel_tool_calls", True)

        # Build messages (support both simple prompt and conversation format)
        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if prompt:
                messages.append({"role": "user", "content": prompt})

        # If prompt provided but messages exist, add prompt to messages
        elif prompt and messages:
            messages.append({"role": "user", "content": prompt})

        # Build request payload
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }

        # Add tool calling parameters if tools provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
            if parallel_tool_calls:
                payload["parallel_tool_calls"] = True

        # Add logprobs if requested
        if logprobs_enabled:
            payload["logprobs"] = True
            if top_logprobs:
                payload["top_logprobs"] = min(top_logprobs, 20)

        try:
            # Make API request
            response = await self.client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()
            choice = data["choices"][0]

            # Extract content (may be None if tool_calls present)
            content = choice["message"].get("content") or ""

            # Extract usage
            prompt_tokens = data["usage"]["prompt_tokens"]
            completion_tokens = data["usage"]["completion_tokens"]
            tokens_used = data["usage"]["total_tokens"]

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # vLLM is self-hosted, so cost is 0
            cost = 0.0

            # Build metadata for confidence system
            metadata_for_confidence = {
                "finish_reason": choice["finish_reason"],
                "temperature": temperature,
                "query": prompt or (messages[-1]["content"] if messages else ""),
            }

            # Parse tool calls if present (OpenAI format)
            tool_calls = None
            if "tool_calls" in choice["message"] and choice["message"]["tool_calls"]:
                tool_calls = []
                for tc in choice["message"]["tool_calls"]:
                    tool_calls.append(
                        {
                            "id": tc["id"],
                            "type": tc["type"],
                            "name": tc["function"]["name"],
                            "arguments": json.loads(tc["function"]["arguments"]),
                        }
                    )

                # Add to metadata
                metadata_for_confidence["has_tool_calls"] = True
                metadata_for_confidence["tool_count"] = len(tool_calls)

            # Parse logprobs if available
            tokens_list = []
            logprobs_list = []
            top_logprobs_list = []

            if logprobs_enabled and "logprobs" in choice and choice["logprobs"]:
                logprobs_data = choice["logprobs"]

                if "content" in logprobs_data and logprobs_data["content"]:
                    for token_data in logprobs_data["content"]:
                        tokens_list.append(token_data["token"])
                        logprobs_list.append(token_data["logprob"])

                        if "top_logprobs" in token_data and token_data["top_logprobs"]:
                            top_k = {}
                            for alt in token_data["top_logprobs"]:
                                top_k[alt["token"]] = alt["logprob"]
                            top_logprobs_list.append(top_k)
                        else:
                            top_logprobs_list.append({})

                    metadata_for_confidence["logprobs"] = logprobs_list
                    metadata_for_confidence["tokens"] = tokens_list

            # 🎯 DETERMINE CONFIDENCE METHOD (NEW!)
            # This tracks HOW we calculated confidence for diagnostic insights
            confidence_method = "unknown"

            if tool_calls:
                # Model called a tool - highest confidence signal
                confidence_method = "tool-call-present"
            elif tools and not tool_calls:
                # Tools were available but model chose to respond with text
                confidence_method = "tool-available-text-chosen"
            elif logprobs_list:
                # Using native logprobs for confidence
                if top_logprobs_list and any(top_logprobs_list):
                    confidence_method = "multi-signal-hybrid"  # logprobs + top_k
                else:
                    confidence_method = "logprobs-native"
            else:
                # Fallback to heuristic-based confidence
                confidence_method = "heuristic-based"

            # Calculate confidence
            confidence = self.calculate_confidence(content, metadata_for_confidence)

            # Build response metadata with confidence_method tracking
            response_metadata = {
                "finish_reason": choice["finish_reason"],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "base_url": self.base_url,
                "query": metadata_for_confidence["query"],
                "confidence_method": confidence_method,  # 🎯 Track method used!
            }

            if tools:
                response_metadata["tools_available"] = len(tools)

            # Build base response
            model_response = ModelResponse(
                content=content,
                model=model,
                provider="vllm",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata=response_metadata,
                tool_calls=tool_calls,  # Add tool calls to response!
            )

            # Add logprobs data if available
            if logprobs_list:
                model_response.tokens = tokens_list
                model_response.logprobs = logprobs_list
                model_response.top_logprobs = top_logprobs_list
                model_response.metadata["has_logprobs"] = True
                model_response.metadata["estimated"] = False
            elif logprobs_enabled:
                model_response = self.add_logprobs_fallback(
                    model_response, temperature, base_confidence=0.80
                )

            return model_response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelError(
                    f"Model '{model}' not found in vLLM server. "
                    f"Available models can be checked at {self.base_url}/models",
                    model=model,
                    provider="vllm",
                )
            elif e.response.status_code == 400:
                error_msg = "vLLM bad request (400)"
                try:
                    error_data = e.response.json()
                    if "message" in error_data:
                        error_msg = f"vLLM validation error: {error_data['message']}"
                except:
                    pass
                raise ProviderError(error_msg, provider="vllm", original_error=e)
            elif e.response.status_code == 500:
                raise ProviderError(
                    "vLLM internal server error (500). This is often transient in vLLM - retrying.",
                    provider="vllm",
                    original_error=e,
                )
            elif e.response.status_code == 503:
                raise ProviderError(
                    "vLLM server is overloaded or unavailable (503)",
                    provider="vllm",
                    original_error=e,
                )
            else:
                raise ProviderError(
                    f"vLLM API error: {e.response.status_code}", provider="vllm", original_error=e
                )
        except httpx.TimeoutException as e:
            raise ProviderError(
                f"vLLM request timed out after {self.timeout}s. "
                "vLLM can hang intermittently - consider using --disable-custom-all-reduce flag.",
                provider="vllm",
                original_error=e,
            )
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Failed to connect to vLLM server at {self.base_url}. "
                f"Make sure vLLM server is running.",
                provider="vllm",
                original_error=e,
            )
        except httpx.RequestError as e:
            raise ProviderError(
                f"Failed to connect to vLLM server at {self.base_url}",
                provider="vllm",
                original_error=e,
            )
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ModelError(f"Failed to parse vLLM response: {e}", model=model, provider="vllm")

    async def _stream_impl(
        self,
        prompt: Optional[str] = None,
        model: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream response from vLLM server with optional tool support.

        NOTE: Streaming mode does NOT include logprobs in the stream.
        Tool calls are streamed incrementally as deltas.

        Args:
            prompt: User prompt (for simple queries)
            model: Model name (must match what's loaded in vLLM)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            messages: Conversation history (OpenAI format)
            tools: Tool definitions (OpenAI format)
            tool_choice: Tool selection strategy
            **kwargs: Additional vLLM parameters

        Yields:
            Content chunks or tool call deltas as they arrive

        Example:
            >>> async for chunk in provider.stream(
            ...     prompt="Count to 5",
            ...     model="meta-llama/Llama-3-8B-Instruct"
            ... ):
            ...     print(chunk, end='', flush=True)
        """
        parallel_tool_calls = kwargs.pop("parallel_tool_calls", True)

        # Build messages
        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if prompt:
                messages.append({"role": "user", "content": prompt})
        elif prompt and messages:
            messages.append({"role": "user", "content": prompt})

        # Build request payload
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            **kwargs,
        }

        # Add tool parameters if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
            if parallel_tool_calls:
                payload["parallel_tool_calls"] = True

        try:
            async with self.client.stream(
                "POST", f"{self.base_url}/chat/completions", json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.strip() or not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(data_str)
                        if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                            delta = chunk_data["choices"][0].get("delta", {})

                            # Stream content if present
                            if "content" in delta and delta["content"]:
                                yield delta["content"]

                            # Note: Tool calls are also streamed as deltas
                            # but we yield content only for simplicity
                            # Full tool call handling should be done with complete()

                    except json.JSONDecodeError:
                        continue

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelError(
                    f"Model '{model}' not found in vLLM server.", model=model, provider="vllm"
                )
            elif e.response.status_code == 400:
                error_msg = "vLLM bad request (400)"
                try:
                    error_data = e.response.json()
                    if "message" in error_data:
                        error_msg = f"vLLM validation error: {error_data['message']}"
                except:
                    pass
                raise ProviderError(error_msg, provider="vllm", original_error=e)
            elif e.response.status_code in (500, 503):
                raise ProviderError(
                    f"vLLM server error ({e.response.status_code})",
                    provider="vllm",
                    original_error=e,
                )
            else:
                raise ProviderError(
                    f"vLLM API error: {e.response.status_code}", provider="vllm", original_error=e
                )
        except httpx.TimeoutException as e:
            raise ProviderError(
                f"vLLM streaming timed out after {self.timeout}s.",
                provider="vllm",
                original_error=e,
            )
        except (httpx.ConnectError, httpx.RequestError) as e:
            raise ProviderError(
                f"Failed to connect to vLLM server at {self.base_url}",
                provider="vllm",
                original_error=e,
            )

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for vLLM model.

        vLLM is self-hosted, so there are no API costs.

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

        Raises:
            ProviderError: If unable to fetch models
        """
        try:
            response = await self.client.get(f"{self.base_url}/models")
            response.raise_for_status()
            data = response.json()
            return [model["id"] for model in data.get("data", [])]
        except Exception as e:
            raise ProviderError(f"Failed to list models from vLLM server: {e}", provider="vllm")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
