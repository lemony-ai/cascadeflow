"""
Nvidia Jetson Thor/Spark Edge Device with vLLM - cascadeflow Example

This example demonstrates running cascadeflow on edge AI devices like:
- Nvidia Jetson Thor
- Nvidia Jetson Orin (AGX, NX, Nano)
- Nvidia Jetson Xavier
- Spark AI accelerator cards

What it demonstrates:
- Local inference with vLLM on edge device (privacy-first)
- Automatic cascade to cloud (Claude) for complex queries
- Zero-cost local processing with cloud fallback
- Real-time latency optimization for edge computing
- Tool calling support on both tiers

Hardware Requirements:
- Nvidia Jetson Thor / Orin / Xavier device with GPU
- 8GB+ RAM (16GB recommended for larger models)
- Ubuntu 20.04+ (JetPack 5.0+)
- CUDA 11.8+ support

Software Requirements:
- vLLM server running locally (http://localhost:8000)
- Anthropic API key for cloud fallback
- Python 3.9+

Setup Instructions:

    1. Install vLLM on Jetson device:
       ```bash
       # Install CUDA-enabled PyTorch
       pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

       # Install vLLM (may need to build from source on Jetson)
       pip3 install vllm
       ```

    2. Start vLLM server with a small model optimized for edge:
       ```bash
       # Option 1: Llama 3.2 1B (ultra-fast, 1GB VRAM)
       python -m vllm.entrypoints.openai.api_server \
           --model meta-llama/Llama-3.2-1B-Instruct \
           --dtype half \
           --max-model-len 2048 \
           --gpu-memory-utilization 0.7

       # Option 2: Qwen2.5 3B (balanced, 3GB VRAM)
       python -m vllm.entrypoints.openai.api_server \
           --model Qwen/Qwen2.5-3B-Instruct \
           --dtype half \
           --max-model-len 4096 \
           --gpu-memory-utilization 0.8

       # Option 3: Llama 3.2 3B (quality, 3GB VRAM)
       python -m vllm.entrypoints.openai.api_server \
           --model meta-llama/Llama-3.2-3B-Instruct \
           --dtype half \
           --max-model-len 4096 \
           --gpu-memory-utilization 0.8
       ```

    3. Set environment variables:
       ```bash
       export VLLM_BASE_URL="http://localhost:8000/v1"
       export ANTHROPIC_API_KEY="sk-ant-..."
       ```

    4. Run the example:
       ```bash
       python nvidia_thor_edge_device.py
       ```

Expected Results:
- Simple queries: Processed locally on Jetson (<100ms latency)
- Complex queries: Automatically cascade to Claude (~500-1000ms)
- 70-80% of queries stay on device (zero cost, maximum privacy)
- 20-30% cascade to cloud only when needed
- Full tool calling support on both local and cloud tiers

Use Cases:
- Smart factories: Local vision + reasoning, cloud for complex analysis
- Healthcare devices: HIPAA-compliant local processing, cloud consultation
- Retail kiosks: Fast local responses, cloud for inventory management
- Autonomous robots: Real-time local control, cloud for path planning
- Edge AI servers: Process locally, escalate complex queries to cloud
- IoT gateways: Aggregate sensor data locally, cloud for analytics

Cost Analysis (10k queries/month):

    Without cascadeflow (all cloud - Claude Sonnet):
        10,000 × $0.003 = $30.00/month

    With cascadeflow (edge-first strategy):
        Local  (7,000): $0.00 (free - your hardware)
        Cloud  (3,000): 3,000 × $0.003 = $9.00/month

        Total: $9.00/month

    Savings: $21.00/month (70%) + Enhanced privacy + Lower latency

Documentation:
    See docs/guides/edge-devices.md for detailed deployment guide
"""

import asyncio
import os
import sys
import time
from typing import Any

from cascadeflow import CascadeAgent, ModelConfig, QualityConfig

try:
    import httpx
