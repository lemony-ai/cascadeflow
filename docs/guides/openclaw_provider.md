# OpenClaw Custom Provider (Cascadeflow)

This guide shows how to expose Cascadeflow as an OpenAI-compatible provider
so OpenClaw can route its model calls through Cascadeflow without any
OpenClaw code changes.

## 1) Start the Cascadeflow OpenAI server

```bash
python -m cascadeflow.server --mode agent --port 8084
```

Common options:
- `--preset balanced|cost_optimized|speed_optimized|quality_optimized|development`
- `--config /path/to/cascadeflow.yaml` (override models + channels via config file)
- `--no-classifier` to disable the OpenClaw pre-router classifier
- `--no-stream` to disable streaming responses

Compatibility:
```bash
# Legacy entrypoint (still supported)
python -m cascadeflow.integrations.openclaw.openai_server --port 8084
```

## 2) Configure OpenClaw custom provider

Example config (use your own API key if required):

```json
{
  "models": {
    "providers": {
      "cascadeflow": {
        "baseUrl": "http://localhost:8084/v1",
        "apiKey": "unused",
        "api": "openai-completions",
        "models": [
          {
            "id": "cascadeflow-auto",
            "name": "Cascadeflow (Auto)",
            "contextWindow": 200000,
            "maxTokens": 8192,
            "reasoning": false,
            "input": ["text"],
            "cost": {
              "input": 0,
              "output": 0,
              "cacheRead": 0,
              "cacheWrite": 0
            }
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "models": {
        "cascadeflow/cascadeflow-auto": {
          "alias": "cf-auto"
        }
      }
    }
  }
}
```

## 3) Optional profile routing

Use virtual model ids to force routing strategy:
- `cascadeflow-quality` -> direct verifier
- `cascadeflow-cost`, `cascadeflow-cheap`, `cascadeflow-fast` -> cascade

These map to `kpi_flags.profile` inside Cascadeflow.

## 4) Optional explicit tags

If you use the OpenClaw skill to add explicit tags, the server will honor
`payload.cascadeflow` or `payload.metadata.kpi_flags` for routing hints.

## 5) Optional tenant + channel routing

You can pass `metadata.tenant_id` and `metadata.channel` in OpenClaw requests
to activate per-tenant rules and channel failover routing in Cascadeflow.

## 6) Optional OpenClaw-native channels (heartbeat/cron)

To route trivial system events to a smaller model, define channels in a
Cascadeflow config and start the server with `--config`:

```yaml
models:
  - name: gpt-4o-mini
    provider: openai
    cost: 0.00015
  - name: gpt-4o
    provider: openai
    cost: 0.0025

channels:
  heartbeat:
    models: gpt-4o-mini
    strategy: direct_cheap
  cron:
    models: gpt-4o-mini
    strategy: direct_cheap
```

When OpenClaw sends `metadata.method`/`metadata.event` (or explicit tags),
Cascadeflow will map categories to channels and use these smaller models.
Heartbeat/cron default to direct cheap if a channel model is configured,
and you can override per-channel strategy via the `strategy` field.

## Tested Model Setups (Cascadeflow configs)
These example configs were validated in OpenClaw E2E tests. Replace model IDs
with the exact names for your providers.

### 1) Anthropic-only
| Role      | Model               | Use Case            |
| --------- | ------------------- | ------------------- |
| Verifier  | Opus 4.5            | Quality baseline    |
| Drafter   | Haiku 4.5           | Default fast        |
| Code      | Sonnet 4            | More capability     |
| Reasoning | Sonnet 4.5          | Complex logic       |
| Creative  | Sonnet 4            | Balanced creativity |
| Heartbeat | Haiku 4 -> Haiku 4.5 | Ultra cheap         |

```yaml
openclaw:
  channels:
    drafter: "claude-haiku-4-5"
    verifier: "claude-opus-4-5"
    code: "claude-sonnet-4"
    reasoning: "claude-sonnet-4-5"
    creative: "claude-sonnet-4"
    heartbeat: "claude-haiku-4-5"
```

### 2) OpenAI-only
| Role      | Model       | Use Case            |
| --------- | ----------- | ------------------- |
| Verifier  | GPT-5.2     | Quality baseline    |
| Drafter   | GPT-5 mini  | Default fast        |
| Code      | GPT-5       | Strong at code      |
| Reasoning | o3-mini     | Excellent reasoning |
| Heartbeat | nano -> mini | Ultra cheap         |
| Cron      | nano -> mini | Cost efficient      |

```yaml
openclaw:
  channels:
    drafter: "gpt-5-mini"
    verifier: "gpt-5.2"
    code: "gpt-5"
    reasoning: "o3-mini"
    heartbeat: "gpt-5-nano"
    cron: "gpt-5-nano"
```

### 3) Mixed (Best of Both)
| Domain       | Drafter    | Verifier   | Why                    |
| ------------ | ---------- | ---------- | ---------------------- |
| Default      | GPT-5 mini | Opus 4.5   | Speed + quality        |
| Code         | GPT-5      | GPT-5.2    | OpenAI excels          |
| Reasoning    | o3-mini    | Opus 4.5   | o3 + Opus verification |
| Creative     | Sonnet 4   | Opus 4.5   | Anthropic voice        |
| Conversation | Haiku 4.5  | Sonnet 4.5 | Natural feel           |
| Tools        | GPT-5 mini | GPT-5      | OpenAI tool support    |
| Heartbeat    | nano       | mini       | Cheapest               |

```yaml
openclaw:
  channels:
    drafter: "gpt-5-mini"
    verifier: "claude-opus-4-5"
    code:
      models: ["gpt-5", "gpt-5.2"]
    reasoning:
      models: ["o3-mini", "claude-opus-4-5"]
    creative:
      models: ["claude-sonnet-4", "claude-opus-4-5"]
    conversation:
      models: ["claude-haiku-4-5", "claude-sonnet-4-5"]
    tools:
      models: ["gpt-5-mini", "gpt-5"]
    heartbeat: "gpt-5-nano"
```

## Notes
- This server is transport-agnostic; OpenClaw only needs to call the OpenAI
  endpoint configured above.
- For production, you can front the server with a reverse proxy and auth.

## Optional Stats Endpoint
Cascadeflow exposes runtime metrics at `GET /stats` on the OpenAI server.
Use this to view savings, acceptance rate, tool usage, and latency.

Example:
```
curl http://127.0.0.1:8084/stats | jq .
```

Savings fields live under `/stats.summary`:
- `total_cost`, `baseline_cost`, `total_saved`, `savings_percent`
- `draft_tokens`, `verifier_tokens`, `total_tokens` (if providers report tokens)
