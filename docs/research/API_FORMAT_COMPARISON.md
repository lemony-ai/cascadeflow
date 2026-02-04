# Anthropic Messages API vs OpenAI Chat Completions API

> **Note:** This document reflects publicly documented formats as of early 2025. It is intended for building a translation/proxy layer and focuses on *shape/semantics* rather than model availability or pricing.

## 1. Anthropic `/v1/messages` (new Messages API)

### Request schema (high level)
```json
POST /v1/messages
{
  "model": "claude-3-5-sonnet-20240620",
  "max_tokens": 1024,
  "system": "You are a helpful assistant.",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "Summarize this:"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}}
      ]
    }
  ],
  "temperature": 0.2,
  "top_p": 0.9,
  "top_k": 40,
  "stop_sequences": ["\n\nHuman:"],
  "metadata": {"user_id": "abc-123"},
  "tools": [
    {
      "name": "get_weather",
      "description": "Fetch weather for a city",
      "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"]
      }
    }
  ],
  "tool_choice": {"type": "auto"},
  "stream": false
}
```

**Key points**
- `system` is a **top‑level field** (string or array of content blocks), not a `role` in `messages`.
- `messages` contains **only `user` and `assistant` roles**.
- `content` is **always an array of blocks**, even for text‑only use cases.
- Tools are declared in `tools` with `input_schema`; tool selection uses `tool_choice`.

### Response schema (high level)
```json
{
  "id": "msg_01...",
  "type": "message",
  "role": "assistant",
  "model": "claude-3-5-sonnet-20240620",
  "content": [
    {"type": "text", "text": "Here's a summary..."},
    {"type": "tool_use", "id": "toolu_01...", "name": "get_weather", "input": {"city": "Boston"}}
  ],
  "stop_reason": "tool_use",
  "stop_sequence": null,
  "usage": {"input_tokens": 123, "output_tokens": 45}
}
```

### Streaming format (SSE)
Anthropic streams **structured events** (each `data:` line is JSON, with `event:` names):

```
event: message_start

data: {"type":"message_start","message":{"id":"msg_...","role":"assistant","model":"...","content":[],"usage":{"input_tokens":123,"output_tokens":0}}}

event: content_block_start

data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta

data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: content_block_stop

data: {"type":"content_block_stop","index":0}

event: message_delta

data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":12}}

event: message_stop

data: {"type":"message_stop"}
```

Tool‑use streaming uses `content_block_delta` with `delta.type = "input_json_delta"` to incrementally stream tool input JSON.

### Tool/function calling
- Tool calls are represented as **content blocks** of type `tool_use` in the assistant response.
- Tools are **described** in the request under `tools` and chosen using `tool_choice`.
- Tool results are sent back by the client as a **user message** containing a `tool_result` content block:
```json
{
  "role": "user",
  "content": [
    {"type": "tool_result", "tool_use_id": "toolu_01...", "content": "72°F and sunny"}
  ]
}
```

### System message handling
- **Single top‑level** `system` field; can be a string or an array of content blocks.
- **No `system` role** in the `messages` list.

---

## 2. OpenAI `/v1/chat/completions` (Chat Completions)

### Request schema (high level)
```json
POST /v1/chat/completions
{
  "model": "gpt-4o-mini",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Summarize this:"}
  ],
  "temperature": 0.2,
  "top_p": 0.9,
  "stop": ["\n\nHuman:"],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Fetch weather for a city",
        "parameters": {
          "type": "object",
          "properties": {"city": {"type": "string"}},
          "required": ["city"]
        }
      }
    }
  ],
  "tool_choice": "auto",
  "stream": false
}
```

### Response schema (high level)
```json
{
  "id": "chatcmpl_...",
  "object": "chat.completion",
  "created": 1710000000,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Here's a summary...",
        "tool_calls": [
          {
            "id": "call_01...",
            "type": "function",
            "function": {"name": "get_weather", "arguments": "{\"city\":\"Boston\"}"}
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ],
  "usage": {"prompt_tokens": 123, "completion_tokens": 45, "total_tokens": 168}
}
```

### Streaming format (SSE)
OpenAI streams **choice deltas**:

```
data: {"id":"chatcmpl_...","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant","content":"Hel"},"index":0,"finish_reason":null}]}

data: {"id":"chatcmpl_...","object":"chat.completion.chunk","choices":[{"delta":{"content":"lo"},"index":0,"finish_reason":null}]}

data: {"id":"chatcmpl_...","object":"chat.completion.chunk","choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_01...","type":"function","function":{"name":"get_weather","arguments":"{\"city\":\"Bos"}}]}}]}

data: {"id":"chatcmpl_...","object":"chat.completion.chunk","choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"ton\"}"}}]}}]}

data: {"id":"chatcmpl_...","object":"chat.completion.chunk","choices":[{"delta":{},"index":0,"finish_reason":"tool_calls"}]}

data: [DONE]
```

