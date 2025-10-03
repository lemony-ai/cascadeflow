"""Complete HuggingFace provider supporting all three endpoint types.

Supports:
1. Serverless Inference API (free tier) - UNRELIABLE but free
2. Inference Endpoints (paid, dedicated instances) - RELIABLE, production
3. Inference Providers (pay-per-use, third-party) - RELIABLE, alternative
"""

import os
import time
import asyncio
from typing import Optional, Dict, Any, List
from enum import Enum

import httpx

from .base import BaseProvider, ModelResponse
from ..exceptions import ProviderError, ModelError


class HuggingFaceEndpointType(Enum):
    """Types of HuggingFace endpoints."""
    SERVERLESS = "serverless"  # Free tier, small models
    INFERENCE_ENDPOINT = "inference_endpoint"  # Paid, dedicated, any model
    INFERENCE_PROVIDERS = "inference_providers"  # Pay-per-use, third-party


def get_serverless_models() -> List[str]:
    """
    Get recommended models for serverless (free) tier.

    WARNING: HuggingFace Serverless is notoriously unreliable!
    - 404 errors are common (models get unloaded)
    - 503 errors frequent (server overload)
    - Cold starts can take 30+ seconds
    - Many models simply don't work

    These models are MORE LIKELY to work, but no guarantees.
    """
    return [
        "distilgpt2",                          # Most reliable (82M params)
        "gpt2",                                # Classic (124M params)
        "openai-community/gpt2",               # Full path version
        "bigscience/bloom-560m",               # Bloom 560M
        "facebook/opt-125m",                   # OPT 125M (fast)
        "EleutherAI/pythia-70m",               # Pythia 70M (tiny)
    ]


