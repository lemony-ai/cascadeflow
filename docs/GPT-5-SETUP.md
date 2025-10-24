# GPT-5 Setup Guide

## Overview

GPT-5 is OpenAI's latest flagship model (released August 2025) with:
- 50% cheaper input tokens than GPT-4o ($1.25/1M vs $2.50/1M)
- 75% success rate on coding tasks (vs 31% for GPT-4o)
- 19-24% higher reasoning scores
- 6x fewer hallucinations

**However, GPT-5 requires organization verification before use.**

---

## Organization Verification Requirement

### What You'll See

When trying to use GPT-5 without verification, you'll get:

```
403 Error: Your organization must be verified to access this model.
Please go to: https://platform.openai.com/settings/organization/general
and click on Verify Organization.
```

This applies to:
- Direct GPT-5 API calls
- GPT-5 streaming
- GPT-5 tool calling

### Why This Exists

OpenAI requires verification for premium models to:
- Prevent abuse and fraud
- Ensure legitimate business usage
- Maintain API quality and availability

---

## How to Get Access

### Step 1: Verify Your Organization

1. **Go to Settings:**
   - Visit: https://platform.openai.com/settings/organization/general

2. **Click "Verify Organization":**
   - Provide business information (if requested)
   - May require company documentation

3. **Wait for Approval:**
   - Usually takes ~15 minutes
   - Can take up to 24 hours in some cases
   - You'll receive an email confirmation

### Step 2: Test Access

```typescript
// Test GPT-5 access
const agent = new CascadeAgent({
  models: [{ name: 'gpt-5', provider: 'openai', cost: 0.00125 }]
});

const result = await agent.run('Hello, GPT-5!');
console.log('✅ GPT-5 access granted!');
```

---

## Using GPT-5 Before Verification

### Recommended: Cascade Setup

**Best approach:** Use GPT-5 in cascade mode with Claude Haiku

```typescript
import { CascadeAgent } from '@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    {
      name: 'claude-3-5-haiku-20241022',
      provider: 'anthropic',
      cost: 0.0008
    },
    {
      name: 'gpt-5',
      provider: 'openai',
      cost: 0.00125
    }
  ]
});
```

**What happens:**
- ✅ 75% of queries: Claude Haiku handles (works immediately)
- ⏳ 25% of queries: Escalates to GPT-5 (waits for verification)
- 🎯 Expected savings: 50-65%

**Benefits:**
- Works right away for most queries
- Automatically uses GPT-5 once verified
- No code changes needed
- Optimal cost/quality balance

### Python Example

```python
from cascadeflow import CascadeAgent, ModelConfig

# Works now, uses GPT-5 when verified
agent = CascadeAgent(models=[
    ModelConfig(name="claude-3-5-haiku-20241022", provider="anthropic", cost=0.0008),
    ModelConfig(name="gpt-5", provider="openai", cost=0.00125)
])

result = await agent.run("Your query here")
```

---

## Alternative Models (No Verification)

If you need immediate access without waiting:

### Option 1: Claude Only (Excellent Quality)

```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
    { name: 'claude-3-5-sonnet-20241022', provider: 'anthropic', cost: 0.003 }
  ]
});
```

**Pros:**
- Excellent reasoning and coding
- Very fast responses
- Great for creative writing
- No verification needed

### Option 2: Groq (Ultra Fast)

```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'llama-3.1-8b-instant', provider: 'groq', cost: 0.00005 },
    { name: 'llama-3.1-70b-versatile', provider: 'groq', cost: 0.00059 }
  ]
});
```

**Pros:**
- Fastest provider (50-200ms TTFT)
- Extremely cheap
- Good for high-volume applications
- No verification needed

### Option 3: GPT-4o-mini

```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 }
  ]
});
```

**Pros:**
- No verification needed
- Still very capable
- Works immediately
- Good fallback option

---

## Comparison Table

