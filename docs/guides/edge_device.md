# Edge Device Deployment Guide

Run CascadeFlow on edge AI devices (Nvidia Jetson, Raspberry Pi) with local inference and cloud fallback for privacy, cost savings, and low latency.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Hardware Requirements](#hardware-requirements)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Use Cases](#use-cases)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

## Overview

### What is Edge Deployment?

Edge deployment runs AI models **locally on your device** (Jetson, Raspberry Pi, industrial PC) instead of cloud servers. CascadeFlow makes this practical by:
- Processing simple queries locally (fast, private, free)
- Cascading complex queries to cloud when needed
- Maintaining quality while maximizing edge processing

### Why Edge + Cascade?

| **Benefit** | **Edge-First** | **All-Cloud** |
|-------------|----------------|---------------|
| **Privacy** | ✅ Data stays on device | ❌ Sent to cloud |
| **Latency** | ✅ <100ms locally | ❌ 500-2000ms |
| **Cost** | ✅ 70%+ savings | ❌ Full API costs |
| **Offline** | ✅ Works for local queries | ❌ Requires internet |
| **Quality** | ✅ Cloud fallback | ✅ Always high |

**Best of both worlds**: Local speed and privacy, cloud intelligence when needed.

---

## Architecture

### Edge-Cloud Cascade Flow

```
┌────────────────────────────────────────────────────────┐
│              Edge Device (Jetson/Pi)                   │
│                                                        │
│  ┌──────────┐       ┌──────────────┐                 │
│  │  Query   │──────▶│ Local Model  │                 │
│  └──────────┘       │  (vLLM/Ollama)                  │
│                     │  - Llama 3.2   │                 │
│                     │  - Qwen 2.5    │                 │
│                     └───────┬────────┘                 │
│                             │                          │
│                             ▼                          │
│                     ┌───────────────┐                  │
│                     │ Quality Check │                  │
│                     └───────┬───────┘                  │
│                             │                          │
│                 ┌───────────┴───────────┐             │
│                 │                       │             │
│                 ▼                       ▼             │
│          ┌──────────┐           ┌──────────┐         │
│          │   PASS   │           │   FAIL   │         │
│          │ (70-80%) │           │ (20-30%) │         │
│          └─────┬────┘           └─────┬────┘         │
│                │                      │               │
│                ▼                      │               │
│          Return Result               │               │
│                                       │               │
└───────────────────────────────────────┼───────────────┘
                                        │
                                        ▼ CASCADE
                              ┌──────────────────┐
                              │   Cloud Model    │
                              │  (Claude/GPT)    │
                              └──────────────────┘
```

### Data Flow

1. **Query arrives** at edge device
2. **Local model** generates response (<100ms)
3. **Quality validation** checks if sufficient
4. **If passes**: Return immediately (70-80% of queries)
5. **If fails**: Cascade to cloud (20-30% of queries)

---

## Hardware Requirements

### Supported Devices

| **Device** | **RAM** | **Models Supported** | **Performance** |
|------------|---------|----------------------|-----------------|
| **Jetson Nano** | 4GB | Llama 3.2 1B, TinyLlama | Basic (3-5 tok/s) |
| **Jetson Orin Nano** | 8GB | Llama 3.2 3B, Qwen 2.5 3B | Good (8-12 tok/s) |
| **Jetson Orin NX** | 16GB | Llama 3.1 8B, Mistral 7B | Excellent (15-25 tok/s) |
| **Jetson AGX Orin** | 32GB+ | Llama 3.1 70B (quantized) | Outstanding (20-35 tok/s) |
| **Jetson Thor** | 64GB+ | Multiple large models | Ultra (30-50+ tok/s) |
| **Raspberry Pi 5** | 8GB | TinyLlama, Phi-2 (CPU) | Limited (1-3 tok/s) |

### Software Requirements

- **OS**: Ubuntu 20.04+ (JetPack 5.0+ for Jetson)
- **Python**: 3.9+
- **CUDA**: 11.8+ (for GPU acceleration)
- **vLLM**: Latest version
- **CascadeFlow**: Latest version

---

## Quick Start

### Step 1: Install vLLM on Edge Device

```bash
# Install CUDA-enabled PyTorch (Jetson)
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install vLLM
pip3 install vllm

# Install CascadeFlow
pip3 install cascadeflow[all]
```

### Step 2: Start Local Model Server

```bash
# For Jetson Orin Nano (8GB) - Recommended
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-3.2-3B-Instruct \
    --dtype half \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.8

# For Jetson Orin NX (16GB)
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --dtype half \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.9
```

### Step 3: Configure Edge Agent

```python
from cascadeflow import CascadeAgent, ModelConfig, QualityConfig

# Edge-first cascade: Local → Cloud
agent = CascadeAgent(models=[
    # Tier 1: Local model (fast, private, free)
    ModelConfig(
        name="meta-llama/Llama-3.2-3B-Instruct",
        provider="vllm",
        cost=0.0,  # Free - runs on your device
    ),

    # Tier 2: Cloud fallback (quality guarantee)
    ModelConfig(
        name="claude-sonnet-4-5-20250929",
        provider="anthropic",
        cost=0.003,  # Only pay when cascading
    ),
])

# Run query
result = await agent.run("What is machine learning?")

# Check which tier was used
if result.model_used.startswith("meta-llama"):
    print("✅ Processed locally (free, private)")
else:
    print("☁️ Cascaded to cloud (quality needed)")
```

---

## Configuration

### Quality Thresholds

Edge devices benefit from **lower thresholds** to maximize local processing:

```python
from cascadeflow import QualityConfig

# Aggressive local processing (maximize edge)
quality_config = QualityConfig(
    min_confidence=0.60,  # Lower = more local processing
    require_validation=True,
    enable_adaptive=True,
)

# Balanced (recommended)
quality_config = QualityConfig(
    min_confidence=0.70,  # Default cascade threshold
    require_validation=True,
    enable_adaptive=True,
)

# Conservative (quality-first)
quality_config = QualityConfig(
    min_confidence=0.85,  # Higher = more cloud cascades
    require_validation=True,
    enable_adaptive=True,
)

agent = CascadeAgent(models=models, quality_config=quality_config)
```

### Model Selection by Device

```python
# Jetson Nano (4GB)
models = [
    ModelConfig("meta-llama/Llama-3.2-1B-Instruct", "vllm", cost=0),
    ModelConfig("gpt-4o-mini", "openai", cost=0.00015),
]

# Jetson Orin Nano (8GB) - Recommended
models = [
    ModelConfig("meta-llama/Llama-3.2-3B-Instruct", "vllm", cost=0),
    ModelConfig("claude-3-5-sonnet", "anthropic", cost=0.003),
]

# Jetson Orin NX (16GB)
models = [
    ModelConfig("meta-llama/Llama-3.1-8B-Instruct", "vllm", cost=0),
    ModelConfig("gpt-4o", "openai", cost=0.00625),
]
```

### Auto-Discovery

**Dynamically discover models** available on your vLLM server:

```python
from cascadeflow.providers.vllm import VLLMProvider
from cascadeflow import CascadeAgent, ModelConfig

# Discover available models
provider = VLLMProvider(base_url="http://localhost:8000/v1")
available_models = await provider.list_models()
print(f"Available models: {available_models}")
# Output: ['meta-llama/Llama-3.2-3B-Instruct', 'Qwen/Qwen2.5-3B-Instruct']

# Build cascade from discovered models
models = []
for model_name in available_models:
    models.append(ModelConfig(
        name=model_name,
        provider="vllm",
        cost=0.0
    ))

# Add cloud fallback
models.append(ModelConfig("gpt-4o", "openai", cost=0.00625))

agent = CascadeAgent(models=models)
```

**Benefits:**
- ✅ No hardcoded model names
- ✅ Works with any vLLM configuration
- ✅ Automatically adapts to server changes
- ✅ Useful for multi-model edge deployments

---

## Use Cases

### 1. Smart Manufacturing

**Scenario**: Factory floor quality control and predictive maintenance

```python
# Edge processing for real-time decisions
agent = CascadeAgent(models=[
    ModelConfig("llama-3.2-3b", "vllm", cost=0),  # Local Jetson
    ModelConfig("gpt-4o", "openai", cost=0.00625),  # Cloud expertise
])

# Simple QC checks stay local (<50ms)
result = await agent.run(
    "Part #A1234 dimensions: 10.02mm x 5.01mm. "
    "Spec: 10.00mm ± 0.05mm. Pass or fail?"
)
# ✅ Processed locally

# Complex failure analysis cascades to cloud
result = await agent.run(
    "Motor: 85°C, Vibration: 12mm/s, Current: 45A. "
    "Analyze failure mode and maintenance schedule."
)
# ☁️ Cascaded to cloud for expert analysis
```

### 2. Healthcare Devices

**Scenario**: HIPAA-compliant local processing with cloud consultation

```python
# Medical device: Privacy-first with cloud fallback
agent = CascadeAgent(models=[
    ModelConfig("llama-3.1-8b-medical-finetune", "vllm", cost=0),
    ModelConfig("claude-3-5-sonnet", "anthropic", cost=0.003),
])

# Routine queries stay on device (HIPAA compliant)
result = await agent.run("Normal blood pressure range for 45-year-old?")
# ✅ Stays on device (patient data never leaves)

# Complex cases can cascade with consent
result = await agent.run("Analyze EKG anomalies: [detailed data]...")
# ☁️ Cascade only if patient consents
```

### 3. Retail Kiosks

**Scenario**: Fast customer service with inventory management

- **Local**: Product info, basic questions (<100ms response)
- **Cloud**: Inventory optimization, complex recommendations

### 4. Autonomous Robots

**Scenario**: Real-time control with cloud planning

- **Local**: Obstacle avoidance, navigation commands
- **Cloud**: Path planning, complex decision-making

---

## Performance

### Expected Latency

| **Tier** | **Model** | **Device** | **Latency** |
|----------|-----------|------------|-------------|
| Local | Llama 3.2 1B | Jetson Nano | 150-300ms |
| Local | Llama 3.2 3B | Jetson Orin Nano | 80-150ms |
| Local | Llama 3.1 8B | Jetson Orin NX | 50-100ms |
| Cloud | GPT-4o | OpenAI | 600-1500ms |
| Cloud | Claude 3.5 | Anthropic | 800-1200ms |

### Cost Savings

**Example: 10,000 queries/month**

| **Strategy** | **Local %** | **Cloud %** | **Monthly Cost** | **Savings** |
|--------------|-------------|-------------|------------------|-------------|
| All Cloud | 0% | 100% | $30.00 | 0% |
| Edge-First (Conservative) | 60% | 40% | $12.00 | 60% |
| Edge-First (Balanced) | 75% | 25% | $7.50 | 75% |
| Edge-First (Aggressive) | 85% | 15% | $4.50 | 85% |

---

## Troubleshooting

### vLLM Server Won't Start

**Issue**: OOM (Out of Memory) errors

**Solution**:
```bash
# Use smaller model
--model meta-llama/Llama-3.2-1B-Instruct

# Reduce GPU memory usage
--gpu-memory-utilization 0.6

# Reduce context length
--max-model-len 2048
```

### High Cascade Rate

**Issue**: Too many queries cascading to cloud

**Solutions**:
1. **Lower quality threshold**:
   ```python
   quality_config = QualityConfig(min_confidence=0.60)
   ```

2. **Use better local model**: Upgrade from 1B to 3B or 8B

3. **Fine-tune local model**: Train on your specific domain

### Slow Local Inference

**Issue**: Local responses taking >500ms

**Solutions**:
1. **Check GPU utilization**: `nvidia-smi`
2. **Enable tensor parallelism** (multi-GPU):
   ```bash
   --tensor-parallel-size 2
   ```
3. **Use quantized models** (GPTQ/AWQ)
4. **Reduce batch size** if using continuous batching

---

## Best Practices

### 1. Monitor GPU Health

```bash
# Watch GPU temperature and usage
watch -n 1 nvidia-smi

# Set power mode (Jetson)
sudo nvpmodel -m 0  # MAXN mode for performance
sudo nvpmodel -m 1  # 15W mode for efficiency
```

### 2. Implement Circuit Breaker

```python
from cascadeflow import CascadeAgent

class EdgeAgent:
    def __init__(self):
        self.cloud_failures = 0
        self.max_failures = 5

    async def run_with_fallback(self, query):
        try:
            result = await self.agent.run(query)
            self.cloud_failures = 0  # Reset on success
            return result
        except Exception as e:
            self.cloud_failures += 1
            if self.cloud_failures >= self.max_failures:
                # Disable cloud cascade temporarily
                return await self.agent.run(query, force_tier=1)
            raise
```

### 3. Cache Common Queries

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_cached_response(query: str):
    return await agent.run(query)
```

### 4. Production Deployment

```python
# Use systemd service for vLLM
# /etc/systemd/system/vllm.service
[Unit]
Description=vLLM Server
After=network.target

[Service]
Type=simple
User=jetson
WorkingDirectory=/home/jetson
ExecStart=/usr/bin/python3 -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-3.2-3B-Instruct \
    --dtype half \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.8
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Next Steps

- **Example**: See [`examples/edge_device.py`](../../examples/edge_device.py)
- **vLLM Setup**: Check [`docs/configs/vllm_setup.md`](../configs/vllm_setup.md)
- **Production**: Read [`production.md`](production.md) for deployment patterns

---

## Summary

✅ **Privacy**: Data stays on device for 70-80% of queries
✅ **Cost**: 70-85% savings vs all-cloud
✅ **Latency**: <100ms for local queries
✅ **Quality**: Cloud fallback ensures complex queries handled well
✅ **Offline**: Works without internet for local queries

**Perfect for**: Manufacturing, healthcare, retail, robotics, IoT gateways

---

**Ready to deploy?** Run `python examples/edge_device.py` to test your setup!
