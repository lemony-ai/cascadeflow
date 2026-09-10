# Model Warmup Guide

## Overview

The **Model Warmup** feature eliminates cold-start latency by pre-loading models into memory before the first request arrives. This is especially beneficial for local inference providers like Ollama, vLLM, and HuggingFace Inference Endpoints.

## Benefits

- **50-70% faster first requests**: Eliminates model loading time
- **Predictable latency**: All requests have consistent response times
- **Early error detection**: Configuration issues discovered at startup
- **Better resource utilization**: Models stay resident in memory

## Quick Start

```python
from cascadeflow import CascadeAgent
from cascadeflow.providers import OllamaProvider
from cascadeflow.schema.config import ModelConfig

# Create agent with local models
cheap_model = ModelConfig(
    provider=OllamaProvider(),
    model="llama3.2:1b",
    cost=0.0,
    speed_ms=100,
    quality=0.6
)

agent = CascadeAgent(models=[cheap_model])

# Warm up models during startup
result = await agent.warmup()

print(f"Warmed up {result['models_warmed']} models in {result['total_time_ms']:.0f}ms")

# Now all requests are fast (no cold start)
response = await agent.run("What is AI?")  # ⚡ Fast from the start!
```

## How It Works

### For Local Providers

**Ollama**:
1. Sends minimal inference request to load model into memory
2. Uses `keep_alive` to keep model resident
3. Eliminates 2-10 second cold start

**vLLM**:
1. Performs test inference to prime KV cache
2. Triggers model compilation (if using TensorRT)
3. Establishes connection pool

**HuggingFace Inference Endpoints**:
1. Wakes up dedicated instance
2. Loads model weights
3. Primes inference engine

### For Cloud Providers

Cloud providers (OpenAI, Anthropic, Groq, etc.) automatically skip warmup since they don't have cold-start issues.

## Performance Comparison

### Without Warmup
```python
agent = CascadeAgent(models=[local_model])

# First request: 5,234ms ❌ (cold start)
await agent.run("Hello")

# Second request: 1,523ms ✅ (warmed up)
await agent.run("Hello")
```

### With Warmup
```python
agent = CascadeAgent(models=[local_model])

# Warmup: 1,200ms (one-time cost)
await agent.warmup()

# First request: 1,534ms ✅ (already warm)
await agent.run("Hello")

# Second request: 1,521ms ✅ (consistent)
await agent.run("Hello")
```

**Result**: 50-70% faster first request!

## Configuration Options

### Basic Configuration

```python
# Warm up all configured models
result = await agent.warmup()
```

### Custom Warmup Prompt

```python
# Use custom prompt (default: "Hello")
result = await agent.warmup(warmup_prompt="test")
```

### Provider-Specific Configuration

```python
# Ollama: Configure keep-alive duration
result = await agent.warmup(
    warmup_config={
        "keep_alive": 7200,  # Keep models in memory for 2 hours
        "max_tokens": 1,     # Generate minimal tokens
        "parallel": True     # Warm up models in parallel
    }
)
```

### Sequential Warmup (Memory-Constrained Systems)

```python
# Warm up models one at a time (lower memory usage)
result = await agent.warmup(parallel=False)
```

## Production Patterns

### Pattern 1: Startup Warmup

```python
async def start_server():
    # Initialize agent
    agent = CascadeAgent(models=[...])

    # Warm up before accepting requests
    print("Warming up models...")
    result = await agent.warmup()

    if result['success']:
        print(f"✅ Ready! Warmed {result['models_warmed']} models")
        # Start accepting requests
        start_request_handler(agent)
    else:
        print("⚠️ Warmup failed, but can still serve (with cold starts)")
        start_request_handler(agent)
```

### Pattern 2: Background Warmup

```python
async def start_server():
    # Initialize agent
    agent = CascadeAgent(models=[...])

    # Start warmup in background (non-blocking)
    warmup_task = asyncio.create_task(agent.warmup())

    # Do other initialization
    await initialize_database()
    await load_configuration()

    # Wait for warmup to complete
    await warmup_task

    # Start serving
    start_request_handler(agent)
```

### Pattern 3: Health Check Integration

```python
class HealthCheck:
    def __init__(self, agent):
        self.agent = agent
        self.warmed_up = False

    async def warmup(self):
        """Warm up and mark as ready."""
        result = await self.agent.warmup()
        self.warmed_up = result['success']
        return self.warmed_up

    async def is_ready(self):
        """Check if service is ready."""
        return self.warmed_up

# Usage
health = HealthCheck(agent)
await health.warmup()

@app.get("/health")
async def health_check():
    if await health.is_ready():
        return {"status": "ready"}
    return {"status": "warming_up"}, 503
```

## Advanced Usage

### Multiple Providers

```python
from cascadeflow.providers import OllamaProvider, VLLMProvider

# Mix local and cloud providers
models = [
    ModelConfig(provider=OllamaProvider(), model="llama3.2:1b", ...),
    ModelConfig(provider=VLLMProvider(), model="mistral-7b", ...),
    ModelConfig(provider=OpenAIProvider(), model="gpt-4", ...),
]

agent = CascadeAgent(models=models)

# Warmup intelligently handles all providers
result = await agent.warmup()

# Result shows per-provider details
for provider_result in result['results']:
    print(f"{provider_result['provider']}: {provider_result['models_warmed']}")
```

