# 🌊 cascadeflow Streaming Guide

Complete guide to real-time streaming with cascadeflow.

---

## 📋 Table of Contents

### **Basic (Getting Started)**
1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Text Streaming](#text-streaming)
4. [Tool Streaming](#tool-streaming)
5. [Event Types](#event-types)

### **Advanced (Power Features)**
6. [Advanced Usage](#advanced-usage)
7. [Performance](#performance)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)

---

# Basic Usage

Essential streaming patterns for cascadeflow.

---

## Overview

cascadeflow provides **real-time streaming** for both text responses and tool calls, with full visibility into cascade decisions, quality validation, and cost tracking.

### Key Features

- ⚡ **Real-time output** - See tokens as they arrive
- 🔄 **Cascade events** - Track draft decisions and model switches
- 🔧 **Tool streaming** - Progressive JSON parsing of tool calls
- 📊 **Live metrics** - Cost and latency tracking per query
- ✅ **Quality validation** - Automatic quality checks with events

### Requirements

```bash
# Basic streaming (text only)
pip install cascadeflow

# Tool streaming (includes JSON parser in the core package)
pip install cascadeflow

# All features
pip install cascadeflow[all]
```

### Prerequisites

**⚠️ CRITICAL: Streaming requires 2+ models (cascade must be enabled)**

```python
# ✅ Streaming available (2+ models)
agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig(name="gpt-4o", provider="openai", cost=0.00625),
])

# Check availability
if agent.text_streaming_manager:
    print("✅ Text streaming available")

if agent.tool_streaming_manager:
    print("✅ Tool streaming available")

# ❌ No streaming (single model)
agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o", provider="openai"),
])
# agent.text_streaming_manager == None
# agent.tool_streaming_manager == None
```

---

## Quick Start

### Text Streaming (5 Lines)

```python
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.streaming import StreamEventType

agent = CascadeAgent(models=[...])  # 2+ models

# ✅ CORRECT: Use stream_events()
async for event in agent.stream_events("Hello"):
    if event.type == StreamEventType.CHUNK:
        print(event.content, end='', flush=True)
```

### Tool Streaming (10 Lines)

```python
from cascadeflow.streaming import ToolStreamEventType

tools = [{"name": "get_weather", "description": "...", "parameters": {...}}]  # Universal format

# ✅ CORRECT: Use stream_events() with tools
async for event in agent.stream_events(
    "What's the weather in Paris?",
    tools=tools
):
    if event.type == ToolStreamEventType.TOOL_CALL_COMPLETE:
        tool = event.data.get('tool_call', {})
        print(f"Tool: {tool.get('name')}")
```

---

## Text Streaming

### Basic Usage

```python
import asyncio
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.streaming import StreamEventType


async def main():
    # Setup agent with 2+ models (required)
    agent = CascadeAgent(models=[
        ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
        ModelConfig(name="gpt-4o", provider="openai", cost=0.00625),
    ])
    
    # ✅ CORRECT: Check streaming availability
    if not agent.text_streaming_manager:
        print("Streaming not available (need 2+ models)")
        return
    
    # ✅ CORRECT: Use stream_events()
    async for event in agent.stream_events(
        "Explain Python in one sentence.",
        max_tokens=100,
        temperature=0.7
    ):
        match event.type:
            case StreamEventType.CHUNK:
                # Real-time text output
                print(event.content, end='', flush=True)
            
            case StreamEventType.DRAFT_DECISION:
                # Quality check result
                if event.data['accepted']:
                    print(f"\n✓ Draft accepted")
                else:
                    print(f"\n✗ Rejected: {event.data['reason']}")
            
            case StreamEventType.SWITCH:
                # Model switching
                print(f"\n⤴️ Cascading to {event.data['to_model']}")
            
            case StreamEventType.COMPLETE:
                # Final result
                result = event.data['result']
                print(f"\n💰 ${result['total_cost']:.6f}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Event Flow

**Simple Query (Draft Accepted):**
```
ROUTING → CHUNK → CHUNK → ... → DRAFT_DECISION → COMPLETE
```

**Complex Query (Cascaded):**
```
ROUTING → CHUNK → ... → DRAFT_DECISION → SWITCH →
CHUNK → CHUNK → ... → COMPLETE
```

### Event Types

| Event | When | Data Available |
|-------|------|----------------|
| `ROUTING` | Strategy chosen | `strategy`, `complexity` |
| `CHUNK` | Token arrives | `content` (string) |
| `DRAFT_DECISION` | Quality check done | `accepted`, `confidence`, `reason` |
| `SWITCH` | Escalating to verifier | `from_model`, `to_model` |
| `COMPLETE` | Stream finished | `result` (full response) |
| `ERROR` | Error occurred | `error` (exception) |

### Parameters

```python
agent.stream_events(
    query="Your question",           # Required
    max_tokens=100,                  # Token limit (default: 100)
    temperature=0.7,                 # Sampling temp (default: 0.7)
    complexity_hint="simple",        # Query complexity hint
    force_direct=False,              # Force direct routing
    tools=None,                      # Tools (None for text-only)
)
```

### Complete Example

See [`examples/streaming_text.py`](../../examples/streaming_text.py) for a full working example with:
- Multiple complexity levels
- Complete event handling
- Cost and timing tracking
- Visual feedback

---

## Tool Streaming

### Basic Usage

```python
import asyncio
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.streaming import ToolStreamEventType


# ✅ CORRECT: Define tools in universal format
tools = [{
    "name": "get_weather",
    "description": "Get current weather for a location",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City name"}
        },
        "required": ["location"]
    }
}]


async def main():
    # Setup agent with 2+ models (REQUIRED!)
    agent = CascadeAgent(models=[
        ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
        ModelConfig(name="gpt-4o", provider="openai", cost=0.00625),
    ])
    
    # ✅ CORRECT: Check tool streaming availability
    if not agent.tool_streaming_manager:
        print("Tool streaming not available (need 2+ models)")
        return
    
    # ✅ CORRECT: Use agent.stream_events() with tools
    async for event in agent.stream_events(
        "What's the weather in Paris?",
        tools=tools
    ):
        match event.type:
            case ToolStreamEventType.TEXT_CHUNK:
                # Regular text
                print(event.content, end='', flush=True)
            
            case ToolStreamEventType.TOOL_CALL_START:
                # Tool call detected
                print(f"\n🔧 Tool call starting...")
            
            case ToolStreamEventType.TOOL_CALL_COMPLETE:
                # ✅ CORRECT: Access via event.data
                tool = event.data.get('tool_call', {})
                print(f"🔧 Tool: {tool.get('name')}({tool.get('arguments')})")
            
            case ToolStreamEventType.COMPLETE:
                # All done
                print("\n✅ Done")


if __name__ == "__main__":
    asyncio.run(main())
```

### Tool Format (IMPORTANT!)

**✅ CORRECT - Universal Format:**
```python
tools = [{
    "name": "get_weather",           # ← Direct properties
    "description": "Get weather",
    "parameters": {
        "type": "object",
        "properties": {...}
    }
}]
```

**❌ WRONG - OpenAI Format:**
```python
tools = [{
    "type": "function",              # ← Don't wrap!
    "function": {
        "name": "get_weather",
        ...
    }
}]
```

cascadeflow uses a **universal format** that works with all providers. It automatically converts to each provider's expected format (OpenAI, Anthropic, Groq, etc.).

### Tool Execution

**IMPORTANT:** Tool streaming shows tool calls being formed, but does **NOT** automatically execute them.

For actual tool execution, you need to:

1. Create `ToolConfig` objects with executable functions
2. Use `ToolExecutor` to execute tool calls
3. Manually handle execution in your streaming loop

**Example with actual execution:**

```python
from cascadeflow.tools import ToolConfig, ToolExecutor, ToolCall, ToolCallFormat

# Define tools with executable functions
def get_weather(location: str, unit: str = "celsius") -> str:
    # Your actual implementation
    return f"{location}: 22°C, sunny"

tool_configs = [
    ToolConfig(
        name="get_weather",
        description="Get weather",
        parameters={
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "unit": {"type": "string"}
            },
            "required": ["location"]
        },
        function=get_weather  # ← Actual function
    )
]

# Create executor
executor = ToolExecutor(tool_configs)

# Define tools for model (universal format)
tools = [{
    "name": "get_weather",
    "description": "Get weather",
    "parameters": {...}
}]

# Stream and execute
async for event in agent.stream_events(query, tools=tools):
    if event.type == ToolStreamEventType.TOOL_CALL_COMPLETE:
        tool_call_data = event.data.get('tool_call', {})
        
        # Create ToolCall object
        tc = ToolCall(
            id=tool_call_data.get('id', 'call_0'),
            name=tool_call_data['name'],
            arguments=tool_call_data['arguments'],
            provider_format=ToolCallFormat.OPENAI
        )
        
        # Execute the tool
        result = await executor.execute(tc)
        print(f"Result: {result.result}")
```

See [`examples/tool_execution.py`](../../examples/tool_execution.py) for a complete working example.

### Event Flow

**Single Tool Call:**
```
TEXT_CHUNK → TOOL_CALL_START → TOOL_CALL_DELTA → TOOL_CALL_DELTA →
TOOL_CALL_COMPLETE → TEXT_CHUNK → COMPLETE
```

**Multiple Tool Calls:**
```
TOOL_CALL_START (tool1) → TOOL_CALL_COMPLETE (tool1) →
TOOL_CALL_START (tool2) → TOOL_CALL_COMPLETE (tool2) →
TEXT_CHUNK → COMPLETE
```

### Event Types

| Event | When | Data Available |
|-------|------|----------------|
| `TEXT_CHUNK` | Text token arrives | `content` |
| `TOOL_CALL_START` | Tool call detected | Minimal info |
| `TOOL_CALL_DELTA` | JSON chunk parsed | `delta` (JSON fragment) |
| `TOOL_CALL_COMPLETE` | Full JSON parsed | `data['tool_call']` (complete) |
| `DRAFT_DECISION` | Quality check | `accepted`, `confidence` |
| `SWITCH` | Model switching | `from_model`, `to_model` |
| `COMPLETE` | Stream finished | `result` |
| `ERROR` | Fatal error | `error` |

### Parameters

```python
agent.stream_events(
    query="Your question",           # Required
    tools=[...],                     # Tool definitions (required)
    max_tokens=1000,                 # Token limit
    temperature=0.7,                 # Sampling temperature
    complexity_hint=None,            # Complexity override
    force_direct=False,              # Skip cascade
    tool_choice=None,                # Tool selection strategy
)
```

### Tool Choice Options

```python
# Let model decide (default)
tool_choice=None  # or {"type": "auto"}

# Force specific tool (if provider supports)
tool_choice={
    "type": "function",
    "function": {"name": "get_weather"}
}
```

### Complete Example

See [`examples/streaming_tools.py`](../../examples/streaming_tools.py) for a full working example with:
- Multiple tool scenarios
- Progressive tool call formation
- Event handling
- Error handling

---

## Event Types

### StreamEvent (Text)

```python
@dataclass
class StreamEvent:
    type: StreamEventType      # Event type enum
    content: str              # Text content (for CHUNK)
    data: Dict[str, Any]      # Additional data
```

**Common Data Fields:**

```python
# ROUTING
event.data = {
    'strategy': 'cascade',
    'complexity': 'simple'
}

# DRAFT_DECISION
event.data = {
    'accepted': True,
    'confidence': 0.85,
    'reason': 'quality_passed',
    'score': 0.82
}

# SWITCH
event.data = {
    'from_model': 'gpt-4o-mini',
    'to_model': 'gpt-4o',
    'reason': 'quality_insufficient'
}

# COMPLETE
event.data = {
    'result': {
        'content': '...',
        'total_cost': 0.000123,
        'latency_ms': 847,
        'model_used': 'gpt-4o-mini',
        'draft_accepted': True
    }
}
```

### ToolStreamEvent (Tools)

```python
@dataclass
class ToolStreamEvent:
    type: ToolStreamEventType  # Event type enum
    content: str              # Text content
    delta: str                # JSON delta (progressive)
    data: Dict[str, Any]      # Additional data
```

**Common Data Fields:**

```python
# TOOL_CALL_COMPLETE
event.data = {
    'tool_call': {
        'id': 'call_abc123',
        'name': 'get_weather',
        'arguments': {'location': 'Paris', 'unit': 'celsius'}
    }
}

# Access it correctly:
tool = event.data.get('tool_call', {})
name = tool.get('name')
args = tool.get('arguments')
```

---

# Advanced Usage

Power features for streaming in production environments.

---

## Advanced Usage

### Custom Event Handlers

```python
class MyStreamHandler:
    """Custom streaming handler with callbacks."""
    
    def __init__(self):
        self.chunks = []
        self.tools_called = []
    
    async def on_chunk(self, content: str):
        """Handle text chunks."""
        self.chunks.append(content)
        print(content, end='', flush=True)
    
    async def on_tool_call(self, tool_call: Dict):
        """Handle tool calls."""
        self.tools_called.append(tool_call['name'])
        print(f"\nCalling: {tool_call['name']}")
    
    async def handle_stream(self, agent, query, tools=None):
        """Process stream with custom logic."""
        async for event in agent.stream_events(query, tools=tools):
            if event.type in (StreamEventType.CHUNK, ToolStreamEventType.TEXT_CHUNK):
                await self.on_chunk(event.content)
            elif event.type == ToolStreamEventType.TOOL_CALL_COMPLETE:
                tool = event.data.get('tool_call', {})
                await self.on_tool_call(tool)

# Usage
handler = MyStreamHandler()
await handler.handle_stream(agent, "What's the weather?", tools=weather_tools)
```

### Collecting Stream Results

```python
async def collect_stream_content(agent, query):
    """Collect all content from stream."""
    chunks = []
    
    async for event in agent.stream_events(query):
        if event.type == StreamEventType.CHUNK:
            chunks.append(event.content)
        elif event.type == StreamEventType.COMPLETE:
            return ''.join(chunks), event.data['result']
    
    return ''.join(chunks), None

# Usage
content, result = await collect_stream_content(agent, "Explain AI")
print(f"Content: {content}")
print(f"Cost: ${result['total_cost']:.6f}")
```

### Timeout Handling

```python
import asyncio

async def stream_with_timeout(agent, query, timeout=30):
    """Stream with timeout protection."""
    try:
        async with asyncio.timeout(timeout):
            async for event in agent.stream_events(query):
                if event.type == StreamEventType.CHUNK:
                    print(event.content, end='', flush=True)
                elif event.type == StreamEventType.COMPLETE:
                    return event.data['result']
    
    except asyncio.TimeoutError:
        print(f"\n⚠️  Streaming timeout after {timeout}s")
        return None
```

### Error Recovery

```python
async def stream_with_retry(agent, query, max_retries=3):
    """Stream with automatic retry on failure."""
    for attempt in range(max_retries):
        try:
            async for event in agent.stream_events(query):
                if event.type == StreamEventType.ERROR:
                    print(f"\n⚠️  Attempt {attempt + 1} failed: {event.data['error']}")
                    break
                
                if event.type == StreamEventType.CHUNK:
                    print(event.content, end='', flush=True)
                
                if event.type == StreamEventType.COMPLETE:
                    return event.data['result']
        
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"\n⚠️  Retrying... ({attempt + 1}/{max_retries})")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
    
    return None
```

---

## Performance

### Latency Metrics

| Metric | Typical Value | Notes |
|--------|---------------|-------|
| First chunk | <200ms | Initial response time |
| Chunk rate | 10-50 tokens/s | Varies by model and load |
| Overhead per event | 1-5ms | Processing cost |
| Total latency | 1-5s | Depends on response length |

### Optimization Tips

#### 1. Reduce First Chunk Latency

```python
# Use faster draft models
ModelConfig(name="gpt-3.5-turbo", provider="openai")  # Fast
ModelConfig(name="gpt-4o-mini", provider="openai")    # Faster
ModelConfig(name="llama-3.1-8b", provider="groq")     # Fastest
```

#### 2. Disable Verbose Logging

```python
agent = CascadeAgent(
    models=[...],
    verbose=False  # ← Reduces I/O overhead
)
```

### Memory Usage

- **Text streaming:** ~1-10 MB (minimal, streaming)
- **Tool streaming:** ~5-20 MB (JSON parsing buffers)
- **Per query:** O(response_length) memory

---

## Troubleshooting

### Common Issues

#### 1. "No streaming manager available"

**Problem:**
```python
agent.text_streaming_manager  # None
```

**Solution:**
```python
# Need 2+ models for cascade
agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig(name="gpt-4o", provider="openai", cost=0.00625),  # ← Add second model
])

