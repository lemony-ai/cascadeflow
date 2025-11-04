# Local Providers Guide: Ollama & vLLM

Complete guide for setting up and using Ollama and vLLM in various deployment scenarios.

---

## Overview

Both Ollama and vLLM are **100% FREE** local inference solutions with **zero API costs**. They provide:

- ✅ **Privacy-first**: Your data never leaves your infrastructure
- ✅ **No rate limits**: Unlimited requests
- ✅ **Full control**: Deploy where you want, how you want
- ✅ **Tool calling support**: Full agentic capabilities
- ✅ **Production-ready**: Proven at scale

---

## Quick Start

### Ollama

```python
from cascadeflow.providers.ollama import OllamaProvider

# Default: localhost:11434
provider = OllamaProvider()

response = await provider.complete(
    prompt="What is AI?",
    model="llama3.2"
)
```

### vLLM

```python
from cascadeflow.providers.vllm import VLLMProvider

# Default: localhost:8000/v1
provider = VLLMProvider()

response = await provider.complete(
    prompt="What is AI?",
    model="meta-llama/Llama-3-8B-Instruct"
)
```

---

## Deployment Scenarios

### 1. Local Installation (Default)

**Best for:** Development, testing, single-user

#### Ollama

**Installation:**
```bash
# Download and install from https://ollama.ai/download
# macOS/Windows: Automatically starts on boot
# Linux: Run manually
ollama serve

# Pull a model
ollama pull llama3.2
```

**Configuration:**
```python
# No configuration needed - uses localhost:11434
provider = OllamaProvider()
```

**Environment variables:**
```bash
# .env (optional)
OLLAMA_BASE_URL=http://localhost:11434
```

#### vLLM

**Installation:**
```bash
# Install vLLM
pip install vllm

# Start server
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3-8B-Instruct \
  --port 8000
```

**Configuration:**
```python
# No configuration needed - uses localhost:8000/v1
provider = VLLMProvider()
```

**Environment variables:**
```bash
# .env (optional)
VLLM_BASE_URL=http://localhost:8000/v1
```

---

### 2. Network Deployment

**Best for:** Team sharing, GPU server, centralized resources

#### Ollama

**Server setup (192.168.1.100):**
```bash
# Start Ollama accepting network connections
OLLAMA_HOST=0.0.0.0:11434 ollama serve

# Pull models
ollama pull llama3.2
ollama pull mistral
```

**Client configuration:**
```python
# Option A: Environment variable
os.environ["OLLAMA_BASE_URL"] = "http://192.168.1.100:11434"
provider = OllamaProvider()

# Option B: Parameter
provider = OllamaProvider(base_url="http://192.168.1.100:11434")
```

**Environment variables:**
```bash
# .env
OLLAMA_BASE_URL=http://192.168.1.100:11434
```

#### vLLM

**Server setup (192.168.1.200):**
```bash
# Start vLLM accepting network connections
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3-70B-Instruct \
  --host 0.0.0.0 \
  --port 8000
```

**Client configuration:**
```python
# Option A: Environment variable
os.environ["VLLM_BASE_URL"] = "http://192.168.1.200:8000/v1"
provider = VLLMProvider()

# Option B: Parameter
provider = VLLMProvider(base_url="http://192.168.1.200:8000/v1")
```

**Environment variables:**
```bash
# .env
VLLM_BASE_URL=http://192.168.1.200:8000/v1
```

---

### 3. Remote Server (with Authentication)

**Best for:** Cloud deployment, multi-user, internet access

#### Ollama

**Server setup (ollama.yourdomain.com):**

1. **Install Ollama** on cloud server
2. **Set up reverse proxy** (nginx example):

```nginx
# /etc/nginx/sites-available/ollama
server {
    listen 443 ssl http2;
    server_name ollama.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/ollama.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ollama.yourdomain.com/privkey.pem;

    location /api/ {
        # Optional: Add authentication
        auth_basic "Ollama API";
        auth_basic_user_file /etc/nginx/.htpasswd;

        proxy_pass http://localhost:11434/api/;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header Host $host;
    }
}
```

3. **Create auth token** (if using Bearer token instead of Basic Auth):
```bash
# Generate secure token
openssl rand -hex 32
```

**Client configuration:**
```python
# Option A: Environment variables
os.environ["OLLAMA_BASE_URL"] = "https://ollama.yourdomain.com"
os.environ["OLLAMA_API_KEY"] = "your_auth_token_here"
provider = OllamaProvider()

# Option B: Parameters
provider = OllamaProvider(
    base_url="https://ollama.yourdomain.com",
    api_key="your_auth_token_here"
)
```

**Environment variables:**
```bash
# .env
OLLAMA_BASE_URL=https://ollama.yourdomain.com
OLLAMA_API_KEY=your_auth_token_here
```

#### vLLM

**Server setup (vllm.yourdomain.com):**

1. **Deploy vLLM** to cloud GPU (AWS, GCP, Azure)
2. **Start with API key:**

```bash
# Generate secure API key
openssl rand -hex 32

# Start vLLM with authentication
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3-70B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key your_secure_api_key_here
```

3. **Set up SSL** (nginx example):

```nginx
# /etc/nginx/sites-available/vllm
server {
    listen 443 ssl http2;
    server_name vllm.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/vllm.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vllm.yourdomain.com/privkey.pem;

    location /v1/ {
        proxy_pass http://localhost:8000/v1/;
        proxy_set_header Authorization $http_authorization;
        proxy_set_header Host $host;
    }
}
```

**Client configuration:**
```python
# Option A: Environment variables
os.environ["VLLM_BASE_URL"] = "https://vllm.yourdomain.com/v1"
os.environ["VLLM_API_KEY"] = "your_secure_api_key"
provider = VLLMProvider()

# Option B: Parameters
provider = VLLMProvider(
    base_url="https://vllm.yourdomain.com/v1",
    api_key="your_secure_api_key"
)
```