def get_inference_endpoint_models() -> List[str]:
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
    Complete HuggingFace provider supporting all endpoint types.

    **IMPORTANT: Serverless API is UNRELIABLE!**

    We've implemented this for completeness, but strongly recommend
    using Groq (free + reliable) or Together.ai instead for free tier.

    **Three Endpoint Options:**

    1. **Serverless Inference API (Free Tier)** ⚠️ UNRELIABLE
       - Cost: $0 (with rate limits)
       - Models: Small CPU models only
       - Reliability: ~50% (404/503 errors common)
       - Use for: Testing only, NOT production
       - Alternative: Use Groq instead (free + reliable)

    2. **Inference Endpoints (Paid, Dedicated)** ✅ RELIABLE
       - Cost: ~$0.60-$4/hour (per instance)
       - Models: Any model you want
       - Reliability: Excellent (99%+)
       - Use for: Production, custom models

    3. **Inference Providers (Pay-per-use)** ✅ RELIABLE
       - Cost: Per-token pricing
       - Models: Provider-specific
       - Reliability: Provider-dependent (usually good)
       - Use for: Alternative to OpenAI/Together.ai

    Examples:
        >>> # Serverless (free tier) - NOT RECOMMENDED
        >>> provider = HuggingFaceProvider.serverless()
        >>> # Better: Use Groq instead

        >>> # Inference Endpoint (paid, dedicated) - RECOMMENDED for custom models
        >>> provider = HuggingFaceProvider.inference_endpoint(
        ...     endpoint_url="https://xyz.endpoints.huggingface.cloud"
        ... )

        >>> # Inference Providers (pay-per-use) - GOOD alternative
        >>> provider = HuggingFaceProvider.inference_providers(
        ...     provider_name="replicate"
        ... )
    """

    def __init__(
            self,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
            endpoint_type: Optional[HuggingFaceEndpointType] = None,
            verbose: bool = False,
    ):
        """
        Initialize HuggingFace provider.

        Args:
            api_key: HuggingFace API token (reads from HF_TOKEN if None)
            base_url: Custom base URL (for Inference Endpoints)
            endpoint_type: Type of endpoint (auto-detected if None)
            verbose: Print debug information
        """
        super().__init__(api_key)

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
            print("   • Not suitable for production")
            print("   • Consider using Groq instead (free + reliable)")
            print("   • Get Groq key: https://console.groq.com")

        # Set base URL based on endpoint type
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = self._get_default_base_url(endpoint_type)

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            headers=self._get_headers(),
            timeout=60.0
        )

    @classmethod
    def serverless(cls, api_key: Optional[str] = None, verbose: bool = False):
        """
        Create provider for Serverless Inference API (free tier).

        ⚠️  WARNING: This endpoint is UNRELIABLE!
        - 404 errors common (models unloaded)
        - 503 errors frequent (overload)
        - Cold starts 30+ seconds
        - Not suitable for production

        Alternative: Use Groq (free + reliable)
        https://console.groq.com

        Example:
            >>> provider = HuggingFaceProvider.serverless(verbose=True)
            >>> # Try distilgpt2 (most reliable)
            >>> result = await provider.complete(
            ...     model="distilgpt2",
            ...     prompt="Hello",
            ...     max_retries=3  # Retry on errors
            ... )
        """
        return cls(
            api_key=api_key,
            endpoint_type=HuggingFaceEndpointType.SERVERLESS,
            verbose=verbose
        )

    @classmethod
    def inference_endpoint(
            cls,
            endpoint_url: str,
            api_key: Optional[str] = None,
            verbose: bool = False
    ):
        """
        Create provider for Inference Endpoint (paid, dedicated).

        ✅ RELIABLE - This is the production-grade option.

        Args:
            endpoint_url: Your endpoint URL from HuggingFace
            api_key: HuggingFace API token
            verbose: Print debug information

        Setup:
            1. Go to: https://ui.endpoints.huggingface.co/
            2. Create endpoint with your model
            3. Wait 2-3 minutes for deployment
            4. Copy endpoint URL

        Example:
            >>> provider = HuggingFaceProvider.inference_endpoint(
            ...     endpoint_url="https://abc.us-east-1.aws.endpoints.huggingface.cloud"
            ... )
            >>> result = await provider.complete(
            ...     model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            ...     prompt="Hello"
            ... )
        """
        return cls(
            api_key=api_key,
            base_url=endpoint_url,
            endpoint_type=HuggingFaceEndpointType.INFERENCE_ENDPOINT,
            verbose=verbose
        )

    @classmethod
    def inference_providers(
            cls,
            provider_name: str,
            api_key: Optional[str] = None,
            verbose: bool = False
    ):
        """
        Create provider for Inference Providers (pay-per-use).

        ✅ RELIABLE - Good alternative to OpenAI/Together.ai

        Args:
            provider_name: Provider name (e.g., "replicate", "aws")
            api_key: HuggingFace API token
            verbose: Print debug information

        Example:
            >>> provider = HuggingFaceProvider.inference_providers(
            ...     provider_name="replicate"
            ... )
        """
        return cls(
            api_key=api_key,
            base_url=f"https://api.endpoints.huggingface.cloud/v2/provider/{provider_name}",
            endpoint_type=HuggingFaceEndpointType.INFERENCE_PROVIDERS,
            verbose=verbose
        )

    def _detect_endpoint_type(
            self,
            base_url: Optional[str]
    ) -> HuggingFaceEndpointType:
        """Detect endpoint type from base URL."""
        if not base_url:
            return HuggingFaceEndpointType.SERVERLESS

        if "endpoints.huggingface.cloud" in base_url:
            if "/provider/" in base_url:
                return HuggingFaceEndpointType.INFERENCE_PROVIDERS
            else:
                return HuggingFaceEndpointType.INFERENCE_ENDPOINT

        return HuggingFaceEndpointType.SERVERLESS

    def _get_default_base_url(
            self,
            endpoint_type: HuggingFaceEndpointType
    ) -> str:
        """Get default base URL for endpoint type."""
        if endpoint_type == HuggingFaceEndpointType.SERVERLESS:
            return "https://api-inference.huggingface.co"
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

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for endpoint type."""
        headers = {
            "Content-Type": "application/json"
        }

        # Authorization header format differs by endpoint type
        if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.endpoint_type == HuggingFaceEndpointType.INFERENCE_ENDPOINT:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.endpoint_type == HuggingFaceEndpointType.INFERENCE_PROVIDERS:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment."""
        api_key = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")
        if not api_key:
            raise ValueError(
                "HuggingFace API token not found. Set HF_TOKEN or HUGGINGFACE_API_KEY "
                "environment variable. Get token at: https://huggingface.co/settings/tokens"
            )
        return api_key

    async def complete(
            self,
            prompt: str,
            model: str,
            max_tokens: int = 512,
            temperature: float = 0.7,
            system_prompt: Optional[str] = None,
            max_retries: int = 3,
            retry_delay: float = 2.0,
            **kwargs
    ) -> ModelResponse:
        """
        Complete a prompt using configured HuggingFace endpoint.

        Args:
            prompt: User prompt
            model: Model name (e.g., "distilgpt2", "gpt2")
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt
            max_retries: Max retry attempts for 500/503 errors
            retry_delay: Delay between retries in seconds
            **kwargs: Additional parameters

        Returns:
            ModelResponse with standardized format

        Raises:
            ProviderError: If API call fails
            ModelError: If model execution fails
        """
        start_time = time.time()

        # Build prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Build payload based on endpoint type
        payload = self._build_payload(
            full_prompt,
            model,
            max_tokens,
            temperature,
            **kwargs
        )

        # Build URL based on endpoint type
        url = self._build_url(model)

        if self.verbose:
            print(f"🔍 Requesting: {url}")
            print(f"   Model: {model}")
            print(f"   Endpoint type: {self.endpoint_type.value}")

        last_error = None

        # Retry loop (mainly for serverless which can be flaky)
        for attempt in range(max_retries):
            try:
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
                confidence = self.calculate_confidence(content)

                if self.verbose:
                    print(f"✅ Success! ({latency_ms:.0f}ms)")

                return ModelResponse(
                    content=content,
                    model=model,
                    provider="huggingface",
                    cost=cost,
                    tokens_used=tokens_used,
                    confidence=confidence,
                    latency_ms=latency_ms,
                    metadata={
                        "endpoint_type": self.endpoint_type.value,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "attempts": attempt + 1,
                    }
                )

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise ProviderError(
                        "Invalid HuggingFace API token. Get token at: "
                        "https://huggingface.co/settings/tokens",
                        provider="huggingface",
                        original_error=e
                    )
                elif e.response.status_code == 404:
                    # 404 - Model not found or not loaded
                    error_detail = e.response.text

                    # Try to extract more info from error
                    suggested_models = get_serverless_models() if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS else []

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

                    raise ProviderError(
                        error_msg,
                        provider="huggingface",
                        original_error=e
                    )
                elif e.response.status_code == 429:
                    raise ProviderError(
                        "HuggingFace rate limit exceeded. "
                        "Free tier has strict limits. Consider using Groq instead.",
                        provider="huggingface",
                        original_error=e
                    )
                elif e.response.status_code in (500, 503):
                    # Server error - retry (mainly for serverless)
                    last_error = e
                    if attempt < max_retries - 1:
                        if self.verbose:
                            print(f"⚠️  Attempt {attempt + 1}/{max_retries} failed (HTTP {e.response.status_code}), retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        error_msg = (
                            f"HuggingFace server error after {max_retries} attempts (HTTP {e.response.status_code}).\n"
                        )

                        if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
                            error_msg += (
                                "\n⚠️  Serverless API is frequently overloaded.\n"
                                "This is expected behavior for the free tier.\n\n"
                                "Recommended alternatives:\n"
                                "• Groq: https://console.groq.com (free + reliable)\n"
                                "• Together.ai: https://api.together.ai ($25 free credits)"
                            )

                        raise ProviderError(
                            error_msg,
                            provider="huggingface",
                            original_error=e
                        )
                else:
                    error_detail = e.response.text
                    raise ProviderError(
                        f"HuggingFace API error: {e.response.status_code}\n{error_detail[:200]}",
                        provider="huggingface",
                        original_error=e
                    )
            except httpx.RequestError as e:
                raise ProviderError(
                    "Failed to connect to HuggingFace API. Check your internet connection.",
                    provider="huggingface",
                    original_error=e
                )
            except (KeyError, IndexError, TypeError) as e:
                raise ModelError(
                    f"Failed to parse HuggingFace response: {e}\n"
                    f"This might indicate an API format change.",
                    model=model,
                    provider="huggingface"
                )

        if last_error:
            raise ProviderError(
                f"HuggingFace request failed after {max_retries} attempts. "
                f"Last error: {last_error}",
                provider="huggingface",
                original_error=last_error
            )

    def _build_payload(
            self,
            prompt: str,
            model: str,
            max_tokens: int,
            temperature: float,
            **kwargs
    ) -> Dict[str, Any]:
        """Build request payload based on endpoint type."""
        if self.endpoint_type == HuggingFaceEndpointType.SERVERLESS:
            # Serverless API format
            return {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "return_full_text": False,
                    **kwargs
                },
                "options": {
                    "wait_for_model": True,
                    "use_cache": False
                }
            }
        else:
            # Inference Endpoints & Providers use OpenAI-compatible format
            return {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs
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
            # Free tier
            return 0.0
        elif self.endpoint_type == HuggingFaceEndpointType.INFERENCE_ENDPOINT:
            # Paid by hour, not by token
            # Return 0 since user pays for uptime
            return 0.0
        elif self.endpoint_type == HuggingFaceEndpointType.INFERENCE_PROVIDERS:
            # Pay-per-use, but pricing varies by provider
            # Return estimate (user should check provider pricing)
            return (tokens / 1000) * 0.001  # Rough estimate

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()