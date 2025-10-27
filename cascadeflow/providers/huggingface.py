"""Complete HuggingFace provider supporting all three endpoint types with tool calling.

Supports:
1. Serverless Inference API (free tier) - UNRELIABLE but free - ❌ NO TOOL SUPPORT
2. Inference Endpoints (paid, dedicated instances) - RELIABLE, production - ⚠️ MODEL-DEPENDENT TOOLS
3. Inference Providers (pay-per-use, third-party) - RELIABLE, alternative - ✅ TOOLS SUPPORTED

LOGPROBS SUPPORT: Uses fallback estimation (HuggingFace doesn't support native logprobs)
TOOL CALLING SUPPORT: Limited - Only Inference Providers have reliable tool support

Now supports both complete() and stream() methods.
"""

import json
import os
import time
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any, Optional

import httpx

from ..exceptions import ModelError, ProviderError
from .base import BaseProvider, ModelResponse, RetryConfig


class HuggingFaceEndpointType(Enum):
    """Types of HuggingFace endpoints."""

    SERVERLESS = "serverless"  # Free tier, small models - NO TOOLS
    INFERENCE_ENDPOINT = "inference_endpoint"  # Paid, dedicated, any model - TOOLS MAYBE
    INFERENCE_PROVIDERS = "inference_providers"  # Pay-per-use, third-party - TOOLS YES


def get_serverless_models() -> list[str]:
    """
    Get recommended models for serverless (free) tier.

    WARNING: HuggingFace Serverless is notoriously unreliable!
    - 404 errors are common (models get unloaded)
    - 503 errors frequent (server overload)
    - Cold starts can take 30+ seconds
    - Many models simply don't work
    - NO TOOL CALLING SUPPORT

    These models are MORE LIKELY to work, but no guarantees.
    """
    return [
        "distilgpt2",  # Most reliable (82M params)
        "gpt2",  # Classic (124M params)
        "openai-community/gpt2",  # Full path version
        "bigscience/bloom-560m",  # Bloom 560M
        "facebook/opt-125m",  # OPT 125M (fast)
        "EleutherAI/pythia-70m",  # Pythia 70M (tiny)
    ]


def get_inference_endpoint_models() -> list[str]:
    """Get recommended models for inference endpoints (paid, reliable)."""
    return [
        "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "meta-llama/Meta-Llama-3.1-70B-Instruct",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "mistralai/Mistral-7B-Instruct-v0.2",
        "google/gemma-7b-it",
        "Qwen/Qwen2.5-72B-Instruct",
    ]


