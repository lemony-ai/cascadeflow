# Gateway Server (Drop-In Integration)

This is the fastest way to try cascadeflow with an existing app or agent stack.

Run a local HTTP gateway and point your existing OpenAI or Anthropic client at it.
No framework changes, no SDK rewrite.

## What You Get

- OpenAI-compatible endpoint: `POST /v1/chat/completions`
- Anthropic-compatible endpoint: `POST /v1/messages`
- Health check: `GET /health`
- Metrics (best-effort): `GET /stats`
- Two modes:
  - **mock**: no API keys required, deterministic responses (validate wiring quickly)
  - **agent**: routes through a real `CascadeAgent` (uses your provider keys/config)

## 1) Start The Gateway

### Agent mode (real cascade)

```bash
python -m cascadeflow.server --mode agent --port 8084
```

If installed via pip, you can also use:

```bash
cascadeflow-gateway --mode agent --port 8084
```

Common options:
- `--preset balanced|cost_optimized|speed_optimized|quality_optimized|development`
- `--config /path/to/cascadeflow.yaml` (override models/channels via config file)
- `--no-stream` to disable streaming

### Mock mode (no keys needed)

```bash
python -m cascadeflow.server --mode mock --port 8084
```

## 2) Point Your Existing Client To The Gateway

### OpenAI SDK (Python)

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8084/v1", api_key="unused")
resp = client.chat.completions.create(
    model="cascadeflow",
    messages=[{"role": "user", "content": "Hello"}],
)
print(resp.choices[0].message.content)
```

### OpenAI SDK (Node)

```ts
import OpenAI from "openai";

const client = new OpenAI({ baseURL: "http://127.0.0.1:8084/v1", apiKey: "unused" });
const resp = await client.chat.completions.create({
  model: "cascadeflow",
  messages: [{ role: "user", content: "Hello" }],
});
console.log(resp.choices[0].message.content);
```

### Anthropic SDK

Point the Anthropic client at the gateway base URL, then call `messages.create` as usual.

## 3) Quick Validation Checklist

```bash
curl -s http://127.0.0.1:8084/health
curl -s http://127.0.0.1:8084/stats
```

And a smoke call:

```bash
curl -s http://127.0.0.1:8084/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"cascadeflow","messages":[{"role":"user","content":"hello"}]}' | jq .
```

