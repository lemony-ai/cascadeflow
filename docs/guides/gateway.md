# Gateway Server (Drop-In Integration)

This is the fastest way to try cascadeflow with an existing app or agent stack.

Run a local HTTP gateway and point your existing OpenAI or Anthropic client at it.
No framework changes, no SDK rewrite.

## What You Get

- OpenAI-compatible endpoint: `POST /v1/chat/completions`
- OpenAI-compatible endpoint: `POST /v1/embeddings`
- OpenAI-compatible endpoint: `POST /v1/completions` (legacy)
- OpenAI-compatible endpoint: `GET /v1/models`
- Anthropic-compatible endpoint: `POST /v1/messages`
- Health check: `GET /health`
- Metrics (best-effort): `GET /stats`
- Two modes:
  - **mock**: no API keys required, deterministic responses (validate wiring quickly)
  - **agent**: routes through a real `CascadeAgent` (uses your provider keys/config)

Notes:
- The `/v1` prefix is optional. If your SDK can't set `base_url` to include `/v1`, you can use `http://127.0.0.1:8084` and the gateway will accept both `/chat/completions` and `/v1/chat/completions` (same for other endpoints).
- `/v1/embeddings` is implemented locally for fast integration tests. If `fastembed` is installed, it uses `UnifiedEmbeddingService`; otherwise it falls back to deterministic embeddings with the same shape.

Optional debug info (no client changes required):
- By default, the gateway adds response headers:
  - `X-Cascadeflow-Gateway-*` (API, endpoint, mode, version)
- If you want the same info inside JSON responses, start the server with:

```bash
python -m cascadeflow.server --include-gateway-metadata
```

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

### Vercel AI SDK (OpenAI-Compatible)

If you already use Vercel AI SDK's OpenAI adapter, you can typically switch by setting `baseURL`.

```ts
import { openai } from "@ai-sdk/openai";
import { generateText } from "ai";

const result = await generateText({
  model: openai("cascadeflow", { baseURL: "http://127.0.0.1:8084/v1" }),
  prompt: "Hello",
});
console.log(result.text);
```

### Anthropic (HTTP / SDK)

If your Anthropic client supports overriding `base_url`, point it at the gateway and call
`messages.create` as usual. Otherwise, use raw HTTP against `POST /v1/messages`.

See: `examples/gateway_client_anthropic.py`

### Optional Routing Hints (No Schema Changes)

The gateway supports opt-in hint headers. If you don't set these, cascadeflow will auto-detect
complexity and domains.

- `X-Cascadeflow-Complexity: trivial|simple|moderate|hard|expert`
- `X-Cascadeflow-Domain: code|math|legal|medical|...`

## 3) Quick Validation Checklist

```bash
curl -s http://127.0.0.1:8084/health
curl -s http://127.0.0.1:8084/stats
curl -s http://127.0.0.1:8084/v1/models | jq .
```

And a smoke call:

```bash
curl -s http://127.0.0.1:8084/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"cascadeflow","messages":[{"role":"user","content":"hello"}]}' | jq .
```

Embeddings smoke call:

```bash
curl -s http://127.0.0.1:8084/v1/embeddings \
  -H 'content-type: application/json' \
  -d '{"model":"cascadeflow","input":"hello"}' | jq .
```
