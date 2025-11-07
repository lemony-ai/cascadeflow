# Multi-Instance Ollama with Docker Compose

Run draft and verifier models on separate Ollama instances using Docker Compose. Perfect for multi-GPU systems where you want to maximize hardware utilization.

## Architecture

```
┌─────────────────────────────────────────────┐
│  CascadeFlow Agent                          │
│                                             │
│  ┌────────────┐        ┌─────────────────┐ │
│  │   Draft    │───┬───>│   Verifier      │ │
│  │  Model     │   │    │   Model         │ │
│  └────────────┘   │    └─────────────────┘ │
└───────│───────────┼──────────────│──────────┘
        │           │              │
        ▼           │              ▼
  ┌─────────┐       │        ┌─────────┐
  │ Ollama  │       │        │ Ollama  │
  │ Draft   │       │        │Verifier │
  │ :11434  │       │        │ :11435  │
  │ GPU 0   │       │        │ GPU 1   │
  └─────────┘       │        └─────────┘
        │           │              │
        └───────────┴──────────────┘
            Docker Network
```

## Quick Start

### 1. Prerequisites

- Docker and Docker Compose installed
- NVIDIA GPU(s) with drivers installed
- NVIDIA Container Toolkit installed

**Install NVIDIA Container Toolkit:**

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. Start the Instances

```bash
# From this directory
docker-compose up -d
```

This starts:
- `ollama-draft` on port 11434 (GPU 0)
- `ollama-verifier` on port 11435 (GPU 1)

### 3. Pull Models

Pull models on each instance:

```bash
# Draft model (fast, small)
docker exec ollama-draft ollama pull llama3.2:1b

# Verifier model (accurate, large)
docker exec ollama-verifier ollama pull llama3.1:70b
```

**Model Recommendations:**

| Use Case | Draft Model | Verifier Model |
|----------|-------------|----------------|
| **Fast** | llama3.2:1b (1GB) | llama3.1:8b (4.7GB) |
| **Balanced** | llama3.2:3b (2GB) | llama3.1:70b (40GB) |
| **Quality** | qwen2.5:7b (4.7GB) | qwen2.5:72b (41GB) |

### 4. Verify Setup

```bash
# Check draft instance
curl http://localhost:11434/api/tags

# Check verifier instance
curl http://localhost:11435/api/tags
```

### 5. Run Example

```bash
# Configure environment
export OLLAMA_DRAFT_URL=http://localhost:11434
export OLLAMA_VERIFIER_URL=http://localhost:11435
export OLLAMA_DRAFT_MODEL=llama3.2:1b
export OLLAMA_VERIFIER_MODEL=llama3.1:70b

# Run the example
cd ../../../packages/core/examples/nodejs
npx tsx multi-instance-ollama.ts
```

## Configuration Options

### Single GPU System

If you only have one GPU, remove the `device_ids` restriction:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          capabilities: [gpu]
          # Remove device_ids to share GPU
```

Both instances will share the same GPU but still run independently.

### CPU-Only

For testing without GPU (slower):

```yaml
# Remove entire deploy section
# deploy:
#   resources:
#     reservations:
#       devices:
#         - driver: nvidia
```

### Custom Ports

Change external ports if needed:

```yaml
services:
  ollama-draft:
    ports:
      - "12000:11434"  # External:Internal

  ollama-verifier:
    ports:
      - "12001:11434"
```

Then set `OLLAMA_DRAFT_URL=http://localhost:12000`.

## Management Commands

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f ollama-draft
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart one
docker-compose restart ollama-draft
```

### Stop and Remove

```bash
# Stop (keeps data)
docker-compose stop

# Remove (keeps data)
docker-compose down

# Remove including data volumes
docker-compose down -v
```

### Monitor GPU Usage

```bash
# Watch GPU utilization
watch -n 1 nvidia-smi
```

## Performance Tuning

### Model Selection

Choose models based on your GPU memory:

**For 8GB VRAM:**
- Draft: llama3.2:1b (1GB) + Verifier: llama3.1:8b (4.7GB)
- Or: llama3.2:3b (2GB) + mistral:7b (4.1GB)

**For 24GB VRAM:**
- Draft: qwen2.5:7b (4.7GB) + Verifier: qwen2.5:32b (19GB)
- Or: llama3.1:8b (4.7GB) + llama3.1:70b (split across GPUs)

**For 48GB+ VRAM (per GPU):**
- Draft: qwen2.5:7b (4.7GB) + Verifier: qwen2.5:72b (41GB)
- Or: llama3.1:8b (4.7GB) + qwen2.5:72b (41GB)

### Environment Variables

Set in `.env` file:

```env
# Model URLs
OLLAMA_DRAFT_URL=http://localhost:11434
OLLAMA_VERIFIER_URL=http://localhost:11435

# Model names
OLLAMA_DRAFT_MODEL=llama3.2:1b
OLLAMA_VERIFIER_MODEL=llama3.1:70b

# Ollama options (optional)
OLLAMA_NUM_PARALLEL=1
OLLAMA_MAX_LOADED_MODELS=2
```

## Troubleshooting

### "No NVIDIA GPU found"

Ensure NVIDIA Container Toolkit is installed:

```bash
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### "Device already in use"

Another process is using the GPU. Check with:

```bash
nvidia-smi
fuser -v /dev/nvidia*
```

### "Out of memory"

- Use smaller models
- Reduce `OLLAMA_MAX_LOADED_MODELS`
- Restart Docker to free memory

### "Connection refused"

Check if services are running:

```bash
docker-compose ps
docker-compose logs
```

## Next Steps

- Adjust quality thresholds in your code
- Monitor cascade effectiveness
- Try different model combinations
- Scale horizontally with more instances

## Additional Resources

- [Ollama Documentation](https://ollama.ai/docs)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-docker)
- [Multi-Instance vLLM Example](../multi-instance-vllm/)
