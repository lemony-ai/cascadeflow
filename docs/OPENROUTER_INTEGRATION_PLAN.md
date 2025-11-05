# OpenRouter Integration Plan

## Overview

This document outlines the plan for integrating OpenRouter support into CascadeFlow. OpenRouter is a unified API gateway that provides access to 400+ AI models from multiple providers through a single API endpoint.

## What is OpenRouter?

OpenRouter is a unified API gateway that provides access to **400+ AI models** from multiple providers (OpenAI, Anthropic, Google, Meta, Mistral, etc.) through a single API endpoint.

### Key Benefits
- **Single API key** for all models
- **OpenAI-compatible API** (drop-in replacement)
- **Automatic fallbacks** and routing
- **Pass-through pricing** (no markup)
- Models from $0 (free) to $100+ per million tokens

### Technical Details
- **Base URL**: `https://openrouter.ai/api/v1`
- **Authentication**: `Authorization: Bearer <OPENROUTER_API_KEY>`
- **Endpoint**: `/chat/completions` (OpenAI-compatible)
- **Model Format**: `provider/model-name` (e.g., `openai/gpt-4o`, `anthropic/claude-3.5-sonnet`)
- **Features**: Streaming, tool calling, structured outputs, reasoning modes
- **Models API**: `GET https://openrouter.ai/api/v1/models` - Programmatic access to model list and pricing

## Implementation Plan

### Phase 1: Python Provider Implementation (Core)

#### 1.1 Create OpenRouter Provider Class
**File**: `cascadeflow/providers/openrouter.py`

**Requirements**:
- Extend `BaseProvider` abstract class
- Implement authentication with Bearer token
- Implement required methods:
  - `_load_api_key()` - Load from `OPENROUTER_API_KEY` environment variable
  - `complete()` - Generate completions using OpenRouter API
  - `stream()` - Implement streaming support
  - `complete_with_tools()` - Tool calling support
  - `_check_logprobs_support()` - Return True (OpenRouter supports logprobs)
  - `_check_tool_support()` - Return True (OpenRouter supports tools)
- Add dynamic model list fetching from Models API
- Add pricing calculation based on model

**Implementation Details**:
```python
class OpenRouterProvider(BaseProvider):
    """OpenRouter provider - unified access to 400+ models."""

    def __init__(self, api_key: Optional[str] = None, retry_config: Optional[RetryConfig] = None):
        super().__init__(api_key=api_key, retry_config=retry_config)
        if not self.api_key:
            raise ValueError("OpenRouter API key not found...")
        self.base_url = "https://openrouter.ai/api/v1"
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://github.com/lemony-ai/cascadeflow",  # For rankings
                "X-Title": "CascadeFlow"  # For rankings
            },
            timeout=180.0
        )

    def _load_api_key(self) -> Optional[str]:
        return os.getenv("OPENROUTER_API_KEY")
```

**Reference Implementations**:
- Simple template: `cascadeflow/providers/vllm.py` (650 lines)
- Complex template: `cascadeflow/providers/openai.py` (1,017 lines)
- Use OpenAI provider as base since OpenRouter is OpenAI-compatible

**Estimated Lines of Code**: 500-800 lines

#### 1.2 Register Python Provider
**File**: `cascadeflow/providers/__init__.py`

**Changes**:
```python
from .openrouter import OpenRouterProvider

PROVIDER_REGISTRY = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "groq": GroqProvider,
    "vllm": VLLMProvider,
    "huggingface": HuggingFaceProvider,
    "together": TogetherProvider,
    "openrouter": OpenRouterProvider,  # ADD THIS
}

__all__ = [
    # ... existing exports ...
    "OpenRouterProvider",  # ADD THIS
]
```

### Phase 2: TypeScript Provider Implementation (Core)

#### 2.1 Create TypeScript Provider
**File**: `packages/core/src/providers/openrouter.ts`

**Requirements**:
- Extend `BaseProvider` class
- Implement `generate()` method
- Implement `calculateCost()` with dynamic pricing
- Add streaming support (optional)
- Mirror Python implementation