### Idempotent Warmup

```python
# Safe to call multiple times
await agent.warmup()  # First call: actually warms up
await agent.warmup()  # Second call: redundant but safe
await agent.warmup()  # Third call: still safe
```

### Error Handling

```python
result = await agent.warmup()

if not result['success']:
    # Check which models failed
    for provider_result in result['results']:
        if not provider_result['success']:
            errors = provider_result.get('errors', {})
            print(f"Failed to warm {provider_result['provider']}: {errors}")

    # Decide how to proceed
    if result['models_warmed'] == 0:
        # No models warmed - abort
        raise RuntimeError("Warmup failed completely")
    else:
        # Some models warmed - continue with degraded performance
        print(f"⚠️ Partial warmup: {result['models_warmed']}/{result['total_models']}")
```

## Provider-Specific Notes

### Ollama

```python
# Default: 1 hour keep-alive
await agent.warmup()

# Custom keep-alive (2 hours)
await agent.warmup(warmup_config={"keep_alive": 7200})

# No keep-alive (model unloads after each request)
await agent.warmup(warmup_config={"keep_alive": 0})
```

**Best Practices**:
- Use longer `keep_alive` for production (3600-7200 seconds)
- Use shorter `keep_alive` for development (300-600 seconds)
- Monitor Ollama memory usage with `ollama ps`

### vLLM

```python
# vLLM warmup is fast (usually < 500ms)
await agent.warmup()

# Parallel warmup for multiple models
await agent.warmup(warmup_config={"parallel": True})
```

**Best Practices**:
- Warmup is especially beneficial for TensorRT-optimized models
- First request after warmup primes KV cache
- Use warmup to detect model loading issues early

### HuggingFace Inference Endpoints

```python
# Only benefits dedicated Inference Endpoints
provider = HuggingFaceProvider.inference_endpoint(
    endpoint_url="https://xyz.endpoints.huggingface.cloud"
)

# Serverless and Inference Providers skip warmup
await agent.warmup()  # No-op for serverless
```

## Benchmarking

Use the included benchmark to measure improvements:

```bash
python benchmarks/warmup_benchmark.py
```

Expected results:
- **Cold start**: 3,000-8,000ms (first request)
- **With warmup**: 1,500-2,000ms (first request)
- **Improvement**: 50-70% faster

## Troubleshooting

### Warmup Takes Too Long

```python
# Reduce warmup overhead
await agent.warmup(
    warmup_config={
        "max_tokens": 1,      # Generate only 1 token
        "parallel": True      # Warm up in parallel
    }
)
```

### Models Not Staying in Memory (Ollama)

```python
# Increase keep-alive duration
await agent.warmup(
    warmup_config={"keep_alive": 7200}  # 2 hours
)

# Or configure globally
provider = OllamaProvider(keep_alive="2h")
```

### Warmup Fails but Requests Work

This is expected! Warmup failure doesn't prevent the agent from working - it just means first requests will have cold-start latency.

```python
result = await agent.warmup()

if not result['success']:
    print("⚠️ Warmup failed, but agent can still serve requests")
    # Continue anyway - first request will be slower
```

### Out of Memory

```python
# Warm up models sequentially (one at a time)
await agent.warmup(parallel=False)

# Or reduce keep-alive so models unload faster
await agent.warmup(warmup_config={"keep_alive": 300})  # 5 minutes
```

## API Reference

### CascadeAgent.warmup()

```python
async def warmup(
    self,
    warmup_prompt: str = "Hello",
    warmup_config: Optional[dict[str, Any]] = None,
    parallel: bool = True,
) -> dict[str, Any]
```

**Parameters**:
- `warmup_prompt`: Test prompt to use (default: "Hello")
- `warmup_config`: Provider-specific configuration
- `parallel`: Warm up models in parallel (default: True)

**Returns**:
```python
{
    "total_models": 3,
    "models_warmed": 2,
    "total_time_ms": 1234.5,
    "success": True,
    "results": [...]
}
```

### BaseProvider.warmup()

```python
async def warmup(
    self,
    models: Optional[list[str]] = None,
    warmup_prompt: str = "Hello",
    warmup_config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]
```

**Parameters**:
- `models`: List of model names to warm up
- `warmup_prompt`: Test prompt
- `warmup_config`: Provider-specific config

**Returns**:
```python
{
    "models_warmed": ["llama3.2:1b"],
    "warmup_time_ms": 1234.5,
    "success": True,
    "errors": {},
    "provider": "ollama"
}
```

## Examples

See complete examples:
- [`examples/warmup_demo.py`](../examples/warmup_demo.py) - Comprehensive demonstration
- [`benchmarks/warmup_benchmark.py`](../benchmarks/warmup_benchmark.py) - Performance benchmarks
- [`tests/test_warmup.py`](../tests/test_warmup.py) - Unit tests

## Summary

**Key Takeaways**:
1. **Call warmup() during startup** for best performance
2. **50-70% faster first requests** for local providers
3. **Cloud providers skip warmup automatically** (no overhead)
4. **Safe to call multiple times** (idempotent)
5. **Failures are non-fatal** (agent still works, just with cold starts)

**Recommended Pattern**:
```python
agent = CascadeAgent(models=[...])
await agent.warmup()  # One line eliminates cold starts!
```
