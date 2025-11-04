"""Together.ai provider implementation with tool calling support."""

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from ..exceptions import ModelError, ProviderError
from .base import BaseProvider, ModelResponse, RetryConfig


class TogetherProvider(BaseProvider):
    """
    Together.ai provider for open-source models with tool calling support.

    Supports 100+ optimized open-source models including:
    - Llama 3.1, 3.2, 3.3, 4 (Scout/Maverick)
    - DeepSeek (V3, R1, distilled variants)
    - Qwen (2.5, 3, QwQ, Coder)
    - Mixtral, Mistral
    - And many more

    Enhanced with full logprobs support and intelligent defaults for token-level confidence.

    Tool Calling Support:
    - ✅ Full support (OpenAI-compatible API)
    - ✅ Parallel tool calls
    - ⭐ Best models: Llama 3.1+, Qwen 2.5+, Mixtral models

                           Together.ai-specific retry behavior:
                           - 401 (invalid key): No retry (permanent error)
                           - 429 (rate limit): Retry with exponential backoff
                           - 408/503/504 (timeout/overload): Retry with backoff
                           - Network errors: Retry with backoff
    Now supports both complete() and stream() methods.
    Uses hybrid confidence (logprobs + semantic) for maximum accuracy.

    Example (Basic):
        >>> # Basic usage (automatic retry on failures)
        >>> provider = TogetherProvider(api_key="...")
        >>>
        >>> # Non-streaming (traditional):
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
        ... )
        >>> print(f"Confidence: {response.confidence}")

    Example (Tool Calling - NEW!):
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
        ...     model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        ...     tools=tools
        ... )
        >>>
        >>> if response.tool_calls:
        ...     for tool_call in response.tool_calls:
        ...         print(f"Tool: {tool_call['name']}")
        ...         print(f"Args: {tool_call['arguments']}")
    """

    def __init__(self, api_key: Optional[str] = None, retry_config: Optional[RetryConfig] = None):
        """
        Initialize Together.ai provider with automatic retry logic.

        Args:
            api_key: Together.ai API key. If None, reads from TOGETHER_API_KEY env var.
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
                "Together.ai API key not found. Please set TOGETHER_API_KEY environment "
                "variable or pass api_key parameter."
            )

        # Now initialize HTTP client with the loaded API key
        self.base_url = "https://api.together.xyz/v1"
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            timeout=30.0,  # 30 second default timeout
        )

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment."""
        return os.getenv("TOGETHER_API_KEY")

    def _check_logprobs_support(self) -> bool:
        """
        Together.ai supports native logprobs for confidence analysis.

        Returns:
            True - Together.ai provides native logprobs (with their own format)
        """
        return True

    def _convert_tools_to_openai(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert tools from universal format to OpenAI/Together.ai format.

        Together.ai uses OpenAI-compatible API format.

        Universal format:
        {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {...}  # JSON Schema
        }

        OpenAI/Together.ai format:
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
            List of tools in OpenAI/Together.ai format
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
        Parse tool calls from Together.ai response into universal format.

        Together.ai uses OpenAI-compatible format.

        Together.ai/OpenAI format:
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
            choice: Together.ai response choice

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
        model: str = "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Complete a conversation with tool calling support.

        This method enables the model to call tools/functions during generation.
        The model can request to call multiple tools in parallel.

        Together.ai Provider Tool Integration
        - Full tool support (OpenAI-compatible)
        - 100+ models available
        - Best models: Llama 3.1+, Qwen 2.5+, Mixtral

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
            model: Model name (e.g., 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            tool_choice: Control tool calling behavior:
                - None/omitted: Model decides
                - "auto": Model decides (explicit)
                - "none": Prevent tool calling
                - {"type": "function", "function": {"name": "get_weather"}}: Force specific tool
            **kwargs: Additional Together.ai parameters

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
            ...     model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
            ... )
            >>>
            >>> # Check if model wants to call tools
            >>> if response.tool_calls:
            ...     for tool_call in response.tool_calls:
            ...         print(f"Calling: {tool_call['name']}")
            ...         print(f"Arguments: {tool_call['arguments']}")
        """
        start_time = time.time()

        # Convert tools to OpenAI/Together.ai format
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
                confidence = 0.85  # Good confidence for Together.ai tool calls

                # Temperature-based confidence adjustment
                if temperature == 0:
                    confidence = 0.90  # Higher for deterministic calls
                elif temperature > 0.9:
                    confidence = 0.80  # Lower for very creative calls

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
                    confidence = 0.85
                    confidence_components = {"fallback": 0.85}

            # Optional debug logging
            if os.getenv("DEBUG_CONFIDENCE"):
                print("🔍 Together.ai Tool Call Confidence Debug:")
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
                provider="together",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,  # Use calculated confidence
                latency_ms=latency_ms,
                metadata=response_metadata,
            )

            # Add tool calls to response
            if tool_calls:
                model_response.tool_calls = tool_calls

            return model_response

        except httpx.TimeoutException as e:
            raise ProviderError(
                f"Together.ai API timeout after {self.client.timeout}s",
                provider="together",
                original_error=e,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid Together.ai API key", provider="together", original_error=e
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "Together.ai rate limit exceeded", provider="together", original_error=e
                )
            elif e.response.status_code == 400:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get("error", {}).get("message", str(e))

                    # Check if model doesn't support tools
                    if "tool" in error_message.lower() or "function" in error_message.lower():
                        raise ModelError(
                            f"Model '{model}' may not support tool calling. "
                            f"Error: {error_message}\n\n"
                            f"Try models like: meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo, "
                            f"Qwen/Qwen2.5-72B-Instruct-Turbo",
                            model=model,
                            provider="together",
                        )

                    raise ProviderError(
                        f"Together.ai API error: {error_message}",
                        provider="together",
                        original_error=e,
                    )
                except:
                    raise ProviderError(
                        f"Together.ai API error: {e.response.status_code}",
                        provider="together",
                        original_error=e,
                    )
            elif e.response.status_code in [408, 503, 504]:
                raise ProviderError(
                    f"Together.ai server error ({e.response.status_code}). Server may be overloaded.",
                    provider="together",
                    original_error=e,
                )
            else:
                raise ProviderError(
                    f"Together.ai API error: {e.response.status_code}",
                    provider="together",
                    original_error=e,
                )
        except httpx.RequestError as e:
            raise ProviderError(
                f"Failed to connect to Together.ai API: {str(e)}",
                provider="together",
                original_error=e,
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse Together.ai response: {e}", model=model, provider="together"
            )

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
        Complete a prompt using Together.ai API (internal implementation with automatic retry).

        This is the internal implementation called by the public complete() method.
        Retry logic is handled automatically by the parent class.


        Args:
            prompt: User prompt
            model: Model name (e.g., 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt
            tools: Optional list of tools in universal format (for tool calling)
            tool_choice: Optional tool choice ("auto", "none", or specific tool)
            **kwargs: Additional Together.ai parameters including:
                - logprobs (bool): Enable logprobs (default: True for accurate confidence)
                - top_logprobs (int): Get top-k alternatives (default: 5)

        Returns:
            ModelResponse with standardized format (enhanced with logprobs by default)
            If tools are provided and model wants to call them, tool_calls will be populated.

        Raises:
            ProviderError: If API call fails (will be caught by retry logic)
            ModelError: If model execution fails (will be caught by retry logic)
        """
        # If tools are provided, use complete_with_tools()
        if tools:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            return await self.complete_with_tools(
                messages=messages,
                tools=tools,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                tool_choice=tool_choice,
                **kwargs,
            )

        # Regular completion (no tools)
        start_time = time.time()

        # INTELLIGENT DEFAULT: Request logprobs unless explicitly disabled
        # This ensures accurate multi-signal confidence estimation
        if "logprobs" not in kwargs:
            kwargs["logprobs"] = self.should_request_logprobs(**kwargs)

        # Extract logprobs parameters
        logprobs_enabled = kwargs.pop("logprobs", False)
        top_logprobs = kwargs.pop("top_logprobs", 5)  # Default to 5

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
            **kwargs,
        }

        # CRITICAL: Together.ai expects logprobs as INTEGER, not boolean!
        # logprobs=N means "return top-N alternatives"
        # NOTE: Together.ai may timeout with logprobs=1, so we default to 2 minimum
        if logprobs_enabled:
            if top_logprobs and top_logprobs > 0:
                payload["logprobs"] = max(2, min(top_logprobs, 20))  # Clamp to [2, 20]
            else:
                # Default to 2 instead of 1 (Together.ai API issue with logprobs=1)
                payload["logprobs"] = 2

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
            # Enhanced confidence calculation with logprobs
            # Together.ai has REAL logprobs - uses hybrid confidence!
            # ============================================================

            # Parse logprobs if available
            tokens_list = []
            logprobs_list = []
            top_logprobs_data = []

            # Together.ai uses DIFFERENT logprobs format than OpenAI!
            if logprobs_enabled and "logprobs" in choice and choice["logprobs"]:
                logprobs_data = choice["logprobs"]

                # Check for Together.ai's format (tokens + token_logprobs)
                if "tokens" in logprobs_data and "token_logprobs" in logprobs_data:
                    tokens_list = logprobs_data["tokens"]
                    raw_logprobs = logprobs_data["token_logprobs"]
                    top_logprobs_data = logprobs_data.get("top_logprobs", [])

                    # Keep zeros - they mean 100% confidence!
                    # Filter only None values (truly missing logprobs)
                    logprobs_list = [lp for lp in raw_logprobs if lp is not None]

            # Build comprehensive metadata for confidence system
            metadata_for_confidence = {
                "finish_reason": choice["finish_reason"],
                "temperature": temperature,
                "query": prompt,
                "model": model,
                "logprobs": logprobs_list if logprobs_list else None,
                "tokens": tokens_list if tokens_list else None,
            }

            # Get FULL confidence analysis
            if self._confidence_estimator:
                confidence_analysis = self._confidence_estimator.estimate(
                    response=content,
                    query=prompt,
                    logprobs=logprobs_list if logprobs_list else None,
                    tokens=tokens_list if tokens_list else None,
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

            # Optional debug logging
            if os.getenv("DEBUG_CONFIDENCE"):
                print("🔍 Together Confidence Debug:")
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

            # Build response metadata
            response_metadata = {
                "finish_reason": choice["finish_reason"],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "query": prompt,
                "confidence_method": confidence_method,
                "confidence_components": confidence_components,
            }

            # Build base response
            model_response = ModelResponse(
                content=content,
                model=model,
                provider="together",
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
                model_response.top_logprobs = top_logprobs_data if top_logprobs_data else []
                model_response.metadata["has_logprobs"] = True
                model_response.metadata["estimated"] = False
            elif logprobs_enabled:
                # Logprobs were requested but not available - use fallback
                model_response = self.add_logprobs_fallback(
                    model_response,
                    temperature,
                    base_confidence=0.82,  # Together.ai models are good quality
                )

            return model_response

        except httpx.TimeoutException as e:
            raise ProviderError(
                f"Together.ai API timeout after {self.client.timeout}s. "
                "Note: logprobs=1 may cause timeouts; try top_logprobs >= 2",
                provider="together",
                original_error=e,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid Together.ai API key", provider="together", original_error=e
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "Together.ai rate limit exceeded", provider="together", original_error=e
                )
            elif e.response.status_code in [408, 503, 504]:
                raise ProviderError(
                    f"Together.ai server error ({e.response.status_code}). Server may be overloaded.",
                    provider="together",
                    original_error=e,
                )
            else:
                raise ProviderError(
                    f"Together.ai API error: {e.response.status_code}",
                    provider="together",
                    original_error=e,
                )
        except httpx.RequestError as e:
            raise ProviderError(
                f"Failed to connect to Together.ai API: {str(e)}",
                provider="together",
                original_error=e,
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse Together.ai response: {e}", model=model, provider="together"
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
        Stream response from Together.ai API (internal implementation with automatic retry).

        This is the internal implementation called by the public stream() method.
        Retry logic is handled automatically by the parent class.

        This method enables real-time streaming for better UX. Yields chunks
        as they arrive from the API.

        NOTE: Together.ai's streaming API is OpenAI-compatible, so we use the
        same SSE (Server-Sent Events) parsing as OpenAI. Streaming mode does
        NOT support tool calling or logprobs in the stream.

        Args:
            prompt: User prompt
            model: Model name (e.g., 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt
            **kwargs: Additional Together.ai parameters

        Yields:
            Content chunks as they arrive from the API

        Raises:
            ProviderError: If API call fails (will be caught by retry logic)
            ModelError: If model execution fails (will be caught by retry logic)
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

                # Process SSE stream (Together.ai uses OpenAI-compatible format)
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

                        # Extract content delta (same format as OpenAI)
                        if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                            delta = chunk_data["choices"][0].get("delta", {})

                            if "content" in delta and delta["content"]:
                                # Yield content chunk
                                yield delta["content"]

                    except json.JSONDecodeError:
                        # Skip malformed JSON
                        continue

        except httpx.TimeoutException as e:
            raise ProviderError(
                f"Together.ai API timeout after {self.client.timeout}s during streaming",
                provider="together",
                original_error=e,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid Together.ai API key", provider="together", original_error=e
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "Together.ai rate limit exceeded", provider="together", original_error=e
                )
            elif e.response.status_code in [408, 503, 504]:
                raise ProviderError(
                    f"Together.ai server error ({e.response.status_code}). Server may be overloaded.",
                    provider="together",
                    original_error=e,
                )
            else:
                raise ProviderError(
                    f"Together.ai API error: {e.response.status_code}",
                    provider="together",
                    original_error=e,
                )
        except httpx.RequestError as e:
            raise ProviderError(
                f"Failed to connect to Together.ai API: {str(e)}",
                provider="together",
                original_error=e,
            )

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for Together.ai models.

        Note: This is a simplified estimate that doesn't split input/output.
        Together.ai charges different rates for input vs output for some models.

        Official Together.ai Pricing (October 2025):
        Source: https://www.together.ai/pricing

        Args:
            tokens: Total tokens (prompt + completion combined)
            model: Model name

        Returns:
            Estimated cost in USD (blended average)
        """
        # Together.ai pricing (October 2025) - Blended rates where applicable
        # Format: per 1M tokens (some models have input/output split)

        model_lower = model.lower()

        # Llama 4 Series (newest)
        if "llama-4-maverick" in model_lower or "llama4-maverick" in model_lower:
            # $0.27 input / $0.85 output = avg $0.56 per 1M tokens
            return (tokens / 1_000_000) * 0.56
        elif "llama-4-scout" in model_lower or "llama4-scout" in model_lower:
            # $0.18 input / $0.59 output = avg $0.385 per 1M tokens
            return (tokens / 1_000_000) * 0.385

        # Llama 3 Series (most popular)
        elif "405b" in model_lower:
            # Llama 3.1 405B Turbo: $3.50 per 1M tokens
            return (tokens / 1_000_000) * 3.50
        elif (
            "llama-3.3-70b" in model_lower
            or "llama3.3-70b" in model_lower
            or "llama-3.1-70b" in model_lower
            or "llama3.1-70b" in model_lower
            or "llama-3-70b" in model_lower
            or "llama3-70b" in model_lower
        ):
            # 70B models: $0.54-$0.90 depending on variant
            if "turbo" in model_lower:
                return (tokens / 1_000_000) * 0.88
            else:
                return (tokens / 1_000_000) * 0.90  # Reference
        elif "llama-3.2-11b" in model_lower or "llama3.2-11b" in model_lower:
            # 11B Vision: $0.18 per 1M tokens (Turbo)
            return (tokens / 1_000_000) * 0.18
        elif (
            "llama-3.2-8b" in model_lower
            or "llama3.2-8b" in model_lower
            or "llama-3.1-8b" in model_lower
            or "llama3.1-8b" in model_lower
            or "llama-3-8b" in model_lower
            or "llama3-8b" in model_lower
        ):
            # 8B models: $0.10-$0.20 depending on variant
            if "turbo" in model_lower:
                return (tokens / 1_000_000) * 0.18
            elif "reference" in model_lower:
                return (tokens / 1_000_000) * 0.20
            else:
                return (tokens / 1_000_000) * 0.10  # Lite (default)
        elif (
            "llama-3.2-3b" in model_lower
            or "llama3.2-3b" in model_lower
            or "llama-3.2-1b" in model_lower
            or "llama3.2-1b" in model_lower
        ):
            # Up to 3B: $0.06 per 1M tokens
            return (tokens / 1_000_000) * 0.06
        elif "llama-3.2-90b" in model_lower or "llama3.2-90b" in model_lower:
            # 90B Vision: $1.20 per 1M tokens (Turbo)
            return (tokens / 1_000_000) * 1.20

        # DeepSeek Series
        elif "deepseek-r1-distill-llama-70b" in model_lower:
            return (tokens / 1_000_000) * 2.00
        elif "deepseek-r1-distill-qwen-14b" in model_lower:
            return (tokens / 1_000_000) * 1.60
        elif "deepseek-r1-distill-qwen-1.5b" in model_lower:
            return (tokens / 1_000_000) * 0.18
        elif "deepseek-r1-throughput" in model_lower:
            # $0.55 input / $2.19 output = avg $1.37 per 1M tokens
            return (tokens / 1_000_000) * 1.37
        elif "deepseek-r1" in model_lower:
            # $3 input / $7 output = avg $5 per 1M tokens
            return (tokens / 1_000_000) * 5.00
        elif "deepseek-v3" in model_lower:
            return (tokens / 1_000_000) * 1.25
        elif "deepseek" in model_lower and "67b" in model_lower:
            return (tokens / 1_000_000) * 0.90

        # Qwen Series
        elif "qwen3-235b" in model_lower or "qwen-3-235b" in model_lower:
            # $0.20 input / $0.60 output = avg $0.40 per 1M tokens
            return (tokens / 1_000_000) * 0.40
        elif "qwen3-coder-480b" in model_lower or "qwen-3-coder-480b" in model_lower:
            return (tokens / 1_000_000) * 2.00
        elif (
            "qwen2.5-72b" in model_lower
            or "qwen-2.5-72b" in model_lower
            or "qwen-2-72b" in model_lower
        ):
            return (tokens / 1_000_000) * 1.20
        elif "qwen2.5-coder-32b" in model_lower or "qwen-2.5-coder-32b" in model_lower:
            return (tokens / 1_000_000) * 0.80
        elif "qwq-32b" in model_lower:
            return (tokens / 1_000_000) * 1.20
        elif "qwen2.5-14b" in model_lower or "qwen-2.5-14b" in model_lower:
            return (tokens / 1_000_000) * 0.80
        elif "qwen2.5-7b" in model_lower or "qwen-2.5-7b" in model_lower:
            return (tokens / 1_000_000) * 0.30
        elif "qwen" in model_lower and "vl" in model_lower:
            return (tokens / 1_000_000) * 1.20

        # Kimi Series
        elif "kimi-k2" in model_lower:
            # $1.00 input / $3.00 output = avg $2.00 per 1M tokens
            return (tokens / 1_000_000) * 2.00

        # Generic pricing by size (fallback)
        elif any(size in model_lower for size in ["110b", "100b", "90b"]):
            return (tokens / 1_000_000) * 1.80  # 80.1B - 110B
        elif any(size in model_lower for size in ["80b", "70b", "60b"]):
            return (tokens / 1_000_000) * 0.90  # 41.1B - 80B
        elif any(size in model_lower for size in ["40b", "30b", "21b"]):
            return (tokens / 1_000_000) * 0.80  # 21.1B - 41B
        elif any(size in model_lower for size in ["20b", "14b", "13b", "8b"]):
            return (tokens / 1_000_000) * 0.30  # 8.1B - 21B
        elif any(size in model_lower for size in ["7b", "6b", "4b"]):
            return (tokens / 1_000_000) * 0.20  # 4.1B - 8B
        elif any(size in model_lower for size in ["3b", "2b", "1b"]):
            return (tokens / 1_000_000) * 0.10  # Up to 4B

        # Mixtral/MoE models
        elif "mixtral" in model_lower or "mixture" in model_lower:
            if "176b" in model_lower or "480b" in model_lower:
                return (tokens / 1_000_000) * 2.40  # 176.1B - 480B total
            elif "56b" in model_lower:
                return (tokens / 1_000_000) * 1.20  # 56.1B - 176B total
            else:
                return (tokens / 1_000_000) * 0.60  # Up to 56B total

        # Default fallback (conservative estimate - 8B model)
        return (tokens / 1_000_000) * 0.20

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
