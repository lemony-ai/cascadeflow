# vLLM Setup Guide

vLLM is a high-performance inference server that provides:
- 24x faster throughput than standard serving
- Efficient GPU memory management (PagedAttention)
- Continuous batching
- OpenAI-compatible API

## Installation
```bash
# Install vLLM
pip install vllm

# Or with CUDA support
pip install vllm[cuda]




# Using with CascadeFlow
from cascadeflow import CascadeAgent, ModelConfig

models = [
    ModelConfig(
        name="meta-llama/Llama-3-8B-Instruct",
        provider="vllm",
        base_url="http://localhost:8000/v1",
        cost=0.0
    ),
    ModelConfig(name="gpt-4", provider="openai", cost=0.03),
]

agent = CascadeAgent(models)
result = await agent.run("Your query")