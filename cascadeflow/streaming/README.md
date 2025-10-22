# CascadeFlow Streaming Module

Real-time streaming for both text and tool-calling cascades with complete diagnostics and quality validation.

## 📁 Structure

```
cascadeflow/streaming/
├── __init__.py          # Main exports
├── base.py              # Text streaming (StreamManager)
├── tools.py             # Tool streaming (ToolStreamManager)
└── utils.py             # Shared utilities (JSON parser, validators)
```

## 🚀 Quick Start

### Text Streaming

```python
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.streaming import StreamEventType

# Setup agent with cascade
agent = CascadeAgent(
    models=[
        ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002),
        ModelConfig(name="gpt-4o", provider="openai", cost=0.03),
    ],
    enable_cascade=True
)

# ✅ CORRECT: Access streaming via agent.text_streaming_manager
async for event in agent.text_streaming_manager.stream("What is Python?"):
    match event.type:
        case StreamEventType.CHUNK:
            print(event.content, end='', flush=True)
        case StreamEventType.SWITCH:
            print("\n⤴️ Cascading...")
        case StreamEventType.COMPLETE:
            print(f"\n✓ Done in {event.data['result']['latency_ms']:.0f}ms")
```

### Tool Streaming

```python
from cascadeflow.streaming import ToolStreamEventType

# Define tools
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            },
            "required": ["location"]
        }
    }
}]

# ✅ CORRECT: Access tool streaming via agent.tool_streaming_manager
async for event in agent.tool_streaming_manager.stream(
    "What's the weather in NYC?",
    tools=tools
):
    match event.type:
        case ToolStreamEventType.CHUNK:
            print(event.content, end='')
        case ToolStreamEventType.TOOL_CALL_START:
            print(f"\n🔧 Calling: {event.tool_call['name']}")
        case ToolStreamEventType.TOOL_RESULT:
            print(f"✓ Result: {event.tool_result}")
```

## 📖 Access Patterns

### ✅ Correct Way (v2.4+)

```python
# For text-only streaming
agent.text_streaming_manager.stream(query)

# For tool streaming
agent.tool_streaming_manager.stream(query, tools=tools)
```

### ❌ Old Way (Deprecated)

```python
# DON'T DO THIS - streaming_manager is deprecated
agent.streaming_manager.stream(query)  # ⚠️ Deprecated!

# DON'T DO THIS - no direct StreamManager import needed
from cascadeflow.streaming import StreamManager  # ⚠️ Not needed!
manager = StreamManager(agent.cascade)  # ⚠️ Use agent.text_streaming_manager instead!
```

## 🎯 Event Types

### Text Streaming Events (`StreamEventType`)

| Event | When | Data |
|-------|------|------|
| `DRAFT_START` | Draft model begins | `model`, `strategy` |
| `DRAFT_DECISION` | Draft completes | `accepted`, `confidence`, `reason` |
| `CHUNK` | Token received | `content` (string) |
| `SWITCH` | Escalating to verifier | `from_model`, `to_model` |
| `COMPLETE` | Stream finished | `result` (full response) |
| `ERROR` | Error occurred | `error` (exception) |

### Tool Streaming Events (`ToolStreamEventType`)

| Event | When | Data |
|-------|------|------|
| `CHUNK` | Text token | `content` |
| `TOOL_CALL_START` | Tool call begins | `tool_call` (partial) |
| `TOOL_CALL_DELTA` | Tool call updates | `delta` (JSON chunk) |
| `TOOL_CALL_COMPLETE` | Tool call ready | `tool_call` (complete) |
| `TOOL_RESULT` | Tool executed | `tool_result` |
| `TOOL_ERROR` | Tool failed | `error` |
| `COMPLETE` | All done | `result` |
| `ERROR` | Fatal error | `error` |

## 🔧 Advanced Usage

### Custom Event Handling

```python
from cascadeflow.streaming import StreamEventType

async for event in agent.text_streaming_manager.stream(query):
    match event.type:
        case StreamEventType.DRAFT_START:
            print(f"Starting draft with {event.data['model']}")
        
        case StreamEventType.DRAFT_DECISION:
            if event.data['accepted']:
                print(f"✓ Draft accepted ({event.data['confidence']:.1%})")
            else:
                print(f"✗ Draft rejected: {event.data['reason']}")
        
        case StreamEventType.CHUNK:
            # Real-time streaming
            print(event.content, end='', flush=True)
        
        case StreamEventType.SWITCH:
            print(f"\n⤴️ Escalating: {event.data['from_model']} → {event.data['to_model']}")
        
        case StreamEventType.COMPLETE:
            result = event.data['result']
            print(f"\n✓ Done | Cost: ${result['total_cost']:.4f} | {result['latency_ms']:.0f}ms")
        
        case StreamEventType.ERROR:
            print(f"\n✗ Error: {event.content}")
```

