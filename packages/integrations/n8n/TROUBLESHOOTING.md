# n8n Integration Troubleshooting

## Issue: Seeing old model names in logs after reconnecting

### Root Cause
n8n caches the node instance. When you disconnect/reconnect models, the old `CascadeChatModel` instance may still have references to previous models.

### Solution
1. **Stop the workflow** in n8n
2. **Restart the workflow** (or restart n8n if that doesn't work)
3. **Look for initialization log**:
   ```
   🚀 CascadeFlow initialized
      PORT MAPPING:
      ├─ TOP port (labeled "Verifier") → VERIFIER model: lazy-loaded (will fetch only if needed)
      └─ BOTTOM port (labeled "Drafter") → DRAFTER model: [type] ([name])
   ```

   This shows which models are ACTUALLY connected.

### Verifying Correct Operation

**Expected logs when drafter is accepted:**
```
🎯 CascadeFlow: Trying drafter model (from BOTTOM port): ollama (gemma3:1b)
   📊 Simple quality check: confidence=0.75

┌─────────────────────────────────────────┐
│  ✅ FLOW: DRAFTER ACCEPTED (FAST PATH) │
└─────────────────────────────────────────┘
   Model used: ollama (gemma3:1b)
   Confidence: 0.75 (threshold: 0.64)
```

**Expected logs when verifier is triggered:**
```
🎯 CascadeFlow: Trying drafter model (from BOTTOM port): ollama (gemma3:1b)
   📊 Simple quality check: confidence=0.50

┌────────────────────────────────────────────────┐
│  ⚠️  FLOW: ESCALATED TO VERIFIER (SLOW PATH)  │
└────────────────────────────────────────────────┘
   🔄 Loading verifier model from TOP port (labeled "Verifier")...
   ✓ Verifier model loaded: ollama (mistral:7b-instruct)
   ✅ Verifier completed successfully
   Model used: ollama (mistral:7b-instruct)
```

## Issue: "Only drafts getting accepted"

### Is this a problem?
**NO - This is correct behavior!**

With quality threshold 0.64:
- If drafter produces good responses → Quality check passes → Use cheap model (SAVE MONEY ✅)
- If drafter produces poor responses → Quality check fails → Escalate to verifier

### When to adjust threshold

**See 100% drafter acceptance?**
- Your drafter is doing well for these queries
- Consider lowering threshold to 0.50-0.55 if you want stricter quality

**See 100% verifier escalation?**
- Drafter quality too low for these queries
- Increase threshold to 0.70-0.80 to accept more drafts
- Or use a better drafter model

### Testing Verifier Triggering

To force verifier usage, try:
1. Lower quality threshold to 0.90 (very strict)
2. Ask complex questions that drafter struggles with
3. Use a weaker drafter model

## Checking Model Connections

**Initialization log location:**
- n8n workflow logs (when workflow starts)
- Server console logs (if running n8n manually)

**Per-request logs:**
- Show in n8n execution logs
- Show actual model used: `Model used: [type] ([name])`

## Common Mistakes

❌ **Connecting models to wrong ports**
- TOP port = Verifier (expensive, high quality)
- BOTTOM port = Drafter (cheap, tried first)

❌ **Not restarting workflow after changing connections**
- Must restart for new models to be loaded

❌ **Expecting verifier to be called every time**
- Verifier is ONLY called when drafter quality < threshold
- This is the cost-saving feature!
