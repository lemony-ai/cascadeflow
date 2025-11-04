"""Groq provider implementation with tool calling support."""

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from ..exceptions import ModelError, ProviderError
from .base import BaseProvider, ModelResponse, RetryConfig


class GroqProvider(BaseProvider):
    """
    Groq provider for ultra-fast LLM inference with tool calling support.

    Groq powers leading open-source AI models with exceptional speed using
    their custom LPU (Language Processing Unit) architecture.

    Enhanced with full retry logic, intelligent confidence estimation, and tool calling.

    - ❌ gemma2-9b-it DEPRECATED (removed Oct 8, 2025)
    - ✅ Use openai/gpt-oss-20b instead (recommended replacement)
    - ✅ Or use llama-3.1-8b-instant for fast inference
    - 🚨 FIXED: Pricing was 1000x too small (now correct)

    Supports: Llama 3.1, Llama 3.3, Llama 4, DeepSeek, Qwen, Mixtral, Mistral
    Pricing: Pay-as-you-go token pricing (as low as $0.05/million tokens)
    Logprobs: Uses fallback estimation (Groq doesn't support native logprobs)
    Tool Calling: ✅ Full support via OpenAI-compatible API (Phase 2)

    NOTE: Despite using OpenAI-compatible API, Groq does NOT support
    logprobs with their models. We use fallback estimation instead.

    Example (Basic):
        >>> # Basic usage (automatic retry on failures)
        >>> provider = GroqProvider(api_key="gsk_...")
        >>>
        >>> # Non-streaming (traditional):
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="openai/gpt-oss-20b"
        ... )
        >>> print(response.content)
        >>>
        >>> # Streaming (new):
        >>> async for chunk in provider.stream(
        ...     prompt="What is AI?",
        ...     model="llama-3.1-8b-instant"
        ... ):
        ...     print(chunk, end='', flush=True)

    Example (Tool Calling - NEW!):
        >>> # Define tools (OpenAI format)
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
        >>> # Use complete() with tools parameter
        >>> response = await provider.complete(
        ...     prompt="What's the weather in Paris?",
        ...     model="llama-3.3-70b-versatile",
        ...     tools=tools,
        ...     tool_choice="auto"
        ... )
        >>>
        >>> # Check if model wants to call tools
        >>> if response.tool_calls:
        ...     for tool_call in response.tool_calls:
        ...         print(f"Tool: {tool_call['name']}")
        ...         print(f"Args: {tool_call['arguments']}")
        >>>
        >>> # Or use complete_with_tools() for multi-turn conversations
        >>> messages = [{"role": "user", "content": "What's the weather in Paris?"}]
        >>> response = await provider.complete_with_tools(
        ...     messages=messages,
        ...     tools=tools,
        ...     model="llama-3.3-70b-versatile"
        ... )
    """

    def __init__(self, api_key: Optional[str] = None, retry_config: Optional[RetryConfig] = None):
        """
        Initialize Groq provider with automatic retry logic.

        Args:
            api_key: Groq API key. If None, reads from GROQ_API_KEY env var.
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
                "Groq API key not found. Please set GROQ_API_KEY environment "
                "variable or pass api_key parameter. Get free key at: "
                "https://console.groq.com"
            )

        # Initialize HTTP client
        self.base_url = "https://api.groq.com/openai/v1"
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            timeout=60.0,
        )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment."""
        return os.getenv("GROQ_API_KEY")

    def _check_logprobs_support(self) -> bool:
        """
        Check if provider supports native logprobs.

        NOTE: Despite using OpenAI-compatible API, Groq does NOT support
        logprobs with their models. We use fallback estimation instead.

        Returns:
            False - Groq does not support native logprobs (uses fallback)
        """
        return False

    def _convert_tools_to_openai(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert tools from universal format to OpenAI format.

        Since Groq uses OpenAI-compatible API, this is the same conversion
        as OpenAI provider.

        Universal format:
        {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {...}  # JSON Schema
        }

        OpenAI/Groq format:
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
            List of tools in OpenAI/Groq format
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
        Parse tool calls from Groq response into universal format.

        Since Groq uses OpenAI-compatible API, the format is the same.

        Groq/OpenAI format:
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
            choice: Groq response choice

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
        model: str = "llama-3.3-70b-versatile",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Complete a conversation with tool calling support.

        This method enables the model to call tools/functions during generation.
        The model can request to call multiple tools in parallel.

        Phase 2: Groq Provider Tool Integration
        - Leverages OpenAI compatibility for tool calling
        - Ultra-fast tool execution with LPU acceleration
        - Same format as OpenAI for easy migration

        - Tracks "tool-call-present" when tools are called
        - Tracks "tool-available-text-chosen" when tools available but text chosen
        - Tracks "multi-signal-hybrid" when no tools provided

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
            model: Model name (e.g., 'llama-3.3-70b-versatile', 'llama-3.1-8b-instant')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            tool_choice: Control tool calling behavior:
                - None/omitted: Model decides
                - "auto": Model decides (explicit)
                - "none": Prevent tool calling
                - {"type": "function", "function": {"name": "get_weather"}}: Force specific tool
            **kwargs: Additional Groq parameters

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
            ...     model="llama-3.3-70b-versatile"
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

        # Check for deprecated model
        if "gemma2-9b-it" in model.lower() or "gemma2:9b" in model.lower():
            raise ModelError(
                f"Model '{model}' has been deprecated by Groq as of October 8, 2025. "
                f"Please use 'openai/gpt-oss-20b' or 'llama-3.3-70b-versatile'.",
                model=model,
                provider="groq",
            )

        # Convert tools to OpenAI/Groq format
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
            content = message.get("content", "") or ""  # May be None if only tool calls
            prompt_tokens = data["usage"]["prompt_tokens"]
            completion_tokens = data["usage"]["completion_tokens"]
            tokens_used = data["usage"]["total_tokens"]

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate cost using LiteLLM if available, otherwise fallback
            cost = self.calculate_accurate_cost(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=tokens_used,
            )

            # Parse tool calls if present
            tool_calls = self._parse_tool_calls(choice)

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
                confidence = 0.85  # High confidence for successful tool calls (Groq quality)

                # Temperature-based confidence adjustment
                if temperature == 0:
                    confidence = 0.90  # Even higher for deterministic calls
                elif temperature > 1.5:
                    confidence = 0.80  # Slightly lower for very creative calls

                confidence_components = {"base": 0.85, "temperature_adjustment": confidence - 0.85}

            elif tools:
                # Tools were available but model chose to respond with text
                confidence_method = "tool-available-text-chosen"

                # Use semantic confidence estimation for text response quality
                if self._confidence_estimator and content:
                    metadata_for_confidence = {
                        "finish_reason": choice["finish_reason"],
                        "temperature": temperature,
                        "query": user_query,
                        "model": model,
                        "tools_available": True,
                        "tool_choice_declined": True,
                    }

                    confidence_analysis = self._confidence_estimator.estimate(
                        response=content,
                        query=user_query,
                        logprobs=None,
                        temperature=temperature,
                        metadata=metadata_for_confidence,
                    )
                    confidence = confidence_analysis.final_confidence
                    confidence_components = confidence_analysis.components or {}
                else:
                    # Fallback: Lower confidence when tools available but not used
                    confidence = 0.70
                    confidence_components = {"fallback": 0.70}

            else:
                # No tools provided - use standard semantic confidence
                confidence_method = "multi-signal-hybrid"

                if self._confidence_estimator and content:
                    metadata_for_confidence = {
                        "finish_reason": choice["finish_reason"],
                        "temperature": temperature,
                        "query": user_query,
                        "model": model,
                    }

                    confidence_analysis = self._confidence_estimator.estimate(
                        response=content,
                        query=user_query,
                        logprobs=None,
                        temperature=temperature,
                        metadata=metadata_for_confidence,
                    )
                    confidence = confidence_analysis.final_confidence
                    confidence_components = confidence_analysis.components or {}
                else:
                    # Fallback
                    confidence = 0.82
                    confidence_components = {"fallback": 0.82}

            # Optional debug logging
            if os.getenv("DEBUG_CONFIDENCE"):
                print("🔍 Groq Tool Call Confidence Debug:")
                print(f"  Query: {user_query[:50]}...")
                print(f"  Has tool calls: {bool(tool_calls)}")
                print(f"  Tools provided: {bool(tools)}")
                print(f"  Response: {content[:50]}..." if content else "  (no text)")
                print(f"  Confidence: {confidence:.3f}")
                print(f"  Method: {confidence_method}")
                if confidence_components:
                    print("  Components:")
                    for comp, val in confidence_components.items():
                        print(f"    • {comp:18s}: {val:.3f}")

            # Build response metadata WITH confidence details
            response_metadata = {
                "finish_reason": choice["finish_reason"],
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
                content=content,
                model=model,
                provider="groq",
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
                    "Invalid Groq API key. Get free key at: https://console.groq.com",
                    provider="groq",
                    original_error=e,
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "Groq rate limit exceeded. Consider upgrading your plan.",
                    provider="groq",
                    original_error=e,
                )
            elif e.response.status_code == 400:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get("error", {}).get("message", str(e))
                    raise ProviderError(
                        f"Groq API error: {error_message}", provider="groq", original_error=e
                    )
                except:
                    raise ProviderError(
                        f"Groq API error: {e.response.status_code}",
                        provider="groq",
                        original_error=e,
                    )
            else:
                raise ProviderError(
                    f"Groq API error: {e.response.status_code}", provider="groq", original_error=e
                )
        except httpx.RequestError as e:
            raise ProviderError("Failed to connect to Groq API", provider="groq", original_error=e)
        except (KeyError, IndexError) as e:
            raise ModelError(f"Failed to parse Groq response: {e}", model=model, provider="groq")

    async def _complete_impl(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Complete a prompt using Groq API (internal implementation with automatic retry).

        This is the internal implementation called by the public complete() method.
        Retry logic is handled automatically by the parent class.


        Groq uses OpenAI-compatible API format but does NOT support logprobs.
        When logprobs are requested, we use fallback estimation instead.

        Args:
            prompt: User prompt
            model: Model name (e.g., 'openai/gpt-oss-20b', 'llama-3.1-8b-instant')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            tools: Optional list of tools in universal format (for tool calling)
            tool_choice: Optional tool choice ("auto", "none", or specific tool)
            **kwargs: Additional parameters including:
                - logprobs (bool): Include log probabilities (estimated)
                - top_logprobs (int): Number of top logprobs to return

        Returns:
            ModelResponse with standardized format (with estimated logprobs if requested)
            If tools are provided and model wants to call them, tool_calls will be populated.

        Raises:
            ProviderError: If API call fails (will be caught by retry logic)
            ModelError: If model execution fails (will be caught by retry logic)
        """
        start_time = time.time()

        # Check for deprecated model and provide helpful error
        if "gemma2-9b-it" in model.lower() or "gemma2:9b" in model.lower():
            raise ModelError(
                f"Model '{model}' has been deprecated by Groq as of October 8, 2025. "
                f"Please use one of these replacements:\n"
                f"  - 'openai/gpt-oss-20b' (recommended, better quality)\n"
                f"  - 'llama-3.1-8b-instant' (faster, good quality)\n"
                f"  - 'llama-3.3-70b-versatile' (highest quality)",
                model=model,
                provider="groq",
            )

        # Extract logprobs parameters (but don't send to API - Groq doesn't support them)
        request_logprobs = kwargs.pop("logprobs", False)
        kwargs.pop("top_logprobs", 5)

        # Convert tools to OpenAI/Groq format if provided
        openai_tools = self._convert_tools_to_openai(tools) if tools else None

        # Build messages (OpenAI format)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request payload
        # NOTE: We do NOT add logprobs to payload - Groq doesn't support it
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }

        # Add tools if provided (NEW!)
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

            # Extract response (OpenAI format)
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content", "") or ""  # May be None if only tool calls
            prompt_tokens = data["usage"]["prompt_tokens"]
            completion_tokens = data["usage"]["completion_tokens"]
            tokens_used = data["usage"]["total_tokens"]

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate cost using LiteLLM if available, otherwise fallback
            cost = self.calculate_accurate_cost(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=tokens_used,
            )

            # Parse tool calls if present (NEW!)
            tool_calls = self._parse_tool_calls(choice)

            # ============================================================
            # Enhanced confidence calculation with tool call awareness
            # ============================================================

            if tool_calls:
                # Model successfully generated tool calls
                confidence_method = "tool-call-present"
                confidence = 0.85  # High confidence for successful tool calls (Groq quality)

                # Temperature-based confidence adjustment
                if temperature == 0:
                    confidence = 0.90  # Even higher for deterministic calls
                elif temperature > 1.5:
                    confidence = 0.80  # Slightly lower for very creative calls

                confidence_components = {"base": 0.85, "temperature_adjustment": confidence - 0.85}

            elif tools:
                # Tools were available but model chose to respond with text
                confidence_method = "tool-available-text-chosen"

                # Use semantic confidence estimation for text response quality
                if self._confidence_estimator and content:
                    metadata_for_confidence = {
                        "finish_reason": choice["finish_reason"],
                        "temperature": temperature,
                        "query": prompt,
                        "model": model,
                        "tools_available": True,
                        "tool_choice_declined": True,
                    }

                    confidence_analysis = self._confidence_estimator.estimate(
                        response=content,
                        query=prompt,
                        logprobs=None,
                        temperature=temperature,
                        metadata=metadata_for_confidence,
                    )
                    confidence = confidence_analysis.final_confidence
                    confidence_components = confidence_analysis.components or {}
                else:
                    # Fallback: Lower confidence when tools available but not used
                    confidence = 0.70
                    confidence_components = {"fallback": 0.70}

            else:
                # No tools provided - use standard semantic confidence
                confidence_method = "multi-signal-hybrid"

                if self._confidence_estimator and content:
                    metadata_for_confidence = {
                        "finish_reason": choice["finish_reason"],
                        "temperature": temperature,
                        "query": prompt,
                        "model": model,
                    }

                    confidence_analysis = self._confidence_estimator.estimate(
                        response=content,
                        query=prompt,
                        logprobs=None,
                        temperature=temperature,
                        metadata=metadata_for_confidence,
                    )
                    confidence = confidence_analysis.final_confidence
                    confidence_components = confidence_analysis.components or {}
                else:
                    # Fallback
                    confidence = 0.82
                    confidence_components = {"fallback": 0.82}

            # Optional debug logging (enable with DEBUG_CONFIDENCE=1)
            if os.getenv("DEBUG_CONFIDENCE"):
                print("🔍 Groq Confidence Debug:")
                print(f"  Query: {prompt[:50]}...")
                print(f"  Response: {content[:50]}..." if content else "  (no text)")
                print(f"  Has tool calls: {bool(tool_calls)}")
                print(f"  Tools provided: {bool(tools)}")
                print(f"  Response length: {len(content)} chars")
                print(f"  Confidence: {confidence:.3f}")
                print(f"  Method: {confidence_method}")
                if confidence_components:
                    print("  Components:")
                    for comp, val in confidence_components.items():
                        print(f"    • {comp:18s}: {val:.3f}")

            # Build metadata for response WITH confidence details
            metadata = {
                "finish_reason": choice["finish_reason"],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "has_tool_calls": bool(tool_calls),
                # Add confidence analysis details for test validation
                "query": prompt,
                "confidence_method": confidence_method,
                "confidence_components": confidence_components,
                "tools_provided": bool(tools),
            }

            # Create base response
            response_obj = ModelResponse(
                content=content,
                model=model,
                provider="groq",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata=metadata,
            )

            # Add tool calls to response if present (NEW!)
            if tool_calls:
                response_obj.tool_calls = tool_calls

            # Add logprobs via fallback if requested (and no tool calls)
            if request_logprobs and not tool_calls:
                response_obj = self.add_logprobs_fallback(
                    response=response_obj,
                    temperature=temperature,
                    base_confidence=0.82,  # Groq models are good quality
                )

            return response_obj

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid Groq API key. Get free key at: https://console.groq.com",
                    provider="groq",
                    original_error=e,
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "Groq rate limit exceeded. Consider upgrading your plan.",
                    provider="groq",
                    original_error=e,
                )
            elif e.response.status_code == 400:
                # Extract error message from response
                try:
                    error_data = e.response.json()
                    error_message = error_data.get("error", {}).get("message", str(e))

                    # Check if it's a model not found error
                    if "model" in error_message.lower() and "not found" in error_message.lower():
                        raise ModelError(
                            f"Model '{model}' not found. "
                            f"This might be a deprecated model. "
                            f"Try 'openai/gpt-oss-20b' or 'llama-3.1-8b-instant'.",
                            model=model,
                            provider="groq",
                        )

                    raise ProviderError(
                        f"Groq API error: {error_message}", provider="groq", original_error=e
                    )
                except:
                    raise ProviderError(
                        f"Groq API error: {e.response.status_code}",
                        provider="groq",
                        original_error=e,
                    )
            else:
                raise ProviderError(
                    f"Groq API error: {e.response.status_code}", provider="groq", original_error=e
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to Groq API. Check your internet connection.",
                provider="groq",
                original_error=e,
            )
        except (KeyError, IndexError) as e:
            raise ModelError(f"Failed to parse Groq response: {e}", model=model, provider="groq")

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
        Stream response from Groq API (internal implementation with automatic retry).

        This is the internal implementation called by the public stream() method.
        Retry logic is handled automatically by the parent class.

        This method enables real-time streaming for better UX. Yields chunks
        as they arrive from the API. Groq uses OpenAI-compatible SSE format.

        NOTE: Streaming mode does NOT support tool calling or logprobs in the stream.
        The StreamingCascadeWrapper will call complete() separately to get
        the full result with confidence scores.

        Args:
            prompt: User prompt
            model: Model name (e.g., 'openai/gpt-oss-20b', 'llama-3.1-8b-instant')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            **kwargs: Additional Groq parameters

        Yields:
            Content chunks as they arrive from the API

        Raises:
            ProviderError: If API call fails (will be caught by retry logic)
            ModelError: If model execution fails (will be caught by retry logic)

        Example:
            >>> provider = GroqProvider()
            >>> async for chunk in provider.stream(
            ...     prompt="What is Python?",
            ...     model="llama-3.1-8b-instant"
            ... ):
            ...     print(chunk, end='', flush=True)
            Python is a high-level programming language...
        """
        # Check for deprecated model
        if "gemma2-9b-it" in model.lower() or "gemma2:9b" in model.lower():
            raise ModelError(
                f"Model '{model}' has been deprecated by Groq as of October 8, 2025. "
                f"Please use 'openai/gpt-oss-20b' or 'llama-3.1-8b-instant'.",
                model=model,
                provider="groq",
            )

        # Build messages (OpenAI format)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request payload with streaming enabled
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

                # Process SSE stream (OpenAI-compatible format)
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
                raise ProviderError("Invalid Groq API key", provider="groq", original_error=e)
            elif e.response.status_code == 429:
                raise ProviderError("Groq rate limit exceeded", provider="groq", original_error=e)
            elif e.response.status_code == 400:
                # Extract error message
                try:
                    error_data = e.response.json()
                    error_message = error_data.get("error", {}).get("message", str(e))
                    raise ProviderError(
                        f"Groq API error: {error_message}", provider="groq", original_error=e
                    )
                except:
                    raise ProviderError(
                        f"Groq API error: {e.response.status_code}",
                        provider="groq",
                        original_error=e,
                    )
            else:
                raise ProviderError(
                    f"Groq API error: {e.response.status_code}", provider="groq", original_error=e
                )
        except httpx.RequestError as e:
            raise ProviderError("Failed to connect to Groq API", provider="groq", original_error=e)

    def estimate_cost(
        self,
        tokens: int,
        model: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ) -> float:
        """
        Estimate cost for Groq model.

        🚨 FIXED (Oct 7, 2025): Pricing was 1000x too small - now corrected!

        This method now:
        1. Uses correct per-million-token rates (was 1000x too small)
        2. Supports split pricing for accuracy when token counts are available
        3. Uses realistic 30/70 input/output split for blended estimates

        Official Groq Pricing (October 2025): https://groq.com/pricing
        - Input and output tokens are charged at different rates
        - Output tokens typically cost 1.3-2x more than input tokens
        - When split is unavailable, uses 30/70 ratio (typical usage pattern)

        Args:
            tokens: Total tokens (prompt + completion combined)
            model: Model name (e.g., 'openai/gpt-oss-20b', 'llama-3.1-8b-instant')
            prompt_tokens: Input tokens (optional, for accurate split pricing)
            completion_tokens: Output tokens (optional, for accurate split pricing)

        Returns:
            Estimated cost in USD

        Example:
            >>> # With split pricing (most accurate)
            >>> cost = provider.estimate_cost(
            ...     tokens=1000,
            ...     model="llama-3.1-8b-instant",
            ...     prompt_tokens=300,
            ...     completion_tokens=700
            ... )
            >>>
            >>> # Without split (uses 30/70 estimate)
            >>> cost = provider.estimate_cost(1000, "llama-3.1-8b-instant")
        """
        # 🚨 FIXED: All rates are now per 1M tokens (were 1000x too small!)
        # Format: (input_rate_per_1M, output_rate_per_1M)
        MODEL_COSTS = {
            # Llama 4 Series (newest, experimental)
            "llama-4-scout": (0.11, 0.34),  # Official: $0.11 in / $0.34 out per 1M
            "llama-4-maverick": (0.20, 0.60),  # Official: $0.20 in / $0.60 out per 1M
            "llama-guard-4": (0.20, 0.20),  # Official: $0.20 in / $0.20 out per 1M
            # Llama 3.3 Series (recommended for quality)
            "llama-3.3-70b": (0.59, 0.79),  # Official: $0.59 in / $0.79 out per 1M
            "llama3-70b": (0.59, 0.79),  # Alias
            # Llama 3.1 Series (most popular - fast & cheap)
            "llama-3.1-8b": (0.05, 0.08),  # Official: $0.05 in / $0.08 out per 1M
            "llama-3.1-70b": (0.59, 0.79),  # Official: $0.59 in / $0.79 out per 1M
            "llama3-8b": (0.05, 0.08),  # Alias
            # Llama 3 Series (older but still available)
            "llama-3-8b": (0.05, 0.08),  # Same as 3.1
            "llama-3-70b": (0.59, 0.79),  # Same as 3.1
            "llama3-groq": (0.05, 0.08),  # Groq-tuned variants
            # DeepSeek Series
            "deepseek-r1": (0.75, 0.99),  # Official: $0.75 in / $0.99 out per 1M
            # Qwen Series
            "qwen3-32b": (0.29, 0.59),  # Official: $0.29 in / $0.59 out per 1M
            # Mixtral Series
            "mixtral-8x7b": (0.24, 0.24),  # Official: $0.24 in / $0.24 out per 1M
            # Mistral Series
            "mistral-saba": (0.79, 0.79),  # Official: $0.79 in / $0.79 out per 1M
            # Guard Models
            "llama-guard-3": (0.20, 0.20),  # Official: $0.20 in / $0.20 out per 1M
            # OpenAI Models (new recommended replacement for deprecated Gemma)
            "openai/gpt-oss-20b": (0.11, 0.34),  # Estimated: $0.11 in / $0.34 out per 1M
        }

        # Convert model name to lowercase for matching
        model_lower = model.lower()

        # Find matching model pricing
        input_rate, output_rate = 0.05, 0.08  # Default to Llama 3.1 8B (cheapest)

        for model_prefix, (inp_rate, out_rate) in MODEL_COSTS.items():
            if model_lower.startswith(model_prefix):
                input_rate = inp_rate
                output_rate = out_rate
                break

        # Calculate cost with split pricing if available (most accurate)
        if prompt_tokens is not None and completion_tokens is not None:
            input_cost = (prompt_tokens / 1_000_000) * input_rate
            output_cost = (completion_tokens / 1_000_000) * output_rate
            return input_cost + output_cost

        # Fallback: Use blended rate with 30/70 split (typical usage pattern)
        # Most queries use ~30% input, ~70% output tokens
        blended_rate = (input_rate * 0.3) + (output_rate * 0.7)
        return (tokens / 1_000_000) * blended_rate

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
