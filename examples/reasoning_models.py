"""
Example: Using Reasoning Models Across All Providers

cascadeflow supports reasoning models from 4 providers with automatic detection:

1. OpenAI (o1, o1-mini, o3-mini)
   - Chain-of-thought reasoning with hidden thinking
   - reasoning_effort parameter (low/medium/high)
   - max_completion_tokens required

2. Anthropic (claude-3-7-sonnet-20250219)
   - Extended thinking mode (enable with thinking_budget)
   - Minimum 1024 tokens thinking budget
   - Visible reasoning in response

3. Ollama (deepseek-r1, deepseek-r1-distill)
   - Free local inference
   - DeepSeek-R1 reasoning models
   - Full privacy, no API costs

4. vLLM (deepseek-r1, deepseek-r1-distill)
   - Self-hosted high-performance inference
   - 24x faster than standard serving
   - Production-ready deployment

Zero configuration required - cascadeflow auto-detects capabilities!
"""

import asyncio
from cascadeflow import CascadeAgent, ModelConfig


async def main():
    # Example 1: o1-mini (supports streaming, no tools, no system messages)
    print("\n=== Example 1: o1-mini (original reasoning model) ===")
    agent1 = CascadeAgent(
        models=[
            ModelConfig(
                name="o1-mini",  # Auto-detected as reasoning model
                provider="openai",
            )
        ],
    )

    result1 = await agent1.run(
        query="Solve this problem step by step: If a train travels at 80 km/h for 2.5 hours, then slows to 60 km/h for the next hour, what is the total distance traveled?",
        max_tokens=2000,
    )

    print(f"Response: {result1.content}")
    print(f"\nUsage:")
    print(f"  Prompt tokens: {result1.metadata.get('prompt_tokens')}")
    print(f"  Completion tokens: {result1.metadata.get('completion_tokens')}")
    print(f"  Reasoning tokens: {result1.metadata.get('reasoning_tokens')}")  # Hidden reasoning
    print(f"Cost: ${result1.cost:.6f}")

    # Example 2: o1-2024-12-17 (newer model with reasoning_effort)
    print("\n=== Example 2: o1-2024-12-17 with reasoning_effort ===")
    agent2 = CascadeAgent(
        models=[
            ModelConfig(
                name="o1-2024-12-17",
                provider="openai",
            )
        ],
        default_provider="openai",
    )

    # High reasoning effort for complex problem
    result2 = await agent2.run(
        query="Design an efficient algorithm to find all palindromic substrings in a string of length n. Analyze the time and space complexity.",
        max_tokens=4000,
        reasoning_effort="high",  # More thorough reasoning
    )

    print(f"Response: {result2.content[:500]}...")
    print(f"\nReasoning tokens used: {result2.metadata.get('reasoning_tokens')}")
    print(f"Cost: ${result2.cost:.6f}")

    # Example 3: Using in cascade (auto-routing to reasoning model)
    print("\n=== Example 3: Cascade with reasoning model fallback ===")
    agent3 = CascadeAgent(
        models=[
            ModelConfig(
                name="gpt-4o-mini",  # Fast, cheap model tries first
                provider="openai",
            ),
            ModelConfig(
                name="o1-mini",  # Falls back to reasoning model if needed
                provider="openai",
            ),
        ],
        default_provider="openai",
        min_quality=0.8,  # High quality threshold
    )

    result3 = await agent3.run(
        query="Prove that the square root of 2 is irrational.",
        max_tokens=2000,
    )

    print(f"Model used: {result3.model}")
    print(f"Response: {result3.content[:300]}...")
    print(f"Quality score: {result3.quality_score}")

    # Example 4: Comparing reasoning efforts
    print("\n=== Example 4: Comparing reasoning efforts ===")
    query = "What are the implications of quantum entanglement for computing?"

    for effort in ["low", "medium", "high"]:
        result = await agent2.run(
            query=query,
            max_tokens=1000,
            reasoning_effort=effort,
        )

        print(f"\n{effort.upper()} effort:")
        print(f"  Reasoning tokens: {result.metadata.get('reasoning_tokens')}")
        print(f"  Total cost: ${result.cost:.6f}")
        print(f"  Response length: {len(result.content)} chars")

    # Example 5: Anthropic Claude 3.7 Sonnet with Extended Thinking
    print("\n=== Example 5: Claude 3.7 Sonnet (Extended Thinking) ===")
    agent4 = CascadeAgent(
        models=[
            ModelConfig(
                name="claude-3-7-sonnet-20250219",
                provider="anthropic",
            )
        ],
        default_provider="anthropic",
    )

    result4 = await agent4.run(
        query="Design a fault-tolerant distributed consensus algorithm. Explain your reasoning process.",
        max_tokens=5000,
        thinking_budget=2048,  # Enable extended thinking (min 1024)
    )

    print(f"Response: {result4.content[:500]}...")
    print(f"\nUsage:")
    print(f"  Prompt tokens: {result4.metadata.get('prompt_tokens')}")
    print(f"  Completion tokens: {result4.metadata.get('completion_tokens')}")
    print(f"Cost: ${result4.cost:.6f}")
    print("\nNote: Claude extended thinking produces visible reasoning in the response!")

    # Example 6: DeepSeek-R1 via Ollama (Free Local Inference)
    print("\n=== Example 6: DeepSeek-R1 via Ollama (Local) ===")
    print("Prerequisites: Install Ollama (https://ollama.ai) and run:")
    print("  ollama pull deepseek-r1:8b")
    print()

    try:
        agent5 = CascadeAgent(
            models=[
                ModelConfig(
                    name="deepseek-r1:8b",  # Auto-detected as reasoning model
                    provider="ollama",
                )
            ],
            default_provider="ollama",
        )

        result5 = await agent5.run(
            query="Explain the time complexity of quicksort in best, average, and worst cases.",
            max_tokens=2000,
        )

        print(f"Response: {result5.content[:400]}...")
        print(f"Cost: ${result5.cost:.6f} (FREE - local inference)")
    except Exception as e:
        print(f"Skipping - Ollama not available: {e}")
        print("Install from: https://ollama.ai")

    # Example 7: DeepSeek-R1 via vLLM (High-Performance Self-Hosted)
    print("\n=== Example 7: DeepSeek-R1 via vLLM (Self-Hosted) ===")
    print("Prerequisites: Start vLLM server:")
    print("  python -m vllm.entrypoints.openai.api_server \\")
    print("    --model deepseek-ai/DeepSeek-R1-Distill-Llama-8B \\")
    print("    --port 8000")
    print()

    try:
        agent6 = CascadeAgent(
            models=[
                ModelConfig(
                    name="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
                    provider="vllm",
                    base_url="http://localhost:8000/v1",
                )
            ],
            default_provider="vllm",
        )

        result6 = await agent6.run(
            query="What is the difference between TCP and UDP? When would you use each?",
            max_tokens=1500,
        )

        print(f"Response: {result6.content[:400]}...")
        print(f"Cost: ${result6.cost:.6f} (FREE - self-hosted)")
        print("Note: vLLM provides 24x faster inference than standard serving!")
    except Exception as e:
        print(f"Skipping - vLLM server not available: {e}")
        print("See: https://docs.vllm.ai")

    # Example 8: Multi-Provider Reasoning Cascade
    print("\n=== Example 8: Multi-Provider Reasoning Cascade ===")
    agent7 = CascadeAgent(
        models=[
            ModelConfig(
                name="deepseek-r1:8b",
                provider="ollama",
                cost=0,  # Free local inference
            ),
            ModelConfig(
                name="o1-mini",
                provider="openai",
            ),
            ModelConfig(
                name="claude-3-7-sonnet-20250219",
                provider="anthropic",
            ),
        ],
        min_quality=0.85,
    )

    print("This cascade tries:")
    print("  1. DeepSeek-R1 (local, free)")
    print("  2. Falls back to o1-mini if quality < 0.85")
    print("  3. Falls back to Claude 3.7 as final option")
    print()
    print("Perfect for cost optimization with reasoning models!")


if __name__ == "__main__":
    asyncio.run(main())
