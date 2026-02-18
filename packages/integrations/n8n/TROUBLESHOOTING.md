# n8n Integration Troubleshooting

## Which node should I use?

| Node | Use when... |
|------|------------|
| **CascadeFlow (Model)** | You want a drop-in Language Model for Chain/LLM nodes |
| **CascadeFlow Agent** | You need tool calling, memory, or a standalone agent workflow |

---

## Issue: Seeing old model names in logs after reconnecting

### Root Cause
n8n caches the node instance. When you disconnect/reconnect models, the old `CascadeChatModel` instance may still have references to previous models.

### Solution
1. **Stop the workflow** in n8n
2. **Restart the workflow** (or restart n8n if that doesn't work)
3. **Look for initialization log** confirming the correct models are loaded

---

## Issue: "Only drafts getting accepted"

### Is this a problem?
**NO - This is correct behavior!**

With the default complexity thresholds enabled:
- If drafter produces good responses → Quality check passes → Use cheap model (SAVE MONEY)
- If drafter produces poor responses → Quality check fails → Escalate to verifier

### When to adjust threshold

**See 100% drafter acceptance?**
- Your drafter is doing well for these queries
- Consider raising thresholds if you want stricter quality

**See 100% verifier escalation?**
- Drafter quality too low for these queries
- Lower thresholds to accept more drafts
- Or use a better drafter model

### Testing Verifier Triggering

To force verifier usage, try:
1. Set quality threshold to 0.90 (very strict)
2. Ask complex questions that drafter struggles with
3. Use a weaker drafter model

---

## Issue: Not seeing cascade logs

### CascadeFlow (Model)
Logs appear in the **downstream Chain node's Logs tab**, not the cascadeflow node itself:
1. Execute your workflow
2. Click on the **Chain node** (Basic LLM Chain, Chain, etc.)
3. Navigate to the **Logs** tab

### CascadeFlow Agent
Cascade metadata and trace are in the **Agent node's Output tab**:
1. Execute your workflow
2. Click on the **CascadeFlow Agent** node
3. Check the **Output** tab — the JSON includes `output`, `model_used`, `confidence`, and `trace`

---

## Issue: Domain cascading not triggering

1. Verify **Enable Domain Cascading** is turned on in the node settings
2. Make sure you've **enabled the specific domain toggle** (e.g., Enable Code Domain)
3. Connect a domain-specific model to the new input port that appears
4. Note: general queries (e.g., "What's the weather?") classify as `general` — enable the General domain toggle if you want those routed to a domain model
5. Code/math/data queries should route correctly (e.g., "Write a JavaScript function" → code domain)

---

## Issue: "This node cannot be connected"

- **CascadeFlow (Model)** outputs `ai_languageModel` — connect to Chain/LLM nodes
- **CascadeFlow Agent** has `main` in/out — connect to any workflow node (Chat Trigger, Respond to Webhook, etc.)

Do not try to connect the Agent node to a Language Model input or vice versa.

---

## Issue: Always escalating to verifier

### Debug steps
1. Check the Logs tab (Model) or Output tab (Agent) for confidence scores
2. If scores are just below threshold, lower it slightly (e.g., 0.55 → 0.45)
3. Verify your drafter model is appropriate (not too weak)
4. Try a better drafter model (e.g., gpt-4o-mini instead of gpt-3.5-turbo)

---

## Issue: Drafter connection always shows green in UI (Model node)

**This is expected behavior.** Due to n8n's rendering, the first sub-node connection is always highlighted. This does not affect functionality. Check the **Logs tab** to see which model was actually used.

---

## Checking Model Connections

**Per-request logs (Model node):**
- Show in the downstream Chain node's Logs tab
- Display which path was taken (drafter accepted vs. verifier escalated)
- Include confidence scores and latency

**Per-request output (Agent node):**
- Show in the Agent node's Output tab
- Include `model_used`, `confidence`, `domain`, and step-by-step `trace`

---

## Common Mistakes

**Connecting models to wrong ports**
- Verifier = powerful, expensive model
- Drafter = cheap, fast model (tried first)

**Not restarting workflow after changing connections**
- Must restart for new models to be loaded

**Expecting verifier to be called every time**
- Verifier is ONLY called when drafter quality < threshold
- This is the cost-saving feature!

**Using CascadeFlow Agent where CascadeFlow (Model) is needed**
- If you're plugging into a Basic LLM Chain, use the Model node
- If you want standalone agent with tools/memory, use the Agent node