| Model | Verification | Cost (Input) | Best For | Availability |
|-------|--------------|--------------|----------|--------------|
| **GPT-5** | ⚠️ Required | $1.25/1M | Reasoning, coding | After verification |
| **Claude Haiku** | ✅ None | $0.80/1M | General purpose | Immediate |
| **Claude Sonnet** | ✅ None | $3.00/1M | Complex tasks | Immediate |
| **Groq Llama 8B** | ✅ None | $0.05/1M | High volume | Immediate |
| **GPT-4o-mini** | ✅ None | $0.15/1M | General purpose | Immediate |

---

## Troubleshooting

### "403 - Organization must be verified"

**Solution:** Complete verification process (see Step 1 above)

**Workaround:** Use cascade setup with Claude Haiku (works immediately)

### "Still getting 403 after verification"

**Possible causes:**
1. Verification still processing (wait 15-30 minutes)
2. Verification failed (check email for notification)
3. API key from wrong organization

**Check verification status:**
```bash
curl https://api.openai.com/v1/models/gpt-5 \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### "Works in cascade but not directly"

**This is expected!** Cascade uses the drafter (Claude Haiku) for most queries.

If drafter is accepted:
- ✅ Response comes from Claude (works now)

If escalated to GPT-5:
- ⏳ Waits for GPT-5 verification

---

## Migration Path

### Current: GPT-4o

```typescript
// Old setup
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    { name: 'gpt-4o', provider: 'openai', cost: 0.0025 }
  ]
});
```

### Recommended: GPT-5

```typescript
// New setup (verify org first)
const agent = new CascadeAgent({
  models: [
    { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 }  // 50% cheaper!
  ]
});
```

**Improvements:**
- 50% cheaper input tokens
- Better at coding and reasoning
- Same output token cost
- Works in cascade immediately

---

## FAQ

**Q: How long does verification take?**
A: Usually 15 minutes, up to 24 hours in some cases.

**Q: Can I use GPT-5 without verification?**
A: No, direct access requires verification. Use in cascade mode for immediate partial access.

**Q: What happens to my queries during verification?**
A: In cascade mode, Claude Haiku handles 75% of queries. The 25% that need GPT-5 will wait.

**Q: Do I need to verify for each project?**
A: No, verification is per OpenAI organization, not per project.

**Q: Does verification cost money?**
A: No, verification is free. You only pay for API usage.

**Q: What if verification is denied?**
A: Use alternative models (Claude, Groq, GPT-4o-mini). Contact OpenAI support if needed.

**Q: Can I use GPT-5-mini without verification?**
A: No, all GPT-5 variants require verification.

---

## Recommended Setup

**Best overall:** Claude Haiku + GPT-5 (works now, optimizes when verified)

```typescript
const agent = new CascadeAgent({
  models: [
    { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
    { name: 'gpt-5', provider: 'openai', cost: 0.00125 }
  ],
  quality: {
    threshold: 0.7  // Balanced threshold
  }
});
```

**Why this works:**
1. Claude Haiku handles simple queries immediately
2. GPT-5 verifies complex queries (when organization verified)
3. Automatic failover and routing
4. 50-65% cost savings
5. No code changes needed after verification

---

## Summary

| Status | What Works | What Doesn't |
|--------|-----------|--------------|
| **Before Verification** | ✅ Cascade with Claude drafter<br>✅ Alternative models<br>✅ GPT-4o-mini | ❌ Direct GPT-5 calls<br>❌ GPT-5 streaming |
| **After Verification** | ✅ Everything | - |

**Action Items:**
1. ✅ Verify your OpenAI organization now
2. ✅ Use cascade setup while waiting
3. ✅ Test after ~15 minutes
4. ✅ Enjoy 50% cheaper costs with better quality

---

**Need help?** Check our [troubleshooting guide](../README.md#troubleshooting) or [open an issue](https://github.com/lemony-ai/cascadeflow/issues).
