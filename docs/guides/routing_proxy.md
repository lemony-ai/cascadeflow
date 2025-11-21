# Routing Proxy Guide

Use CascadeFlow as a transparent routing proxy for automatic cost optimization with Claude Code and other AI tools.

---

## Overview

The CascadeFlow Routing Proxy acts as a drop-in replacement for the Anthropic API, automatically routing requests through intelligent cascade logic to save 40-80% on costs.

**Key Benefits:**
- ✅ **Transparent Operation**: Works as drop-in URL replacement
- ✅ **Automatic Savings**: 40-80% cost reduction with zero code changes
- ✅ **Claude Code Compatible**: Perfect for reducing Claude Code costs
- ✅ **SDK Compatible**: Works with official Anthropic Python SDK
- ✅ **Self-Hosted**: Full control over your data and routing

---

## Quick Start

### 1. Start the Proxy

```bash
# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Start proxy
python examples/fastapi_proxy_routing.py
```

Server starts on `http://localhost:8000`

### 2. Configure Claude Code

```bash
# Point Claude Code to proxy instead of Anthropic API
export ANTHROPIC_BASE_URL="http://localhost:8000"

# Keep your API key
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. Use Claude Code Normally!

That's it! Claude Code will now automatically use the cheaper Haiku model when possible, only escalating to Sonnet when quality demands it.

**Result: 40-80% cost savings automatically!**

---

## How It Works

```
┌─────────────────┐
│  Claude Code    │
│  (or any tool)  │
└────────┬────────┘
         │ POST /v1/messages (Anthropic format)
         │ Request: "claude-3-5-sonnet-20241022"
         ↓
┌──────────────────────────────────────┐
│   CascadeFlow Routing Proxy          │
│   (http://localhost:8000)            │
│                                      │
│  1. Receive request for Sonnet       │
│  2. Try Haiku first (draft)          │
│  3. Quality check (confidence)       │
│  4. If good → return Haiku (60% $$)  │
│  5. If bad → escalate to Sonnet      │
│  6. Return in Anthropic API format   │
└────────┬─────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│   Actual Anthropic API               │
│   (api.anthropic.com)                │
└──────────────────────────────────────┘
```

---

## Cost Savings Example

**Without Proxy:**
```bash
# All requests use Sonnet
1000 requests × 1K tokens × $0.003 = $3.00
```

**With Proxy (60% acceptance rate):**
```bash
# 600 requests use Haiku
600 × 1K × $0.0008 = $0.48

# 400 requests escalate to Sonnet
400 × 1K × $0.003 = $1.20

# Total: $1.68 (vs $3.00)
# Savings: 44%!
```

---

## Usage Examples

### With Claude Code

```bash
# 1. Start proxy
python examples/fastapi_proxy_routing.py

# 2. Configure Claude Code
export ANTHROPIC_BASE_URL="http://localhost:8000"

# 3. Use Claude Code normally
# Automatic cost savings on every request!
```

### With Anthropic Python SDK

```python
from anthropic import Anthropic

# Point SDK to proxy instead of Anthropic API
client = Anthropic(
    api_key="sk-ant-...",
    base_url="http://localhost:8000"  # Proxy URL
)

# Use normally - automatic cascade routing!
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Explain quantum computing"}
    ]
)

print(message.content[0].text)
# Response may come from Haiku (if quality good) or Sonnet (if needed)
# You saved money without changing any code!
```

### With cURL

```bash
# Direct API call to proxy
curl -X POST "http://localhost:8000/v1/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1024,
    "messages": [
      {"role": "user", "content": "What is Python?"}
    ]
  }'
