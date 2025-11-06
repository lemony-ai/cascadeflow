# CascadeFlow Routing Proxy - MVP

**Drop-in replacement for Anthropic/OpenAI APIs with automatic cost optimization**

Stop overpaying for AI API calls. Point Claude Code (or any AI tool) to CascadeFlow's routing proxy and get **40-85% cost savings** automatically through intelligent cascade routing.

---

## 🎯 What It Does

CascadeFlow Routing Proxy is a **transparent proxy** that intercepts AI API requests and intelligently routes them through a cascade of models:

1. **Try cheap models first** (e.g., gpt-4o-mini, llama-3.1-8b)
2. **Verify quality** automatically
3. **Escalate if needed** to more powerful models
4. **Return response** in original API format

**Result:** 40-85% cost reduction with zero quality loss and zero code changes.

---

## 🚀 Quick Start

### Option 1: Local Development

```bash
# Install dependencies
pip install cascadeflow[all] fastapi uvicorn

# Set up environment
export CASCADEFLOW_API_KEY="your-secret-key"
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Run proxy
python examples/routing_proxy.py
```

### Option 2: Docker

```bash
# Copy environment template
cp examples/routing_proxy.env.example .env

# Edit .env with your API keys
nano .env

# Run with Docker Compose
docker-compose -f examples/routing_proxy.docker-compose.yml up -d
```

---

## 🔧 Claude Code Setup

Point Claude Code to the proxy:

```bash
export ANTHROPIC_BASE_URL="http://localhost:8000"
export ANTHROPIC_API_KEY="your-cascadeflow-api-key"
```

**That's it!** Claude Code now routes through CascadeFlow with automatic cost optimization.

---

## 📡 API Endpoints

### Anthropic Messages API
- **Endpoint:** `POST /v1/messages`
- **Compatible with:** `api.anthropic.com/v1/messages`
- **Streaming:** ✅ Full SSE support
- **Authentication:** Bearer token or x-api-key header

### OpenAI Chat Completions API
- **Endpoint:** `POST /v1/chat/completions`
- **Compatible with:** `api.openai.com/v1/chat/completions`
- **Streaming:** ✅ Full SSE support
- **Authentication:** Bearer token or x-api-key header

### Monitoring
- **Stats:** `GET /api/stats` - Usage statistics and cost tracking
- **Health:** `GET /health` - Health check and provider status
- **Docs:** `GET /docs` - Interactive API documentation

---

## 💡 How It Works

### Traditional Approach (Expensive)
```
User Request → Claude Code → api.anthropic.com → Claude Sonnet ($3/1M tokens)
```

### With CascadeFlow Proxy (Optimized)
```
User Request → Claude Code → CascadeFlow Proxy
                                   ↓
                    Try gpt-4o-mini first ($0.15/1M tokens)
                                   ↓
                    Quality check: Is answer good enough?
                                   ↓
                    ✅ YES: Return (saved 95%!)
                    ❌ NO: Escalate to Claude Sonnet
```

**Result:** Most simple queries handled by cheap models, complex queries get premium models.

---

## 🎯 Cost Savings Examples

### Example 1: Code Reviews
- **Without proxy:** 1000 requests × $0.003 = **$3.00**
- **With proxy:** 800 × $0.00015 + 200 × $0.003 = **$0.72** (76% savings)

### Example 2: Documentation
- **Without proxy:** 500 requests × $0.003 = **$1.50**
- **With proxy:** 480 × $0.00015 + 20 × $0.003 = **$0.13** (91% savings)

### Example 3: General Coding
- **Without proxy:** 2000 requests × $0.003 = **$6.00**
- **With proxy:** 1400 × $0.00015 + 600 × $0.003 = **$2.01** (66% savings)

---

## 🔐 Security

### API Key Authentication

Set `CASCADEFLOW_API_KEY` to require authentication:

```bash
# Generate a secure key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in environment
export CASCADEFLOW_API_KEY="kJ8n_X2mP9..."
```

Clients authenticate with:
- **Bearer token:** `Authorization: Bearer kJ8n_X2mP9...`
- **Custom header:** `x-api-key: kJ8n_X2mP9...`

### Without API Key

If `CASCADEFLOW_API_KEY` is not set, the proxy accepts all requests. **Not recommended for production.**

---

## 📊 Monitoring & Stats

Check cost savings in real-time:

