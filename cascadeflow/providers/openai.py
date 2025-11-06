"""OpenAI provider implementation with tool calling support."""

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from ..exceptions import ModelError, ProviderError
from .base import BaseProvider, ModelResponse, RetryConfig

# ==============================================================================
# REASONING MODEL SUPPORT
# ==============================================================================


class ReasoningModelInfo:
    """
    Information about reasoning model capabilities and limitations.

    Used for auto-detection and configuration across all providers.
    Unified type that matches TypeScript ReasoningModelInfo interface.
    """

    def __init__(
        self,
        is_reasoning: bool = False,
        provider: str = "openai",
        supports_streaming: bool = True,
        supports_tools: bool = True,
        supports_system_messages: bool = True,
        supports_reasoning_effort: bool = False,
        supports_extended_thinking: bool = False,
        requires_max_completion_tokens: bool = False,
        requires_thinking_budget: bool = False,
        supports_logprobs: bool = True,
        supports_temperature: bool = True,
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
        self.supports_logprobs = supports_logprobs  # Whether model supports logprobs
        self.supports_temperature = supports_temperature  # Whether model supports temperature param


def get_reasoning_model_info(model_name: str) -> ReasoningModelInfo:
    """
    Detect if model is a reasoning model and get its capabilities.

    This function provides automatic detection of reasoning models and their
    capabilities, enabling zero-configuration usage. Just specify the model name
    and all limitations/features are handled automatically.

    Args:
        model_name: Model name to check (case-insensitive)

    Returns:
        ReasoningModelInfo with capability flags

    Examples:
        >>> info = get_reasoning_model_info('o1-mini')
        >>> print(info.is_reasoning)  # True
        >>> print(info.supports_tools)  # False

        >>> info = get_reasoning_model_info('gpt-4o')
        >>> print(info.is_reasoning)  # False
        >>> print(info.supports_tools)  # True
    """
    name = model_name.lower()

    # O1 preview/mini (original reasoning models)
    if "o1-preview" in name or "o1-mini" in name:
        return ReasoningModelInfo(
            is_reasoning=True,
            supports_streaming=True,
            supports_tools=False,
            supports_system_messages=False,
            supports_reasoning_effort=False,
            requires_max_completion_tokens=False,
        )

    # O1 (2024-12-17) - more capable with reasoning_effort
    if "o1-2024-12-17" in name or name == "o1":
        return ReasoningModelInfo(
            is_reasoning=True,
            supports_streaming=False,  # Not supported
            supports_tools=False,
            supports_system_messages=False,
            supports_reasoning_effort=True,
            requires_max_completion_tokens=True,
        )

    # O3-mini (future reasoning model)
    if "o3-mini" in name:
        return ReasoningModelInfo(
            is_reasoning=True,
            supports_streaming=True,
            supports_tools=True,
            supports_system_messages=False,
            supports_reasoning_effort=True,
            requires_max_completion_tokens=True,
        )

    # GPT-5 series (reasoning model like o1/o3)
    if name.startswith("gpt-5"):
        return ReasoningModelInfo(
            is_reasoning=True,  # GPT-5 is a reasoning model with internal reasoning tokens
            supports_streaming=True,
            supports_tools=True,
            supports_system_messages=True,
            supports_reasoning_effort=False,  # GPT-5 doesn't use reasoning_effort parameter
            requires_max_completion_tokens=True,  # GPT-5 requires this parameter
            supports_logprobs=False,  # GPT-5 doesn't support logprobs
            supports_temperature=False,  # GPT-5 only supports temperature=1 (default)
        )

    # Not a reasoning model - standard GPT model
    return ReasoningModelInfo(
        is_reasoning=False,
        supports_streaming=True,
        supports_tools=True,
        supports_system_messages=True,
        supports_reasoning_effort=False,
        requires_max_completion_tokens=False,
    )


# ==============================================================================


class OpenAIProvider(BaseProvider):
    """
    OpenAI provider for GPT models with tool calling support.

    Supports: GPT-3.5, GPT-4, GPT-4 Turbo, GPT-4o, GPT-4o mini, GPT-5 (when available)

    Enhanced with full logprobs support and intelligent defaults for token-level confidence.

    Uses hybrid confidence (logprobs + semantic) for maximum accuracy.

    Example:
        >>> # Basic usage (automatic retry on failures)
        >>> provider = OpenAIProvider(api_key="sk-...")
        >>>
        >>> # Non-streaming (traditional):
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="gpt-3.5-turbo"
        ... )
        >>> print(f"Confidence: {response.confidence}")
        >>>
        >>> # Streaming (new):
        >>> async for chunk in provider.stream(
        ...     prompt="What is AI?",
        ...     model="gpt-3.5-turbo"
        ... ):
        ...     print(chunk, end='', flush=True)
        >>>
        >>> # Tool calling (Step 1.3 - NEW!):
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
        >>> response = await provider.complete_with_tools(
        ...     messages=[{"role": "user", "content": "What's the weather in Paris?"}],
        ...     tools=tools,
        ...     model="gpt-4o-mini"
        ... )
        >>> if response.tool_calls:
        ...     for tool_call in response.tool_calls:
        ...         print(f"Tool: {tool_call['name']}")
        ...         print(f"Args: {tool_call['arguments']}")
        >>>
        >>> # Custom retry configuration
        >>> custom_retry = RetryConfig(
        ...     max_attempts=5,
        ...     rate_limit_backoff=60.0
        ... )
        >>> provider = OpenAIProvider(api_key="sk-...", retry_config=custom_retry)
        >>>
        >>> # Check retry metrics
        >>> print(provider.get_retry_metrics())
    """

    def __init__(self, api_key: Optional[str] = None, retry_config: Optional[RetryConfig] = None):
        """
        Initialize OpenAI provider with automatic retry logic.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
            retry_config: Custom retry configuration (optional). If None, uses defaults:
                - max_attempts: 3
                - initial_delay: 1.0s
                - rate_limit_backoff: 30.0s
        """
        # Call parent init to load API key, check logprobs support, and setup retry
        super().__init__(api_key=api_key, retry_config=retry_config)

        # Verify API key is set
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Please set OPENAI_API_KEY environment "
                "variable or pass api_key parameter."
            )

        # Initialize HTTP client with the loaded API key
        self.base_url = "https://api.openai.com/v1"
        # Increased timeout for reasoning models (GPT-5, o1, o3) which can take 60-120+ seconds
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            timeout=180.0,  # 3 minutes for reasoning models
        )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment."""
        return os.getenv("OPENAI_API_KEY")

    def _check_logprobs_support(self) -> bool:
        """
        OpenAI supports native logprobs for confidence analysis.

        Returns:
            True - OpenAI provides native logprobs
        """
        return True

    def _convert_tools_to_openai(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert tools from universal format to OpenAI format.

        Universal format:
        {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {...}  # JSON Schema
        }

        OpenAI format:
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {...}  # JSON Schema
            }
        }

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
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            openai_tools.append(openai_tool)

        return openai_tools

    def _parse_tool_calls(self, choice: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
        """
        Parse tool calls from OpenAI response into universal format.

        OpenAI format:
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": '{"location": "Paris"}'
            }
        }

        Universal format:
        {
            "id": "call_abc123",
            "type": "function",
            "name": "get_weather",
            "arguments": {"location": "Paris"}  # Parsed JSON
        }

        Args:
            choice: OpenAI response choice

        Returns:
            List of tool calls in universal format, or None
        """
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            return None

        universal_tool_calls = []
        for tool_call in tool_calls:
            try:
                # Parse arguments JSON string
                arguments_str = tool_call["function"]["arguments"]
                arguments = json.loads(arguments_str) if arguments_str else {}

                universal_call = {
                    "id": tool_call["id"],
                    "type": tool_call["type"],
                    "name": tool_call["function"]["name"],
                    "arguments": arguments,
                }
                universal_tool_calls.append(universal_call)
            except (json.JSONDecodeError, KeyError) as e:
                # Log error but continue processing other tool calls
                if os.getenv("DEBUG_TOOLS"):
                    print(f"⚠️ Error parsing tool call: {e}")
                continue

        return universal_tool_calls if universal_tool_calls else None

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict[str, Any]]] = None,
        model: str = "gpt-4o-mini",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Complete a conversation with tool calling support.

        This method enables the model to call tools/functions during generation.
        The model can request to call multiple tools in parallel.

        STEP 1.3: OpenAI Provider Tool Integration
        - Implements universal tool schema format
        - Uses adapter pattern for format conversion
        - OpenAI format as baseline for other providers


        Args:
            messages: List of conversation messages in format:
                [{"role": "user", "content": "What's the weather?"}]
                Supports roles: system, user, assistant, tool
            tools: List of available tools in universal format (optional):
                [{
                    "name": "get_weather",
                    "description": "Get current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"}
                        },
                        "required": ["location"]
                    }
                }]
            model: Model name (e.g., 'gpt-4o-mini', 'gpt-4', 'gpt-4-turbo')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            tool_choice: Control tool calling behavior:
                - None/omitted: Model decides
                - "auto": Model decides (explicit)
                - "none": Prevent tool calling
                - {"type": "function", "function": {"name": "get_weather"}}: Force specific tool
            **kwargs: Additional OpenAI parameters

        Returns:
            ModelResponse with tool_calls populated if model wants to call tools:
                response.tool_calls = [
                    {
                        "id": "call_abc123",
                        "type": "function",
                        "name": "get_weather",
                        "arguments": {"location": "Paris"}
                    }
                ]

        Raises:
            ProviderError: If API call fails
            ModelError: If model execution fails

        Example:
            >>> # Define tools
            >>> tools = [{
            ...     "name": "search_web",
            ...     "description": "Search the web for information",
            ...     "parameters": {
            ...         "type": "object",
            ...         "properties": {
            ...             "query": {"type": "string", "description": "Search query"}
            ...         },
            ...         "required": ["query"]
            ...     }
            ... }]
            >>>
            >>> # Call with tools
            >>> messages = [{"role": "user", "content": "Search for AI news"}]
            >>> response = await provider.complete_with_tools(
            ...     messages=messages,
            ...     tools=tools,
            ...     model="gpt-4o-mini"
            ... )
            >>>
            >>> # Check if model wants to call tools
            >>> if response.tool_calls:
            ...     for tool_call in response.tool_calls:
            ...         print(f"Calling: {tool_call['name']}")
            ...         print(f"Arguments: {tool_call['arguments']}")
            ...         # Execute tool and add result to messages
            ...         # Then call complete_with_tools again with tool results
        """
        start_time = time.time()

        # Convert tools to OpenAI format
        openai_tools = self._convert_tools_to_openai(tools) if tools else None

        # Build request payload
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }

        # Add tools if provided
        if openai_tools:
            payload["tools"] = openai_tools

            # Add tool_choice if specified
            if tool_choice:
                payload["tool_choice"] = tool_choice

        try:
            # Make API request (retry handled by parent class)
            response = await self.client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()

            # Extract response
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content", "")  # May be None if only tool calls
            prompt_tokens = data["usage"]["prompt_tokens"]
            completion_tokens = data["usage"]["completion_tokens"]
            tokens_used = data["usage"]["total_tokens"]

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate cost (automatically uses LiteLLM if available)
            cost = self.calculate_accurate_cost(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=tokens_used,
            )

            # Parse tool calls if present
            tool_calls = self._parse_tool_calls(choice)

            # ============================================================
            # NEW (Week 2 Day 4): Determine confidence method for tool calls
            # ============================================================
            if tool_calls:
                # Model successfully generated tool calls
                confidence_method = "tool-call-present"
                confidence = 0.9  # High confidence for successful tool calls

                # Optional: More sophisticated confidence for tool calls
                # Could analyze tool call quality, parameter completeness, etc.
                if temperature == 0:
                    confidence = 0.95  # Even higher for deterministic
                elif temperature > 1.0:
                    confidence = 0.85  # Slightly lower for high temperature
            else:
                # Tools were available but model chose text response
                if openai_tools:
                    confidence_method = "tool-available-text-chosen"
                    confidence = 0.7  # Lower confidence when tools not used
                else:
                    # No tools provided (shouldn't happen in this method)
                    confidence_method = "text-only"
                    confidence = 0.8
            # ============================================================

            # Build response metadata
            response_metadata = {
                "finish_reason": choice["finish_reason"],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "has_tool_calls": bool(tool_calls),
                "confidence_method": confidence_method,  # ← NEW!
                "tool_choice_reasoning": (
                    "model_generated_tool_calls" if tool_calls else "model_chose_text_response"
                ),
            }

            # Build model response
            model_response = ModelResponse(
                content=content or "",  # Empty string if only tool calls
                model=model,
                provider="openai",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,  # ← Now uses calculated confidence
                latency_ms=latency_ms,
                metadata=response_metadata,
            )

            # Add tool calls to response
            if tool_calls:
                model_response.tool_calls = tool_calls

            return model_response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError("Invalid OpenAI API key", provider="openai", original_error=e)
            elif e.response.status_code == 429:
                raise ProviderError(
                    "OpenAI rate limit exceeded", provider="openai", original_error=e
                )
            else:
                raise ProviderError(
                    f"OpenAI API error: {e.response.status_code}",
                    provider="openai",
                    original_error=e,
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to OpenAI API", provider="openai", original_error=e
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse OpenAI response: {e}", model=model, provider="openai"
            )

    async def _complete_impl(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Complete a prompt using OpenAI API (internal implementation with automatic retry).

        This is the internal implementation called by the public complete() method.
        Retry logic is handled automatically by the parent class.

        method and component breakdown for test validation and debugging.

        Args:
            prompt: User prompt
            model: Model name (e.g., 'gpt-3.5-turbo', 'gpt-4', 'gpt-4o-mini')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            **kwargs: Additional OpenAI parameters including:
                - logprobs (bool): Enable logprobs (default: True for accurate confidence)
                - top_logprobs (int): Get top-k alternatives (default: 5)

        Returns:
            ModelResponse with standardized format (enhanced with logprobs by default)

        Raises:
            ProviderError: If API call fails (will be caught by retry logic)
            ModelError: If model execution fails (will be caught by retry logic)
        """
        start_time = time.time()

        # INTELLIGENT DEFAULT: Request logprobs unless explicitly disabled
        # This ensures accurate multi-signal confidence estimation
        if "logprobs" not in kwargs:
            kwargs["logprobs"] = self.should_request_logprobs(**kwargs)

        # Extract logprobs parameters
        logprobs_enabled = kwargs.pop("logprobs", False)
        top_logprobs = kwargs.pop("top_logprobs", 5)  # Default to 5

        # Get reasoning model info for auto-configuration
        model_info = get_reasoning_model_info(model)

        # Build messages (handle system prompt for reasoning models)
        messages = []
        if system_prompt:
            if model_info.supports_system_messages:
                messages.append({"role": "system", "content": system_prompt})
            else:
                # Prepend system prompt to first user message
                prompt = f"{system_prompt}\n\n{prompt}"
        messages.append({"role": "user", "content": prompt})

        # Check if this is GPT-5 model for correct token parameter
        is_gpt5 = model.lower().startswith("gpt-5")

        # Build request payload with correct parameters
        payload = {
            "model": model,
            "messages": messages,
        }

        # Add temperature if supported by model
        if model_info.supports_temperature:
            payload["temperature"] = temperature

        # Use correct token limit parameter
        if is_gpt5 or model_info.requires_max_completion_tokens:
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens

        # Add reasoning_effort if supported and provided
        if model_info.supports_reasoning_effort and "reasoning_effort" in kwargs:
            payload["reasoning_effort"] = kwargs.pop("reasoning_effort")

        # Add remaining kwargs
        payload.update(kwargs)

        # Add logprobs if requested and supported by model
        if logprobs_enabled and model_info.supports_logprobs:
            payload["logprobs"] = True
            if top_logprobs:
                payload["top_logprobs"] = min(top_logprobs, 20)  # OpenAI max is 20

        try:
            # Make API request (retry handled by parent class)
            response = await self.client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()

            # Extract response
            choice = data["choices"][0]
            content = choice["message"]["content"]
            prompt_tokens = data["usage"]["prompt_tokens"]
            completion_tokens = data["usage"]["completion_tokens"]
            tokens_used = data["usage"]["total_tokens"]

            # Extract reasoning tokens for o1/o3 models (if available)
            reasoning_tokens = None
            if "completion_tokens_details" in data["usage"]:
                completion_details = data["usage"]["completion_tokens_details"]
                if "reasoning_tokens" in completion_details:
                    reasoning_tokens = completion_details["reasoning_tokens"]

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate accurate cost using input/output split
            cost = self.estimate_cost(
                tokens_used, model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
            )

            # ============================================================
            # Now captures full analysis for test validation
            # OpenAI has REAL logprobs - uses hybrid confidence!
            # ============================================================

            # Parse logprobs if available
            tokens_list = []
            logprobs_list = []
            top_logprobs_list = []

            if logprobs_enabled and "logprobs" in choice and choice["logprobs"]:
                logprobs_data = choice["logprobs"]

                if "content" in logprobs_data and logprobs_data["content"]:
                    for token_data in logprobs_data["content"]:
                        # Extract token
                        tokens_list.append(token_data["token"])

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

            # Build comprehensive metadata for confidence system
            metadata_for_confidence = {
                "finish_reason": choice["finish_reason"],
                "temperature": temperature,
                "query": prompt,
                "model": model,
                "logprobs": logprobs_list if logprobs_list else None,
                "tokens": tokens_list if tokens_list else None,
            }

            # Get FULL confidence analysis (not just float)
            # OpenAI has real logprobs - will use hybrid method!
            if self._confidence_estimator:
                confidence_analysis = self._confidence_estimator.estimate(
                    response=content,
                    query=prompt,
                    logprobs=logprobs_list if logprobs_list else None,  # ← REAL logprobs!
                    tokens=tokens_list if tokens_list else None,
                    temperature=temperature,
                    metadata=metadata_for_confidence,
                )
                confidence = confidence_analysis.final_confidence
                confidence_method = confidence_analysis.method_used  # "multi-signal-hybrid"!
                confidence_components = confidence_analysis.components or {}
            else:
                # Fallback if estimator not available
                confidence = self.calculate_confidence(content, metadata_for_confidence)
                confidence_method = "legacy"
                confidence_components = {}

            # Optional debug logging (enable with DEBUG_CONFIDENCE=1)
            if os.getenv("DEBUG_CONFIDENCE"):
                print("🔍 OpenAI Confidence Debug:")
                print(f"  Query: {prompt[:50]}...")
                print(f"  Response: {content[:50]}...")
                print(f"  Has logprobs: {bool(logprobs_list)}")
                print(f"  Num tokens: {len(tokens_list) if tokens_list else 0}")
                print(f"  Confidence: {confidence:.3f}")
                print(f"  Method: {confidence_method}")
                if confidence_components:
                    print("  Components:")
                    for comp, val in confidence_components.items():
                        print(f"    • {comp:20s}: {val:.3f}")

            # Build response metadata WITH confidence details
            response_metadata = {
                "finish_reason": choice["finish_reason"],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                # NEW: Add confidence analysis details for test validation
                "query": prompt,
                "confidence_method": confidence_method,
                "confidence_components": confidence_components,
            }

            # Add reasoning tokens if available (for o1/o3 models)
            if reasoning_tokens is not None:
                response_metadata["reasoning_tokens"] = reasoning_tokens

            # Build base response
            model_response = ModelResponse(
                content=content,
                model=model,
                provider="openai",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata=response_metadata,
            )

            # Add logprobs data to response if available
            if logprobs_list:
                model_response.tokens = tokens_list
                model_response.logprobs = logprobs_list
                model_response.top_logprobs = top_logprobs_list
                model_response.metadata["has_logprobs"] = True
                model_response.metadata["estimated"] = False
            elif logprobs_enabled:
                # Logprobs were requested but not available - use fallback
                model_response = self.add_logprobs_fallback(
                    model_response, temperature, base_confidence=0.85  # OpenAI is high quality
                )

            return model_response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError("Invalid OpenAI API key", provider="openai", original_error=e)
            elif e.response.status_code == 429:
                raise ProviderError(
                    "OpenAI rate limit exceeded", provider="openai", original_error=e
                )
            else:
                raise ProviderError(
                    f"OpenAI API error: {e.response.status_code}",
                    provider="openai",
                    original_error=e,
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to OpenAI API", provider="openai", original_error=e
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse OpenAI response: {e}", model=model, provider="openai"
            )

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
        Stream response from OpenAI API (internal implementation with automatic retry).

        This is the internal implementation called by the public stream() method.
        Retry logic is handled automatically by the parent class.

        This method enables real-time streaming for better UX. Yields chunks
        as they arrive from the API.

        NOTE: Streaming mode does NOT include logprobs in the stream, but
        the StreamingCascadeWrapper will call complete() separately to get
        the full result with confidence scores.

        Args:
            prompt: User prompt
            model: Model name (e.g., 'gpt-3.5-turbo', 'gpt-4', 'gpt-4o-mini')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            **kwargs: Additional OpenAI parameters

        Yields:
            Content chunks as they arrive from the API

        Raises:
            ProviderError: If API call fails (will be caught by retry logic)
            ModelError: If model execution fails (will be caught by retry logic)

        Example:
            >>> provider = OpenAIProvider()
            >>> async for chunk in provider.stream(
            ...     prompt="What is Python?",
            ...     model="gpt-3.5-turbo"
            ... ):
            ...     print(chunk, end='', flush=True)
            Python is a high-level programming language...
        """
        # Build messages
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
            "stream": True,  # Enable streaming
            **kwargs,
        }

        try:
            # Make streaming API request (retry handled by parent class)
            async with self.client.stream(
                "POST", f"{self.base_url}/chat/completions", json=payload
            ) as response:
                response.raise_for_status()

                # Process SSE stream
                async for line in response.aiter_lines():
                    # Skip empty lines
                    if not line.strip():
                        continue

                    # Skip if not a data line
                    if not line.startswith("data: "):
                        continue

                    # Extract JSON data
                    data_str = line[6:]  # Remove "data: " prefix

                    # Check for stream end
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        # Parse JSON chunk
                        chunk_data = json.loads(data_str)

                        # Extract content delta
                        if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                            delta = chunk_data["choices"][0].get("delta", {})

                            if "content" in delta and delta["content"]:
                                # Yield content chunk
                                yield delta["content"]

                    except json.JSONDecodeError:
                        # Skip malformed JSON
                        continue

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError("Invalid OpenAI API key", provider="openai", original_error=e)
            elif e.response.status_code == 429:
                raise ProviderError(
                    "OpenAI rate limit exceeded", provider="openai", original_error=e
                )
            else:
                raise ProviderError(
                    f"OpenAI API error: {e.response.status_code}",
                    provider="openai",
                    original_error=e,
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to OpenAI API", provider="openai", original_error=e
            )

    def estimate_cost(
        self,
        tokens: int,
        model: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ) -> float:
        """
        Estimate cost for OpenAI model with accurate input/output pricing.

        OpenAI charges different rates for input vs output tokens.
        This method provides accurate cost calculation when token split is available.

        Args:
            tokens: Total tokens (fallback if split not available)
            model: Model name (e.g., 'gpt-4o-mini', 'gpt-4', 'gpt-3.5-turbo')
            prompt_tokens: Input tokens (if available)
            completion_tokens: Output tokens (if available)

        Returns:
            Estimated cost in USD
        """
        # OpenAI pricing per 1K tokens (as of January 2025)
        # Source: https://openai.com/api/pricing/
        pricing = {
            # GPT-5 series (current flagship - released August 2025)
            # 50% cheaper input than GPT-4o, superior performance on coding, reasoning, math
            "gpt-5": {"input": 0.00125, "output": 0.010},
            "gpt-5-mini": {"input": 0.00025, "output": 0.002},
            "gpt-5-nano": {"input": 0.00005, "output": 0.0004},
            "gpt-5-chat-latest": {"input": 0.00125, "output": 0.010},
            # GPT-4o series (previous flagship)
            "gpt-4o": {"input": 0.0025, "output": 0.010},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            # O1 series (reasoning models)
            "o1-preview": {"input": 0.015, "output": 0.060},
            "o1-mini": {"input": 0.003, "output": 0.012},
            "o1": {"input": 0.015, "output": 0.060},
            "o1-2024-12-17": {"input": 0.015, "output": 0.060},
            # O3 series (reasoning models)
            "o3-mini": {"input": 0.001, "output": 0.005},
            # GPT-4 series (previous generation)
            "gpt-4-turbo": {"input": 0.010, "output": 0.030},
            "gpt-4": {"input": 0.030, "output": 0.060},
            # GPT-3.5 series (deprecated - use gpt-4o-mini instead)
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        }

        # Find model pricing
        model_pricing = None
        model_lower = model.lower()
        for prefix, rates in pricing.items():
            if model_lower.startswith(prefix):
                model_pricing = rates
                break

        # Default to GPT-4 pricing if unknown
        if not model_pricing:
            model_pricing = {"input": 0.030, "output": 0.060}

        # Calculate accurate cost if we have the split
        if prompt_tokens is not None and completion_tokens is not None:
            input_cost = (prompt_tokens / 1000) * model_pricing["input"]
            output_cost = (completion_tokens / 1000) * model_pricing["output"]
            return input_cost + output_cost

        # Fallback: estimate with blended rate
        blended_rate = (model_pricing["input"] * 0.3) + (model_pricing["output"] * 0.7)
        return (tokens / 1000) * blended_rate

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