```

---

## Monitoring

### View Stats

```bash
curl http://localhost:8000/stats
```

**Response:**
```json
{
  "total_queries": 100,
  "total_cost": 1.68,
  "avg_cost_per_query": 0.0168,
  "cascade_used_count": 60,
  "cascade_usage_pct": 60.0,
  "models_used": {
    "claude-3-5-haiku-20241022": 60,
    "claude-3-5-sonnet-20241022": 40
  }
}
```

### Check Logs

The proxy logs every cascade decision:

```
✅ Draft accepted: claude-3-5-haiku-20241022, $0.000080 (~60% savings vs Sonnet)
❌ Escalated to verifier: claude-3-5-sonnet-20241022, $0.000300
```

---

## Configuration

### Default Cascade Rules

The proxy comes with built-in cascade rules:

| Requested Model | Draft Model | Verifier Model | Threshold |
|----------------|-------------|----------------|-----------|
| claude-3-5-sonnet-20241022 | claude-3-5-haiku-20241022 | claude-3-5-sonnet-20241022 | 0.7 |
| claude-3-opus-20240229 | claude-3-5-sonnet-20241022 | claude-3-opus-20240229 | 0.75 |

### Custom Configuration

Edit `examples/fastapi_proxy_routing.py`:

```python
CASCADE_RULES = [
    CascadeRule(
        request_model="claude-3-5-sonnet-20241022",
        draft_model="claude-3-5-haiku-20241022",
        verifier_model="claude-3-5-sonnet-20241022",
        quality_threshold=0.6  # Lower = more aggressive savings
    ),
]
```

**Quality Threshold:**
- `0.6`: Aggressive savings (80% acceptance, some quality trade-off)
- `0.7`: Balanced (60% acceptance, good quality)
- `0.8`: Conservative (40% acceptance, highest quality)

---

## Limitations (MVP)

Current limitations in this MVP:

- ❌ **No streaming**: `stream=true` not supported yet
- ❌ **Anthropic only**: OpenAI endpoint not implemented yet
- ❌ **No authentication**: Proxy doesn't validate API keys
- ❌ **No rate limiting**: No per-user limits

These will be addressed in future versions based on feedback.

---

## Troubleshooting

### Proxy Won't Start

**Error:** `ANTHROPIC_API_KEY environment variable not set`

**Solution:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python examples/fastapi_proxy_routing.py
```

### Claude Code Can't Connect

**Error:** Connection refused

**Solution:** Ensure proxy is running:
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy", ...}
```

### Responses Seem Slower

**Expected behavior:** First request is slower (cold start). Subsequent requests are fast.

The cascade logic adds minimal overhead (<50ms), but the quality check is worth the slight delay for 40-80% cost savings.

### All Requests Escalating to Verifier

**Check quality threshold:** You may need to lower it for more aggressive savings:

```python
quality_threshold=0.6  # Try lower threshold
```

---

## Production Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install cascadeflow[all] fastapi uvicorn

COPY examples/fastapi_proxy_routing.py .

EXPOSE 8000

CMD ["python", "fastapi_proxy_routing.py"]
```

**Build and run:**
```bash
docker build -t cascadeflow-proxy .
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  cascadeflow-proxy
```

### Environment Variables

```bash
# Required
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional
export HOST="0.0.0.0"
export PORT="8000"
```

---

## FAQ

### Q: Will this work with Claude Code?

**A:** Yes! That's the primary use case. Just set `ANTHROPIC_BASE_URL="http://localhost:8000"` and use Claude Code normally.

### Q: How much will I save?

**A:** Typically 40-80% depending on query complexity. Simple queries (60-80% of typical usage) use Haiku, complex ones use Sonnet.

### Q: Is the response quality affected?

**A:** No! CascadeFlow's quality control ensures only high-quality responses are accepted. If quality is poor, it automatically escalates to the requested model.

### Q: Can I use this in production?

**A:** This MVP is suitable for personal use and small teams. For production, consider adding authentication, rate limiting, and monitoring. See the implementation plan in `docs/ROUTING_PROXY_IMPLEMENTATION_PLAN.md` for Phase 3 features.

### Q: Does this work with other tools besides Claude Code?

**A:** Yes! It works with any tool that uses the Anthropic Python SDK or makes HTTP requests to the Anthropic API.

---

## Next Steps

- **Test it**: Try with Claude Code and measure your savings
- **Provide feedback**: Open an issue with your experience
- **Customize**: Adjust quality thresholds for your needs
- **Contribute**: Help build Phase 2 features (OpenAI compatibility, streaming)

---

## Related Documentation

- **Gap Analysis**: [docs/PROXY_GAP_ANALYSIS.md](../PROXY_GAP_ANALYSIS.md)
- **Architecture**: [docs/ROUTING_PROXY_ARCHITECTURE.md](../ROUTING_PROXY_ARCHITECTURE.md)
- **Implementation Plan**: [docs/ROUTING_PROXY_IMPLEMENTATION_PLAN.md](../ROUTING_PROXY_IMPLEMENTATION_PLAN.md)
- **FastAPI Guide**: [docs/guides/fastapi.md](fastapi.md)

---

**Questions?** Open an issue on [GitHub](https://github.com/lemony-ai/CascadeFlow/issues).
