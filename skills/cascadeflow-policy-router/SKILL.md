---
name: "Cascadeflow Policy Router"
description: "Route OpenClaw requests through Cascadeflow with fast drafter + verifier, optional failover, and opt-in domain routing."
homepage: "https://github.com/lemony-ai/cascadeflow"
metadata: '{"tags":["routing","openclaw","cascadeflow","cost-optimization","latency"],"source":"cascadeflow","openclaw":{"homepage":"https://github.com/lemony-ai/cascadeflow"}}'
---

# Cascadeflow OpenClaw Router (Fast Start)

This skill tags OpenClaw requests so the Cascadeflow gateway can apply
fast drafter + verifier routing, with optional failover and optional
domain-aware routing. It is designed to be low-latency and easy to adopt.

## Fast Start (1 minute)
1) Configure Cascadeflow with:
   - drafter model (fast/cheap)
   - verifier model (your current best model)
2) Use this skill. It works immediately without any extra routing config.

## Channel Model Setup (Cascadeflow-side)
Define the core channels in your Cascadeflow OpenClaw config:

- `drafter`: required (fast/cheap model)
- `verifier`: required (quality model)
- `failover`: optional (backup provider/model)
  - If not set: fallback = drafter, then verifier

Optional OpenClaw-native channels (opt-in, explicitly tagged in this skill; classifier can also map when enabled):
- `heartbeat` (system/heartbeat flows)
- `cron` (scheduled jobs / cron events)
- `voice` (tts/voicewake)
- `image_understanding` (image attachments)
- `web_search` (web_search/web_fetch when user enables)
- `brain`, `coding`, `content` (OpenClaw categories)

Optional Cascadeflow domains (opt-in, auto-detected by Cascadeflow):
- `code`
- `data`
- `structured`
- `rag`
- `conversation`
- `tool`
- `creative`
- `summary`
- `translation`
- `math`
- `medical`
- `legal`
- `financial`
- `multimodal`
- `general`

Note:
- OpenClaw categories can map to Cascadeflow domains if you want:
  - `coding` -> `code`
  - `image_understanding` -> `multimodal`
  - `brain` -> `general`
- Cascadeflow domains are handled by Cascadeflow's automatic domain routing.
- Explicit tags are optional and only needed if you want to force a specific domain.
 - Suggested routing: OpenClaw-native via explicit tags (or classifier), Cascadeflow domains via auto-detection.

Example:
```yaml
openclaw:
  channels:
    drafter: "claude-3-5-haiku-20241022"
    verifier: "claude-3-5-sonnet-20241022"
    failover: "gpt-4o-mini"   # optional

    # Optional OpenClaw-native channels
    heartbeat:
      models: "claude-3-5-haiku-20241022"
      strategy: direct_cheap
    cron:
      models: "claude-3-5-haiku-20241022"
      strategy: direct_cheap
    voice:
      models: "gpt-4o-realtime"
      strategy: direct_best
    image_understanding: "gpt-4o"
    web_search: "claude-3-5-haiku-20241022"
    brain: "claude-3-5-sonnet-20241022"
    coding: "claude-3-5-opus-20240229"
    content: "claude-3-5-sonnet-20241022"

    # Optional Cascadeflow domains (explicit tags optional)
    code: "claude-3-5-opus-20240229"
    data: "gpt-4o"
    structured: "gpt-4o-mini"
    rag: "gpt-4o"
    conversation: "claude-3-5-sonnet-20241022"
    tool: "claude-3-5-sonnet-20241022"
    creative: "claude-3-5-sonnet-20241022"
    summary: "claude-3-5-haiku-20241022"
    translation: "claude-3-5-haiku-20241022"
    math: "deepseek-r1"
    medical: "claude-3-5-opus-20240229"
    legal: "claude-3-5-opus-20240229"
    financial: "gpt-4o"
    multimodal: "gpt-4o"
    general: "claude-3-5-sonnet-20241022"
```

## Domain Routing Notes
- OpenClaw-native categories are routed in two ways:
  1) Explicit tags from this skill (deterministic, recommended).
  2) OpenClaw pre-router classifier (method/payload hints only, opt-in).
- Cascadeflow domains are auto-detected by Cascadeflow logic.
- If no tag/classifier match, Cascadeflow handles the request dynamically.
- Suggested routing: OpenClaw-native via explicit tags; Cascadeflow domains via auto-detection.
 - Heartbeat/cron channels default to direct cheap when a channel model is configured.

## Metrics & Stats (OpenClaw-side)
Cascadeflow exposes runtime metrics at `GET /stats` on the OpenAI server.
Use this to validate savings, acceptance rate, tool usage, and latency.

Suggested commands:
- `/cascade stats` → summarize cost savings + acceptance rate
- `/cascade domains` → per-domain performance
- `/cascade latency` → overhead analysis
- `/cascade savings` → cost comparison vs verifier-only baseline

Example:
```
curl http://127.0.0.1:8084/stats | jq .
```

Savings fields (from `/stats.summary`):
- `total_cost`: actual spend
- `baseline_cost`: verifier-only baseline (actual + saved)
- `total_saved`: baseline - actual
- `savings_percent`: savings / baseline
- `draft_tokens`, `verifier_tokens`, `total_tokens` (if providers report tokens)

Example output (formatted in the skill):
```
📊 CascadeFlow Savings Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Queries: 1,247
Draft Acceptance: 64%

💰 Cost Comparison:
  Verifier-only: $18.72
  With Cascade:  $6.54
  ━━━━━━━━━━━━━━━━
  Savings:       $12.18 (65%)
```

## Tagging Rules (What this skill sends)
This skill adds explicit routing hints only when the domain is predictable.

- Use `cascadeflow_category` for explicit domain routing.
- Optionally use `cascadeflow_profile`:
  - `best`
  - `cost_savings`
- Optionally set `cascadeflow_model` to force a model.

Example (explicit domain routing):
```json
{
  "cascadeflow": {
    "category": "web_search",
    "profile": "cost_savings"
  }
}
```

## Fallback Behavior (Preferred-if-Available)
1) If category mapping exists and model is available -> use it
2) Else use failover if set
3) Else fallback to drafter, then verifier

## When NOT to Tag
If the domain is dynamic or unclear, do not tag.
Cascadeflow will handle it with domain-aware routing and cascading.

## Safety Note
Skills run as executable logic. Review third-party skills before use.
