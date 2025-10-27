# CascadeAgent (Python)

The main agent class for intelligent AI model cascading with automatic cost optimization.

## Class: `CascadeAgent`

```python
from cascadeflow import CascadeAgent, ModelConfig
```

### Constructor

```python
CascadeAgent(
    models: List[ModelConfig],
    quality: Optional[QualityConfig] = None,
    cascade: Optional[CascadeConfig] = None
)
```

**Parameters:**
- `models` (`List[ModelConfig]`, required): List of models to cascade through, automatically sorted by cost
- `quality` (`QualityConfig`, optional): Quality validation configuration
- `cascade` (`CascadeConfig`, optional): Advanced cascade settings

**Example:**
```python
from cascadeflow import CascadeAgent, ModelConfig

agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig(name="gpt-4o", provider="openai", cost=0.00625)
])
```

---

## Methods

### `run()`

Execute a query with automatic cascading.

```python
async def run(
    prompt: str | List[Message],
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    system_prompt: Optional[str] = None,
    tools: Optional[List[Dict]] = None,
    force_direct: bool = False
) -> CascadeResult
```

**Parameters:**
- `prompt` (`str` or `List[Message]`): Query text or message list
- `max_tokens` (`int`, optional): Maximum tokens to generate
- `temperature` (`float`, optional): Temperature (0-2), default: 0.7
- `system_prompt` (`str`, optional): System prompt override
- `tools` (`List[Dict]`, optional): Tools/functions available for calling
- `force_direct` (`bool`, optional): Skip cascade, use best model directly

**Returns:** `CascadeResult` - Result object with content, costs, and metrics

**Example:**
```python
# Basic usage
result = await agent.run("What is Python?")
print(result.content)
print(f"Cost: ${result.total_cost:.6f}")

# With options
result = await agent.run(
    "Explain quantum computing",
    max_tokens=500,
    temperature=0.3,
    system_prompt="You are a physics expert"
)
```

---

### `stream()`

Stream responses with real-time events.

```python
async def stream(
    prompt: str | List[Message],
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    system_prompt: Optional[str] = None,
    tools: Optional[List[Dict]] = None
) -> AsyncIterator[StreamEvent]
```

**Parameters:** Same as `run()`

**Yields:** `StreamEvent` - Stream events with incremental content

**Example:**
```python
async for event in agent.stream("Tell me a story"):
    if event.type == StreamEventType.CONTENT_DELTA:
        print(event.content, end="", flush=True)
    elif event.type == StreamEventType.COMPLETE:
        print(f"\nCost: ${event.total_cost:.6f}")
```

---

### `from_preset()`

Create agent from built-in preset configuration.

```python
@classmethod
def from_preset(cls, preset: PresetConfig) -> CascadeAgent
```

**Parameters:**
- `preset` (`PresetConfig`): Preset configuration (e.g., `PRESET_BEST_OVERALL`)

**Returns:** `CascadeAgent` - Configured agent instance

**Example:**
```python
from cascadeflow import CascadeAgent, PRESET_BEST_OVERALL, PRESET_ULTRA_FAST

# Balanced performance
agent = CascadeAgent.from_preset(PRESET_BEST_OVERALL)

# Optimized for speed
agent_fast = CascadeAgent.from_preset(PRESET_ULTRA_FAST)
```

---

## Complete Examples

### Basic Query

```python
from cascadeflow import CascadeAgent, ModelConfig

agent = CascadeAgent(models=[
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
    ModelConfig(name="gpt-4o", provider="openai", cost=0.00625)
])

result = await agent.run("What is the capital of France?")

print(f"Answer: {result.content}")
print(f"Model used: {result.model_used}")
print(f"Cost: ${result.total_cost:.6f}")
print(f"Savings: {result.cost_saved_percentage:.1f}%")
```

### With Quality Configuration

```python
from cascadeflow import CascadeAgent, ModelConfig, QualityConfig

agent = CascadeAgent(
    models=[
        ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
        ModelConfig(name="gpt-4o", provider="openai", cost=0.00625)
    ],
    quality=QualityConfig(
        threshold=0.8,  # Stricter quality requirements
        require_minimum_tokens=20
    )
)

result = await agent.run("Explain machine learning")
```

### Multi-Provider Setup

```python
agent = CascadeAgent(models=[
    # Groq (fastest)
    ModelConfig(name="llama-3.1-8b", provider="groq", cost=0.00005),
    # OpenAI (balanced)
    ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
    # Anthropic (quality)
    ModelConfig(name="claude-3-5-sonnet", provider="anthropic", cost=0.003)
])
```

### Tool Calling

```python
tools = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"}
            },
            "required": ["location"]
        }
    }
]

result = await agent.run(
    "What's the weather in San Francisco?",
    tools=tools
)

if result.has_tool_calls:
    for call in result.tool_calls:
        print(f"Tool: {call['name']}")
        print(f"Args: {call['arguments']}")
```

### Streaming with Events

```python
async for event in agent.stream("Write a short poem about AI"):
    match event.type:
        case StreamEventType.MODEL_SELECTED:
            print(f"Using model: {event.model}")

        case StreamEventType.CONTENT_DELTA:
            print(event.content, end="", flush=True)

        case StreamEventType.CASCADE_TRIGGERED:
            print("\n[Escalating to better model...]")

        case StreamEventType.COMPLETE:
            print(f"\nTotal cost: ${event.total_cost:.6f}")
```

---

## See Also

- [ModelConfig](./config.md) - Model configuration options
- [CascadeResult](./result.md) - Result object documentation
- [QualityConfig](./quality.md) - Quality validation settings
- [Streaming Guide](../../guides/streaming.md) - Streaming responses
- [Tools Guide](../../guides/tools.md) - Function calling
