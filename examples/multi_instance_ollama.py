"""
Multi-Instance Ollama Example

Demonstrates running draft and verifier models on separate Ollama instances.
Perfect for multi-GPU systems or distributed inference.

Use Cases:
- GPU 0: Fast 1B/3B model for draft (high throughput)
- GPU 1: Powerful 70B model for verifier (high quality)
- Separate machines for load distribution
- Different hardware for different models

Setup Options:

Option 1: Docker Compose (see examples/docker/multi-instance-ollama/)
Option 2: Multiple local instances (different ports)
Option 3: Network-distributed instances

Requirements:
    - Two Ollama instances running
    - Models pulled on each instance
    - Network connectivity

Setup:
    # Start Docker Compose instances
    cd examples/docker/multi-instance-ollama
    docker-compose up -d

    # Pull models
    docker exec ollama-draft ollama pull llama3.2:1b
    docker exec ollama-verifier ollama pull llama3.1:70b

    # Run example
    export OLLAMA_DRAFT_URL=http://localhost:11434
    export OLLAMA_VERIFIER_URL=http://localhost:11435
    export OLLAMA_DRAFT_MODEL=llama3.2:1b
    export OLLAMA_VERIFIER_MODEL=llama3.1:70b
    python examples/multi_instance_ollama.py
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
    """Configuration for an Ollama instance"""

    url: str
    model: str
    description: str


@dataclass
class MultiInstanceConfig:
    """Configuration for multi-instance Ollama setup"""

    draft_instance: InstanceConfig
    verifier_instance: InstanceConfig


# Example configurations for different scenarios
CONFIGURATIONS = {
    # Scenario 1: Docker Compose with GPU separation
    "docker": MultiInstanceConfig(
        draft_instance=InstanceConfig(
            url="http://localhost:11434",
            model="llama3.2:1b",
            description="Fast 1B model on GPU 0",
        ),
        verifier_instance=InstanceConfig(
            url="http://localhost:11435",
            model="llama3.1:70b",
            description="Powerful 70B model on GPU 1",
        ),
    ),
    # Scenario 2: Network-distributed instances
    "distributed": MultiInstanceConfig(
        draft_instance=InstanceConfig(
            url="http://ollama-gpu-1:11434",
            model="qwen2.5:7b",
            description="Fast 7B model on machine 1",
        ),
        verifier_instance=InstanceConfig(
            url="http://ollama-gpu-2:11434",
            model="qwen2.5:72b",
            description="Powerful 72B model on machine 2",
        ),
    ),
    # Scenario 3: Environment variables (production)
    "fromEnv": MultiInstanceConfig(
        draft_instance=InstanceConfig(
            url=os.getenv("OLLAMA_DRAFT_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_DRAFT_MODEL", "llama3.2:1b"),
            description="Draft model from environment",
        ),
        verifier_instance=InstanceConfig(
            url=os.getenv("OLLAMA_VERIFIER_URL", "http://localhost:11435"),
            model=os.getenv("OLLAMA_VERIFIER_MODEL", "llama3.1:70b"),
            description="Verifier model from environment",
        ),
    ),
}


def create_multi_instance_agent(config: MultiInstanceConfig) -> CascadeAgent:
    """Create agent with multi-instance configuration"""
    return CascadeAgent(
        models=[
            ModelConfig(
                name=config.draft_instance.model,
                provider="ollama",
                cost=0,  # Local execution is free
                base_url=config.draft_instance.url,
                quality_threshold=0.7,  # Accept if confidence >= 70%
            ),
            ModelConfig(
                name=config.verifier_instance.model,
                provider="ollama",
                cost=0,
                base_url=config.verifier_instance.url,
                quality_threshold=0.95,  # Very high quality
            ),
        ]
    )


async def check_instance_health(url: str, model_name: str) -> bool:
    """Health check for Ollama instances"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check if instance is responding
            response = await client.get(f"{url}/api/tags")
            if response.status_code != 200:
                print(f"Instance at {url} returned {response.status_code}")
                return False

            data = response.json()
            models = data.get("models", [])
            model_exists = any(model_name.split(":")[0] in m.get("name", "") for m in models)

            if not model_exists:
                model_names = [m.get("name", "") for m in models]
                print(f"Model {model_name} not found on {url}")
                print(f"Available models: {', '.join(model_names)}")
                return False

            return True
    except Exception as e:
        print(f"Failed to connect to {url}: {e}")
        return False