# Always check:
if not agent.text_streaming_manager:
    print("Need 2+ models for streaming")
    return
```

#### 2. "KeyError: 'name'" (Tool format)

**Problem:**
```python
tools = [{
    "type": "function",      # ← Wrong format!
    "function": {...}
}]
```

**Solution:**
```python
# Use universal format
tools = [{
    "name": "get_weather",   # ← Direct properties
    "description": "...",
    "parameters": {...}
}]
```

#### 3. "AttributeError: no attribute 'stream'"

**Problem:**
```python
# Wrong API
async for event in agent.tool_streaming_manager.stream(query, tools=tools):
    ...
```

**Solution:**
```python
# Use agent.stream_events() instead
async for event in agent.stream_events(query, tools=tools):
    ...
```

#### 4. Stream hangs/never completes

**Possible causes:**
- Network timeout
- Model API issue
- Invalid API key

**Solution:**
```python
import asyncio

# Add timeout
async with asyncio.timeout(30):  # 30 second timeout
    async for event in agent.stream_events(query):
        ...
```

#### 5. Can't access tool_call data

**Problem:**
```python
tool = event.tool_call  # AttributeError or None
```

**Solution:**
```python
# Access via event.data
tool = event.data.get('tool_call', {})
name = tool.get('name')
args = tool.get('arguments')
```

---

## Best Practices

### 1. Always Check Availability

```python
# ✅ CORRECT: Check before streaming
if not agent.text_streaming_manager:
    print("Streaming not available (need 2+ models)")
    result = await agent.run(query)  # Fallback to non-streaming