**Implementation Details**:
```typescript
import { BaseProvider, type ProviderRequest } from './base';
import type { ModelConfig } from '../config';
import type { ProviderResponse } from '../types';

export class OpenRouterProvider extends BaseProvider {
    readonly name = 'openrouter';
    private baseUrl = 'https://openrouter.ai/api/v1';

    constructor(config: ModelConfig) {
        super(config);
    }

    async generate(request: ProviderRequest): Promise<ProviderResponse> {
        const apiKey = this.getApiKey();

        const response = await fetch(`${this.baseUrl}/chat/completions`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${apiKey}`,
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/lemony-ai/cascadeflow',
                'X-Title': 'CascadeFlow'
            },
            body: JSON.stringify({
                model: request.model,
                messages: request.messages,
                temperature: request.temperature,
                max_tokens: request.maxTokens,
                // ... other parameters
            })
        });

        // Parse response and return ProviderResponse
    }

    calculateCost(promptTokens: number, completionTokens: number, model: string): number {
        // Implement dynamic pricing lookup
        // Could cache model pricing from Models API
    }
}
```

**Reference Implementations**:
- `packages/core/src/providers/openai.ts`
- `packages/core/src/providers/groq.ts`

**Estimated Lines of Code**: 300-400 lines

#### 2.2 Register TypeScript Provider
**File**: `packages/core/src/agent.ts`

**Changes**:
```typescript
import { OpenRouterProvider } from './providers/openrouter';

// Register providers (around lines 24-31)
providerRegistry.register('openai', OpenAIProvider);
providerRegistry.register('anthropic', AnthropicProvider);
providerRegistry.register('groq', GroqProvider);
providerRegistry.register('together', TogetherProvider);
providerRegistry.register('ollama', OllamaProvider);
providerRegistry.register('huggingface', HuggingFaceProvider);
providerRegistry.register('vllm', VLLMProvider);
providerRegistry.register('openrouter', OpenRouterProvider);  // ADD THIS
```

### Phase 3: Configuration & Documentation

#### 3.1 Environment Configuration
**File**: `.env.example`

**Add Section**:
```bash
# ============================================================================
# OpenRouter - Unified API for 400+ Models
# ============================================================================
OPENROUTER_API_KEY=your_openrouter_api_key_here
# Get your key: https://openrouter.ai/keys
# Browse models: https://openrouter.ai/models
#
# Model Format: provider/model-name
# Examples:
#   - openai/gpt-4o
#   - anthropic/claude-3.5-sonnet
#   - meta-llama/llama-3.1-405b-instruct
#   - google/gemini-pro-1.5
#   - mistralai/mistral-large
#
# Pricing: Pass-through (no markup) + platform fee
# Free models available with rate limits (50 requests/day)
```

#### 3.2 Create Python Usage Example
**File**: `examples/openrouter_example.py`

```python
"""Example using OpenRouter to access multiple models with one API key."""

import asyncio
from cascadeflow import CascadeAgent, ModelConfig


async def main():
    """Demonstrate OpenRouter integration with CascadeFlow."""

    # Define models from different providers via OpenRouter
    models = [
        # Free/cheap models for initial attempts
        ModelConfig(
            name="meta-llama/llama-3.1-8b-instruct",
            provider="openrouter",
            cost=0.00005,  # $0.05 per 1M tokens
            speed_ms=500,
        ),
        # Mid-tier model
        ModelConfig(
            name="openai/gpt-4o-mini",
            provider="openrouter",
            cost=0.00015,  # $0.15 per 1M tokens
            speed_ms=800,
        ),
        # Premium model for complex tasks
        ModelConfig(
            name="anthropic/claude-3.5-sonnet",
            provider="openrouter",
            cost=0.003,  # $3.00 per 1M tokens
            speed_ms=1200,
        ),
    ]

    # Create agent with cascade configuration
    agent = CascadeAgent(
        models=models,
        initial_threshold=0.7,  # Use cheap models if confidence >= 70%
    )

    # Example 1: Simple question
    print("=" * 80)
    print("Example 1: Simple Question")
    print("=" * 80)
    result = await agent.run("What is the capital of France?")
    print(f"Answer: {result.content}")
    print(f"Model used: {result.model_used}")
    print(f"Cost: ${result.total_cost:.6f}")
    print(f"Savings: {result.savings_percentage:.1f}%")

    # Example 2: Complex reasoning task
    print("\n" + "=" * 80)
    print("Example 2: Complex Reasoning")
    print("=" * 80)
    result = await agent.run(
        "Explain the implications of quantum entanglement for "
        "quantum computing and cryptography."
    )
    print(f"Answer: {result.content[:200]}...")
    print(f"Model used: {result.model_used}")
    print(f"Cost: ${result.total_cost:.6f}")

    # Example 3: With tools
    print("\n" + "=" * 80)
    print("Example 3: Tool Calling")
    print("=" * 80)

    tools = [
        {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name"
                    }
                },
                "required": ["location"]
            }
        }
    ]

    result = await agent.run(
        "What's the weather like in Tokyo?",
        tools=tools
    )
    print(f"Tool calls: {result.tool_calls}")
    print(f"Model used: {result.model_used}")