**Environment variables:**
```bash
# .env
VLLM_BASE_URL=https://vllm.yourdomain.com/v1
VLLM_API_KEY=your_secure_api_key
```

---

## Configuration Reference

### Ollama

| Configuration | Environment Variable | Code Parameter | Default |
|--------------|---------------------|----------------|---------|
| Server URL | `OLLAMA_BASE_URL` | `base_url` | `http://localhost:11434` |
| API Key (optional) | `OLLAMA_API_KEY` | `api_key` | `None` |
| Timeout | - | `timeout` | `300.0` (5 min) |
| Keep Alive | - | `keep_alive` | `"5m"` |

**Legacy:** `OLLAMA_HOST` is still supported but deprecated. Use `OLLAMA_BASE_URL` instead.

### vLLM

| Configuration | Environment Variable | Code Parameter | Default |
|--------------|---------------------|----------------|---------|
| Server URL | `VLLM_BASE_URL` | `base_url` | `http://localhost:8000/v1` |
| API Key (optional) | `VLLM_API_KEY` | `api_key` | `None` |
| Timeout | - | `timeout` | `120.0` (2 min) |
| Model Name | `VLLM_MODEL_NAME` | - | Auto-detected |

---

## Security Best Practices

### 1. Use HTTPS for Remote Deployments
```bash
# Use Let's Encrypt for free SSL certificates
certbot certonly --nginx -d ollama.yourdomain.com
certbot certonly --nginx -d vllm.yourdomain.com
```

### 2. Strong API Keys
```bash
# Generate secure tokens (32+ bytes)
openssl rand -hex 32
# Output: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

### 3. Firewall Configuration
```bash
# Only allow specific IPs (example with ufw)
sudo ufw allow from 192.168.1.0/24 to any port 11434  # Ollama
sudo ufw allow from 192.168.1.0/24 to any port 8000   # vLLM
```

### 4. Use VPN for Network Deployments
```bash
# Consider WireGuard or Tailscale for secure network access
# This way servers don't need to be exposed to the internet
```

### 5. Monitor Access Logs
```bash
# Check nginx logs for suspicious activity
tail -f /var/log/nginx/access.log

# Check Ollama logs
journalctl -u ollama -f

# Check vLLM logs
tail -f /var/log/vllm/server.log
```

### 6. Rotate API Keys Regularly
```python
# Update keys every 90 days
# Use secrets manager in production (AWS Secrets Manager, Vault, etc.)
```

---

## Hybrid Setup (Recommended)

Combine both providers for maximum flexibility:

```python
from cascadeflow import CascadeAgent
from cascadeflow.providers.ollama import OllamaProvider
from cascadeflow.providers.vllm import VLLMProvider

# Configure both providers
ollama = OllamaProvider()  # Local development
vllm = VLLMProvider(base_url="http://192.168.1.200:8000/v1")  # Production

# Create agent with cascading fallback
agent = CascadeAgent(
    models=[
        {
            "provider": vllm,
            "model": "meta-llama/Llama-3-70B-Instruct",
            "priority": 1,  # Use vLLM for best quality
        },
        {
            "provider": ollama,
            "model": "llama3.2:1b",
            "priority": 2,  # Fallback to Ollama if vLLM unavailable
        },
    ]
)

# Automatically uses best available provider
response = await agent.run("What is machine learning?")
```

**Benefits:**
- ✅ Best quality when vLLM available
- ✅ Always works (fallback to Ollama)
- ✅ Zero API costs
- ✅ Complete privacy

---

## Troubleshooting

### Ollama

**Issue: "Cannot connect to Ollama"**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve

# Check logs
journalctl -u ollama -f  # Linux
cat ~/Library/Logs/Ollama/server.log  # macOS
```

**Issue: "Model not found"**
```bash
# List available models
ollama list

# Pull the model
ollama pull llama3.2
```

**Issue: "Connection refused" on network**
```bash
# Make sure server is listening on 0.0.0.0
OLLAMA_HOST=0.0.0.0:11434 ollama serve

# Check firewall
sudo ufw status
```

### vLLM

**Issue: "Failed to connect to vLLM server"**
```bash
# Check if vLLM is running
curl http://localhost:8000/v1/models

# Check vLLM process
ps aux | grep vllm

# Start vLLM if not running
python -m vllm.entrypoints.openai.api_server --model <model>
```

**Issue: "Request timed out"**
```python
# Increase timeout for large models
provider = VLLMProvider(timeout=300.0)  # 5 minutes
```

**Issue: "Model not loaded"**
```bash
# Check which model is loaded
curl http://localhost:8000/v1/models

# Make sure model name matches
VLLM_MODEL_NAME=meta-llama/Llama-3-8B-Instruct
```

---

## Examples

See complete working examples:
- `examples/integrations/local_providers_setup.py` - All deployment scenarios
- `examples/integrations/test_all_providers.py` - Provider testing

---

## Resources

### Ollama
- Website: https://ollama.ai/
- Documentation: https://github.com/ollama/ollama/tree/main/docs
- Models: https://ollama.ai/library
- API Reference: https://github.com/ollama/ollama/blob/main/docs/api.md

### vLLM
- Website: https://docs.vllm.ai/
- GitHub: https://github.com/vllm-project/vllm
- Documentation: https://docs.vllm.ai/en/latest/
- Supported Models: https://docs.vllm.ai/en/latest/models/supported_models.html

### CascadeFlow
- Documentation: `docs/`
- Examples: `examples/integrations/`
- Provider Guide: `docs/guides/`