else:
    async for event in agent.stream_events(query):
        ...
```

### 2. Handle All Event Types

```python
# Use match/case for exhaustive handling
async for event in agent.stream_events(query):
    match event.type:
        case StreamEventType.CHUNK:
            print(event.content, end='')
        case StreamEventType.DRAFT_DECISION:
            logger.info(f"Draft: {event.data['accepted']}")
        case StreamEventType.COMPLETE:
            return event.data['result']
        case StreamEventType.ERROR:
            logger.error(f"Error: {event.data['error']}")
        case _:
            # Unknown event type (future-proof)
            logger.warning(f"Unknown event: {event.type}")
```

### 3. Implement Timeouts

```python
# Always set a reasonable timeout
import asyncio

try:
    async with asyncio.timeout(30):
        async for event in agent.stream_events(query):
            ...
except asyncio.TimeoutError:
    print("Streaming timeout")
```

### 4. Log Important Events

```python
import logging

logger = logging.getLogger(__name__)

async for event in agent.stream_events(query):
    if event.type == StreamEventType.DRAFT_DECISION:
        logger.info(f"Draft {'accepted' if event.data['accepted'] else 'rejected'}")
    
    if event.type == StreamEventType.ERROR:
        logger.error(f"Stream error: {event.data.get('error')}")
