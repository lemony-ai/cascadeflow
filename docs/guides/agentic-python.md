# 🤖 Agentic Patterns (Python)

Practical patterns for building agentic and multi-agent systems on top of `cascadeflow`:

- 🔁 Tool loops (multi-turn tool calling)
- 🧩 Multi-agent orchestration (planner/executor/researcher)
- 🧰 Agent-as-a-tool delegation
- 🧱 Message list best practices (tool history + system prompts)

---

## 📋 Table of Contents

1. [What cascadeflow Gives You (and What You Still Own)](#what-cascadeflow-gives-you-and-what-you-still-own)
2. [Message Format (Tool Loops)](#message-format-tool-loops)
3. [Tool Loop: Fast DX With `tool_executor`](#tool-loop-fast-dx-with-tool_executor)
4. [Multi-Agent: Two Proven Orchestration Patterns](#multi-agent-two-proven-orchestration-patterns)
5. [System Prompts (Important)](#system-prompts-important)
6. [Example (Runnable)](#example-runnable)
7. [Troubleshooting](#troubleshooting)

---

## What cascadeflow Gives You (and What You Still Own)

**cascadeflow handles:**
- ✅ Model cascading (cheap first, escalate when needed)
- ✅ Tool-capable model filtering (when tools are present)
- ✅ Tool intent/risk routing (choose strong tool models when needed)
- ✅ Streaming helpers (`stream_events`) for UIs and observability

**You still implement:**
- 🔁 Tool implementations (your functions, your side effects)
- 🧠 Multi-agent orchestration (agent graph, delegation, memory, state)

---

## Message Format (Tool Loops)

For multi-turn tool calling, your message history will contain:

1. `role="assistant"` with `tool_calls` (the model asking to call tools)
2. `role="tool"` with `tool_call_id` (your tool results, one per tool call)
3. Regular `user`/`assistant` messages

Example:

```python
messages = [
  {"role": "user", "content": "Compute 2+2"},
  {
    "role": "assistant",
    "content": "",
    "tool_calls": [
      {"id": "call_1", "type": "function", "function": {"name": "calculate", "arguments": "{\"expression\":\"2+2\"}"}}
    ],
  },
  {"role": "tool", "tool_call_id": "call_1", "content": "{\"result\": 4}"},
  {"role": "user", "content": "Explain the result briefly."},
]
```

---

## Tool Loop: Fast DX With `tool_executor`

If you pass a `tool_executor` to `CascadeAgent`, cascadeflow can automatically:

- Execute tool calls when the model emits them
- Append tool results
- Continue until the model stops requesting tools (or `max_steps` is reached)

```python
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.tools import ToolConfig, ToolExecutor

def calculate(expression: str) -> dict:
    return {"expression": expression, "result": 4}

executor = ToolExecutor([
    ToolConfig(
        name="calculate",
        description="Calculator",
        parameters={
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
        function=calculate,
    )
])

agent = CascadeAgent(
    models=[
        ModelConfig("gpt-4o-mini", "openai", cost=0.00015, supports_tools=True),
        ModelConfig("gpt-4o", "openai", cost=0.00625, supports_tools=True),
    ],
    tool_executor=executor,
)

tools = [
    {
        "name": "calculate",
        "description": "Calculator",
        "parameters": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    }
]

result = await agent.run(
    "Compute 2+2 using the calculate tool.",
    tools=tools,
    max_steps=5,
)
print(result.content)
```

---

## Multi-Agent: Two Proven Orchestration Patterns

### Pattern A: “Coordinator Calls Specialists”

- `planner_agent` produces a plan
- `research_agent` gathers facts/tools
- `writer_agent` produces final output

Use multiple `CascadeAgent` instances with different prompts, models, and tool sets.

### Pattern B: “Agent-as-a-Tool” Delegation

Expose a tool like `delegate_to_researcher({question})` where the tool implementation calls a second agent.
This scales well because delegation becomes just another tool call, with separate rate-limits and tracing if needed.

---

## System Prompts (Important)

Python providers typically accept system prompts as `role="system"` messages in the message list.

Recommendation:
- Put your system prompt either in `system_prompt=...` (agent-level) or as the first message with `role="system"`.
- Avoid duplicating the same instruction in multiple places.

---

## Example (Runnable)

See:
- `examples/agentic_multi_agent.py`

It demonstrates:
- Tool loop with `tool_executor`
- Multi-agent delegation as a tool

---

## Troubleshooting

**Tool loop stops early**
- Ensure your tools are passed as `tools=[...]`.
- Ensure the agent is created with `tool_executor=...`.

**Tool results are not matched to tool calls**
- Ensure each tool result message includes the correct `tool_call_id`.