except ImportError:
    print("⚠️  httpx not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

# ============================================================
# EDGE DEVICE CONFIGURATION
# ============================================================


# Define edge cascade: Local vLLM → Cloud Claude
def create_edge_agent() -> CascadeAgent:
    """
    Create CascadeAgent optimized for Nvidia Jetson Thor/Spark edge devices.

    Tier 1: Local vLLM (Llama 3.2 3B) - Fast, private, zero-cost
    Tier 2: Cloud Claude (Claude Sonnet 4.5) - Complex reasoning fallback
    """

    models = [
        # Tier 1: Local inference on Jetson device
        # - Llama 3.2 3B runs great on Jetson Orin/Thor
        # - ~100ms latency for simple queries
        # - Zero API cost (your hardware)
        # - Maximum privacy (data never leaves device)
        ModelConfig(
            name="meta-llama/Llama-3.2-3B-Instruct",
            provider="vllm",
            cost=0.0,  # Free - runs on your edge device
            metadata={
                "device": "jetson-thor",
                "location": "edge",
                "vram_required": "3GB",
                "avg_latency_ms": 100,
            },
        ),
        # Tier 2: Cloud fallback for complex queries
        # - Claude Sonnet 4.5 for advanced reasoning
        # - Only used when local model insufficient (~20-30% of queries)
        # - Higher latency but superior quality
        # - Cost-effective cloud tier
        ModelConfig(
            name="claude-sonnet-4-5-20250929",
            provider="anthropic",
            cost=0.003,  # $3 per 1M tokens
            metadata={"device": "cloud", "location": "anthropic-datacenter", "avg_latency_ms": 800},
        ),
    ]

    # Configure quality thresholds optimized for edge devices
    quality_config = QualityConfig(
        confidence_thresholds={
            "trivial": 0.65,   # Lower thresholds for fast local responses
            "simple": 0.60,
            "moderate": 0.55,
            "hard": 0.50,
            "expert": 0.45,
        },
        enable_adaptive=True,  # Adapt based on query complexity
    )

    agent = CascadeAgent(
        models=models, quality_config=quality_config, enable_cascade=True, verbose=True
    )

    return agent


# ============================================================
# TEST QUERIES FOR EDGE DEVICES
# ============================================================


def get_test_queries() -> list[dict[str, Any]]:
    """
    Test queries spanning edge device use cases.

    Categories:
    - Simple factual: Should stay on device (Tier 1)
    - Moderate reasoning: Might stay on device or cascade
    - Complex analysis: Will cascade to cloud (Tier 2)
    - Tool-based: Demonstrates tool calling support
    """

    return [
        # CATEGORY 1: Simple factual (local device)
        {
            "query": "What is the speed of light?",
            "expected_tier": 1,
            "category": "factual",
            "use_case": "Quick reference lookup",
        },
        {
            "query": "Convert 100 degrees Fahrenheit to Celsius.",
            "expected_tier": 1,
            "category": "calculation",
            "use_case": "Simple math computation",
        },
        # CATEGORY 2: Moderate reasoning (might cascade)
        {
            "query": "A factory sensor reads 75°C. Is this within normal operating range for a hydraulic pump?",
            "expected_tier": 1,  # May cascade if model uncertain
            "category": "domain-reasoning",
            "use_case": "Industrial monitoring",
        },
        {
            "query": "List three common causes of conveyor belt misalignment in manufacturing.",
            "expected_tier": 1,
            "category": "knowledge-retrieval",
            "use_case": "Maintenance assistance",
        },
        # CATEGORY 3: Complex analysis (cloud cascade)
        {
            "query": "Analyze the following sensor readings and predict potential failures: "
            "Motor temp: 85°C (normal: 60-75°C), Vibration: 12mm/s (normal: <10mm/s), "
            "Current draw: 45A (normal: 35-40A). Provide root cause analysis and maintenance recommendations.",
            "expected_tier": 2,
            "category": "complex-analysis",
            "use_case": "Predictive maintenance",
        },
        {
            "query": "Given these production metrics from the last 30 days (units: 10k, 12k, 8k, 15k, 9k per week), "
            "predict next week's output considering seasonal trends and recommend staffing adjustments.",
            "expected_tier": 2,
            "category": "forecasting",
            "use_case": "Production planning",
        },
        # CATEGORY 4: Real-time edge scenarios
        {
            "query": "Object detected in restricted zone. Current: 2:45 PM, Location: Assembly Line 3, "
            "Object type: Unknown. Recommend immediate action.",
            "expected_tier": 1,  # Fast response needed
            "category": "safety-alert",
            "use_case": "Security monitoring",
        },
        {
            "query": "Quality control: Part #A1234 measured dimensions are 10.02mm x 5.01mm (spec: 10.00mm ± 0.05mm x 5.00mm ± 0.05mm). "
            "Is this part within tolerance? Should it be approved or rejected?",
            "expected_tier": 1,
            "category": "quality-control",
            "use_case": "Automated inspection",
        },
    ]


# ============================================================
# MAIN DEMONSTRATION
# ============================================================


async def main():
    """
    Demonstrate cascadeflow on Nvidia Jetson Thor/Spark edge device.
    """

    print("=" * 80)
    print("NVIDIA JETSON THOR/SPARK EDGE DEVICE - CASCADEFLOW DEMONSTRATION")
    print("=" * 80)
    print()
    print("Edge Device Configuration:")
    print("  Hardware: Nvidia Jetson Thor/Orin")
    print("  Local Model: Llama 3.2 3B (vLLM)")
    print("  Cloud Fallback: Claude Sonnet 4.5 (Anthropic)")
    print("  Strategy: Process locally first, cascade to cloud if needed")
    print()

    # Check if vLLM server is running
    vllm_url = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    print(f"🔌 Checking vLLM server at {vllm_url}...")

    try:
        # Try to connect to vLLM server
        response = httpx.get(f"{vllm_url.replace('/v1', '')}/health", timeout=5)
        if response.status_code == 200:
            print("✅ vLLM server is running")
        else:
            print(f"⚠️  vLLM server returned status {response.status_code}")
            print("\n❌ This example requires a local vLLM server.")
            print("\n💡 To run this example:")
            print("   1. Install vLLM: pip install vllm")
            print("   2. Start server:")
            print("      python -m vllm.entrypoints.openai.api_server \\")
            print("          --model meta-llama/Llama-3.2-3B-Instruct \\")
            print("          --dtype half \\")
            print("          --max-model-len 4096")
            print("\n✅ Exiting gracefully (this is not an error)")
            sys.exit(0)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        print(f"❌ Cannot connect to vLLM server: {e}")
        print("\n💡 This example requires a local vLLM server for edge device simulation.")
        print("\n📖 Setup instructions:")
        print("   1. Install vLLM: pip install vllm")
        print("   2. Start server:")
        print("      python -m vllm.entrypoints.openai.api_server \\")
        print("          --model meta-llama/Llama-3.2-3B-Instruct \\")
        print("          --dtype half \\")
        print("          --max-model-len 4096")
        print("\n✅ Exiting gracefully (this is not an error)")
        sys.exit(0)

    # Check if Anthropic API key is set
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  Warning: ANTHROPIC_API_KEY not set. Cloud fallback will not work.")
        print("   Set it with: export ANTHROPIC_API_KEY='sk-ant-...'")
    print()

    # Create edge-optimized agent
    print("🚀 Initializing edge agent...")
    agent = create_edge_agent()
    print("✅ Agent initialized")
    print()

    # Get test queries
    queries = get_test_queries()

    print("=" * 80)
    print(f"RUNNING {len(queries)} TEST QUERIES")
    print("=" * 80)
    print()

    # Track statistics
    total_cost = 0.0
    local_count = 0
    cloud_count = 0
    total_latency = 0.0

    # Run queries
    for i, query_data in enumerate(queries, 1):
        query = query_data["query"]
        category = query_data["category"]
        use_case = query_data["use_case"]

        print(f"Query {i}/{len(queries)}: {category.upper()}")
        print(f"Use Case: {use_case}")
        print(f"Prompt: {query[:100]}..." if len(query) > 100 else f"Prompt: {query}")
        print()

        # Run query with timing
        start_time = time.time()

        try:
            result = await agent.run(query)

            latency = (time.time() - start_time) * 1000  # Convert to ms
            total_latency += latency

            # Determine which tier was used
            if result.model_used.startswith("meta-llama"):
                tier = 1
                tier_name = "LOCAL (Jetson)"
                tier_color = "💚"
                local_count += 1
            else:
                tier = 2
                tier_name = "CLOUD (Claude)"
                tier_color = "💛"
                cloud_count += 1

            # Display results
            print(f"  {tier_color} Tier {tier}: {tier_name}")
            print(f"  ⚡ Latency: {latency:.0f}ms")
            print(f"  💰 Cost: ${result.total_cost:.6f}")
            print(f"  🎯 Confidence: {result.confidence:.2f}")

            if result.cascaded:
                print("  🔄 Cascaded: Yes (local model insufficient)")

            # Show abbreviated response
            response_preview = (
                result.content[:150] + "..." if len(result.content) > 150 else result.content
            )
            print(f"  📤 Response: {response_preview}")
            print()

            # Update cost tracking
            total_cost += result.total_cost

        except Exception as e:
            print(f"  ❌ Error: {e}")
            print()

    # Print summary statistics
    print("=" * 80)
    print("EDGE DEVICE PERFORMANCE SUMMARY")
    print("=" * 80)
    print()

    print(f"Total Queries:           {len(queries)}")
    print(f"Local Processing:        {local_count} ({local_count/len(queries)*100:.1f}%)")
    print(f"Cloud Cascade:           {cloud_count} ({cloud_count/len(queries)*100:.1f}%)")
    print()

    print(f"Total Cost:              ${total_cost:.6f}")
    print(f"Average Latency:         {total_latency/len(queries):.0f}ms")
    print("Local Avg Latency:       ~100ms (estimated)")
    print("Cloud Avg Latency:       ~800ms (estimated)")
    print()

    # Cost comparison
    all_cloud_cost = len(queries) * 0.003  # Rough estimate
    savings = all_cloud_cost - total_cost
    savings_pct = (savings / all_cloud_cost * 100) if all_cloud_cost > 0 else 0

    print("Cost Analysis:")
    print(f"  All-Cloud Cost:        ${all_cloud_cost:.6f}")
    print(f"  Edge-First Cost:       ${total_cost:.6f}")
    print(f"  Savings:               ${savings:.6f} ({savings_pct:.1f}%)")
    print()

    # Key benefits
    print("=" * 80)
    print("KEY BENEFITS FOR EDGE DEVICES")
    print("=" * 80)
    print()
    print("✅ Privacy: Sensitive data stays on device")
    print("✅ Latency: <100ms response time for local queries")
    print("✅ Cost: 70%+ cost reduction vs all-cloud")
    print("✅ Reliability: Works offline for local queries")
    print("✅ Scalability: No API rate limits for local tier")
    print("✅ Quality: Cloud fallback ensures complex queries handled well")
    print()

    print("=" * 80)
    print("DEPLOYMENT RECOMMENDATIONS")
    print("=" * 80)
    print()
    print("For Production:")
    print("  1. Use quantized models (GPTQ/AWQ) for lower VRAM")
    print("  2. Enable KV cache optimization in vLLM")
    print("  3. Monitor GPU temperature and throttling")
    print("  4. Implement circuit breaker for cloud cascade failures")
    print("  5. Set up local fallback if cloud unavailable")
    print("  6. Use Jetson power modes (MAXN for performance, 15W for efficiency)")
    print()

    print("Model Selection by Device:")
    print("  Jetson Nano (4GB):     Llama 3.2 1B")
    print("  Jetson Orin Nano (8GB): Llama 3.2 3B or Qwen 2.5 3B")
    print("  Jetson Orin NX (16GB):  Llama 3.1 8B or Mistral 7B")
    print("  Jetson AGX Orin (32GB): Llama 3.1 70B (quantized) or Mixtral 8x7B")
    print()


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(main())