```

### 5. Progressive UI Updates

```python
# For web UIs - update in real-time
async for event in agent.stream_events(query):
    if event.type == StreamEventType.CHUNK:
        # Update UI with new content
        await websocket.send(json.dumps({
            'type': 'content',
            'data': event.content
        }))
    
    elif event.type == StreamEventType.COMPLETE:
        # Send final statistics
        result = event.data['result']
        await websocket.send(json.dumps({
            'type': 'complete',
            'cost': result['total_cost']
        }))
```

### 6. Access Event Data Correctly

```python
# ✅ CORRECT: Use event.data dictionary
async for event in agent.stream_events(query, tools=tools):
    if event.type == ToolStreamEventType.TOOL_CALL_COMPLETE:
        tool = event.data.get('tool_call', {})  # ← Correct
        name = tool.get('name')
        args = tool.get('arguments')

# ❌ WRONG: Direct attribute access
tool = event.tool_call  # May not work
```

---

## Examples

### Complete Working Examples

1. **[examples/streaming_text.py](../../examples/streaming_text.py)**
    - Multiple complexity levels
    - Complete event handling
    - Cost and timing tracking
    - Visual feedback

2. **[examples/streaming_tools.py](../../examples/streaming_tools.py)**
    - Tool call streaming (formation only)
    - Progressive JSON parsing
    - Event handling

3. **[examples/tool_execution.py](../../examples/tool_execution.py)**
    - Actual tool execution with ToolExecutor
    - Complete workflow: stream → parse → execute
    - Real-world tool implementations

### Run Examples

```bash
# Text streaming
export OPENAI_API_KEY="sk-..."
python examples/streaming_text.py