class HuggingFaceProvider(BaseProvider):
    """
    Complete HuggingFace provider supporting all endpoint types with tool calling.

    Enhanced with full retry logic, intelligent confidence estimation, and LIMITED tool calling.

    **IMPORTANT: Serverless API is UNRELIABLE!**

    We've implemented this for completeness, but strongly recommend
    using Groq (free + reliable) or Together.ai instead for free tier.

    **Three Endpoint Options:**

    1. **Serverless Inference API (Free Tier)** ⚠️ UNRELIABLE + ❌ NO TOOLS
       - Cost: $0 (with rate limits)
       - Models: Small CPU models only
       - Reliability: ~50% (404/503 errors common)
       - Tool Calling: ❌ NOT SUPPORTED
       - Use for: Testing only, NOT production
       - Alternative: Use Groq instead (free + reliable + tools)

    2. **Inference Endpoints (Paid, Dedicated)** ✅ RELIABLE + ⚠️ TOOLS MAYBE
       - Cost: ~$0.60-$4/hour (per instance)
       - Models: Any model you want
       - Reliability: Excellent (99%+)
       - Tool Calling: ⚠️ MODEL-DEPENDENT (some models support it)
       - Use for: Production, custom models

    3. **Inference Providers (Pay-per-use)** ✅ RELIABLE + ✅ TOOLS YES
       - Cost: Per-token pricing
       - Models: Provider-specific
       - Reliability: Provider-dependent (usually good)
       - Tool Calling: ✅ SUPPORTED (OpenAI-compatible)
       - Use for: Alternative to OpenAI/Together.ai

    **Logprobs Support:** Uses fallback estimation (no native API support)
    **Tool Calling Support:** Limited - Only Inference Providers are reliable


    Examples:
        >>> # Serverless (free tier) - NOT RECOMMENDED + NO TOOLS
        >>> provider = HuggingFaceProvider.serverless()
        >>> # Better: Use Groq instead
        >>>
        >>> # Inference Endpoint (paid, dedicated) - Tools may work
        >>> provider = HuggingFaceProvider.inference_endpoint(
        ...     endpoint_url="https://xyz.endpoints.huggingface.cloud"
        ... )
        >>>
        >>> # Inference Providers (pay-per-use) - TOOLS WORK
        >>> provider = HuggingFaceProvider.inference_providers(
        ...     provider_name="nebius"
        ... )
        >>>
        >>> # Tool calling (Inference Providers only!)
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
        >>> response = await provider.complete(
        ...     prompt="What's the weather in Paris?",
        ...     model="deepseek-ai/DeepSeek-R1-0528:nebius",
        ...     tools=tools
        ... )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        endpoint_type: Optional[HuggingFaceEndpointType] = None,
        retry_config: Optional[RetryConfig] = None,
        verbose: bool = False,
    ):
        """
        Initialize HuggingFace provider with automatic retry logic.

        Args:
            api_key: HuggingFace API token (reads from HF_TOKEN if None)
            base_url: Custom base URL (for Inference Endpoints)
            endpoint_type: Type of endpoint (auto-detected if None)
            retry_config: Custom retry configuration (optional). If None, uses defaults:
                - max_attempts: 3
                - initial_delay: 1.0s
                - rate_limit_backoff: 30.0s
            verbose: Print debug information
        """
        # Call parent init to load API key, check logprobs support, and setup retry
        super().__init__(api_key=api_key, retry_config=retry_config)

        self.verbose = verbose

        # Detect endpoint type from base_url if not specified
        if endpoint_type is None:
            endpoint_type = self._detect_endpoint_type(base_url)

        self.endpoint_type = endpoint_type

        # Warn if using serverless
        if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS and verbose:
            print("⚠️  WARNING: HuggingFace Serverless is unreliable!")
            print("   • 404/503 errors are very common")
            print("   • Models get unloaded frequently")
            print("   • ❌ NO tool calling support")
            print("   • Not suitable for production")
            print("   • Consider using Groq instead (free + reliable + tools)")
            print("   • Get Groq key: https://console.groq.com")

        # Set base URL based on endpoint type
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = self._get_default_base_url(endpoint_type)

        # Initialize HTTP client
        self.client = httpx.AsyncClient(headers=self._get_headers(), timeout=60.0)

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment."""
        api_key = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")
        if not api_key:
            raise ValueError(
                "HuggingFace API token not found. Set HF_TOKEN or HUGGINGFACE_API_KEY "
                "environment variable. Get token at: https://huggingface.co/settings/tokens"
            )
        return api_key

    def _check_logprobs_support(self) -> bool:
        """
        Check if provider supports native logprobs.

        HuggingFace does NOT support native logprobs in any of its APIs.
        We use fallback estimation instead.

        Returns:
            False - Always uses fallback estimation
        """
        return False

    def _convert_tools_to_openai(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert tools from universal format to OpenAI format.

        HuggingFace Inference Providers use OpenAI-compatible API.

        Universal format:
        {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {...}  # JSON Schema
        }

        OpenAI/HuggingFace format:
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
            List of tools in OpenAI/HuggingFace format
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
        Parse tool calls from HuggingFace response into universal format.

        HuggingFace Inference Providers use OpenAI-compatible format.

        HuggingFace/OpenAI format:
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
            choice: HuggingFace response choice

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
        model: str = "deepseek-ai/DeepSeek-R1-0528:nebius",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Complete a conversation with tool calling support.

        ⚠️ EXPERIMENTAL - Limited Support:
        - ✅ Inference Providers: Reliable tool support
        - ⚠️ Inference Endpoints: Model-dependent, may not work
        - ❌ Serverless: Not supported, will raise error

        This method enables the model to call tools/functions during generation.
        The model can request to call multiple tools in parallel.

        Phase 4: HuggingFace Provider Tool Integration (Optional/Experimental)
        - Works via Inference Providers (OpenAI-compatible)
        - Limited to models that support tool calling
        - Not available on Serverless API

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
            model: Model name with provider suffix (e.g., 'deepseek-ai/DeepSeek-R1-0528:nebius')
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            tool_choice: Control tool calling behavior:
                - None/omitted: Model decides
                - "auto": Model decides (explicit)
                - "none": Prevent tool calling
                - {"type": "function", "function": {"name": "get_weather"}}: Force specific tool
            **kwargs: Additional HuggingFace parameters

        Returns:
            ModelResponse with tool_calls populated if model wants to call tools

        Raises:
            ProviderError: If API call fails or endpoint doesn't support tools
            ModelError: If model execution fails

        Example:
            >>> # Must use Inference Providers for tool calling
            >>> provider = HuggingFaceProvider.inference_providers(
            ...     provider_name="nebius"
            ... )
            >>>
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
            >>> messages = [{"role": "user", "content": "Search for AI news"}]
            >>> response = await provider.complete_with_tools(
            ...     messages=messages,
            ...     tools=tools,
            ...     model="deepseek-ai/DeepSeek-R1-0528:nebius"
            ... )
        """
        # Check if endpoint supports tools
        if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
            raise ProviderError(
                "Tool calling is NOT supported on HuggingFace Serverless API. "
                "Please use:\n"
                "• HuggingFaceProvider.inference_providers() - Recommended\n"
                "• HuggingFaceProvider.inference_endpoint() - Model-dependent\n"
                "• Or use Groq/OpenAI/Anthropic for better tool support",
                provider="huggingface",
            )

        start_time = time.time()

        # Convert tools to OpenAI/HuggingFace format
        openai_tools = self._convert_tools_to_openai(tools) if tools else None

        # Build request payload (OpenAI format)
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

        # Build URL
        if self.endpoint_type == HuggingFaceEndpointType.INFERENCE_ENDPOINT:
            url = f"{self.base_url}/v1/chat/completions"
        else:  # INFERENCE_PROVIDERS
            url = f"{self.base_url}/chat/completions"

        if self.verbose:
            print(f"🔍 Tool calling request: {url}")
            print(f"   Model: {model}")
            print(f"   Tools: {len(tools) if tools else 0}")

        try:
            # Make API request (retry handled by parent class)
            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()

            # Extract response (OpenAI format)
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content", "") or ""  # May be None if only tool calls

            # Get token usage if available
            if "usage" in data:
                prompt_tokens = data["usage"].get("prompt_tokens", 0)
                completion_tokens = data["usage"].get("completion_tokens", 0)
                tokens_used = data["usage"].get("total_tokens", prompt_tokens + completion_tokens)
            else:
                # Estimate if not provided
                prompt_tokens = sum(len(m.get("content", "")) for m in messages) // 4
                completion_tokens = len(content or "") // 4
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
                confidence = 0.80  # Decent confidence for HuggingFace tool calls

                # Temperature-based confidence adjustment
                if temperature == 0:
                    confidence = 0.85  # Higher for deterministic calls
                elif temperature > 1.5:
                    confidence = 0.75  # Lower for very creative calls

                confidence_components = {"base": 0.80, "temperature_adjustment": confidence - 0.80}

            elif tools:
                # Tools were available but model chose to respond with text
                confidence_method = "tool-available-text-chosen"

                # Use semantic confidence estimation for text response quality
                if self._confidence_estimator and content:
                    metadata_for_confidence = {
                        "finish_reason": choice.get("finish_reason", "stop"),
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
                        "finish_reason": choice.get("finish_reason", "stop"),
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
                    confidence = 0.80
                    confidence_components = {"fallback": 0.80}

            # Optional debug logging
            if os.getenv("DEBUG_CONFIDENCE"):
                print("🔍 HuggingFace Tool Call Confidence Debug:")
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
                "finish_reason": choice.get("finish_reason", "stop"),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "has_tool_calls": bool(tool_calls),
                "endpoint_type": self.endpoint_type.value,
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
                provider="huggingface",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,  # Use calculated confidence
                latency_ms=latency_ms,
                metadata=response_metadata,
            )

            # Add tool calls to response
            if tool_calls:
                model_response.tool_calls = tool_calls

            if self.verbose:
                print(f"✅ Success! ({latency_ms:.0f}ms)")
                if tool_calls:
                    print(f"   Tool calls: {len(tool_calls)}")

            return model_response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid HuggingFace API token", provider="huggingface", original_error=e
                )
            elif e.response.status_code == 404:
                raise ModelError(
                    f"Model '{model}' not found. "
                    f"For Inference Providers, use format: 'org/model:provider' "
                    f"(e.g., 'deepseek-ai/DeepSeek-R1-0528:nebius')",
                    model=model,
                    provider="huggingface",
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "HuggingFace rate limit exceeded", provider="huggingface", original_error=e
                )
            elif e.response.status_code == 400:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get("error", {}).get("message", str(e))

                    # Check if model doesn't support tools
                    if "tool" in error_message.lower() or "function" in error_message.lower():
                        raise ProviderError(
                            f"Model '{model}' may not support tool calling. "
                            f"Error: {error_message}\n\n"
                            f"Try a different model or provider.",
                            provider="huggingface",
                            original_error=e,
                        )

                    raise ProviderError(
                        f"HuggingFace API error: {error_message}",
                        provider="huggingface",
                        original_error=e,
                    )
                except:
                    raise ProviderError(
                        f"HuggingFace API error: {e.response.status_code}",
                        provider="huggingface",
                        original_error=e,
                    )
            else:
                raise ProviderError(
                    f"HuggingFace API error: {e.response.status_code}",
                    provider="huggingface",
                    original_error=e,
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to HuggingFace API", provider="huggingface", original_error=e
            )
        except (KeyError, IndexError) as e:
            raise ModelError(
                f"Failed to parse HuggingFace response: {e}", model=model, provider="huggingface"
            )

    @classmethod
    def serverless(
        cls,
        api_key: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        verbose: bool = False,
    ):
        """
        Create provider for Serverless Inference API (free tier).

        ⚠️  WARNING: This endpoint is UNRELIABLE!
        - 404 errors common (models unloaded)
        - 503 errors frequent (overload)
        - Cold starts 30+ seconds
        - ❌ NO tool calling support
        - Not suitable for production

        Alternative: Use Groq (free + reliable + tools)
        https://console.groq.com

        Args:
            api_key: HuggingFace API token
            retry_config: Custom retry configuration (optional)
            verbose: Print debug information
        """
        return cls(
            api_key=api_key,
            endpoint_type=HuggingFaceEndpointType.SERVERLESS,
            retry_config=retry_config,
            verbose=verbose,
        )

    @classmethod
    def inference_endpoint(
        cls,
        endpoint_url: str,
        api_key: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        verbose: bool = False,
    ):
        """
        Create provider for Inference Endpoint (paid, dedicated).

        ✅ RELIABLE - This is the production-grade option.
        ⚠️ Tool calling: Model-dependent (may or may not work)

        Args:
            endpoint_url: Your endpoint URL from HuggingFace
            api_key: HuggingFace API token
            retry_config: Custom retry configuration (optional)
            verbose: Print debug information

        Setup:
            1. Go to: https://ui.endpoints.huggingface.co/
            2. Create endpoint with your model
            3. Wait 2-3 minutes for deployment
            4. Copy endpoint URL
        """
        return cls(
            api_key=api_key,
            base_url=endpoint_url,
            endpoint_type=HuggingFaceEndpointType.INFERENCE_ENDPOINT,
            retry_config=retry_config,
            verbose=verbose,
        )

    @classmethod
    def inference_providers(
        cls,
        provider_name: str,
        api_key: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        verbose: bool = False,
    ):
        """
        Create provider for Inference Providers (pay-per-use).

        ✅ RELIABLE - Good alternative to OpenAI/Together.ai
        ✅ Tool calling: SUPPORTED (OpenAI-compatible)

        Supported providers:
        - nebius - DeepSeek, Llama models
        - hyperbolic - Various models
        - cerebras - Fast inference
        - groq - (Better to use Groq directly)

        Args:
            provider_name: Provider name (e.g., "nebius", "hyperbolic")
            api_key: HuggingFace API token
            retry_config: Custom retry configuration (optional)
            verbose: Print debug information

        Example:
            >>> provider = HuggingFaceProvider.inference_providers(
            ...     provider_name="nebius"
            ... )
            >>> response = await provider.complete(
            ...     model="deepseek-ai/DeepSeek-R1-0528:nebius",
            ...     prompt="Hello"
            ... )
        """
        return cls(
            api_key=api_key,
            base_url=f"https://api.endpoints.huggingface.cloud/v2/provider/{provider_name}",
            endpoint_type=HuggingFaceEndpointType.INFERENCE_PROVIDERS,
            retry_config=retry_config,
            verbose=verbose,
        )

    def _detect_endpoint_type(self, base_url: Optional[str]) -> HuggingFaceEndpointType:
        """Detect endpoint type from base URL."""
        if not base_url:
            return HuggingFaceEndpointType.SERVERLESS

        if "endpoints.huggingface.cloud" in base_url:
            if "/provider/" in base_url:
                return HuggingFaceEndpointType.INFERENCE_PROVIDERS
            else:
                return HuggingFaceEndpointType.INFERENCE_ENDPOINT

        return HuggingFaceEndpointType.SERVERLESS

    def _get_default_base_url(self, endpoint_type: HuggingFaceEndpointType) -> str:
        """Get default base URL for endpoint type.

        Note: Migrated from deprecated api-inference.huggingface.co (deprecated Jan 2025)
        to new router.huggingface.co endpoint as per HuggingFace migration notice.
        """
        if endpoint_type == HuggingFaceEndpointType.SERVERLESS:
            # New endpoint as of November 2025 (old api-inference.huggingface.co deprecated)
            return "https://router.huggingface.co/hf-inference"
        elif endpoint_type == HuggingFaceEndpointType.INFERENCE_ENDPOINT:
            raise ValueError(
                "Inference Endpoint requires custom endpoint_url. "
                "Use HuggingFaceProvider.inference_endpoint(endpoint_url=...)"
            )
        elif endpoint_type == HuggingFaceEndpointType.INFERENCE_PROVIDERS:
            raise ValueError(
                "Inference Providers requires provider name. "
                "Use HuggingFaceProvider.inference_providers(provider_name=...)"
            )

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for endpoint type."""
        headers = {"Content-Type": "application/json"}

        # Authorization header format differs by endpoint type
        if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.endpoint_type == HuggingFaceEndpointType.INFERENCE_ENDPOINT:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.endpoint_type == HuggingFaceEndpointType.INFERENCE_PROVIDERS:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    async def _complete_impl(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Complete a prompt using configured HuggingFace endpoint (internal implementation with automatic retry).

        This is the internal implementation called by the public complete() method.
        Retry logic is handled automatically by the parent class.

        Tool calling only works with Inference Providers and some Inference Endpoints.

        Args:
            prompt: User prompt
            model: Model name (e.g., "distilgpt2", "deepseek-ai/DeepSeek-R1-0528:nebius")
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt
            tools: Optional list of tools in universal format (for tool calling)
            tool_choice: Optional tool choice ("auto", "none", or specific tool)
            **kwargs: Additional parameters (including logprobs, top_logprobs)

        Returns:
            ModelResponse with standardized format (with logprobs if requested)
            If tools are provided and model wants to call them, tool_calls will be populated.

        Raises:
            ProviderError: If API call fails or endpoint doesn't support tools
            ModelError: If model execution fails
        """
        # If tools are provided, check if endpoint supports them
        if tools and self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
            raise ProviderError(
                "Tool calling is NOT supported on HuggingFace Serverless API. "
                "Use inference_providers() or inference_endpoint() instead.",
                provider="huggingface",
            )

        # For tool calling with supported endpoints, convert to messages format
        if tools and self.endpoint_type in (
            HuggingFaceEndpointType.INFERENCE_ENDPOINT,
            HuggingFaceEndpointType.INFERENCE_PROVIDERS,
        ):
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

        # Extract logprobs parameters
        request_logprobs = kwargs.pop("logprobs", False)
        kwargs.pop("top_logprobs", 5)

        # Build prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Build payload based on endpoint type
        payload = self._build_payload(full_prompt, model, max_tokens, temperature, **kwargs)

        # Build URL based on endpoint type
        url = self._build_url(model)

        if self.verbose:
            print(f"🔍 Requesting: {url}")
            print(f"   Model: {model}")
            print(f"   Endpoint type: {self.endpoint_type.value}")
            if request_logprobs:
                print("   Logprobs: requested (will use fallback estimation)")

        try:
            # Make API request (retry handled by parent class)
            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()

            # Parse response based on endpoint type
            content = self._parse_response(data)

            # Estimate tokens
            prompt_tokens = len(full_prompt) // 4
            completion_tokens = len(content) // 4
            tokens_used = prompt_tokens + completion_tokens

            # Calculate metrics
            latency_ms = (time.time() - start_time) * 1000
            cost = self.estimate_cost(tokens_used, model)

            # Build comprehensive metadata for confidence system
            metadata_for_confidence = {
                "finish_reason": "stop",  # HuggingFace doesn't provide this
                "temperature": temperature,
                "query": prompt,  # Pass original query (not full_prompt with system)
                "model": model,
            }

            # Calculate confidence using production confidence estimator
            # This will use semantic analysis since HuggingFace doesn't provide logprobs
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
                "endpoint_type": self.endpoint_type.value,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "query": prompt,
                "confidence_method": confidence_method,
                "confidence_components": confidence_components,
            }

            if self.verbose:
                print(f"✅ Success! ({latency_ms:.0f}ms)")

            # Create base response
            response_obj = ModelResponse(
                content=content,
                model=model,
                provider="huggingface",
                cost=cost,
                tokens_used=tokens_used,
                confidence=confidence,
                latency_ms=latency_ms,
                metadata=response_metadata,
            )

            # Add logprobs via fallback if requested
            if request_logprobs:
                if self.verbose:
                    print(
                        "   Adding fallback logprobs (HuggingFace doesn't support native logprobs)"
                    )

                response_obj = self.add_logprobs_fallback(
                    response=response_obj,
                    temperature=temperature,
                    base_confidence=0.75,  # HuggingFace models are decent quality
                )

            return response_obj

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ProviderError(
                    "Invalid HuggingFace API token. Get token at: "
                    "https://huggingface.co/settings/tokens",
                    provider="huggingface",
                    original_error=e,
                )
            elif e.response.status_code == 404:
                # 404 - Model not found or not loaded
                error_detail = e.response.text

                # Try to extract more info from error
                suggested_models = (
                    get_serverless_models()
                    if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS
                    else []
                )

                error_msg = (
                    f"HuggingFace model '{model}' not found or not loaded (404).\n"
                    f"Error: {error_detail[:200]}\n\n"
                )

                if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
                    error_msg += (
                        "Common causes for Serverless API:\n"
                        "• Model doesn't exist or name is wrong\n"
                        "• Model was unloaded (common on free tier)\n"
                        "• Model requires more resources than available\n"
                        "• Model is not compatible with Inference API\n\n"
                        "Try these more reliable models:\n"
                        f"{chr(10).join('  • ' + m for m in suggested_models[:3])}\n\n"
                        "Or better: Use Groq (free + reliable)\n"
                        "https://console.groq.com - 14,400 free requests/day"
                    )
                elif self.endpoint_type == HuggingFaceEndpointType.INFERENCE_ENDPOINT:
                    error_msg += (
                        "For Inference Endpoints:\n"
                        "• Check endpoint URL is correct\n"
                        "• Ensure endpoint is running (not paused)\n"
                        "• Model name should match deployed model"
                    )

                raise ProviderError(error_msg, provider="huggingface", original_error=e)
            elif e.response.status_code == 429:
                raise ProviderError(
                    "HuggingFace rate limit exceeded. "
                    "Free tier has strict limits. Consider using Groq instead.",
                    provider="huggingface",
                    original_error=e,
                )
            elif e.response.status_code in (500, 503):
                # Server error - will be retried by parent class
                error_msg = f"HuggingFace server error (HTTP {e.response.status_code}).\n"

                if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
                    error_msg += (
                        "\n⚠️  Serverless API is frequently overloaded.\n"
                        "This is expected behavior for the free tier.\n\n"
                        "Recommended alternatives:\n"
                        "• Groq: https://console.groq.com (free + reliable)\n"
                        "• Together.ai: https://api.together.ai ($25 free credits)"
                    )

                raise ProviderError(error_msg, provider="huggingface", original_error=e)
            else:
                error_detail = e.response.text
                raise ProviderError(
                    f"HuggingFace API error: {e.response.status_code}\n{error_detail[:200]}",
                    provider="huggingface",
                    original_error=e,
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to HuggingFace API. Check your internet connection.",
                provider="huggingface",
                original_error=e,
            )
        except (KeyError, IndexError, TypeError) as e:
            raise ModelError(
                f"Failed to parse HuggingFace response: {e}\n"
                f"This might indicate an API format change.",
                model=model,
                provider="huggingface",
            )

    async def _stream_impl(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream response from HuggingFace API (internal implementation with automatic retry).

        This is the internal implementation called by the public stream() method.
        Retry logic is handled automatically by the parent class.

        This method enables real-time streaming for better UX. Yields chunks
        as they arrive from the API.

        NOTE: Streaming mode does NOT support tool calling or logprobs in the stream.
        The StreamingCascadeWrapper will call complete() separately to get
        the full result with confidence scores.

        NOTE: Serverless API streaming is VERY UNRELIABLE. Use Inference
        Endpoints or Providers for production streaming.

        Args:
            prompt: User prompt
            model: Model name (e.g., "distilgpt2", "gpt2")
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Yields:
            Content chunks as they arrive from the API

        Raises:
            ProviderError: If API call fails (will be caught by retry logic)
            ModelError: If model execution fails (will be caught by retry logic)
        """
        # Build prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Build payload with streaming enabled
        payload = self._build_streaming_payload(
            full_prompt, model, max_tokens, temperature, **kwargs
        )

        # Build URL based on endpoint type
        url = self._build_url(model)

        if self.verbose:
            print(f"🔍 Streaming from: {url}")
            print(f"   Model: {model}")
            print(f"   Endpoint type: {self.endpoint_type.value}")

        try:
            # Make streaming API request (retry handled by parent class)
            async with self.client.stream("POST", url, json=payload) as response:
                response.raise_for_status()

                # Process stream based on endpoint type
                if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
                    # Serverless: newline-delimited JSON
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        try:
                            chunk_data = json.loads(line)
                            # Extract token from serverless format
                            if "token" in chunk_data and "text" in chunk_data["token"]:
                                yield chunk_data["token"]["text"]
                        except json.JSONDecodeError:
                            continue

                else:
                    # Inference Endpoints & Providers: SSE format (OpenAI-compatible)
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

                            # Extract content delta (OpenAI format)
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
                raise ProviderError(
                    "Invalid HuggingFace API token", provider="huggingface", original_error=e
                )
            elif e.response.status_code == 404:
                raise ModelError(
                    f"Model '{model}' not found or not loaded", model=model, provider="huggingface"
                )
            elif e.response.status_code == 429:
                raise ProviderError(
                    "HuggingFace rate limit exceeded", provider="huggingface", original_error=e
                )
            else:
                raise ProviderError(
                    f"HuggingFace API error: {e.response.status_code}",
                    provider="huggingface",
                    original_error=e,
                )
        except httpx.RequestError as e:
            raise ProviderError(
                "Failed to connect to HuggingFace API", provider="huggingface", original_error=e
            )

    def _build_payload(
        self, prompt: str, model: str, max_tokens: int, temperature: float, **kwargs
    ) -> dict[str, Any]:
        """Build request payload based on endpoint type."""
        if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
            # Serverless API format
            return {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "return_full_text": False,
                    **kwargs,
                },
                "options": {"wait_for_model": True, "use_cache": False},
            }
        else:
            # Inference Endpoints & Providers use OpenAI-compatible format
            return {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs,
            }

    def _build_streaming_payload(
        self, prompt: str, model: str, max_tokens: int, temperature: float, **kwargs
    ) -> dict[str, Any]:
        """Build streaming request payload based on endpoint type."""
        if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
            # Serverless API format with streaming
            return {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "return_full_text": False,
                    **kwargs,
                },
                "stream": True,
                "options": {"wait_for_model": True, "use_cache": False},
            }
        else:
            # Inference Endpoints & Providers use OpenAI-compatible format
            return {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,  # Enable streaming
                **kwargs,
            }

    def _build_url(self, model: str) -> str:
        """Build request URL based on endpoint type."""
        if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
            return f"{self.base_url}/models/{model}"
        elif self.endpoint_type == HuggingFaceEndpointType.INFERENCE_ENDPOINT:
            # Inference Endpoints have model baked into URL
            return f"{self.base_url}/v1/chat/completions"
        elif self.endpoint_type == HuggingFaceEndpointType.INFERENCE_PROVIDERS:
            return f"{self.base_url}/chat/completions"

    def _parse_response(self, data: Any) -> str:
        """Parse response based on endpoint type."""
        if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
            # Serverless returns list or dict
            if isinstance(data, list) and len(data) > 0:
                return data[0].get("generated_text", "")
            elif isinstance(data, dict):
                return data.get("generated_text", "")
            else:
                raise ValueError(f"Unexpected serverless response format: {type(data)}")
        else:
            # Inference Endpoints & Providers use OpenAI format
            return data["choices"][0]["message"]["content"]

    def estimate_cost(self, tokens: int, model: str) -> float:
        """
        Estimate cost based on endpoint type.

        Args:
            tokens: Total tokens used
            model: Model name

        Returns:
            Estimated cost in USD
        """
        if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
            # Free tier (with rate limits)
            return 0.0
        elif self.endpoint_type == HuggingFaceEndpointType.INFERENCE_ENDPOINT:
            # Paid by hour ($0.60-$4/hour), not by token
            # Return 0 since user pays for uptime regardless of usage
            return 0.0
        elif self.endpoint_type == HuggingFaceEndpointType.INFERENCE_PROVIDERS:
            # Pay-per-use, but pricing varies by provider
            # Return rough estimate (user should check provider-specific pricing)
            return (tokens / 1000) * 0.001  # ~$1 per million tokens (estimate)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