async def main():
    """Main example demonstrating multi-instance usage"""
    print("=" * 80)
    print("Multi-Instance Ollama Cascade Example")
    print("=" * 80)
    print()

    # Choose configuration (change to 'docker', 'distributed', or 'fromEnv')
    config_name = "fromEnv"
    config = CONFIGURATIONS[config_name]

    print(f"Configuration: {config_name}")
    print(f"Draft:    {config.draft_instance.description}")
    print(f"          {config.draft_instance.url} → {config.draft_instance.model}")
    print(f"Verifier: {config.verifier_instance.description}")
    print(f"          {config.verifier_instance.url} → {config.verifier_instance.model}")
    print()

    # Health checks
    print("Health Checks:")
    draft_healthy = await check_instance_health(
        config.draft_instance.url, config.draft_instance.model
    )
    verifier_healthy = await check_instance_health(
        config.verifier_instance.url, config.verifier_instance.model
    )

    if not draft_healthy or not verifier_healthy:
        print()
        print("Setup Instructions:")
        print("1. Start both Ollama instances (see Docker Compose example)")
        print("2. Pull models:")
        print(f"   docker exec ollama-draft ollama pull {config.draft_instance.model}")
        print(f"   docker exec ollama-verifier ollama pull {config.verifier_instance.model}")
        return

    print(f"  ✅ Draft instance: {config.draft_instance.url}")
    print(f"  ✅ Verifier instance: {config.verifier_instance.url}")
    print()

    # Create agent
    agent = create_multi_instance_agent(config)
    print(f"✅ Agent created with {len(agent.models)}-tier cascade")
    print()

    # Test queries with varying complexity
    queries = [
        {
            "prompt": "What is TypeScript?",
            "expected": "Draft should handle (simple explanation)",
        },
        {
            "prompt": "Explain the difference between async/await and Promises in JavaScript",
            "expected": "Draft might handle or escalate",
        },
        {
            "prompt": "Design a distributed rate limiter with Redis. Include edge cases and failure modes.",
            "expected": "Likely escalates to verifier (complex design)",
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
        draft_model_base = config.draft_instance.model.split(":")[0]
        instance_url = (
            config.draft_instance.url
            if draft_model_base in result.model_used
            else config.verifier_instance.url
        )
        print(f"  Instance: {instance_url}")
        print(f"  Cascaded: {result.cascaded}")
        print(f"  Draft accepted: {result.draft_accepted}")
        print(f"  Latency: {elapsed:.0f}ms")
        print(f"  Response length: {len(result.content)} chars")
        print()
        print(f"Response: {result.content[:200]}...")
        print()

    # Summary
    print("=" * 80)
    print("SESSION SUMMARY")
    print("=" * 80)
    print()

    draft_model_base = config.draft_instance.model.split(":")[0]
    draft_count = sum(1 for r in results if draft_model_base in r.model_used)
    verifier_count = len(results) - draft_count
    avg_latency = sum(r.latency_ms or 0 for r in results) / len(results)

    print(f"Total queries: {len(results)}")
    print(f"Draft instance ({config.draft_instance.model}): {draft_count} queries")
    print(f"Verifier instance ({config.verifier_instance.model}): {verifier_count} queries")
    print(f"Average latency: {avg_latency:.0f}ms")
    print()

    print("Benefits of Multi-Instance:")
    print("  ✅ No resource contention between models")
    print("  ✅ Independent GPU utilization")
    print("  ✅ Parallel inference possible")
    print("  ✅ Easy horizontal scaling")
    print("  ✅ Better fault isolation")
    print()

    print("Performance Notes:")
    print(f"  • Draft handled {(draft_count / len(results) * 100):.0f}% of queries")
    print("  • No API costs (100% local)")
    print("  • Full privacy (no data leaves your infrastructure)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
