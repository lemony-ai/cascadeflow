# OpenClaw Custom Provider (Cascadeflow)

This guide shows how to expose Cascadeflow as an OpenAI-compatible provider
so OpenClaw can route its model calls through Cascadeflow without any
OpenClaw code changes.

## 1) Start the Cascadeflow OpenAI server

```bash
python -m cascadeflow.integrations.openclaw.openai_server --port 8084
```

Common options:
- `--preset balanced|cost_optimized|speed_optimized|quality_optimized|development`
- `--config /path/to/cascadeflow.yaml` (override models + channels via config file)
- `--no-classifier` to disable the OpenClaw pre-router classifier
- `--no-stream` to disable streaming responses

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