if __name__ == "__main__":
    asyncio.run(main())
```

#### 3.3 Create TypeScript Usage Example
**File**: `packages/core/examples/nodejs/openrouter-example.ts`

```typescript
import { CascadeAgent } from '@cascadeflow/core';

async function main() {
    // Define models from different providers via OpenRouter
    const models = [
        {
            name: 'meta-llama/llama-3.1-8b-instruct',
            provider: 'openrouter',
            cost: 0.00005,
        },
        {
            name: 'openai/gpt-4o-mini',
            provider: 'openrouter',
            cost: 0.00015,
        },
        {
            name: 'anthropic/claude-3.5-sonnet',
            provider: 'openrouter',
            cost: 0.003,
        }
    ];

    const agent = new CascadeAgent({
        models,
        initialThreshold: 0.7
    });

    // Example usage
    const result = await agent.run('Explain quantum computing in simple terms');

    console.log(`Answer: ${result.content}`);
    console.log(`Model used: ${result.modelUsed}`);
    console.log(`Cost: $${result.totalCost.toFixed(6)}`);
    console.log(`Savings: ${result.savingsPercentage.toFixed(1)}%`);
}

main();
```

#### 3.4 Update Provider Documentation
**File**: `docs/guides/providers.md`

**Add Section**:
```markdown
### OpenRouter

**Type**: Cloud API (Unified Gateway)
**Cost**: Pass-through pricing (no markup) + platform fee
**Website**: https://openrouter.ai

OpenRouter provides unified access to 400+ AI models from multiple providers through a single API key.

#### Setup

1. Get API key from https://openrouter.ai/keys
2. Set environment variable:
   ```bash
   export OPENROUTER_API_KEY="your_api_key_here"
   ```

#### Supported Models

OpenRouter uses the format `provider/model-name`:

- `openai/gpt-4o` - GPT-4 Optimized
- `openai/gpt-4o-mini` - GPT-4 Mini
- `anthropic/claude-3.5-sonnet` - Claude 3.5 Sonnet
- `anthropic/claude-3-haiku` - Claude 3 Haiku
- `meta-llama/llama-3.1-405b-instruct` - Llama 3.1 405B
- `meta-llama/llama-3.1-8b-instruct` - Llama 3.1 8B
- `google/gemini-pro-1.5` - Gemini Pro 1.5
- `mistralai/mistral-large` - Mistral Large
- And 390+ more models...

Browse all models: https://openrouter.ai/models

#### Features

- ✅ Streaming
- ✅ Tool calling
- ✅ Logprobs
- ✅ Structured outputs
- ✅ Automatic fallbacks
- ✅ Multi-provider access with one key

#### Pricing

OpenRouter uses pass-through pricing (no markup on model costs). Pricing varies by model:

- **Free models**: $0 (with 50 requests/day limit)
- **Budget models**: $0.00002 - $0.0001 per 1K tokens
- **Mid-tier models**: $0.0001 - $0.001 per 1K tokens
- **Premium models**: $0.001 - $0.01+ per 1K tokens

Check current pricing at https://openrouter.ai/models

#### Example Usage

Python:
```python
from cascadeflow import CascadeAgent, ModelConfig

models = [
    ModelConfig(
        name="meta-llama/llama-3.1-8b-instruct",
        provider="openrouter",
        cost=0.00005
    ),
    ModelConfig(
        name="anthropic/claude-3.5-sonnet",
        provider="openrouter",
        cost=0.003
    ),
]

agent = CascadeAgent(models)
result = await agent.run("Your question here")
```

TypeScript:
```typescript
import { CascadeAgent } from '@cascadeflow/core';

const models = [
    { name: 'meta-llama/llama-3.1-8b-instruct', provider: 'openrouter', cost: 0.00005 },
    { name: 'anthropic/claude-3.5-sonnet', provider: 'openrouter', cost: 0.003 },
];

const agent = new CascadeAgent({ models });
const result = await agent.run('Your question here');
```

#### Benefits

1. **Simplified Setup**: One API key for 400+ models
2. **Cost Optimization**: Mix free and paid models easily
3. **Automatic Fallbacks**: If a model is unavailable, OpenRouter routes to alternatives
4. **No Vendor Lock-in**: Access models from all major providers
5. **Dynamic Updates**: New models added automatically
```

### Phase 4: Testing & Validation

#### 4.1 Create Unit Tests
**File**: `tests/test_providers/test_openrouter.py`

```python
"""Tests for OpenRouter provider."""