### Tool/function calling
- Tools are declared in `tools` with `type: "function"` and a JSON Schema‑like `parameters` object.
- Tool calls are **returned in `message.tool_calls`**.
- Tool results are sent back as a **`role: "tool"` message** with `tool_call_id` and `content`.

### System message handling
- System instructions are **message(s) with `role: "system"`** in the `messages` list.

---

## 3. Comparison Matrix

| Category | Anthropic Messages API | OpenAI Chat Completions API |
|---|---|---|
| Message format | `messages` array, roles `user`/`assistant`, **content blocks** | `messages` array, roles `system`/`user`/`assistant`/`tool`, **string or multimodal parts** |
| Role naming | `user` / `assistant` only | `system` / `user` / `assistant` / `tool` |
| System instructions | Top‑level `system` field | `role: "system"` message(s) |
| Tool declaration | `tools: [{name, description, input_schema}]` | `tools: [{type:"function", function:{name, description, parameters}}]` |
| Tool call output | `content` block `tool_use` with `id`, `name`, `input` | `message.tool_calls[]` with `id`, `function.arguments` (stringified JSON) |
| Tool result input | `user` message containing `tool_result` block | `role: "tool"` message with `tool_call_id` |
| Streaming format | SSE **typed events** (message_start, content_block_delta, etc.) | SSE **delta chunks** (`chat.completion.chunk`) |
| Error format | Typically `{type: "error", error: {type, message, ...}}` | Typically `{error: {message, type, param, code}}` |
| Token counts | `usage: {input_tokens, output_tokens}` | `usage: {prompt_tokens, completion_tokens, total_tokens}` |
| Stop reasons | `stop_reason` in message | `finish_reason` in choice |

---

## 4. Translation Layer Design

### 4.1 OpenAI → Anthropic

#### Mapping rules
- **System messages** → concatenate into Anthropic `system` (string or content blocks).
- **User/assistant messages** → map to Anthropic `messages` with block array content.
- **Tool schema** → map `tools[].function.parameters` → `tools[].input_schema`.
- **Tool choice** → map `tool_choice`:
  - `"auto"` → `{ "type": "auto" }`
  - `"none"` → `{ "type": "auto" }` with no tools (or omit tools)
  - `{"type":"function","function":{"name":"X"}}` → `{ "type": "tool", "name": "X" }`

#### Pseudocode
```pseudo
function openai_to_anthropic(request):
  anthropic = {}
  anthropic.model = request.model
  anthropic.max_tokens = request.max_tokens
  anthropic.temperature = request.temperature
  anthropic.top_p = request.top_p
  anthropic.stop_sequences = request.stop

  system_msgs = filter(request.messages, role == "system")
  anthropic.system = join_system(system_msgs)

  anthropic.messages = []
  for msg in request.messages where role in ["user", "assistant", "tool"]:
    if msg.role == "tool":
      # convert tool result to user message with tool_result block
      anthropic.messages.append({
        role: "user",
        content: [{type: "tool_result", tool_use_id: msg.tool_call_id, content: msg.content}]
      })
    else:
      anthropic.messages.append({
        role: msg.role,
        content: to_content_blocks(msg.content)
      })

  anthropic.tools = map_tools_openai_to_anthropic(request.tools)
  anthropic.tool_choice = map_tool_choice_openai_to_anthropic(request.tool_choice)
  return anthropic
```

#### Edge cases / gotchas
- OpenAI allows **multiple system messages**; Anthropic expects a **single system field**. Decide whether to concatenate with separators or preserve as an array of blocks.
- OpenAI tool call arguments are **stringified JSON**; Anthropic expects a **native JSON object** in `tool_use.input`.
- OpenAI `role: "tool"` messages may contain **non‑string content** (e.g., structured JSON in `content`) — must be stringified or embedded as `tool_result` text.

### 4.2 Anthropic → OpenAI

#### Mapping rules
- **Top‑level `system`** → first `messages[]` entry with `role: "system"`.
- **Messages array** → map `content` blocks to OpenAI `content` string (or multimodal parts) where possible.
- **Tool schema** → map `tools[].input_schema` → `tools[].function.parameters`.
- **Tool calls** → map `tool_use` blocks to `message.tool_calls[]`.
- **Tool results** → map `tool_result` blocks to `role: "tool"` messages.

