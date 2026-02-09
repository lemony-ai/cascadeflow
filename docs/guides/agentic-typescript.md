# 🤖 Agentic Patterns (TypeScript)

Practical patterns for building agentic and multi-agent systems on top of `@cascadeflow/core`:

- 🔁 Tool loops (multi-turn tool calling)
- 🧩 Multi-agent orchestration (planner/executor/researcher)
- 🧰 Agent-as-a-tool delegation
- 🧭 Tool cascade routing (pick tool-capable models only when needed)
- 🧱 Message list best practices (including system prompt handling)

---

## 📋 Table of Contents

1. [What cascadeflow Gives You (and What You Still Own)](#what-cascadeflow-gives-you-and-what-you-still-own)
2. [Message Format (Tool Loops)](#message-format-tool-loops)
3. [Tool Loop: Minimal Working Pattern](#tool-loop-minimal-working-pattern)
4. [Multi-Agent: Two Proven Orchestration Patterns](#multi-agent-two-proven-orchestration-patterns)
5. [Tool Cascade Routing](#tool-cascade-routing)
6. [System Prompt Handling (Important)](#system-prompt-handling-important)
7. [Example (Copy/Paste Ready)](#example-copypaste-ready)
8. [Troubleshooting](#troubleshooting)

---

## What cascadeflow Gives You (and What You Still Own)

**cascadeflow handles:**
- ✅ Model cascading (cheap first, escalate when needed)
- ✅ Tool-capable model filtering (if you pass `tools`, non-tool models are skipped)
- ✅ Tool-call detection + tool cascade routing heuristics
- ✅ Streaming events with tool call visibility

**You still implement:**
- 🔁 Tool implementations (your functions, your side effects)
- 🧠 Multi-agent orchestration (agent graph, delegation, memory, state)

**Optional (built-in tool loop):**
- If you configure `toolExecutor` on the agent (or pass `toolExecutor` per call), cascadeflow can automatically:
  - Execute tool calls
  - Append tool results
  - Continue the conversation until the model stops requesting tools (or `maxSteps` is reached)

---

## Message Format (Tool Loops)

For multi-turn tool calling, you must persist **three kinds of messages**:

1. `role: "assistant"` with `tool_calls` (the model asking to run tools)
2. `role: "tool"` with `tool_call_id` (your tool results, one per call)
3. Regular `user`/`assistant` text messages

`@cascadeflow/core` uses a universal message type:

```ts
type Message = {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string
  tool_call_id?: string
  tool_calls?: Array<{ id: string; type: 'function'; function: { name: string; arguments: string } }>
}
```

---

## Tool Loop: Minimal Working Pattern

This is the core pattern:

```ts
import { CascadeAgent, ToolExecutor, ToolCall, ToolConfig, type Message, type Tool } from '@cascadeflow/core';

async function runToolLoop(params: {
  agent: CascadeAgent;
  messages: Message[];
  tools: Tool[];
  executor: ToolExecutor;
  maxTurns?: number;
}) {
  const { agent, tools, executor } = params;
  const maxTurns = params.maxTurns ?? 6;
  const messages: Message[] = [...params.messages];

  for (let turn = 0; turn < maxTurns; turn++) {
    const result = await agent.run(messages, { tools });

    // Persist the assistant message, including tool calls if present.
    messages.push({
      role: 'assistant',
      content: result.content ?? '',
      tool_calls: result.toolCalls,
    });

    if (!result.toolCalls || result.toolCalls.length === 0) {
      return { result, messages };
    }

    for (const raw of result.toolCalls) {
      const call = ToolCall.fromOpenAI(raw as any);
      const toolResult = await executor.execute(call);

      messages.push({
        role: 'tool',
        tool_call_id: call.id,
        content: JSON.stringify(
          toolResult.success ? toolResult.result : { error: toolResult.error },
        ),
      });
    }
  }

  throw new Error(`Tool loop exceeded maxTurns=${maxTurns}`);
}
```

### Built-in Tool Loop (Fastest DX)

If you prefer not to manage the loop yourself, configure a `ToolExecutor`:

```ts
import { CascadeAgent, ToolConfig, ToolExecutor, type Tool } from '@cascadeflow/core';

const executor = new ToolExecutor([
  new ToolConfig({
    name: 'calculate',
    description: 'Calculator',
    parameters: {
      type: 'object',
      properties: { expression: { type: 'string' } },
      required: ['expression'],
    },
    function: async ({ expression }: { expression: string }) => ({ expression, result: 4 }),
  }),
]);

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, supportsTools: true },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625, supportsTools: true },
  ],
  toolExecutor: executor,
});

const tools: Tool[] = [
  {
    type: 'function',
    function: {
      name: 'calculate',
      description: 'Calculator',
      parameters: {
        type: 'object',
        properties: { expression: { type: 'string' } },
        required: ['expression'],
      },
    },
  },
];

const result = await agent.run('Compute 2+2 using the calculate tool.', {
  tools,
  maxSteps: 5,
});
```

Notes:
- When tool execution is enabled, cascadeflow runs a direct multi-step loop using the best available tool-capable model.

---

## Multi-Agent: Two Proven Orchestration Patterns

### Pattern A: “Coordinator Calls Specialists”

- `plannerAgent` produces a plan
- `researchAgent` gathers facts/tools
- `writerAgent` produces final output

Use multiple `CascadeAgent` instances (different prompts, different model stacks, different tool sets).

### Pattern B: “Agent-as-a-Tool” Delegation

Expose a tool like `delegate_to_researcher({ question })` whose implementation calls a second agent:

```ts
const delegateTool = new ToolConfig({
  name: 'delegate_to_researcher',
  description: 'Ask the research agent for focused help',
  parameters: {
    type: 'object',
    properties: { question: { type: 'string' } },
    required: ['question'],
  },
  function: async ({ question }: { question: string }) => {
    const res = await researchAgent.run(question);
    return { answer: res.content, model: res.modelUsed, cost: res.totalCost };
  },
});
```

This pattern scales well because:
- Your “main” agent stays simple
- Delegation becomes just another tool call
- You can rate-limit, sandbox, or trace delegations separately

---

## Tool Cascade Routing

When you pass `tools`, cascadeflow can:
- Filter out models that do not support tools
- Use tool-intent + risk/complexity heuristics to decide:
  - **Direct** to a strong tool model (when tool usage is likely)
  - **Cascade** across tool-capable models (when uncertain / high-risk)

This reduces cost while keeping tool correctness high.

---

## System Prompt Handling (Important)

For best portability across providers, cascadeflow normalizes system prompts:

- If you pass `Message[]` containing `role: "system"` messages, those are extracted and merged.
- If you also pass `options.systemPrompt`, it is merged in front (explicit first).
- Providers then receive:
  - `systemPrompt`: one combined string
  - `messages`: system messages removed

**Recommendation:** Prefer *one* place to define system prompts.

---

## Example (Copy/Paste Ready)

See the runnable example:

- `packages/core/examples/nodejs/agentic-multi-agent.ts`

It demonstrates:
- A full tool loop with persisted assistant `tool_calls`
- A multi-agent “delegate to researcher” tool
- Tool execution with `ToolExecutor`

---

## Troubleshooting

**My tool loop doesn’t continue**
- Ensure you’re persisting the assistant message with `tool_calls`.
- Ensure each tool result message includes the correct `tool_call_id`.

**I see duplicated system prompts**
- Don’t include system prompts both as `options.systemPrompt` and as `role: "system"` messages unless you intend to merge them.

**No tool-capable models found**
- Ensure at least one model config includes `supportsTools: true`.
- Ensure you passed `tools` to `agent.run(...)`.
