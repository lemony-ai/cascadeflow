"""
Multi-Instance vLLM Example

Demonstrates running draft and verifier models on separate vLLM instances.
vLLM provides high-performance inference with PagedAttention and continuous batching.

Use Cases:
- GPU 0: Fast 7B model for draft (200+ tokens/sec)
- GPU 1: Powerful 70B model for verifier (50+ tokens/sec)
- Kubernetes pods with different model sizes
- Load-balanced inference clusters
- Production-scale deployments

Setup Options:

Option 1: Docker Compose (see examples/docker/multi-instance-vllm/)
Option 2: Kubernetes StatefulSets
Option 3: Multiple local vLLM servers

Requirements:
    - Two vLLM instances running
    - Models downloaded locally or from HuggingFace
    - Sufficient GPU memory for each model

Setup:
    # Start draft vLLM instance
    python -m vllm.entrypoints.openai.api_server \\
      --model Qwen/Qwen2.5-7B-Instruct \\
      --port 8000 \\
      --gpu-memory-utilization 0.9

    # Start verifier vLLM instance
    python -m vllm.entrypoints.openai.api_server \\
      --model Qwen/Qwen2.5-72B-Instruct \\
      --port 8001 \\
      --gpu-memory-utilization 0.9

    # Run example
    export VLLM_DRAFT_URL=http://localhost:8000/v1
    export VLLM_VERIFIER_URL=http://localhost:8001/v1
    export VLLM_DRAFT_MODEL=Qwen/Qwen2.5-7B-Instruct
    export VLLM_VERIFIER_MODEL=Qwen/Qwen2.5-72B-Instruct
    python examples/multi_instance_vllm.py
"""

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from cascadeflow import CascadeAgent, ModelConfig


@dataclass
class InstanceConfig:
    """Configuration for a vLLM instance"""
    url: str
    model: str
    description: str
    api_key: Optional[str] = None


@dataclass
class MultiInstanceConfig:
    """Configuration for multi-instance vLLM setup"""
    draft_instance: InstanceConfig
    verifier_instance: InstanceConfig