```bash
curl http://localhost:8000/api/stats
```

```json
{
  "total_requests": 1523,
  "anthropic_requests": 1200,
  "openai_requests": 323,
  "total_cost": 0.45,
  "cascade_used": 1201,
  "cascade_percentage": 78.8,
  "models_used": {
    "gpt-4o-mini": 1201,
    "claude-3-5-sonnet-20241022": 322
  },
  "cost_per_request": 0.000295
}
```

---

## 🐳 Docker Deployment

### Build Image

```bash
docker build -f examples/routing_proxy.Dockerfile -t cascadeflow-proxy:latest .
```

### Run Container

```bash
docker run -d \
  --name cascadeflow-proxy \
  -p 8000:8000 \
  -e CASCADEFLOW_API_KEY="your-secret-key" \
  -e OPENAI_API_KEY="sk-..." \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  --restart unless-stopped \
  cascadeflow-proxy:latest
```

### Docker Compose

```bash
docker-compose -f examples/routing_proxy.docker-compose.yml up -d
```

### Health Check

```bash
docker ps  # Check status
curl http://localhost:8000/health
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CASCADEFLOW_API_KEY` | No* | API key for authentication (*recommended for production) |
| `OPENAI_API_KEY` | Yes** | OpenAI API key |
| `ANTHROPIC_API_KEY` | Yes** | Anthropic API key |
| `GROQ_API_KEY` | No | Groq API key (optional, for ultra-fast inference) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

** At least one provider API key is required

### Model Configuration

The proxy automatically configures models based on available API keys:

**With GROQ_API_KEY:**
- `llama-3.1-8b-instant` (cost: $0.00005/1K tokens) - cheapest, fastest

**With OPENAI_API_KEY:**
- `gpt-4o-mini` (cost: $0.00015/1K tokens) - cheap, good quality
- `gpt-4o` (cost: $0.00625/1K tokens) - expensive, best quality

**With ANTHROPIC_API_KEY:**
- `claude-3-5-sonnet-20241022` (cost: $0.003/1K tokens) - premium

**Cascade order:** Groq → OpenAI Mini → OpenAI 4o → Claude Sonnet

---

## 🧪 Testing

### Test Anthropic API Endpoint

```bash
# Non-streaming
curl -X POST http://localhost:8000/v1/messages \
  -H "x-api-key: your-cascadeflow-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'

# Streaming
curl -N -X POST http://localhost:8000/v1/messages \
  -H "x-api-key: your-cascadeflow-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "Count to 10"}],
    "max_tokens": 100,
    "stream": true
  }'
```

### Test OpenAI API Endpoint

```bash
# Non-streaming
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer your-cascadeflow-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'

# Streaming
curl -N -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer your-cascadeflow-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Count to 10"}],
    "max_tokens": 100,
    "stream": true
  }'
```

### Test with Claude Code

```bash
# Configure Claude Code
export ANTHROPIC_BASE_URL="http://localhost:8000"
export ANTHROPIC_API_KEY="your-cascadeflow-api-key"

# Run Claude Code normally
claude code --prompt "Write a function to calculate fibonacci"

# Check stats to see cost savings
curl http://localhost:8000/api/stats
```

---

## 🎨 Use Cases

### 1. Claude Code Cost Optimization
- Point Claude Code to the proxy
- Get automatic cost optimization on all coding tasks
- **Expected savings:** 60-85%

### 2. API Gateway for Multiple Projects
- Single proxy serves multiple applications
- Centralized cost tracking and monitoring
- Consistent cascade behavior across projects

### 3. Development Environment
- Use cheap models for development/testing
- Automatically escalate for production
- Track costs per environment

### 4. Self-Hosted AI Infrastructure
- Add Groq or Ollama for ultra-cheap inference
- Keep sensitive data on your infrastructure
- Fallback to cloud APIs only when needed

---

## 🔍 Troubleshooting

### Proxy Returns 503 (Service Unavailable)
- Check that at least one provider API key is set
- Check logs: `docker logs cascadeflow-proxy`

### Proxy Returns 401 (Unauthorized)
- Verify `CASCADEFLOW_API_KEY` is set correctly
- Check client is sending API key in header

### Claude Code Can't Connect
- Verify proxy is running: `curl http://localhost:8000/health`
- Check `ANTHROPIC_BASE_URL` is set correctly
- Ensure no trailing slash: `http://localhost:8000` (not `http://localhost:8000/`)

