---
name: cascadeflow
description: OpenClaw-native domain cascading. Use when users need cost/latency reduction via cascading, domain-aware model assignment, OpenClaw-native event handling, and command setup including /model cflow and optional /cascade stats commands.
---

# CascadeFlow: Cost + Latency Reduction | 17+ Domain-Aware Models + OpenClaw-Native Events

Use CascadeFlow as an OpenClaw provider to lower cost and latency via cascading. Assign up to 17 domain-specific models (for coding, web search, reasoning, and more), including OpenClaw-native event handling, and cascade between them (small model first, verifier when needed). Keep setup minimal, then verify with one health check and one chat call.

## Why Use It

- Reduce spend with drafter/verifier cascading.
- Run 17+ domain-aware model assignments (code, reasoning, web-search, and more).
- Support cascading with streaming and multi-step agent loops.
- Handle OpenClaw-native event/domain signals for smarter model selection.

## Security Defaults

- Install from PyPI and verify package artifact before first run.
- Keep the server bound to localhost by default.
- Use explicit auth tokens for chat and stats endpoints (recommended for production).
- Expose remote access only behind TLS/reverse proxy with strong tokens.
- Use least-privilege provider keys (separate test keys from production keys).

## How It Works

1. OpenClaw sends requests to CascadeFlow through OpenAI-compatible `/v1/chat/completions`.
2. CascadeFlow reads prompt context plus OpenClaw-native event/domain metadata (for example `metadata.method`, `metadata.event`, and channel/category hints).
3. CascadeFlow selects a domain-aware drafter/verifier pair (small model first).
4. If quality passes threshold, drafter answer is returned (cost/latency advantage).
5. If quality fails threshold, verifier runs and final answer is upgraded.
6. The same cascading behavior is supported for streaming and multi-step agent loops.

### Advantages

- Lower average cost by avoiding verifier calls when not needed.
- Lower average latency for simple and medium tasks.
- Better quality on hard tasks through verifier fallback.
- Better operational handling through OpenClaw-native event/domain understanding.

## Quick Start

Or ask your OpenClaw agent to set it up for you as an OpenClaw custom provider with OpenClaw-native events and domain understanding.

1. Install and verify package source:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade "cascadeflow[openclaw]>=0.7,<0.8"
python -m pip show cascadeflow
python -m pip download --no-deps "cascadeflow[openclaw]>=0.7,<0.8" -d /tmp/cascadeflow_pkg
python -m pip hash /tmp/cascadeflow_pkg/cascadeflow-*.whl
```

Optional variants:
```bash
python -m pip install --upgrade "cascadeflow[openclaw,anthropic]>=0.7,<0.8"   # Anthropic-only preset
python -m pip install --upgrade "cascadeflow[openclaw,openai]>=0.7,<0.8"      # OpenAI-only preset
python -m pip install --upgrade "cascadeflow[openclaw,providers]>=0.7,<0.8"   # Mixed preset
```

2. Pick preset + credentials:
- Presets: `examples/configs/anthropic-only.yaml`, `examples/configs/openai-only.yaml`, `examples/configs/mixed-anthropic-openai.yaml`
- Provider key(s): `ANTHROPIC_API_KEY=...` and/or `OPENAI_API_KEY=...` (required based on selected preset)
- Service tokens: `--auth-token ...` and `--stats-auth-token ...` (recommended for production; use long random values)

3. Start server (safe local default):
```bash
set -a; source .env; set +a
python3 -m cascadeflow.integrations.openclaw.openai_server \
  --host 127.0.0.1 --port 8084 \
  --config examples/configs/anthropic-only.yaml \
  --auth-token local-openclaw-token \
  --stats-auth-token local-stats-token
```

4. Configure OpenClaw provider:
- `baseUrl`: `http://<cascadeflow-host>:8084/v1` (local default: `http://127.0.0.1:8084/v1`)
- If remote: `http://<server-ip>:8084/v1` or `https://<domain>/v1` (TLS/reverse proxy)
- `api`: `openai-completions`
- `model`: `cascadeflow`
- `apiKey`: same value as your `--auth-token`

## Commands

- `/model cflow`: default OpenClaw model switch using alias `cflow`.
- `/cascade`: optional custom command (if configured in OpenClaw).
- `/cascade savings`: optional custom subcommand for cost stats.
- `/cascade health`: optional custom subcommand for service status.

## Links

- Full setup + configs: `references/clawhub_publish_pack.md`
- Listing strategy: `references/market_positioning.md`
- Official docs: `https://github.com/lemony-ai/cascadeflow/blob/main/docs/guides/openclaw_provider.md`
- GitHub repository: `https://github.com/lemony-ai/cascadeflow`