#### Pseudocode
```pseudo
function anthropic_to_openai(request):
  openai = {}
  openai.model = request.model
  openai.max_tokens = request.max_tokens
  openai.temperature = request.temperature
  openai.top_p = request.top_p
  openai.stop = request.stop_sequences

  openai.messages = []
  if request.system:
    openai.messages.append({role: "system", content: system_to_string(request.system)})

  for msg in request.messages:
    if has_tool_result(msg):
      for block in msg.content where block.type == "tool_result":
        openai.messages.append({
          role: "tool",
          tool_call_id: block.tool_use_id,
          content: block.content
        })
    else:
      openai.messages.append({
        role: msg.role,
        content: blocks_to_openai_content(msg.content)
      })

  openai.tools = map_tools_anthropic_to_openai(request.tools)
  openai.tool_choice = map_tool_choice_anthropic_to_openai(request.tool_choice)
  return openai
```

#### Edge cases / gotchas
- Anthropic `content` blocks can include **non‑text** (images, citations, tool_use) that may not map 1:1 into OpenAI chat content unless using multimodal message parts.
- Anthropic streams **content_block events** which must be reassembled into OpenAI’s **delta chunk** format.
- Anthropic can return **multiple content blocks** (text + tool_use); OpenAI expects tool calls in a separate `tool_calls` array, not in `content`.

### 4.3 What cannot be translated 1:1
- **Streaming semantics:** Anthropic’s typed SSE events do not map cleanly to OpenAI’s delta‑only streaming model without re‑chunking and state management.
- **Tool input streaming:** Anthropic streams `input_json_delta` for tool calls, whereas OpenAI streams string fragments in `function.arguments`.
- **Content block richness:** Anthropic’s block types (citations, images, tool_use) may not have direct equivalents in plain OpenAI chat content.
- **Usage accounting:** token counters are **named differently** and may include different categories in edge cases.

---

## 5. Side‑by‑Side Request Examples

### Basic text request

| Anthropic | OpenAI |
|---|---|
| ```json
{ "model":"claude-3-5-sonnet-20240620", "system":"You are helpful.", "max_tokens":256, "messages":[{"role":"user","content":[{"type":"text","text":"Hello"}]}] }
``` | ```json
{ "model":"gpt-4o-mini", "messages":[{"role":"system","content":"You are helpful."},{"role":"user","content":"Hello"}], "max_tokens":256 }
``` |

### Tool call request

| Anthropic | OpenAI |
|---|---|
| ```json
{ "model":"claude-3-5-sonnet-20240620", "max_tokens":256, "messages":[{"role":"user","content":[{"type":"text","text":"Weather in Boston"}]}], "tools":[{"name":"get_weather","description":"Fetch weather","input_schema":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}], "tool_choice":{"type":"auto"} }
``` | ```json
{ "model":"gpt-4o-mini", "messages":[{"role":"user","content":"Weather in Boston"}], "tools":[{"type":"function","function":{"name":"get_weather","description":"Fetch weather","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}], "tool_choice":"auto" }
``` |

---

## 6. Side‑by‑Side Response Examples

### Tool call response

| Anthropic | OpenAI |
|---|---|
| ```json
{ "id":"msg_...", "type":"message", "role":"assistant", "content":[{"type":"tool_use","id":"toolu_01...","name":"get_weather","input":{"city":"Boston"}}], "stop_reason":"tool_use" }
``` | ```json
{ "id":"chatcmpl_...", "object":"chat.completion", "choices":[{"message":{"role":"assistant","tool_calls":[{"id":"call_01...","type":"function","function":{"name":"get_weather","arguments":"{\"city\":\"Boston\"}"}}]},"finish_reason":"tool_calls"}] }
``` |

---

## 7. Streaming Format Comparison

| Aspect | Anthropic | OpenAI |
|---|---|---|
| Framing | `event:` + `data:` SSE with typed events | `data:` SSE chunks + `[DONE]` sentinel |
| Granularity | Content blocks + deltas (`text_delta`, `input_json_delta`) | Choice deltas (`delta.content`, `delta.tool_calls`) |
| Tool input streaming | `input_json_delta` | string fragments in `function.arguments` |

---

## 8. Tool Calling Comparison

| Topic | Anthropic | OpenAI |
|---|---|---|
| Declaration | `tools[].input_schema` | `tools[].function.parameters` |
| Call location | `content` block `tool_use` | `message.tool_calls[]` |
| Call arguments type | native JSON object | JSON **string** |
| Tool result | `tool_result` block in `user` message | `role: "tool"` message |

---

## 9. Compatibility Notes for Proxy Implementation

- **Normalize system instructions** to a single source of truth: assemble/disassemble system messages consistently.
- **Preserve tool call IDs**: OpenAI uses `tool_call_id`, Anthropic uses `tool_use_id` — map carefully.
- **Round‑trip tool arguments**: stringify/parse JSON deterministically (stable key ordering helps debugging).
- **Streaming bridge**: maintain a small state machine to convert between event types and deltas.
- **Message ordering**: ensure tool results always follow tool calls to avoid invalid API errors.
- **Token accounting**: expose both counts; do not rely on equality when returning metrics to clients.