# Example configurations for different scenarios
CONFIGURATIONS = {
    # Scenario 1: Docker Compose with GPU separation
    "docker": MultiInstanceConfig(
        draft_instance=InstanceConfig(
            url="http://localhost:8000/v1",
            model="Qwen/Qwen2.5-7B-Instruct",
            description="Fast 7B model on GPU 0 (200 tok/s)",
        ),
        verifier_instance=InstanceConfig(
            url="http://localhost:8001/v1",
            model="Qwen/Qwen2.5-72B-Instruct",
            description="Powerful 72B model on GPU 1 (50 tok/s)",
        ),
    ),
    # Scenario 2: Kubernetes pods
    "kubernetes": MultiInstanceConfig(
        draft_instance=InstanceConfig(
            url="http://vllm-draft.default.svc.cluster.local:8000/v1",
            model="mistralai/Mistral-7B-Instruct-v0.2",
            description="Fast 7B model in draft pod",
        ),
        verifier_instance=InstanceConfig(
            url="http://vllm-verifier.default.svc.cluster.local:8000/v1",
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            description="Powerful Mixtral in verifier pod",
        ),
    ),
    # Scenario 3: Environment variables (production)
    "fromEnv": MultiInstanceConfig(
        draft_instance=InstanceConfig(
            url=os.getenv("VLLM_DRAFT_URL", "http://localhost:8000/v1"),
            model=os.getenv("VLLM_DRAFT_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
            description="Draft model from environment",
            api_key=os.getenv("VLLM_DRAFT_API_KEY"),
        ),
        verifier_instance=InstanceConfig(
            url=os.getenv("VLLM_VERIFIER_URL", "http://localhost:8001/v1"),
            model=os.getenv("VLLM_VERIFIER_MODEL", "Qwen/Qwen2.5-72B-Instruct"),
            description="Verifier model from environment",
            api_key=os.getenv("VLLM_VERIFIER_API_KEY"),
        ),
    ),
}


def create_multi_instance_agent(config: MultiInstanceConfig) -> CascadeAgent:
    """Create agent with multi-instance configuration"""
    return CascadeAgent(
        models=[
            ModelConfig(
                name=config.draft_instance.model,
                provider="vllm",
                cost=0,  # Self-hosted is free (no API costs)
                base_url=config.draft_instance.url,
                api_key=config.draft_instance.api_key,
                quality_threshold=0.7,  # Accept if confidence >= 70%
            ),
            ModelConfig(
                name=config.verifier_instance.model,
                provider="vllm",
                cost=0,
                base_url=config.verifier_instance.url,
                api_key=config.verifier_instance.api_key,
                quality_threshold=0.95,  # Very high quality
            ),
        ]
    )


async def check_instance_health(
    url: str, api_key: Optional[str] = None
) -> tuple[bool, list[str]]:
    """Health check for vLLM instances"""
    try:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{url}/models", headers=headers)

            if response.status_code != 200:
                print(f"Instance at {url} returned {response.status_code}")
                return False, []

            data = response.json()
            models = [m.get("id", "") for m in data.get("data", [])]

            return True, models
    except Exception as e:
        print(f"Failed to connect to {url}: {e}")
        return False, []


async def main():
    """Main example demonstrating multi-instance usage"""
    print("=" * 80)
    print("Multi-Instance vLLM Cascade Example")
    print("=" * 80)
    print()

    # Choose configuration (change to 'docker', 'kubernetes', or 'fromEnv')
    config_name = "fromEnv"
    config = CONFIGURATIONS[config_name]

    print(f"Configuration: {config_name}")
    print(f"Draft:    {config.draft_instance.description}")
    print(f"          {config.draft_instance.url}")
    print(f"          Model: {config.draft_instance.model}")
    print(f"Verifier: {config.verifier_instance.description}")
    print(f"          {config.verifier_instance.url}")
    print(f"          Model: {config.verifier_instance.model}")
    print()

    # Health checks
    print("Health Checks:")
    draft_healthy, draft_models = await check_instance_health(
        config.draft_instance.url, config.draft_instance.api_key
    )
    verifier_healthy, verifier_models = await check_instance_health(
        config.verifier_instance.url, config.verifier_instance.api_key
    )

    if not draft_healthy or not verifier_healthy:
        print()
        print("Setup Instructions:")
        print("1. Start draft vLLM instance:")
        print("   python -m vllm.entrypoints.openai.api_server \\")
        print(f"     --model {config.draft_instance.model} \\")
        print("     --port 8000")
        print()
        print("2. Start verifier vLLM instance:")
        print("   python -m vllm.entrypoints.openai.api_server \\")
        print(f"     --model {config.verifier_instance.model} \\")
        print("     --port 8001")
        print()
        print("Or use Docker Compose (see examples/docker/multi-instance-vllm/)")
        return

    print(f"  ✅ Draft instance: {config.draft_instance.url}")
    print(f"     Available models: {', '.join(draft_models)}")
    print(f"  ✅ Verifier instance: {config.verifier_instance.url}")
    print(f"     Available models: {', '.join(verifier_models)}")
    print()

    # Create agent
    agent = create_multi_instance_agent(config)
    print(f"✅ Agent created with {len(agent.models)}-tier cascade")
    print()

    # Test queries with varying complexity
    queries = [
        {
            "prompt": "Write a Hello World program in Python",
            "expected": "Draft should handle (simple code)",
        },
        {
            "prompt": "Implement a binary search tree with insert, delete, and search operations in TypeScript",
            "expected": "Draft might handle or escalate",
        },
        {
            "prompt": "Design a distributed consensus algorithm handling network partitions and Byzantine failures",
            "expected": "Likely escalates to verifier (complex system design)",
        },
    ]

    results = []

    for i, query in enumerate(queries):
        prompt = query["prompt"]
        expected = query["expected"]

        print("=" * 80)
        print(f"Query {i + 1}: {prompt}")
        print(f"Expected: {expected}")
        print("=" * 80)

        start = time.time()
        result = await agent.run(prompt)
        elapsed = (time.time() - start) * 1000

        results.append(result)

        print()
        print("Result:")
        print(f"  Model used: {result.model_used}")
        instance_url = (
            config.draft_instance.url
            if result.model_used == config.draft_instance.model
            else config.verifier_instance.url
        )
        instance_name = "Draft" if instance_url == config.draft_instance.url else "Verifier"
        print(f"  Instance: {instance_name}")
        print(f"  URL: {instance_url}")
        print(f"  Cascaded: {result.cascaded}")
        print(f"  Draft accepted: {result.draft_accepted}")
        print(f"  Latency: {elapsed:.0f}ms")
        print(f"  Total cost: ${result.total_cost:.6f}")

        print()
        print(f"Response preview: {result.content[:300]}...")
        print()

    # Summary
    print("=" * 80)
    print("SESSION SUMMARY")
    print("=" * 80)
    print()

    draft_count = sum(
        1 for r in results if r.model_used == config.draft_instance.model
    )
    verifier_count = len(results) - draft_count
    avg_latency = sum(r.latency_ms or 0 for r in results) / len(results)
    total_cost = sum(r.total_cost for r in results)

    print(f"Total queries: {len(results)}")
    print(
        f"Draft instance: {draft_count} queries ({draft_count / len(results) * 100:.0f}%)"
    )
    print(
        f"Verifier instance: {verifier_count} queries ({verifier_count / len(results) * 100:.0f}%)"
    )
    print(f"Average latency: {avg_latency:.0f}ms")
    print(f"Total cost: ${total_cost:.6f}")
    print()

    print("Multi-Instance Benefits:")
    print("  ✅ Parallel inference (no GPU contention)")
    print("  ✅ Optimized model serving per instance")
    print("  ✅ Independent scaling and monitoring")
    print("  ✅ Better resource utilization")
    print("  ✅ Fault isolation and reliability")
    print()

    print("vLLM Performance Features:")
    print("  • PagedAttention for memory efficiency")
    print("  • Continuous batching for high throughput")
    print("  • 10-24x faster than standard serving")
    print("  • Full OpenAI API compatibility")
    print()

    print("Production Considerations:")
    print("  • Set up health checks and monitoring")
    print("  • Configure auto-scaling based on load")
    print("  • Implement circuit breakers for failover")
    print("  • Use load balancers for high availability")
    print("  • Monitor GPU memory and utilization")
    print()


if __name__ == "__main__":
    asyncio.run(main())
