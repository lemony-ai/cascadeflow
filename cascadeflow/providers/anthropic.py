"""Anthropic Claude provider implementation with tool calling support."""

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
        provider: str = "anthropic",
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
    Detect if model supports extended thinking and get its capabilities.

    This function provides automatic detection of reasoning models and their
    capabilities, enabling zero-configuration usage. Just specify the model name
    and all limitations/features are handled automatically.

    Note: Claude Sonnet 4.5 was released September 29, 2025 with extended thinking.

    Args:
        model_name: Model name to check (case-insensitive)

    Returns:
        ReasoningModelInfo with capability flags

    Examples:
        >>> info = get_reasoning_model_info('claude-sonnet-4-5')
        >>> print(info.is_reasoning)  # True
        >>> print(info.supports_extended_thinking)  # True

        >>> info = get_reasoning_model_info('claude-3-5-sonnet')
        >>> print(info.is_reasoning)  # False
        >>> print(info.supports_tools)  # True
    """
    model_lower = model_name.lower().replace("_", "-")

    # Detect Claude Sonnet 4.5 with extended thinking (released Sept 29, 2025)
    is_sonnet_45 = any(
        pattern in model_lower
        for pattern in [
            "claude-sonnet-4-5",
            "claude-sonnet-4.5",
            "claude-4-5-sonnet",
            "claude-4.5-sonnet",
            "sonnet-4-5",
            "sonnet-4.5",
        ]
    )

    if is_sonnet_45:
        # Claude Sonnet 4.5 with extended thinking capabilities
        return ReasoningModelInfo(
            is_reasoning=True,
            provider="anthropic",
            supports_streaming=True,
            supports_tools=True,
            supports_system_messages=True,
            supports_extended_thinking=True,
            requires_thinking_budget=True,  # Extended thinking requires token budget
        )

    # All other Claude models have standard capabilities
    return ReasoningModelInfo(
        is_reasoning=False,
        provider="anthropic",
        supports_streaming=True,
        supports_tools=True,
        supports_system_messages=True,
        supports_extended_thinking=False,
        requires_thinking_budget=False,
    )


# ==============================================================================
# PROVIDER IMPLEMENTATION
# ==============================================================================


class AnthropicProvider(BaseProvider):
    """
    Anthropic provider for Claude models with tool calling support.

    Supports: Claude 3 (Opus, Sonnet, Haiku), Claude 3.5, Claude 4, etc.

    Enhanced with full retry logic and intelligent confidence estimation.

    confidence estimation (query difficulty + alignment + semantic quality).

    Note: Anthropic does NOT support native logprobs. The system automatically
    uses advanced semantic confidence estimation instead.

    Example:
        >>> # Basic usage (automatic retry on failures)
        >>> provider = AnthropicProvider(api_key="sk-ant-...")
        >>>
        >>> # Non-streaming (traditional):
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="claude-3-sonnet-20240229"
        ... )
        >>> print(f"Confidence: {response.confidence:.2f}")
        >>>
        >>> # Streaming (new):
        >>> async for chunk in provider.stream(
        ...     prompt="What is AI?",
        ...     model="claude-3-sonnet-20240229"
        ... ):
        ...     print(chunk, end='', flush=True)
        >>>
        >>> # Tool calling (Step 1.4 - NEW!):
        >>> tools = [{
        ...     "name": "get_weather",
        ...     "description": "Get weather for a location",
        ...     "parameters": {
        ...         "type": "object",
        ...         "properties": {
        ...             "location": {"type": "string"}
        ...         },
        ...         "required": ["location"]
        ...     }
        ... }]
        >>> response = await provider.complete_with_tools(
        ...     messages=[{"role": "user", "content": "What's the weather in Paris?"}],
        ...     tools=tools,
        ...     model="claude-sonnet-4-20250514"
        ... )
        >>> if response.tool_calls:
        ...     for tool_call in response.tool_calls:
        ...         print(f"Tool: {tool_call['name']}")
        ...         print(f"Args: {tool_call['arguments']}")
    """

    def __init__(self, api_key: Optional[str] = None, retry_config: Optional[RetryConfig] = None):
        """
        Initialize Anthropic provider with automatic retry logic.

        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
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
                "Anthropic API key not found. Please set ANTHROPIC_API_KEY environment "
                "variable or pass api_key parameter."
            )

        # Initialize HTTP client with the loaded API key
        self.base_url = "https://api.anthropic.com/v1"
        self.api_version = "2023-06-01"
        self.client = httpx.AsyncClient(
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": self.api_version,
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment."""
        return os.getenv("ANTHROPIC_API_KEY")

    def _check_logprobs_support(self) -> bool:
        """
        Anthropic does not support logprobs natively.

        Returns:
            False - Uses automatic semantic confidence estimation
        """
        return False

    def _convert_tools_to_anthropic(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert tools from universal format to Anthropic format.

        Universal format:
        {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {...}  # JSON Schema
        }

        Anthropic format:
        {
            "name": "get_weather",
            "description": "Get weather for a location",
            "input_schema": {...}  # JSON Schema (note: input_schema, not parameters)
        }

        Args:
            tools: List of tools in universal format

        Returns:
            List of tools in Anthropic format
        """
        if not tools:
            return []

        anthropic_tools = []
        for tool in tools:
            anthropic_tool = {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
            }
            anthropic_tools.append(anthropic_tool)

        return anthropic_tools

    def _parse_tool_calls(self, content: list[dict[str, Any]]) -> Optional[list[dict[str, Any]]]:
        """
        Parse tool calls from Anthropic response into universal format.

        Anthropic format (in content blocks):
        {
            "type": "tool_use",
            "id": "toolu_abc123",
            "name": "get_weather",
            "input": {"location": "Paris"}  # Already parsed JSON
        }

        Universal format:
        {
            "id": "toolu_abc123",
            "type": "function",
            "name": "get_weather",
            "arguments": {"location": "Paris"}  # Dict
        }

        Args:
            content: Anthropic response content blocks

        Returns:
            List of tool calls in universal format, or None
        """
        if not content:
            return None

        tool_calls = []
        for block in content:
            if block.get("type") == "tool_use":
                try:
                    universal_call = {
                        "id": block["id"],
                        "type": "function",  # Universal format uses "function"
                        "name": block["name"],
                        "arguments": block.get("input", {}),  # Anthropic uses "input"
                    }
                    tool_calls.append(universal_call)
                except KeyError as e:
                    # Log error but continue processing other tool calls
                    if os.getenv("DEBUG_TOOLS"):
                        print(f"⚠️ Error parsing Anthropic tool call: {e}")
                    continue

        return tool_calls if tool_calls else None

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict[str, Any]]] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: Optional[dict[str, str]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Complete a conversation with tool calling support.

        This method enables Claude to call tools/functions during generation.
        Claude can request to call multiple tools in parallel.

        STEP 1.4: Anthropic Provider Tool Integration
        - Converts from universal format to Anthropic format
        - Handles input_schema vs parameters difference
        - Parses tool_use blocks from responses

        - Tracks "tool-call-present" when tools are called
        - Tracks "tool-available-text-chosen" when tools available but text chosen
        - Tracks "multi-signal-hybrid" when no tools provided

        Args:
            messages: List of conversation messages in format:
                [{"role": "user", "content": "What's the weather?"}]
                Supports roles: user, assistant
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
            model: Model name (e.g., 'claude-sonnet-4-20250514', 'claude-3-5-sonnet-20241022')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            tool_choice: Control tool calling behavior:
                - None/omitted: Model decides
                - {"type": "auto"}: Model decides (explicit)
                - {"type": "any"}: Must use a tool
                - {"type": "tool", "name": "get_weather"}: Force specific tool
            **kwargs: Additional Anthropic parameters

        Returns:
            ModelResponse with tool_calls populated if model wants to call tools:
                response.tool_calls = [
                    {
                        "id": "toolu_abc123",
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
            ...     "description": "Search the web",
            ...     "parameters": {
            ...         "type": "object",
            ...         "properties": {
            ...             "query": {"type": "string"}
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
            ...     model="claude-sonnet-4-20250514"
            ... )
            >>>
            >>> # Check if model wants to call tools
            >>> if response.tool_calls:
            ...     for tool_call in response.tool_calls:
            ...         print(f"Calling: {tool_call['name']}")
            ...         print(f"Arguments: {tool_call['arguments']}")
        """
        start_time = time.time()

        # Convert tools to Anthropic format
        anthropic_tools = self._convert_tools_to_anthropic(tools) if tools else None

        # Build request payload
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
            **kwargs,
        }

        # Add tools if provided
        if anthropic_tools:
            payload["tools"] = anthropic_tools

            # Add tool_choice if specified
            if tool_choice:
                payload["tool_choice"] = tool_choice

        try:
            # Make API request (retry handled by parent class)
            response = await self.client.post(f"{self.base_url}/messages", json=payload)
            response.raise_for_status()

            data = response.json()

            # Extract response content (Anthropic returns array of content blocks)
            content_blocks = data.get("content", [])

            # Extract text content (if any)
            text_content = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    text_content += block.get("text", "")

            # Parse tool calls from content blocks
            tool_calls = self._parse_tool_calls(content_blocks)

            # Get usage stats
            usage = data.get("usage", {})
            prompt_tokens = usage.get("input_tokens", 0)
            completion_tokens = usage.get("output_tokens", 0)
            tokens_used = prompt_tokens + completion_tokens

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate cost using LiteLLM if available, otherwise fallback
            cost = self.calculate_accurate_cost(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=tokens_used,
            )

            # ============================================================
            # Determine confidence method based on tool call outcomes
            # ============================================================

            # Extract user query from messages for confidence estimation
            user_query = ""
            for msg in messages:
                if msg.get("role") == "user":
                    user_query = msg.get("content", "")
                    break

            if tool_calls:
                # Model successfully generated tool calls
                confidence_method = "tool-call-present"
                confidence = 0.9  # High confidence for successful tool calls

                # Temperature-based confidence adjustment
                if temperature == 0:
                    confidence = 0.95  # Even higher for deterministic calls
                elif temperature > 0.9:
                    confidence = 0.85  # Slightly lower for creative calls

                confidence_components = {"base": 0.9, "temperature_adjustment": confidence - 0.9}

            elif tools:
                # Tools were available but model chose to respond with text
                confidence_method = "tool-available-text-chosen"

                # Use semantic confidence estimation for text response quality
                if self._confidence_estimator and text_content:
                    metadata_for_confidence = {
                        "finish_reason": data.get("stop_reason"),
                        "temperature": temperature,
                        "query": user_query,
                        "model": model,
                        "tools_available": True,
                        "tool_choice_declined": True,
                    }

                    confidence_analysis = self._confidence_estimator.estimate(
                        response=text_content,
                        query=user_query,
                        logprobs=None,
                        temperature=temperature,
                        metadata=metadata_for_confidence,
                    )
                    confidence = confidence_analysis.final_confidence
                    confidence_components = confidence_analysis.components or {}
                else:
                    # Fallback: Lower confidence when tools available but not used
                    confidence = 0.7
                    confidence_components = {"fallback": 0.7}

            else:
                # No tools provided - use standard semantic confidence
                confidence_method = "multi-signal-hybrid"

                if self._confidence_estimator and text_content:
                    metadata_for_confidence = {
                        "finish_reason": data.get("stop_reason"),
                        "temperature": temperature,
                        "query": user_query,
                        "model": model,
                    }

                    confidence_analysis = self._confidence_estimator.estimate(
                        response=text_content,
                        query=user_query,
                        logprobs=None,
                        temperature=temperature,
                        metadata=metadata_for_confidence,
                    )
                    confidence = confidence_analysis.final_confidence
                    confidence_components = confidence_analysis.components or {}
                else:
                    # Fallback
                    confidence = 0.85
                    confidence_components = {"fallback": 0.85}

            # Optional debug logging
            if os.getenv("DEBUG_CONFIDENCE"):
                print("🔍 Anthropic Tool Call Confidence Debug:")
                print(f"  Query: {user_query[:50]}...")
                print(f"  Has tool calls: {bool(tool_calls)}")
                print(f"  Tools provided: {bool(tools)}")
                print(f"  Response: {text_content[:50]}..." if text_content else "  (no text)")
                print(f"  Confidence: {confidence:.3f}")
                print(f"  Method: {confidence_method}")
                if confidence_components:
                    print("  Components:")
                    for comp, val in confidence_components.items():
                        print(f"    • {comp:18s}: {val:.3f}")

            # Build response metadata WITH confidence details
            response_metadata = {
                "stop_reason": data.get("stop_reason"),
                "id": data.get("id"),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "has_tool_calls": bool(tool_calls),
                # NEW: Add confidence analysis details
                "query": user_query,
                "confidence_method": confidence_method,
                "confidence_components": confidence_components,
                "tools_provided": bool(tools),
            }

            # Build model response
            model_response = ModelResponse(
                content=text_content,
                model=model,
                provider="anthropic",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata=response_metadata,
            )

            # Add tool calls to response
            if tool_calls:
                model_response.tool_calls = tool_calls

            return model_response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid Anthropic API key", provider="anthropic", original_error=e
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "Anthropic rate limit exceeded", provider="anthropic", original_error=e
                )
            else:
                raise ProviderError(
                    f"Anthropic API error: {e.response.status_code}",
                    provider="anthropic",
                    original_error=e,
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to Anthropic API", provider="anthropic", original_error=e
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse Anthropic response: {e}", model=model, provider="anthropic"
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
        Complete a prompt using Anthropic API (internal implementation with automatic retry).

        This is the internal implementation called by the public complete() method.
        Retry logic is handled automatically by the parent class.

        confidence estimation (query difficulty + alignment + semantic quality).

        Args:
            prompt: User prompt
            model: Model name (e.g., 'claude-3-sonnet-20240229', 'claude-3-opus-20240229')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt
            **kwargs: Additional parameters including:
                - logprobs (bool): Request estimated logprobs (uses fallback)
                - top_logprobs (int): Number of alternatives (for estimated logprobs)

        Returns:
            ModelResponse with multi-signal semantic confidence

        Raises:
            ProviderError: If API call fails (will be caught by retry logic)
            ModelError: If model execution fails (will be caught by retry logic)
        """
        start_time = time.time()

        # Extract logprobs parameters (Anthropic doesn't support them natively)
        # System will use fallback estimation if requested
        logprobs_requested = kwargs.pop("logprobs", False)
        kwargs.pop("top_logprobs", 5)

        # Auto-detect extended thinking support
        model_info = get_reasoning_model_info(model)

        # Build request payload (Anthropic format is different from OpenAI)
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }

        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt

        # Add extended thinking configuration for Claude 3.7
        if model_info.supports_extended_thinking and "thinking" in kwargs:
            payload["thinking"] = kwargs.pop("thinking")

        try:
            # Make API request (retry handled by parent class)
            response = await self.client.post(f"{self.base_url}/messages", json=payload)
            response.raise_for_status()

            data = response.json()

            # Extract thinking content (Claude 3.7 extended thinking)
            thinking_blocks = [
                block for block in data["content"] if block.get("type") == "thinking"
            ]
            thinking = (
                "\n\n".join(block.get("thinking", "") for block in thinking_blocks)
                if thinking_blocks
                else None
            )

            # Extract response (Anthropic format)
            text_blocks = [block for block in data["content"] if block.get("type") == "text"]
            content = text_blocks[0]["text"] if text_blocks else ""

            # Anthropic provides token counts in usage
            usage = data.get("usage", {})
            prompt_tokens = usage.get("input_tokens", 0)
            completion_tokens = usage.get("output_tokens", 0)
            tokens_used = prompt_tokens + completion_tokens

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate cost using LiteLLM if available, otherwise fallback
            cost = self.calculate_accurate_cost(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=tokens_used,
            )

            # ============================================================
            # Now captures full analysis for test validation
            # ============================================================

            # Build comprehensive metadata for confidence system
            metadata_for_confidence = {
                "finish_reason": data.get("stop_reason"),
                "temperature": temperature,
                "query": prompt,
                "model": model,
            }

            # Get FULL confidence analysis (not just float)
            if self._confidence_estimator:
                confidence_analysis = self._confidence_estimator.estimate(
                    response=content,
                    query=prompt,
                    logprobs=None,  # Anthropic doesn't support logprobs
                    temperature=temperature,
                    metadata=metadata_for_confidence,
                )
                confidence = confidence_analysis.final_confidence
                confidence_method = confidence_analysis.method_used
                confidence_components = confidence_analysis.components or {}
            else:
                # Fallback if estimator not available
                confidence = self.calculate_confidence(content, metadata_for_confidence)
                confidence_method = "legacy"
                confidence_components = {}

            # Optional debug logging (enable with DEBUG_CONFIDENCE=1)
            if os.getenv("DEBUG_CONFIDENCE"):
                print("🔍 Anthropic Confidence Debug:")
                print(f"  Query: {prompt[:50]}...")
                print(f"  Response: {content[:50]}...")
                print(f"  Response length: {len(content)} chars")
                print(f"  Confidence: {confidence:.3f}")
                print(f"  Method: {confidence_method}")
                if confidence_components:
                    print("  Components:")
                    for comp, val in confidence_components.items():
                        print(f"    • {comp:18s}: {val:.3f}")

            # Build response metadata WITH confidence details
            response_metadata = {
                "stop_reason": data.get("stop_reason"),
                "id": data.get("id"),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                # NEW: Add confidence analysis details for test validation
                "query": prompt,
                "confidence_method": confidence_method,
                "confidence_components": confidence_components,
            }

            # Add thinking to metadata if available (Claude 3.7 extended thinking)
            if thinking:
                response_metadata["thinking"] = thinking

            # Create base response
            model_response = ModelResponse(
                content=content,
                model=model,
                provider="anthropic",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata=response_metadata,
            )

            # Add logprobs using fallback estimation if explicitly requested
            if logprobs_requested:
                model_response = self.add_logprobs_fallback(
                    response=model_response,
                    temperature=temperature,
                    base_confidence=0.90,  # Claude models are very high quality
                )

            return model_response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid Anthropic API key", provider="anthropic", original_error=e
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "Anthropic rate limit exceeded", provider="anthropic", original_error=e
                )
            else:
                raise ProviderError(
                    f"Anthropic API error: {e.response.status_code}",
                    provider="anthropic",
                    original_error=e,
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to Anthropic API", provider="anthropic", original_error=e
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse Anthropic response: {e}", model=model, provider="anthropic"
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
        Stream response from Anthropic API (internal implementation with automatic retry).

        This is the internal implementation called by the public stream() method.
        Retry logic is handled automatically by the parent class.

        This method enables real-time streaming for better UX. Yields chunks
        as they arrive from the API. Anthropic uses Server-Sent Events (SSE) format
        with specific event types.

        NOTE: Streaming mode does NOT include logprobs in the stream, but
        the StreamingCascadeWrapper will call complete() separately to get
        the full result with confidence scores.

        Args:
            prompt: User prompt
            model: Model name (e.g., 'claude-3-sonnet-20240229', 'claude-3-opus-20240229')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt
            **kwargs: Additional Anthropic parameters

        Yields:
            Content chunks as they arrive from the API

        Raises:
            ProviderError: If API call fails (will be caught by retry logic)
            ModelError: If model execution fails (will be caught by retry logic)

        Example:
            >>> provider = AnthropicProvider()
            >>> async for chunk in provider.stream(
            ...     prompt="What is Python?",
            ...     model="claude-3-sonnet-20240229"
            ... ):
            ...     print(chunk, end='', flush=True)
            Python is a high-level programming language...
        """
        # Build request payload with streaming enabled
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,  # Enable streaming
            **kwargs,
        }

        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt

        try:
            # Make streaming API request (retry handled by parent class)
            async with self.client.stream(
                "POST", f"{self.base_url}/messages", json=payload
            ) as response:
                response.raise_for_status()

                # Process SSE stream (Anthropic-specific format)
                # Anthropic uses event-based streaming with different event types
                async for line in response.aiter_lines():
                    # Skip empty lines
                    if not line.strip():
                        continue

                    # SSE format: "event: <type>" or "data: <json>"
                    if line.startswith("event:"):
                        # Event type line (e.g., "event: content_block_delta")
                        continue
                    elif line.startswith("data:"):
                        # Extract JSON data
                        data_str = line[5:].strip()  # Remove "data:" prefix

                        try:
                            # Parse JSON chunk
                            chunk_data = json.loads(data_str)

                            # Extract content based on event type
                            event_type = chunk_data.get("type")

                            if event_type == "content_block_delta":
                                # This event contains the actual text chunks
                                delta = chunk_data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    if text:
                                        # Yield content chunk
                                        yield text

                            elif event_type == "message_stop":
                                # Stream ended
                                break

                        except json.JSONDecodeError:
                            # Skip malformed JSON
                            continue

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid Anthropic API key", provider="anthropic", original_error=e
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "Anthropic rate limit exceeded", provider="anthropic", original_error=e
                )
            else:
                raise ProviderError(
                    f"Anthropic API error: {e.response.status_code}",
                    provider="anthropic",
                    original_error=e,
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to Anthropic API", provider="anthropic", original_error=e
            )

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for Anthropic model.

        NOTE: This is a simplified blended estimate (assumes 50% input, 50% output).
        Anthropic charges different rates for input vs output tokens.
        For accurate costs, use the input/output split from the API response.

        Official Anthropic Pricing (October 2025):
        Source: https://docs.claude.com/en/docs/about-claude/pricing

        Args:
            tokens: Total tokens (prompt + completion combined)
            model: Model name

        Returns:
            Estimated cost in USD (blended average)
        """
        # Anthropic pricing per million tokens (October 2025)
        # Format: Blended rate (50% input, 50% output)
        # Official rates: Input / Output per MTok
        rates = {
            # Claude 4 Series
            "claude-opus-4.1": 45.0,  # $15 in + $75 out = $45 blended
            "claude-opus-4": 45.0,  # $15 in + $75 out = $45 blended
            "claude-sonnet-4.5": 9.0,  # $3 in + $15 out = $9 blended
            "claude-sonnet-4": 9.0,  # $3 in + $15 out = $9 blended
            # Claude 3.5 Series
            "claude-3-5-sonnet": 9.0,  # $3 in + $15 out = $9 blended
            "claude-sonnet-3-5": 9.0,  # $3 in + $15 out = $9 blended (alternative naming)
            "claude-3-5-haiku": 3.0,  # $1 in + $5 out = $3 blended
            "claude-haiku-3-5": 3.0,  # $1 in + $5 out = $3 blended (alternative naming)
            # Claude 3 Series
            "claude-3-opus": 45.0,  # $15 in + $75 out = $45 blended
            "claude-3-sonnet": 9.0,  # $3 in + $15 out = $9 blended
            "claude-3-haiku": 0.75,  # $0.25 in + $1.25 out = $0.75 blended
        }

        model_lower = model.lower()

        # Find matching rate (try exact match first, then prefix)
        for model_prefix, rate in rates.items():
            if model_lower.startswith(model_prefix):
                return (tokens / 1_000_000) * rate

        # Default to Sonnet pricing if unknown (most common model)
        return (tokens / 1_000_000) * 9.0

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