# Tool streaming (watch tool calls form)
python examples/streaming_tools.py

# Tool execution (with real execution)
python examples/tool_execution.py
```

---

## Next Steps

- 📖 Read the [Streaming Examples](../../examples/streaming_text.py)
- 🎯 Try the [Examples](../../examples/)
- 🔧 See [Comprehensive Test Suite](../../tests/2.py)
- 💬 Join [Discord](https://discord.gg/cascadeflow) for help

---

## Summary

**Text Streaming:**
- ✅ Use `agent.stream_events(query)`
- ✅ Check `if agent.text_streaming_manager:` first
- ✅ Handle `CHUNK`, `DRAFT_DECISION`, `SWITCH`, `COMPLETE`
- ✅ Requires 2+ models (cascade enabled)

**Tool Streaming:**
- ✅ Use `agent.stream_events(query, tools=tools)`
- ✅ Check `if agent.tool_streaming_manager:` first
- ✅ Use universal tool format: `{"name": "...", "description": "...", "parameters": {...}}`
- ✅ Access tool data via `event.data.get('tool_call', {})`
- ✅ For execution, use `ToolExecutor` separately

**Critical Fixes:**
- ❌ `agent.can_stream` doesn't exist → Use `if agent.text_streaming_manager:`
- ❌ `agent.tool_streaming_manager.stream()` is not public → Use `agent.stream_events()`
- ❌ `execute_tools` parameter doesn't exist in public API → Use `ToolExecutor` manually
- ❌ `event.tool_call` doesn't work → Use `event.data.get('tool_call', {})`

**Need Help?**
- 🐛 [Report Issues](https://github.com/lemony-ai/cascadeflow/issues)
- 💬 [GitHub Discussions](https://github.com/lemony-ai/cascadeflow/discussions)

Happy streaming! 🌊