### Tool Execution Control

```python
# Auto-execute tools
async for event in agent.tool_streaming_manager.stream(
    query,
    tools=tools,
    execute_tools=True,  # ✅ Automatically execute tools
    max_turns=3  # Limit multi-turn loops
):
    if event.type == ToolStreamEventType.TOOL_RESULT:
        print(f"Got result: {event.tool_result}")

# Manual tool execution
async for event in agent.tool_streaming_manager.stream(
    query,
    tools=tools,
    execute_tools=False  # ⚠️ Manual control
):
    if event.type == ToolStreamEventType.TOOL_CALL_COMPLETE:
        # Execute tool yourself
        result = await my_executor(event.tool_call)
        # ... handle result
```

## 📊 Performance

### Text Streaming
- **First chunk latency**: <200ms (typical)
- **Overhead**: ~1-5ms per event
- **Memory**: Minimal (streaming chunks)

### Tool Streaming
- **JSON parsing**: <1ms per chunk
- **Validation**: <5ms per tool call
- **Execution**: Depends on tool (0-1000ms+)

## 🧪 Testing

```bash
# Test text streaming
pytest tests/test_streaming_base.py -v

# Test tool streaming
pytest tests/test_streaming_tools.py -v

# Test utilities
pytest tests/test_streaming_utils.py -v
```

## 📝 API Reference

### TextStreamingManager (agent.text_streaming_manager)

```python
async def stream(
    query: str,
    max_tokens: int = 100,
    temperature: float = 0.7,
    complexity: str = "simple",
    routing_strategy: str = "cascade",
    tools: None = None,  # Text only
    **kwargs
) -> AsyncIterator[StreamEvent]:
    """
    Stream text responses with cascading.
    
    Args:
        query: User input
        max_tokens: Response length limit
        temperature: Sampling temperature (0-1)
        complexity: Query complexity hint ("simple"/"moderate"/"complex")
        routing_strategy: "cascade" or "direct"
    
    Yields:
        StreamEvent objects with type-specific data
    """
```

### ToolStreamingManager (agent.tool_streaming_manager)

```python
async def stream(
    query: str,
    tools: List[Dict],
    max_tokens: int = 1000,
    temperature: float = 0.7,
    tool_choice: Optional[Dict] = None,
    execute_tools: bool = True,
    max_turns: int = 5,
    **kwargs
) -> AsyncIterator[ToolStreamEvent]:
    """
    Stream tool calls with automatic execution.
    
    Args:
        query: User input
        tools: OpenAI-format tool definitions
        max_tokens: Response length limit
        temperature: Sampling temperature
        tool_choice: {"type": "auto"/"required"/"function", "function": {...}}
        execute_tools: Auto-execute tools vs manual control
        max_turns: Max tool call loops
    
    Yields:
        ToolStreamEvent objects with tool-specific data
    """
```

## 🛠️ Error Handling

```python
try:
    async for event in agent.text_streaming_manager.stream(query):
        if event.type == StreamEventType.ERROR:
            print(f"Error: {event.content}")
            break
        
        # Process events...

except Exception as e:
    print(f"Streaming failed: {e}")
    # Fallback to non-streaming
    result = await agent.execute(query)
```

## 📚 Examples

See `examples/` directory:
- `streaming_text_basic.py` - Basic text streaming
- `streaming_text_advanced.py` - Advanced features
- `streaming_tools_basic.py` - Basic tool streaming
- `streaming_tools_executor.py` - Custom executor
- `streaming_tools_multiturn.py` - Multi-turn conversations

## 🤝 Contributing

When adding new features:
1. Add to appropriate module (`base.py`, `tools.py`, `utils.py`)
2. Update `__init__.py` exports
3. Add tests in `tests/test_streaming_*.py`
4. Update this README
5. Add example in `examples/`

## 📄 License

Part of CascadeFlow - see main LICENSE file.

---

**Status**: ✅ Production Ready  
**Version**: 2.0.0  
**Last Updated**: October 2025