"""OpenAI provider implementation with tool calling support."""

import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx

from ..exceptions import ModelError, ProviderError
from .base import BaseProvider, HttpConfig, ModelResponse, RetryConfig

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

    def __init__(
        self,
        api_key: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        http_config: Optional[HttpConfig] = None,
    ):
        """
        Initialize OpenAI provider with automatic retry logic and enterprise HTTP support.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
            retry_config: Custom retry configuration (optional). If None, uses defaults:
                - max_attempts: 3
                - initial_delay: 1.0s
                - rate_limit_backoff: 30.0s
            http_config: HTTP configuration for SSL/proxy (default: auto-detect from env).
                Supports:
                - Custom CA bundles (SSL_CERT_FILE, REQUESTS_CA_BUNDLE)
                - Proxy servers (HTTPS_PROXY, HTTP_PROXY)
                - SSL verification control

        Example:
            # Auto-detect from environment (default)
            provider = OpenAIProvider()

            # Corporate environment with custom CA bundle
            provider = OpenAIProvider(
                http_config=HttpConfig(verify="/path/to/corporate-ca.pem")
            )

            # With proxy
            provider = OpenAIProvider(
                http_config=HttpConfig(proxy="http://proxy.corp.com:8080")
            )
        """
        # Call parent init to load API key, check logprobs support, setup retry, and http_config
        super().__init__(api_key=api_key, retry_config=retry_config, http_config=http_config)

        # Verify API key is set
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Please set OPENAI_API_KEY environment "
                "variable or pass api_key parameter."
            )

        # Initialize HTTP client with the loaded API key and HTTP config
        self.base_url = "https://api.openai.com/v1"

        # Get httpx kwargs from http_config (includes verify, proxy, timeout)
        httpx_kwargs = self.http_config.get_httpx_kwargs()
        # Override timeout for reasoning models (GPT-5, o1, o3) which can take 60-120+ seconds
        httpx_kwargs["timeout"] = 180.0  # 3 minutes for reasoning models

        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            **httpx_kwargs,
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
            function = tool.get("function") if isinstance(tool, dict) else None
            if isinstance(function, dict):
                name = function.get("name") or tool.get("name")
                description = function.get("description", tool.get("description", ""))
                parameters = function.get(
                    "parameters", tool.get("parameters", {"type": "object", "properties": {}})
                )
            else:
                name = tool.get("name") if isinstance(tool, dict) else None
                description = tool.get("description", "") if isinstance(tool, dict) else ""
                parameters = (
                    tool.get("parameters", {"type": "object", "properties": {}})
                    if isinstance(tool, dict)
                    else {"type": "object", "properties": {}}
                )

            if not name:
                if os.getenv("DEBUG_TOOLS"):
                    print("⚠️ Skipping tool without name")
                continue

            openai_tool = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            }
            openai_tools.append(openai_tool)

        return openai_tools

    def _convert_tools_to_responses(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert tools into the OpenAI Responses API format.

        Responses tools are *flattened* (name/description/parameters at the top level),
        unlike Chat Completions tools which nest fields under `function`.
        """
        if not tools:
            return []

        converted: list[dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue

            # Already in Responses format
            if tool.get("type") == "function" and isinstance(tool.get("name"), str):
                converted.append(tool)
                continue

            function = tool.get("function") if isinstance(tool, dict) else None
            if isinstance(function, dict):
                name = function.get("name") or tool.get("name")
                description = function.get("description", tool.get("description", ""))
                parameters = function.get(
                    "parameters", tool.get("parameters", {"type": "object", "properties": {}})
                )
            else:
                name = tool.get("name")
                description = tool.get("description", "")
                parameters = tool.get("parameters", {"type": "object", "properties": {}})

            if not name:
                continue

            converted.append(
                {
                    "type": "function",
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                }
            )

        return converted

    def _convert_tool_choice_to_responses(self, tool_choice: Any) -> Any:
        """
        Convert a Chat Completions-style tool_choice into Responses-style tool_choice.

        Chat Completions forced choice:
          {"type":"function","function":{"name":"calculator"}}
        Responses forced choice:
          {"type":"function","name":"calculator"}
        """
        if tool_choice is None:
            return None
        if isinstance(tool_choice, str):
            return tool_choice
        if isinstance(tool_choice, dict):
            if tool_choice.get("type") == "function":
                fn = tool_choice.get("function")
                if isinstance(fn, dict) and isinstance(fn.get("name"), str):
                    return {"type": "function", "name": fn["name"]}
                if isinstance(tool_choice.get("name"), str):
                    return tool_choice
        return tool_choice

    def _effective_responses_max_output_tokens(self, model: str, requested: int) -> int:
        """
        Ensure reasoning models have enough output budget to emit *some* text.

        Some GPT-5 responses can be empty if `max_output_tokens` is too small, because
        the budget may be consumed by internal reasoning.
        """
        model_lower = (model or "").lower()

        # Defaults tuned empirically: gpt-5 can consume large budgets in reasoning.
        default_floor = 256
        if model_lower.startswith("gpt-5") and not (
            model_lower.startswith("gpt-5-mini") or model_lower.startswith("gpt-5-nano")
        ):
            default_floor = 1024

        try:
            min_floor = int(os.getenv("CASCADEFLOW_OPENAI_MIN_OUTPUT_TOKENS", str(default_floor)))
        except ValueError:
            min_floor = default_floor

        return max(int(requested), max(1, int(min_floor)))

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

    def _should_use_responses_api(self, model: str) -> bool:
        """
        Use the OpenAI Responses API for models where Chat Completions is not reliable.

        Today this is primarily the GPT-5 family, where /chat/completions can return
        empty assistant content while consuming only reasoning tokens.
        """
        model_lower = (model or "").lower()
        if os.getenv("CASCADEFLOW_OPENAI_FORCE_CHAT_COMPLETIONS") == "1":
            return False
        if os.getenv("CASCADEFLOW_OPENAI_FORCE_RESPONSES") == "1":
            return True
        return model_lower.startswith("gpt-5")

    def _convert_messages_to_responses_input(
        self, messages: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], Optional[str]]:
        """
        Convert OpenAI-style chat messages into a Responses API input list.

        Notes:
        - We extract system messages into `instructions`.
        - Tool result messages (role="tool") are converted into plain user text so we
          don't rely on `previous_response_id` state tracking.
        """
        instructions_parts: list[str] = []
        input_messages: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                if content is None:
                    continue
                if not isinstance(content, str):
                    content = json.dumps(content)
                if content.strip():
                    instructions_parts.append(content.strip())
                continue

            if role == "tool":
                tool_name = msg.get("name")
                call_id = msg.get("tool_call_id")
                tool_content = content
                if tool_content is None:
                    tool_content = ""
                if not isinstance(tool_content, str):
                    tool_content = json.dumps(tool_content)
                prefix = "Tool result"
                if isinstance(tool_name, str) and tool_name.strip():
                    prefix = f"Tool result ({tool_name.strip()})"
                if isinstance(call_id, str) and call_id.strip():
                    prefix = f"{prefix} call_id={call_id.strip()}"
                input_messages.append({"role": "user", "content": f"{prefix}: {tool_content}"})
                continue

            if content is None:
                content = ""
            if not isinstance(content, str):
                content = json.dumps(content)

            input_messages.append({"role": role, "content": content})

        instructions = "\n".join(instructions_parts).strip() if instructions_parts else ""
        return input_messages, instructions or None

    def _parse_responses_output(
        self, data: dict[str, Any]
    ) -> tuple[str, Optional[list[dict[str, Any]]], str]:
        """Parse a Responses API response payload into (content, tool_calls, finish_reason)."""
        output = data.get("output") or []
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for item in output:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")

            if item_type == "message":
                for block in item.get("content") or []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "output_text":
                        text = block.get("text")
                        if isinstance(text, str) and text:
                            text_parts.append(text)
                continue

            if item_type == "function_call":
                name = item.get("name")
                call_id = item.get("call_id") or item.get("id")
                raw_args = item.get("arguments", "")
                parsed_args: Any
                if isinstance(raw_args, str):
                    try:
                        parsed_args = json.loads(raw_args) if raw_args else {}
                    except json.JSONDecodeError:
                        parsed_args = {"raw": raw_args}
                elif isinstance(raw_args, dict):
                    parsed_args = raw_args
                else:
                    parsed_args = {"raw": raw_args}

                if isinstance(name, str) and name:
                    tool_calls.append(
                        {
                            "id": call_id or "unknown",
                            "type": "function",
                            "name": name,
                            "arguments": parsed_args,
                        }
                    )
                continue

        finish_reason = str(data.get("status") or "completed")
        content = "".join(text_parts)
        return content, (tool_calls or None), finish_reason

    def _should_retry_responses_empty_output(
        self, *, data: dict[str, Any], content: str, tool_calls: Optional[list[dict[str, Any]]]
    ) -> bool:
        """
        GPT-5 can return only a `reasoning` output item when `max_output_tokens` is too low.
        In that case we retry once with a larger budget to ensure a non-empty answer.
        """
        if tool_calls:
            return False
        if isinstance(content, str) and content.strip():
            return False
        if os.getenv("CASCADEFLOW_OPENAI_EMPTY_OUTPUT_RETRY", "1") != "1":
            return False

        status = data.get("status")
        incomplete = data.get("incomplete_details") or {}
        reason = incomplete.get("reason") if isinstance(incomplete, dict) else None
        if status == "incomplete" and reason == "max_output_tokens":
            return True

        # Defensive: if we got no message output at all, it's also suspicious.
        output = data.get("output") or []
        if isinstance(output, list) and not any(
            isinstance(item, dict) and item.get("type") == "message" for item in output
        ):
            return True

        return False

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
        responses_tools = self._convert_tools_to_responses(tools) if tools else None

        # Build request payload with reasoning-model compatibility
        model_info = get_reasoning_model_info(model)
        is_gpt5 = model.lower().startswith("gpt-5")
        extra = dict(kwargs)
        extra.pop("max_tokens", None)
        extra.pop("max_completion_tokens", None)
        extra_tool_choice = extra.pop("tool_choice", None)
        if tool_choice is None:
            tool_choice = extra_tool_choice

        # Prefer Responses API for GPT-5 (and optionally via env override).
        if self._should_use_responses_api(model):
            input_messages, instructions = self._convert_messages_to_responses_input(messages)

            max_out = self._effective_responses_max_output_tokens(model, max_tokens)
            payload: dict[str, Any] = {
                "model": model,
                "input": input_messages,
                "max_output_tokens": max_out,
            }
            if instructions:
                payload["instructions"] = instructions

            if model_info.supports_temperature:
                payload["temperature"] = extra.pop("temperature", temperature)
            else:
                extra.pop("temperature", None)

            if responses_tools:
                payload["tools"] = responses_tools
                if tool_choice:
                    payload["tool_choice"] = self._convert_tool_choice_to_responses(tool_choice)

            if model_info.supports_reasoning_effort and "reasoning_effort" in extra:
                payload["reasoning_effort"] = extra.pop("reasoning_effort")

            payload.update(extra)

            try:
                response = await self.client.post(f"{self.base_url}/responses", json=payload)
                response.raise_for_status()
                data = response.json()

                content, tool_calls, finish_reason = self._parse_responses_output(data)
                if self._should_retry_responses_empty_output(
                    data=data, content=content, tool_calls=tool_calls
                ):
                    retry_payload = dict(payload)
                    retry_max = int(os.getenv("CASCADEFLOW_OPENAI_EMPTY_OUTPUT_RETRY_MAX", "4096"))
                    retry_payload["max_output_tokens"] = min(max_out * 2, max(1, retry_max))
                    retry_resp = await self.client.post(
                        f"{self.base_url}/responses", json=retry_payload
                    )
                    retry_resp.raise_for_status()
                    data = retry_resp.json()
                    content, tool_calls, finish_reason = self._parse_responses_output(data)

                usage = data.get("usage") or {}
                prompt_tokens = usage.get("input_tokens") or 0
                completion_tokens = usage.get("output_tokens") or 0
                tokens_used = usage.get("total_tokens") or (prompt_tokens + completion_tokens)

                latency_ms = (time.time() - start_time) * 1000

                cost = self.calculate_accurate_cost(
                    model=model,
                    prompt_tokens=int(prompt_tokens),
                    completion_tokens=int(completion_tokens),
                    total_tokens=int(tokens_used),
                )

                if tool_calls:
                    confidence_method = "tool-call-present"
                    confidence = 0.9
                    if temperature == 0:
                        confidence = 0.95
                    elif temperature > 1.0:
                        confidence = 0.85
                else:
                    if openai_tools:
                        confidence_method = "tool-available-text-chosen"
                        confidence = 0.7
                    else:
                        confidence_method = "text-only"
                        confidence = 0.8

                response_metadata = {
                    "finish_reason": finish_reason,
                    "prompt_tokens": int(prompt_tokens),
                    "completion_tokens": int(completion_tokens),
                    "has_tool_calls": bool(tool_calls),
                    "confidence_method": confidence_method,
                    "tool_choice_reasoning": (
                        "model_generated_tool_calls" if tool_calls else "model_chose_text_response"
                    ),
                }

                model_response = ModelResponse(
                    content=content or "",
                    model=model,
                    provider="openai",
                    cost=cost,
                    tokens_used=int(tokens_used),
                    confidence=confidence,
                    latency_ms=latency_ms,
                    metadata=response_metadata,
                )
                if tool_calls:
                    model_response.tool_calls = tool_calls
                return model_response

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise ProviderError(
                        "Invalid OpenAI API key", provider="openai", original_error=e
                    )
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

        # Build request payload with reasoning-model compatibility
        model_info = get_reasoning_model_info(model)
        is_gpt5 = model.lower().startswith("gpt-5")
        extra = dict(kwargs)
        extra.pop("max_tokens", None)
        extra.pop("max_completion_tokens", None)
        extra_tool_choice = extra.pop("tool_choice", None)
        if tool_choice is None:
            tool_choice = extra_tool_choice

        payload = {
            "model": model,
            "messages": messages,
        }

        if model_info.supports_temperature:
            payload["temperature"] = extra.pop("temperature", temperature)
        else:
            extra.pop("temperature", None)

        if is_gpt5 or model_info.requires_max_completion_tokens:
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens

        if model_info.supports_reasoning_effort and "reasoning_effort" in extra:
            payload["reasoning_effort"] = extra.pop("reasoning_effort")

        payload.update(extra)

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
            if self._should_use_responses_api(model):
                input_messages, instructions = self._convert_messages_to_responses_input(messages)
                max_out = self._effective_responses_max_output_tokens(model, max_tokens)
                responses_payload: dict[str, Any] = {
                    "model": model,
                    "input": input_messages,
                    "max_output_tokens": max_out,
                }
                if instructions:
                    responses_payload["instructions"] = instructions
                if model_info.supports_temperature:
                    responses_payload["temperature"] = temperature

                response = await self.client.post(
                    f"{self.base_url}/responses", json=responses_payload
                )
                response.raise_for_status()
                data = response.json()

                content, _tool_calls, finish_reason = self._parse_responses_output(data)
                if self._should_retry_responses_empty_output(
                    data=data, content=content, tool_calls=None
                ):
                    retry_payload = dict(responses_payload)
                    retry_max = int(os.getenv("CASCADEFLOW_OPENAI_EMPTY_OUTPUT_RETRY_MAX", "4096"))
                    retry_payload["max_output_tokens"] = min(max_out * 2, max(1, retry_max))
                    retry_resp = await self.client.post(
                        f"{self.base_url}/responses", json=retry_payload
                    )
                    retry_resp.raise_for_status()
                    data = retry_resp.json()
                    content, _tool_calls, finish_reason = self._parse_responses_output(data)

                usage = data.get("usage") or {}
                prompt_tokens = int(usage.get("input_tokens") or 0)
                completion_tokens = int(usage.get("output_tokens") or 0)
                tokens_used = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))

                reasoning_tokens = None
                if isinstance(usage.get("output_tokens_details"), dict):
                    details = usage.get("output_tokens_details") or {}
                    if "reasoning_tokens" in details:
                        reasoning_tokens = details.get("reasoning_tokens")

                latency_ms = (time.time() - start_time) * 1000

                cost = self.estimate_cost(
                    tokens_used,
                    model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

                metadata_for_confidence = {
                    "finish_reason": finish_reason,
                    "temperature": temperature,
                    "query": prompt,
                    "model": model,
                    "logprobs": None,
                    "tokens": None,
                }

                if self._confidence_estimator:
                    confidence_analysis = self._confidence_estimator.estimate(
                        response=content,
                        query=prompt,
                        logprobs=None,
                        tokens=None,
                        temperature=temperature,
                        metadata=metadata_for_confidence,
                    )
                    confidence = confidence_analysis.final_confidence
                    confidence_method = confidence_analysis.method_used
                    confidence_components = confidence_analysis.components or {}
                else:
                    confidence = self.calculate_confidence(content, metadata_for_confidence)
                    confidence_method = "legacy"
                    confidence_components = {}

                response_metadata = {
                    "finish_reason": finish_reason,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "query": prompt,
                    "confidence_method": confidence_method,
                    "confidence_components": confidence_components,
                }
                if reasoning_tokens is not None:
                    response_metadata["reasoning_tokens"] = reasoning_tokens

                return ModelResponse(
                    content=content,
                    model=model,
                    provider="openai",
                    cost=cost,
                    tokens_used=tokens_used,
                    confidence=confidence,
                    latency_ms=latency_ms,
                    metadata=response_metadata,
                )

            # Default: Chat Completions API.
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
                        # Handle both numeric and non-numeric values
                        if isinstance(val, (int, float)):
                            print(f"    • {comp:20s}: {val:.3f}")
                        else:
                            print(f"    • {comp:20s}: {val}")

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

        model_info = get_reasoning_model_info(model)
        is_gpt5 = model.lower().startswith("gpt-5")

        if is_gpt5:
            # Remove unsupported params for GPT-5 (keep payload clean for both APIs).
            kwargs.pop("logprobs", None)
            kwargs.pop("top_logprobs", None)

        if self._should_use_responses_api(model):
            input_messages, instructions = self._convert_messages_to_responses_input(messages)
            payload: dict[str, Any] = {
                "model": model,
                "input": input_messages,
                "max_output_tokens": self._effective_responses_max_output_tokens(model, max_tokens),
                "stream": True,
            }
            if instructions:
                payload["instructions"] = instructions
            if model_info.supports_temperature:
                payload["temperature"] = temperature

            # Convert tools/tool_choice if present (agent may pass them through stream()).
            tools_in = kwargs.pop("tools", None)
            if isinstance(tools_in, list):
                payload["tools"] = self._convert_tools_to_responses(tools_in)
            tool_choice_in = kwargs.pop("tool_choice", None)
            if tool_choice_in is not None:
                payload["tool_choice"] = self._convert_tool_choice_to_responses(tool_choice_in)

            payload.update(kwargs)

            try:
                async with self.client.stream(
                    "POST", f"{self.base_url}/responses", json=payload
                ) as response:
                    response.raise_for_status()

                    current_event: Optional[str] = None
                    async for line in response.aiter_lines():
                        if not line or not line.strip():
                            continue

                        if line.startswith("event:"):
                            current_event = line[len("event:") :].strip()
                            continue

                        if not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        event_type = chunk.get("type") or current_event
                        if event_type == "response.output_text.delta":
                            delta = chunk.get("delta")
                            if isinstance(delta, str) and delta:
                                yield delta
                        elif event_type == "response.completed":
                            break

                return

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise ProviderError(
                        "Invalid OpenAI API key", provider="openai", original_error=e
                    )
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

        # Default: Chat Completions streaming.
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,  # Enable streaming
            **kwargs,
        }

        if model_info.supports_temperature:
            payload["temperature"] = temperature

        if model_info.requires_max_completion_tokens or is_gpt5:
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens

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
