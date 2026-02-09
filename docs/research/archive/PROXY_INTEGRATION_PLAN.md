# Proxy Integration Plan

## Goals
- Provide a **single proxy service** that acts as a drop-in replacement for both OpenAI and Anthropic APIs.
- Support **OpenAI** `/v1/chat/completions` (route GPT-4o-mini → GPT-4o cascade).
- Support **Anthropic** `/v1/messages` (route Haiku → Sonnet cascade).
- Preserve client compatibility with official SDKs, LangChain, and Claude Code.
- Maintain shared cascade logic, consistent telemetry, and per-provider cost tracking.

## Reference MVP
- Existing MVP example: `examples/fastapi_proxy_routing.py` (Anthropic-only). Extend it to support OpenAI format while sharing cascade logic.

## Dual-Provider Architecture (Single Proxy)
- **One FastAPI service** with two router groups:
  - `/v1/chat/completions` → OpenAI-compatible handler.
  - `/v1/messages` → Anthropic-compatible handler.
- **Shared core pipeline**:
  - Request normalization → cascade selection → provider dispatch → response normalization.
- **Provider adapters** implement the format translation, model mapping, and response shaping per standard.

## Endpoint Mapping

### OpenAI-Compatible
- **Endpoint**: `POST /v1/chat/completions`
- **Request mapping**:
  - `model`: map GPT-4o-mini → GPT-4o cascade default.
  - `messages`: convert to internal message schema (role/content).
  - `temperature`, `max_tokens`, `top_p`, `stream`, etc.: pass through or apply defaults.
- **Response mapping**:
  - Convert internal completion to `choices[0].message` with `role=assistant`.
  - Populate `usage` and `id` per OpenAI response format.

### Anthropic-Compatible
- **Endpoint**: `POST /v1/messages`
- **Request mapping**:
  - `model`: map Haiku → Sonnet cascade default.
  - `messages`: convert to internal message schema (role/content).
  - `max_tokens`, `temperature`, `top_p`, `stream`, etc.: pass through or apply defaults.
- **Response mapping**:
  - Convert internal completion to Anthropic `content` array.
  - Populate `usage` and `id` per Anthropic response format.

## Response Format Translation
- **Internal canonical response**:
  - `content`: assistant text
  - `tool_calls`: if supported
  - `usage`: prompt/completion/total tokens
  - `model`: resolved cascade model
  - `request_id`: proxy-generated ID
- **OpenAI output**:
  - `choices = [{ index, message: { role: "assistant", content }, finish_reason }]`
  - `usage = { prompt_tokens, completion_tokens, total_tokens }`
- **Anthropic output**:
  - `content = [{ type: "text", text }]`
  - `usage = { input_tokens, output_tokens }`

## Shared Cascade Logic
- **Central cascade policy** used by both providers:
  - Step 1: fast/cheap model (GPT-4o-mini or Haiku).
  - Step 2: fallback to higher-quality model (GPT-4o or Sonnet) when confidence/quality checks fail.
- **Confidence checks** via existing scoring/validation hooks.
- **Unified telemetry**: log cascade steps, latency, and model decisions with provider tags.

## Configuration (Default Models Per Provider)
- **Env-driven defaults**:
  - `OPENAI_DEFAULT_MODEL=gpt-4o-mini`
  - `OPENAI_CASCADE_FALLBACK=gpt-4o`
  - `ANTHROPIC_DEFAULT_MODEL=claude-3-haiku`
  - `ANTHROPIC_CASCADE_FALLBACK=claude-3-sonnet`
- **Allow overrides** per request, but enforce provider mapping logic.

## Cost Tracking Per Provider
- **Tag costs** by provider and resolved model.
- **Aggregate metrics**:
  - `provider=openai|anthropic`
  - `model=<resolved_model>`
  - `cascade_step=<primary|fallback>`
- **Emit metrics** to existing cost tracking interfaces and examples.

## Implementation Steps
1. Create shared request/response normalization layer.
2. Add OpenAI router and adapter for `/v1/chat/completions`.
3. Extend Anthropic handler to use shared cascade pipeline.
4. Add response translation for both standards.
5. Add provider-aware cost tracking and logging.
6. Update examples to include OpenAI-compatible proxy usage.

## Virtual Model Names

The proxy exposes **virtual models** that abstract cascade behavior:

| Virtual Model | Behavior | Use Case |
|---------------|----------|----------|
| `cascadeflow-auto` | Auto-select optimal cascade based on query complexity | Default, balanced |
| `cascadeflow-fast` | Prioritize speed, accept more drafts | Latency-sensitive |
| `cascadeflow-quality` | Prioritize quality, stricter thresholds | Accuracy-critical |
| `cascadeflow-cost` | Maximum cost savings, aggressive draft acceptance | Budget-constrained |

### Usage
```python
# Client just specifies virtual model
client = OpenAI(base_url="http://localhost:8000")
response = client.chat.completions.create(
    model="cascadeflow-auto",  # Proxy handles the cascade
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Model Mapping
When proxy receives a virtual model:
1. Parse cascade strategy from model name
2. Select appropriate drafter/verifier pair
3. Apply strategy-specific thresholds
4. Return response with actual model used in metadata

## Compatibility Notes
- **OpenAI SDK**: base URL override points to proxy.
- **LangChain**: use OpenAI-compatible route with environment variables.
- **Anthropic SDK / Claude Code**: base URL override points to proxy.
- **Virtual models**: work with any OpenAI-compatible client.
