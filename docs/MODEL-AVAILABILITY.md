# Model Availability Guide

**Last Updated:** October 23, 2025

This guide lists currently available models for each provider. Models can be deprecated or require special access, so check this page if you encounter 404 or access errors.

---

## ✅ Tested & Working Models

These models have been validated with real API calls as of October 2025.

### OpenAI

**Production Models:**
- `gpt-4o-mini` - Cost: $0.00015/1K tokens
- `gpt-4o` - Cost: $0.0025/1K tokens
- `gpt-5` - Cost: $0.00125/1K tokens ⚠️ Requires organization verification

**Status:** ✅ All working (basic, streaming, tools)

**Documentation:** https://platform.openai.com/docs/models

**Special Notes:**
- GPT-5 requires [organization verification](https://platform.openai.com/settings/organization/general)
- GPT-5 does not support logprobs
- GPT-5 uses `max_completion_tokens` instead of `max_tokens`

---

### Anthropic (Claude)

**Current Models:**
- `claude-haiku-4-5-20251001` - Cost: ~$0.003/1K tokens (latest)
- `claude-sonnet-4-5-20250929` - Cost: ~$0.009/1K tokens (latest)
- `claude-opus-4-1-20250805` - Cost: ~$0.015/1K tokens (premium)

**Legacy Models (Still Available):**
- `claude-3-5-haiku-20241022` - Cost: ~$0.0008/1K tokens ✅ Working

**Status:** ✅ All working (basic, streaming, tools)

**Documentation:** https://docs.claude.com/en/docs/about-claude/models

**Special Notes:**
- Model naming changed from `claude-3-5-*` to `claude-*-4-5` format
- Legacy 3.5 models still work but may be deprecated
- Use aliases like `claude-sonnet-4-5` for latest version

---

### Groq

**Production Models:**
- `llama-3.1-8b-instant` - Cost: $0.00005/1K tokens ✅ Working
- `llama-3.3-70b-versatile` - Cost: $0.00069/1K tokens ✅ Working

**Deprecated Models:**
- ❌ `llama-3.1-70b-versatile` - Decommissioned, use `llama-3.3-70b-versatile`

**Preview Models:**
- `meta-llama/llama-4-maverick-17b-128e-instruct`
- `meta-llama/llama-4-scout-17b-16e-instruct`

**Status:** ✅ Production models working

**Documentation:** https://console.groq.com/docs/models

**Special Notes:**
- Llama 3.1 70b replaced by Llama 3.3 70b
- Llama 4 models in preview (may require special access)
- Groq offers fastest inference speeds

---

### Together AI

**Current Status:** ⚠️ Requires Setup

**Common Models:**
- `meta-llama/Llama-3-8b-chat-hf` - Requires dedicated endpoint
- `meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo` - Check for serverless access
- `mistralai/Mixtral-8x7B-Instruct-v0.1` - Check for serverless access

**Status:** ⚠️ Many models require dedicated endpoints

**Documentation:** https://docs.together.ai/docs/inference-models

**Special Notes:**
- Some models require creating a dedicated endpoint
- Check model page for serverless availability
- Together AI may have changed pricing/access model

**Setup Required:**
1. Visit model page: `https://api.together.ai/models/<model-name>`
2. Check if serverless is available
3. If not, create dedicated endpoint

---

### Ollama (Local)

**Popular Models:**
- `llama3.1:8b` - Local, free
- `llama3.1:70b` - Local, free (requires powerful GPU)
- `mixtral:8x7b` - Local, free
- `codellama:13b` - Local, free

**Status:** ✅ Working (requires local installation)

**Documentation:** https://ollama.com/library

**Setup:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.1:8b

# Run Ollama server
ollama serve
```

**Special Notes:**
- Requires local installation
- Models run on your hardware (GPU recommended)
- No API costs, but requires compute resources
- Default endpoint: `http://localhost:11434`

---

### HuggingFace

**Access Methods:**
1. **Inference API** (serverless)
2. **Inference Endpoints** (dedicated)
3. **Text Generation Inference** (self-hosted)

**Popular Models:**
- `meta-llama/Llama-3.1-8B-Instruct`
- `mistralai/Mixtral-8x7B-Instruct-v0.1`
- `google/gemma-7b`

**Status:** ✅ Working (requires API token)

**Documentation:** https://huggingface.co/docs/api-inference/

**Special Notes:**
- Inference API is rate-limited on free tier
- Inference Endpoints require setup and payment
- Some models require accepting license agreements

---

### vLLM (Self-Hosted)

**Status:** ✅ Working (requires local deployment)

**Supported Models:** Any model compatible with vLLM
- Llama family
- Mistral family
- Mixtral family
- Many others

**Documentation:** https://docs.vllm.ai/

**Setup:**
```bash
# Install vLLM
pip install vllm

# Start server
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --port 8000
```

**Special Notes:**
- Requires powerful GPU (NVIDIA recommended)
- Self-hosted solution (no API costs)
- OpenAI-compatible API
- Great for high-volume, cost-sensitive workloads

---

## Recommended Configurations

### Best Overall (Tested & Working)
```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 }
  ]
});
```
Status: ✅ Both tested (GPT-5 requires org verification)

### Ultra Cheap (Tested & Working)
```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'llama-3.1-8b-instant', provider: 'groq', cost: 0.00005 },
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 }
  ]
});
```
Status: ✅ Both tested and working

### OpenAI Only (Tested & Working)
```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-4o', provider: 'openai', cost: 0.0025 }
  ]
});
```
Status: ✅ Both tested and working

### Free/Local Only
```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'llama3.1:8b', provider: 'ollama', cost: 0 },
    { name: 'llama3.1:70b', provider: 'ollama', cost: 0 }
  ]
});
```
Status: ✅ Works with local Ollama installation

---

## Checking Model Availability

### Option 1: Test with Small Query
```typescript
import { CascadeAgent } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    { name: 'model-name-here', provider: 'provider-name', cost: 0.001 }
  ]
});

try {
  const result = await agent.run('Hi');
  console.log('✅ Model available:', result.content);
} catch (error) {
  console.error('❌ Model error:', error.message);
}
```

### Option 2: Check Provider Documentation
- **OpenAI:** https://platform.openai.com/docs/models
- **Anthropic:** https://docs.claude.com/en/docs/about-claude/models
- **Groq:** https://console.groq.com/docs/models
- **Together AI:** https://docs.together.ai/docs/inference-models
- **HuggingFace:** https://huggingface.co/models

---

## Common Errors & Solutions

### Error: 404 Model Not Found

**Example:**
```
404 {"type":"error","error":{"type":"not_found_error","message":"model: claude-3-5-sonnet-20241022"}}
```

**Solution:**
1. Check this guide for current model names
2. Visit provider documentation for latest models
3. Update your model name to current version

### Error: 400 Model Decommissioned

**Example:**
```
400 {"error":{"message":"The model `llama-3.1-70b-versatile` has been decommissioned"}}
```

**Solution:**
1. Check this guide for replacement models
2. Update to recommended replacement (e.g., `llama-3.3-70b-versatile`)

### Error: 400 Requires Dedicated Endpoint

**Example:**
```
400 {"error":{"message":"Unable to access non-serverless model...Please visit https://api.together.ai/models/... to create and start a new dedicated endpoint"}}
```

**Solution:**
1. Visit the provided URL to create dedicated endpoint
2. Or switch to a serverless-accessible model
3. Check Together AI documentation for current serverless models

### Error: 403 Organization Verification Required

**Example:**
```
403 {"error":{"message":"Your organization must be verified to use this model"}}
```

**Solution:**
1. Visit https://platform.openai.com/settings/organization/general
2. Click "Verify Organization"
3. Wait ~15 minutes for verification to propagate
4. See [GPT-5 Setup Guide](./GPT-5-SETUP.md) for details

---

## Model Deprecation Policy

**Providers may deprecate models with little notice.** When encountering errors:

1. ✅ Check this guide first (updated monthly)
2. ✅ Check provider documentation
3. ✅ Test with error message URL if provided
4. ✅ Update your code to use current models

**CascadeFlow handles model errors gracefully:**
- Clear error messages with model name
- Provider response included in error
- Cascade continues to next tier if available

---

## Contributing Updates

Found a deprecated model or new model? Help keep this guide current:

1. Test the model with real API call
2. Document the change
3. Submit PR or open issue

**Last Validation:** October 23, 2025
**Next Validation:** November 23, 2025

---

## Quick Reference

| Provider | Cheapest Model | Best Quality | Speed |
|----------|---------------|--------------|-------|
| OpenAI | gpt-4o-mini ($0.00015) | gpt-4o ($0.0025) | Fast |
| Anthropic | claude-3-5-haiku ($0.0008) | claude-opus-4-1 ($0.015) | Fast |
| Groq | llama-3.1-8b-instant ($0.00005) | llama-3.3-70b ($0.00069) | Fastest |
| Ollama | llama3.1:8b (Free) | llama3.1:70b (Free) | Local |
| Together | Check docs | Check docs | Fast |
| HuggingFace | Free tier | Depends on model | Variable |
| vLLM | Free (self-hosted) | Depends on model | Fast |

**Recommendation:** Start with Groq (cheapest, fastest) + OpenAI (reliable) for best cost/performance balance.