import os
import pytest
from cascadeflow.providers import OpenRouterProvider
from cascadeflow.schema import ModelResponse


@pytest.fixture
def provider():
    """Create OpenRouter provider for testing."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set")
    return OpenRouterProvider(api_key=api_key)


@pytest.mark.asyncio
async def test_complete(provider):
    """Test basic completion generation."""
    response = await provider.complete(
        prompt="Say 'Hello, World!' and nothing else.",
        model="meta-llama/llama-3.1-8b-instruct"
    )

    assert isinstance(response, ModelResponse)
    assert response.content
    assert "hello" in response.content.lower()
    assert response.cost >= 0
    assert response.prompt_tokens > 0
    assert response.completion_tokens > 0


@pytest.mark.asyncio
async def test_stream(provider):
    """Test streaming completion."""
    chunks = []
    async for chunk in provider.stream(
        prompt="Count from 1 to 3.",
        model="meta-llama/llama-3.1-8b-instruct"
    ):
        chunks.append(chunk)

    assert len(chunks) > 0
    full_response = "".join(chunks)
    assert full_response


@pytest.mark.asyncio
async def test_tools(provider):
    """Test tool calling support."""
    tools = [
        {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }
    ]

    response = await provider.complete_with_tools(
        messages=[
            {"role": "user", "content": "What's the weather in Paris?"}
        ],
        tools=tools,
        model="openai/gpt-4o-mini"
    )

    assert isinstance(response, ModelResponse)
    # Tool calls are optional - model may or may not use them
    if response.tool_calls:
        assert len(response.tool_calls) > 0


@pytest.mark.asyncio
async def test_error_handling(provider):
    """Test error handling with invalid model."""
    with pytest.raises(Exception):
        await provider.complete(
            prompt="Test",
            model="invalid/nonexistent-model"
        )


@pytest.mark.asyncio
async def test_logprobs_support(provider):
    """Test logprobs support."""
    assert provider._supports_logprobs is True


@pytest.mark.asyncio
async def test_tool_support(provider):
    """Test tool calling support flag."""
    assert provider._supports_tools is True


def test_api_key_loading():
    """Test API key loading from environment."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        provider = OpenRouterProvider()
        assert provider.api_key == api_key
    else:
        with pytest.raises(ValueError, match="API key not found"):
            OpenRouterProvider()
```

#### 4.2 Integration Tests
**File**: `tests/integration/test_openrouter_integration.py`

Test cascading with OpenRouter models:
```python
"""Integration tests for OpenRouter provider."""