### Cost Savings Lower Than Expected
- Check stats to see cascade usage: `curl http://localhost:8000/api/stats`
- Verify multiple models are configured (need 2+ for cascade)
- Some complex queries naturally require premium models

---

## 📚 Architecture

### How Cascade Routing Works

1. **Request arrives** at `/v1/messages` or `/v1/chat/completions`
2. **API key validated** (if configured)
3. **Request parsed** from Anthropic/OpenAI format
4. **CascadeAgent invoked** with query
5. **Cascade execution:**
   - Try cheapest model (e.g., Groq Llama)
   - Quality validation (confidence, completeness)
   - If quality insufficient, escalate to next model
   - Repeat until quality threshold met
6. **Response formatted** in original API format
7. **Stats updated** (cost, models used, cascade rate)

### Key Components

- **`routing_proxy.py`** - Main FastAPI application
- **`AnthropicMessagesRequest/Response`** - Anthropic API models
- **`OpenAIChatCompletionRequest/Response`** - OpenAI API models
- **`CascadeAgent`** - Intelligent cascade routing logic
- **API key validation** - Bearer token + custom header support
- **Streaming support** - Full SSE for both APIs
- **Stats tracking** - Cost, usage, cascade rate monitoring

---

## 🆚 Comparison to Alternatives

| Feature | CascadeFlow | LiteLLM Proxy | OpenRouter |
|---------|-------------|---------------|------------|
| **Cascade routing** | ✅ Different model tiers | ❌ Same model only | ❌ Same model only |
| **Quality verification** | ✅ Automatic | ❌ | ❌ |
| **Anthropic API** | ✅ | ✅ | ❌ |
| **OpenAI API** | ✅ | ✅ | ✅ |
| **Self-hosted** | ✅ | ✅ | ❌ (Hosted only) |
| **Open-source** | ✅ | ✅ | ❌ (Closed) |
| **Cost optimization** | **Automatic** | Manual | Price-based |
| **Streaming** | ✅ Both APIs | ✅ | ✅ |

**CascadeFlow is the only proxy with quality-based cascade routing across model tiers.**

---

## 🤝 Contributing

Found a bug? Have a feature request? Want to improve the proxy?

1. Check existing issues: [GitHub Issues](https://github.com/lemony-ai/cascadeflow/issues)
2. Read the architecture: [docs/ROUTING_PROXY_ARCHITECTURE.md](../docs/ROUTING_PROXY_ARCHITECTURE.md)
3. Submit a PR with tests

---

## 📖 Related Documentation

- **Architecture:** [docs/ROUTING_PROXY_ARCHITECTURE.md](../docs/ROUTING_PROXY_ARCHITECTURE.md)
- **Fact Check:** [docs/ROUTING_PROXY_FACT_CHECK.md](../docs/ROUTING_PROXY_FACT_CHECK.md)
- **Implementation Plan:** [docs/ROUTING_PROXY_IMPLEMENTATION_PLAN.md](../docs/ROUTING_PROXY_IMPLEMENTATION_PLAN.md)
- **Gap Analysis:** [docs/PROXY_GAP_ANALYSIS.md](../docs/PROXY_GAP_ANALYSIS.md)
- **Main README:** [README.md](../README.md)

---

## 📊 Research Validation

The cascade routing approach is validated by peer-reviewed research:

- **FrugalGPT (Stanford):** 98% cost reduction with maintained quality
- **Amazon Bedrock Routing:** 16-56% cost savings
- **Arcee Conductor:** 99% cost reduction per prompt

CascadeFlow's **40-85% savings** is conservative and realistic.

**Research paper:** Chen, Lingjiao, et al. "FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance." arXiv:2305.05176 (2023).

---

## 📝 License

MIT License - see [LICENSE](../LICENSE)

---

## 🙏 Acknowledgments

- Research inspiration: FrugalGPT (Stanford)
- Architecture patterns: LiteLLM, OpenRouter
- Community: Claude Code proxy projects

---

**Questions? Issues? Feedback?**

- GitHub: [lemony-ai/cascadeflow](https://github.com/lemony-ai/cascadeflow)
- Docs: [docs/](../docs/)
- Examples: [examples/](../examples/)

---

**Built with ❤️ by the CascadeFlow team**

*Stop overpaying for AI. Start cascading.*
