"""Ollama provider implementation for local LLM serving with tool calling."""

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
        provider: str = "ollama",
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
    # Variations: deepseek-r1, deepseek-r1:latest, deepseek-r1:8b, deepseek-r1:32b, deepseek-r1:70b
    if "deepseek-r1" in name or "deepseek_r1" in name:
        return ReasoningModelInfo(
            is_reasoning=True,
            provider="ollama",
            supports_streaming=True,
            supports_tools=True,
            supports_system_messages=True,
            supports_extended_thinking=False,
            requires_thinking_budget=False,
        )

    # Standard models (no reasoning)
    return ReasoningModelInfo(
        is_reasoning=False,
        provider="ollama",
        supports_streaming=True,
        supports_tools=True,
        supports_system_messages=True,
        supports_extended_thinking=False,
        requires_thinking_budget=False,
    )


class OllamaProvider(BaseProvider):
    """
    Ollama provider for local LLM serving with tool calling support.

    Supports: Llama 3, Llama 3.1, Llama 3.2, Mistral, CodeLlama, Phi-3, Gemma,
              Qwen, DeepSeek, and 100+ other open-source models.

    Benefits:
    - 100% FREE (no API costs)
    - Unlimited requests (no rate limits)
    - Privacy (runs locally, data never leaves your machine)
    - Fast (no network latency)
    - Works with confidence system (automatic logprobs estimation)
    - ✅ Tool calling support (added July 2024)
    - Perfect for development and testing

    Tool Calling Support:
    - ✅ Full support (added July 2024)
    - ✅ Parallel tool calls
    - ✅ Streaming tool calls
    - ✅ 100% private (local execution)
    - ⭐ Best models: llama3.1, llama3.2, mistral-nemo, qwen2.5

    Requirements:
    - Ollama installed: https://ollama.com/download
    - Model pulled: `ollama pull llama3.1` (tool-compatible model)
    - Server running: `ollama serve` (auto-starts on macOS/Windows)

                           Ollama-specific retry behavior:
                           - 404 (model not found): No retry (permanent error)
                           - 500 (timeout/overload): Retry with exponential backoff
                           - 400 (encoding issues): Retry once (often transient)
                           - Network errors: Retry with backoff
                           - Generous 300s timeout for slow CPU inference
    Now supports both complete() and stream() methods.

    Example (Basic):
        >>> # Basic usage (automatic retry on failures)
        >>> provider = OllamaProvider()
        >>>
        >>> # Non-streaming (traditional):
        >>> response = await provider.complete(
        ...     prompt="What is AI?",
        ...     model="llama3.2:1b"
        ... )
        >>> print(response.content)
        >>> print(f"Cost: ${response.cost}")  # Always $0.00!

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
        >>> # Use with tool-compatible model (llama3.1, llama3.2, etc.)
        >>> response = await provider.complete(
        ...     prompt="What's the weather in Paris?",
        ...     model="llama3.1",
        ...     tools=tools
        ... )
        >>>
        >>> if response.tool_calls:
        ...     for tool_call in response.tool_calls:
        ...         print(f"Tool: {tool_call['name']}")
        ...         print(f"Args: {tool_call['arguments']}")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 300.0,  # 5 minutes (generous for slow CPU inference)
        keep_alive: str = "5m",  # Model keep-alive duration
    ):
        """
        Initialize Ollama provider with automatic retry logic.

        Args:
            api_key: Optional API key for remote Ollama servers with authentication.
                     Not needed for local installations. Can also be set via OLLAMA_API_KEY env var.
            base_url: Ollama server URL. Defaults to http://localhost:11434.
                      Can also be set via OLLAMA_BASE_URL or OLLAMA_HOST env vars.
                      Examples:
                        - Local: http://localhost:11434
                        - Network: http://192.168.1.100:11434
                        - Remote: https://ollama.yourdomain.com
            retry_config: Custom retry configuration (optional). If None, uses defaults:
                - max_attempts: 3
                - initial_delay: 1.0s (longer delays work better for Ollama)
                - rate_limit_backoff: N/A (Ollama has no rate limits)
            timeout: Request timeout in seconds (default: 300s for slow inference)
            keep_alive: How long to keep model loaded (e.g., "5m", "10m", "-1" for always)
        """
        # Call parent init to load API key, check logprobs support, and setup retry
        super().__init__(api_key=api_key, retry_config=retry_config)

        # Support both OLLAMA_BASE_URL (standard) and OLLAMA_HOST (legacy)
        self.base_url = (
            base_url
            or os.getenv("OLLAMA_BASE_URL")
            or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        )
        self.timeout = timeout
        self.keep_alive = keep_alive

        # Initialize HTTP client with optional auth for remote Ollama
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            # Support custom auth for remote/network Ollama servers
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.AsyncClient(
            headers=headers, timeout=self.timeout  # Generous timeout for local inference
        )

    def _load_api_key(self) -> Optional[str]:
        """
        Load API key from environment.

        Ollama doesn't require an API key for local installations,
        but may need one for remote/network deployments with authentication.

        Returns:
            API key from OLLAMA_API_KEY environment variable, or None
        """
        return os.getenv("OLLAMA_API_KEY")

    def _check_logprobs_support(self) -> bool:
        """
        Check if provider supports native logprobs.

        Returns:
            False - Ollama does NOT support native logprobs.
                    Automatic fallback estimation is used instead.
        """
        return False

    def _convert_tools_to_ollama(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert tools from universal format to Ollama format.

        Ollama uses the same format as OpenAI (OpenAI-compatible).

        Universal format:
        {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {...}  # JSON Schema
        }

        Ollama format (same as OpenAI):
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
            List of tools in Ollama format
        """
        if not tools:
            return []

        ollama_tools = []
        for tool in tools:
            ollama_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            ollama_tools.append(ollama_tool)

        return ollama_tools

    def _parse_tool_calls(self, message: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
        """
        Parse tool calls from Ollama response into universal format.

        Ollama uses the same format as OpenAI (OpenAI-compatible).

        Ollama format:
        {
            "tool_calls": [{
                "function": {
                    "name": "get_weather",
                    "arguments": {"location": "Paris"}  # Already parsed as dict
                }
            }]
        }

        Universal format:
        {
            "id": "call_0",  # Generated (Ollama doesn't provide IDs)
            "type": "function",
            "name": "get_weather",
            "arguments": {"location": "Paris"}
        }

        Args:
            message: Ollama response message

        Returns:
            List of tool calls in universal format, or None
        """
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            return None

        universal_tool_calls = []
        for idx, tool_call in enumerate(tool_calls):
            try:
                function_data = tool_call.get("function", {})

                # Parse arguments if they're a string
                arguments = function_data.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                universal_call = {
                    "id": f"call_{idx}",  # Ollama doesn't provide IDs, generate them
                    "type": "function",
                    "name": function_data.get("name", ""),
                    "arguments": arguments,
                }
                universal_tool_calls.append(universal_call)
            except (KeyError, TypeError) as e:
                # Log error but continue processing other tool calls
                if os.getenv("DEBUG_TOOLS"):
                    print(f"⚠️ Error parsing tool call: {e}")
                continue

        return universal_tool_calls if universal_tool_calls else None

    async def complete_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict[str, Any]]] = None,
        model: str = "llama3.1",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Complete a conversation with tool calling support.

        This method enables the model to call tools/functions during generation.
        The model can request to call multiple tools in parallel.

        Phase 3: Ollama Provider Tool Integration
        - Full tool support (added July 2024)
        - 100% local and private
        - OpenAI-compatible format
        - Best models: llama3.1, llama3.2, mistral-nemo, qwen2.5

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
            model: Model name (e.g., 'llama3.1', 'llama3.2', 'mistral-nemo')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            tool_choice: Control tool calling behavior (Ollama doesn't support this parameter,
                        but accepted for API compatibility)
            **kwargs: Additional Ollama parameters

        Returns:
            ModelResponse with tool_calls populated if model wants to call tools:
                response.tool_calls = [
                    {
                        "id": "call_0",
                        "type": "function",
                        "name": "get_weather",
                        "arguments": {"location": "Paris"}
                    }
                ]

        Raises:
            ProviderError: If Ollama server not reachable
            ModelError: If model not found or doesn't support tools

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
            ...     model="llama3.1"
            ... )
            >>>
            >>> # Check if model wants to call tools
            >>> if response.tool_calls:
            ...     for tool_call in response.tool_calls:
            ...         print(f"Calling: {tool_call['name']}")
            ...         print(f"Arguments: {tool_call['arguments']}")
        """
        start_time = time.time()

        # Convert tools to Ollama format
        ollama_tools = self._convert_tools_to_ollama(tools) if tools else None

        # Build request payload (Ollama chat format)
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,  # Non-streaming mode
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "keep_alive": self.keep_alive,
        }

        # Add tools if provided
        if ollama_tools:
            payload["tools"] = ollama_tools

        # Add any additional options
        if kwargs:
            payload["options"].update(kwargs)

        try:
            # Make API request to Ollama chat endpoint (retry handled by parent class)
            response = await self.client.post(
                f"{self.base_url}/api/chat", json=payload  # Use /api/chat for tool calling
            )
            response.raise_for_status()

            data = response.json()

            # Extract response
            message = data.get("message", {})
            content = message.get("content", "") or ""  # May be empty if only tool calls

            # Estimate tokens (Ollama doesn't return counts)
            prompt_tokens = sum(len(m.get("content", "")) for m in messages) // 4
            completion_tokens = len(content) // 4
            tokens_used = prompt_tokens + completion_tokens

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate cost (always $0 for Ollama!)
            cost = 0.0

            # Parse tool calls if present
            tool_calls = self._parse_tool_calls(message)

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
                confidence = 0.75  # Good confidence for local model tool calls

                # Temperature-based confidence adjustment
                if temperature == 0:
                    confidence = 0.80  # Higher for deterministic calls
                elif temperature > 1.5:
                    confidence = 0.70  # Lower for very creative calls

                confidence_components = {"base": 0.75, "temperature_adjustment": confidence - 0.75}

            elif tools:
                # Tools were available but model chose to respond with text
                confidence_method = "tool-available-text-chosen"

                # Use semantic confidence estimation for text response quality
                if self._confidence_estimator and content:
                    metadata_for_confidence = {
                        "finish_reason": "stop" if data.get("done") else "incomplete",
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
                    confidence = 0.65
                    confidence_components = {"fallback": 0.65}

            else:
                # No tools provided - use standard semantic confidence
                confidence_method = "multi-signal-hybrid"

                if self._confidence_estimator and content:
                    metadata_for_confidence = {
                        "finish_reason": "stop" if data.get("done") else "incomplete",
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
                    confidence = 0.75
                    confidence_components = {"fallback": 0.75}

            # Optional debug logging
            if os.getenv("DEBUG_CONFIDENCE"):
                print("🔍 Ollama Tool Call Confidence Debug:")
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
                "done": data.get("done"),
                "total_duration": data.get("total_duration"),
                "load_duration": data.get("load_duration"),
                "prompt_eval_count": data.get("prompt_eval_count"),
                "eval_count": data.get("eval_count"),
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
                provider="ollama",
                cost=cost,  # FREE!
                tokens_used=tokens_used,
                confidence=confidence,  # Use calculated confidence
                latency_ms=latency_ms,
                metadata=response_metadata,
            )

            # Add tool calls to response
            if tool_calls:
                model_response.tool_calls = tool_calls

            return model_response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelError(
                    f"Model '{model}' not found. Did you run 'ollama pull {model}'? "
                    f"For tool calling, use models like: llama3.1, llama3.2, mistral-nemo, qwen2.5",
                    model=model,
                    provider="ollama",
                )
            elif e.response.status_code == 500:
                # Check if error mentions tool support
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", "")
                    if "tool" in error_msg.lower() or "function" in error_msg.lower():
                        raise ModelError(
                            f"Model '{model}' may not support tool calling. "
                            f"Error: {error_msg}\n\n"
                            f"Tool-compatible models: llama3.1, llama3.2, mistral-nemo, qwen2.5, phi3",
                            model=model,
                            provider="ollama",
                        )
                except:
                    pass

                raise ProviderError(
                    "Ollama server error (500). This may be a timeout or server overload.",
                    provider="ollama",
                    original_error=e,
                )
            elif e.response.status_code == 400:
                error_msg = "Ollama bad request (400)"
                try:
                    error_data = e.response.json()
                    if "error" in error_data:
                        error_msg = f"Ollama error: {error_data['error']}"
                except:
                    pass
                raise ProviderError(error_msg, provider="ollama", original_error=e)
            else:
                raise ProviderError(
                    f"Ollama API error: {e.response.status_code}",
                    provider="ollama",
                    original_error=e,
                )
        except httpx.ConnectError as e:
            raise ProviderError(
                "Cannot connect to Ollama. Is it running? Try: 'ollama serve'",
                provider="ollama",
                original_error=e,
            )
        except httpx.TimeoutException as e:
            raise ProviderError(
                f"Ollama request timed out after {self.timeout}s. Consider using a smaller model or increasing timeout.",
                provider="ollama",
                original_error=e,
            )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to Ollama server", provider="ollama", original_error=e
            )
        except (KeyError, IndexError, TypeError) as e:
            raise ModelError(
                f"Failed to parse Ollama response: {e}", model=model, provider="ollama"
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
        Complete a prompt using Ollama (internal implementation with automatic retry).

        This is the internal implementation called by the public complete() method.
        Retry logic is handled automatically by the parent class.

        When tools are provided, uses /api/chat endpoint instead of /api/generate.

        Ollama-specific retry behavior:
        - 404 errors (model not found): Don't retry - permanent error
        - 500 errors (timeout/server overload): Retry with backoff
        - 400 errors (encoding issues): Can retry - often transient
        - Network errors: Retry with backoff

        Args:
            prompt: User prompt
            model: Model name (e.g., 'llama3.2:1b', 'llama3.1', 'mistral:7b')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            tools: Optional list of tools in universal format (for tool calling)
            tool_choice: Optional tool choice (accepted for compatibility, not used by Ollama)
            **kwargs: Additional Ollama parameters including:
                - logprobs (bool): Enable estimated logprobs (automatic fallback)
                - top_logprobs (int): Not used by Ollama but accepted for API compatibility

        Returns:
            ModelResponse with standardized format (with estimated logprobs if requested)
            If tools are provided and model wants to call them, tool_calls will be populated.

        Raises:
            ProviderError: If Ollama server not reachable (will be caught by retry logic)
            ModelError: If model not found or execution fails (will be caught by retry logic)
        """
        # If tools are provided, use chat endpoint with tool support
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

        # Regular completion (no tools) - use /api/generate endpoint
        start_time = time.time()

        # Extract logprobs parameter (for automatic fallback)
        logprobs_enabled = kwargs.pop("logprobs", False)
        kwargs.pop("top_logprobs", None)  # Not used, but remove if present

        # Build request payload (Ollama format)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,  # Non-streaming mode
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,  # Ollama's name for max_tokens
            },
            "keep_alive": self.keep_alive,  # Control model keep-alive
        }

        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt

        # Add any additional options
        if kwargs:
            payload["options"].update(kwargs)

        try:
            # Make API request to Ollama (retry handled by parent class)
            response = await self.client.post(f"{self.base_url}/api/generate", json=payload)
            response.raise_for_status()

            data = response.json()

            # Extract response
            content = data.get("response", "")

            # Ollama doesn't return token counts, estimate them
            prompt_tokens = len(prompt) // 4
            if system_prompt:
                prompt_tokens += len(system_prompt) // 4
            completion_tokens = len(content) // 4
            tokens_used = prompt_tokens + completion_tokens

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Calculate cost (always $0 for Ollama!)
            cost = 0.0

            # Build comprehensive metadata for confidence system
            metadata_for_confidence = {
                "finish_reason": "stop" if data.get("done") else "incomplete",
                "temperature": temperature,
                "query": prompt,  # Pass original query for semantic analysis
                "model": model,
            }

            # Calculate confidence using production confidence estimator
            # This will use semantic analysis since Ollama doesn't provide logprobs
            if self._confidence_estimator:
                confidence_analysis = self._confidence_estimator.estimate(
                    response=content,
                    query=prompt,
                    logprobs=None,  # No native logprobs
                    tokens=None,
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

            # Build response metadata
            response_metadata = {
                "done": data.get("done"),
                "total_duration": data.get("total_duration"),
                "load_duration": data.get("load_duration"),
                "prompt_eval_count": data.get("prompt_eval_count"),
                "eval_count": data.get("eval_count"),
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
                provider="ollama",
                cost=cost,  # FREE!
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata=response_metadata,
            )

            # Add estimated logprobs if requested
            # Ollama doesn't support real logprobs, so we ALWAYS use fallback
            if logprobs_enabled:
                model_response = self.add_logprobs_fallback(
                    response=model_response,
                    temperature=temperature,
                    base_confidence=0.75,  # Local models slightly lower than API models
                )

            return model_response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Model not found - permanent error, don't retry
                raise ModelError(
                    f"Model '{model}' not found. Did you run 'ollama pull {model}'?",
                    model=model,
                    provider="ollama",
                )
            elif e.response.status_code == 500:
                # Server error or timeout - can retry
                raise ProviderError(
                    "Ollama server error (500). This may be a timeout or server overload.",
                    provider="ollama",
                    original_error=e,
                )
            elif e.response.status_code == 400:
                # Bad request - sometimes transient (encoding issues)
                error_msg = "Ollama bad request (400)"
                try:
                    error_data = e.response.json()
                    if "error" in error_data:
                        error_msg = f"Ollama error: {error_data['error']}"
                except:
                    pass
                raise ProviderError(error_msg, provider="ollama", original_error=e)
            else:
                raise ProviderError(
                    f"Ollama API error: {e.response.status_code}",
                    provider="ollama",
                    original_error=e,
                )
        except httpx.ConnectError as e:
            # Connection error - can retry
            raise ProviderError(
                "Cannot connect to Ollama. Is it running? Try: 'ollama serve'",
                provider="ollama",
                original_error=e,
            )
        except httpx.TimeoutException as e:
            # Timeout - can retry
            raise ProviderError(
                f"Ollama request timed out after {self.timeout}s. Consider using a smaller model or increasing timeout.",
                provider="ollama",
                original_error=e,
            )
        except httpx.RequestError as e:
            # Other request errors - can retry
            raise ProviderError(
                "Failed to connect to Ollama server", provider="ollama", original_error=e
            )
        except (KeyError, IndexError) as e:
            # Parse error - likely permanent
            raise ModelError(
                f"Failed to parse Ollama response: {e}", model=model, provider="ollama"
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
        Stream response from Ollama API (internal implementation with automatic retry).

        This is the internal implementation called by the public stream() method.
        Retry logic is handled automatically by the parent class.

        This method enables real-time streaming for better UX. Yields chunks
        as they arrive from the local Ollama server.

        NOTE: Streaming mode does NOT support tool calling or logprobs in the stream.
        The StreamingCascadeWrapper will call complete() separately to get
        the full result with confidence scores.

        Args:
            prompt: User prompt
            model: Model name (e.g., 'llama3.2:1b', 'mistral:7b', 'codellama:7b')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt
            **kwargs: Additional Ollama parameters

        Yields:
            Content chunks as they arrive from the API

        Raises:
            ProviderError: If Ollama server not reachable (will be caught by retry logic)
            ModelError: If model not found or execution fails (will be caught by retry logic)

        Example:
            >>> provider = OllamaProvider()
            >>> async for chunk in provider.stream(
            ...     prompt="What is Python?",
            ...     model="llama3.2:1b"
            ... ):
            ...     print(chunk, end='', flush=True)
            Python is a high-level programming language...
        """
        # Build request payload (Ollama format with streaming enabled)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,  # Enable streaming
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "keep_alive": self.keep_alive,  # Control model keep-alive
        }

        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt

        # Add any additional options
        if kwargs:
            payload["options"].update(kwargs)

        try:
            # Make streaming API request (retry handled by parent class)
            async with self.client.stream(
                "POST", f"{self.base_url}/api/generate", json=payload
            ) as response:
                response.raise_for_status()

                # Process newline-delimited JSON stream
                async for line in response.aiter_lines():
                    # Skip empty lines
                    if not line.strip():
                        continue

                    try:
                        # Parse JSON chunk
                        chunk_data = json.loads(line)

                        # Extract response content
                        if "response" in chunk_data and chunk_data["response"]:
                            # Yield content chunk
                            yield chunk_data["response"]

                        # Check if done
                        if chunk_data.get("done", False):
                            break

                    except json.JSONDecodeError:
                        # Skip malformed JSON
                        continue

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Model not found - permanent error, don't retry
                raise ModelError(
                    f"Model '{model}' not found. Did you run 'ollama pull {model}'?",
                    model=model,
                    provider="ollama",
                )
            elif e.response.status_code == 500:
                # Server error or timeout - can retry
                raise ProviderError(
                    "Ollama server error (500). This may be a timeout or server overload.",
                    provider="ollama",
                    original_error=e,
                )
            elif e.response.status_code == 400:
                # Bad request - sometimes transient
                error_msg = "Ollama bad request (400)"
                try:
                    error_data = e.response.json()
                    if "error" in error_data:
                        error_msg = f"Ollama error: {error_data['error']}"
                except:
                    pass
                raise ProviderError(error_msg, provider="ollama", original_error=e)
            else:
                raise ProviderError(
                    f"Ollama API error: {e.response.status_code}",
                    provider="ollama",
                    original_error=e,
                )
        except httpx.ConnectError as e:
            # Connection error - can retry
            raise ProviderError(
                "Cannot connect to Ollama. Is it running? Try: 'ollama serve'",
                provider="ollama",
                original_error=e,
            )
        except httpx.TimeoutException as e:
            # Timeout - can retry
            raise ProviderError(
                f"Ollama request timed out after {self.timeout}s. Consider using a smaller model or increasing timeout.",
                provider="ollama",
                original_error=e,
            )
        except httpx.RequestError as e:
            # Other request errors - can retry
            raise ProviderError(
                "Failed to connect to Ollama server", provider="ollama", original_error=e
            )

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost for Ollama model.

        Ollama is 100% FREE for all models!
        No API costs, no rate limits, no hidden fees.

        Note: There are infrastructure costs (electricity, hardware) but these
        are not tracked by the API.

        Args:
            tokens: Total tokens (not used)
            model: Model name (not used)

        Returns:
            Always 0.0 (FREE!)
        """
        return 0.0  # Ollama is free!

    async def list_models(self) -> list[str]:
        """
        List available models in Ollama.

        Returns:
            List of model names (e.g., ['llama3.2:1b', 'mistral:7b'])

        Raises:
            ProviderError: If unable to fetch models
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            raise ProviderError(f"Failed to list Ollama models: {e}", provider="ollama")

    async def pull_model(self, model: str) -> None:
        """
        Pull a model from Ollama library.

        Args:
            model: Model name to pull (e.g., 'llama3.2:1b', 'llama3.1', 'mistral:7b')

        Raises:
            ProviderError: If model pull fails
        """
        try:
            response = await self.client.post(f"{self.base_url}/api/pull", json={"name": model})
            response.raise_for_status()
        except Exception as e:
            raise ProviderError(f"Failed to pull model '{model}': {e}", provider="ollama")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