import pytest
from cascadeflow import CascadeAgent, ModelConfig


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cascade_with_openrouter():
    """Test cascading with multiple OpenRouter models."""
    models = [
        ModelConfig(
            name="meta-llama/llama-3.1-8b-instruct",
            provider="openrouter",
            cost=0.00005
        ),
        ModelConfig(
            name="openai/gpt-4o-mini",
            provider="openrouter",
            cost=0.00015
        ),
    ]

    agent = CascadeAgent(models, initial_threshold=0.8)
    result = await agent.run("What is 2+2?")

    assert result.content
    assert "4" in result.content
    assert result.total_cost > 0
    assert result.model_used in ["meta-llama/llama-3.1-8b-instruct", "openai/gpt-4o-mini"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mixed_providers():
    """Test mixing OpenRouter with other providers."""
    models = [
        ModelConfig(name="llama-3.1-8b-instant", provider="groq", cost=0.00005),
        ModelConfig(name="openai/gpt-4o-mini", provider="openrouter", cost=0.00015),
        ModelConfig(name="gpt-4o", provider="openai", cost=0.00625),
    ]

    agent = CascadeAgent(models)
    result = await agent.run("Explain photosynthesis briefly.")

    assert result.content
    assert result.total_cost > 0
```

## Key Implementation Considerations

### 1. Model Naming Convention
OpenRouter uses the format `provider/model-name`:
- `openai/gpt-4o`
- `anthropic/claude-3.5-sonnet`
- `meta-llama/llama-3.1-405b-instruct`
- `google/gemini-pro-1.5`

### 2. Dynamic Pricing
Fetch current pricing from OpenRouter's Models API:
```python
async def _fetch_model_pricing(self) -> dict:
    """Fetch current model pricing from OpenRouter API."""
    response = await self.client.get(f"{self.base_url}/models")
    data = response.json()

    pricing = {}
    for model in data["data"]:
        pricing[model["id"]] = {
            "prompt": float(model["pricing"]["prompt"]),
            "completion": float(model["pricing"]["completion"]),
        }
    return pricing
```

### 3. OpenAI Compatibility
Since OpenRouter is OpenAI-compatible, we can reuse:
- Request/response format from OpenAI provider
- Tool calling schema (OpenAI format)
- Streaming implementation
- Error handling patterns

### 4. Special Features
- **Automatic fallbacks**: OpenRouter can route to alternative models if primary is unavailable
- **Provider routing**: Access models from multiple providers without managing multiple keys
- **Models API**: Dynamic model discovery and pricing updates
- **App attribution**: Use `HTTP-Referer` and `X-Title` headers for leaderboard rankings

### 5. Error Handling
OpenRouter-specific errors to handle:
- `400` - Invalid request (malformed model name, invalid parameters)
- `401` - Authentication failed (invalid API key)
- `402` - Insufficient credits
- `429` - Rate limit exceeded (varies by model)
- `502/503` - Provider unavailable (OpenRouter will retry automatically)
- Provider-specific errors (passed through from underlying provider)

### 6. Cost Calculation
```python
def calculate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """Calculate cost based on token usage and model pricing."""
    pricing = self._get_model_pricing(model)
    if not pricing:
        return 0.0

    prompt_cost = (prompt_tokens / 1_000_000) * pricing["prompt"]
    completion_cost = (completion_tokens / 1_000_000) * pricing["completion"]
    return prompt_cost + completion_cost
```

Note: OpenRouter prices are per million tokens, not per 1K tokens.

## File Changes Summary

| Priority | File Path | Action | Estimated Lines |
|----------|-----------|--------|-----------------|
| **CRITICAL** | `cascadeflow/providers/openrouter.py` | Create provider class | 500-800 |
| **CRITICAL** | `cascadeflow/providers/__init__.py` | Register in PROVIDER_REGISTRY | 5 |
| **CRITICAL** | `packages/core/src/providers/openrouter.ts` | Create TypeScript implementation | 300-400 |
| **CRITICAL** | `packages/core/src/agent.ts` | Register TypeScript provider | 2 |
| **HIGH** | `.env.example` | Add environment variable docs | 15 |
| **MEDIUM** | `examples/openrouter_example.py` | Create usage example | 80-100 |
| **MEDIUM** | `packages/core/examples/nodejs/openrouter-example.ts` | Create TypeScript example | 30-40 |
| **MEDIUM** | `docs/guides/providers.md` | Add provider documentation | 100-150 |
| **MEDIUM** | `tests/test_providers/test_openrouter.py` | Add unit tests | 100-150 |
| **MEDIUM** | `tests/integration/test_openrouter_integration.py` | Add integration tests | 50-80 |

**Total Estimated Lines of Code**: ~1,200-1,700 lines

## Estimated Effort

- **Phase 1 (Python)**: 2-3 hours
- **Phase 2 (TypeScript)**: 1-2 hours
- **Phase 3 (Config/Docs)**: 1 hour
- **Phase 4 (Testing)**: 1-2 hours
- **Total**: 5-8 hours

## Benefits of OpenRouter Integration

1. ✅ **Single API key** for 400+ models (simplifies setup)
2. ✅ **Cost optimization** (mix free and paid models easily)
3. ✅ **Automatic fallbacks** (improves reliability)
4. ✅ **No vendor lock-in** (access models from all major providers)
5. ✅ **Dynamic pricing** (always up-to-date costs)
6. ✅ **Easy experimentation** (try new models without new integrations)
7. ✅ **Unified interface** (consistent API across all providers)

## References

- **OpenRouter Documentation**: https://openrouter.ai/docs
- **API Reference**: https://openrouter.ai/docs/api-reference
- **Models List**: https://openrouter.ai/models
- **Get API Key**: https://openrouter.ai/keys
- **Pricing**: https://openrouter.ai/pricing
- **Models API Endpoint**: `GET https://openrouter.ai/api/v1/models`

## Next Steps

1. Review and approve this plan
2. Set up OpenRouter API key for testing
3. Begin Phase 1 implementation (Python provider)
4. Test Python implementation
5. Proceed to Phase 2 (TypeScript implementation)
6. Add documentation and examples
7. Run full test suite
8. Create pull request

## Notes

- OpenRouter is OpenAI-compatible, so implementation should be straightforward
- Can reuse much of the OpenAI provider code structure
- Dynamic model pricing requires caching to avoid API calls on every request
- Should add rate limiting awareness for free tier models
- Consider adding model listing utility function for users to discover available models
