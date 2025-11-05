# Tool Calling Guide

Complete guide to using tools (function calling) with cascadeflow.

---

## 📋 Table of Contents

### **Basic (Getting Started)**
1. [Introduction](#introduction)
2. [Quick Start](#quick-start)
3. [Core Concepts](#core-concepts)
4. [Defining Tools](#defining-tools)
5. [Tool Execution](#tool-execution)
6. [Multi-Turn Conversations](#multi-turn-conversations)

### **Advanced (Power Features)**
7. [Tool Streaming](#tool-streaming)
8. [Advanced Patterns](#advanced-patterns)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

# Basic Usage

Essential tool calling patterns for cascadeflow.

---

## Introduction

Tools (also called "function calling") allow AI models to interact with external systems, APIs, and data sources. cascadeflow provides a complete tool system that works seamlessly with cascades, streaming, and quality validation.

### What You Can Do With Tools

- 🌐 **Call External APIs**: Weather, stocks, search, etc.
- 🧮 **Perform Calculations**: Math, data analysis, conversions
- 💾 **Access Databases**: Query, update, retrieve data
- 🔧 **Execute Code**: Run scripts, process files, transform data
- 🤖 **Multi-Step Workflows**: Chain multiple tools together

### Key Features

- ✅ **Universal Format**: Works with all providers (OpenAI, Anthropic, Groq)
- ✅ **Automatic Conversion**: Provider-specific format handling
- ✅ **Quality Validation**: Built-in tool call validation
- ✅ **Cascade Compatible**: Tools work with all cascade types
- ✅ **Streaming Support**: Watch tool calls form in real-time
- ✅ **Parallel Execution**: Run multiple tools concurrently
- ✅ **Error Handling**: Robust error recovery

---

## Quick Start

### 3-Step Tool Setup

```python
from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.tools import ToolConfig, ToolExecutor

# Step 1: Define your function
def get_weather(location: str, unit: str = "celsius") -> dict:
    """Get weather for a location."""
    # Your implementation here
    return {"temp": 22, "condition": "sunny"}

# Step 2: Create ToolConfig
tool_config = ToolConfig(
    name="get_weather",
    description="Get current weather for a location",
    parameters={
        "type": "object",
        "properties": {
            "location": {"type": "string"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
        },
        "required": ["location"]
    },
    function=get_weather  # Link to actual function
)

# Step 3: Create executor and use with agent
executor = ToolExecutor([tool_config])

agent = CascadeAgent(models=[...])
result = await agent.run(
    "What's the weather in Paris?",
    tools=[{
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {...}
    }]
)

# Execute tool calls
for tool_call in result.tool_calls:
    tool_result = await executor.execute(tool_call)
    print(f"Result: {tool_result.result}")
```

---

## Core Concepts

### Tool Definition vs Tool Schema

**Important Distinction:**

1. **ToolConfig** (Python object with function):
    - Used by `ToolExecutor` to run tools
    - Contains actual function reference
    - Never sent to model

2. **Tool Schema** (JSON dict):
    - Sent to model to describe available tools
    - Contains only name, description, parameters
    - No function reference

```python
# ToolConfig - for execution
tool_config = ToolConfig(
    name="get_weather",
    description="Get weather",
    parameters={...},
    function=get_weather  # ← Actual function
)

# Tool Schema - for model
tool_schema = {
    "name": "get_weather",
    "description": "Get weather",
    "parameters": {...}
    # No function! Model doesn't see implementation
}
```

### Tool Call Lifecycle

```
1. User Query
   ↓
2. Model Generates Tool Calls
   ↓
3. Parse Tool Calls (ToolCall objects)
   ↓
4. Execute with ToolExecutor
   ↓
5. Format Results (ToolResult objects)
   ↓
6. Feed Back to Model
   ↓
7. Model Generates Final Answer
```

### Key Classes

| Class | Purpose | Contains |
|-------|---------|----------|
| `ToolConfig` | Tool definition | Schema + function |
| `ToolCall` | Model's request | Tool name + arguments |
| `ToolResult` | Execution result | Result or error |
| `ToolExecutor` | Execution engine | Runs tools |

---

## Defining Tools

### Method 1: Manual ToolConfig

```python
from cascadeflow.tools import ToolConfig

def calculate(operation: str, x: float, y: float) -> dict:
    """Perform a calculation."""
    ops = {
        "add": x + y,
        "subtract": x - y,
        "multiply": x * y,
        "divide": x / y if y != 0 else None
    }
    return {"result": ops[operation], "operation": operation}

tool = ToolConfig(
    name="calculate",
    description="Perform basic math operations",
    parameters={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["add", "subtract", "multiply", "divide"]
            },
            "x": {"type": "number"},
            "y": {"type": "number"}
        },
        "required": ["operation", "x", "y"]
    },
    function=calculate
)
```

### Method 2: Auto-Generate from Function

```python
from cascadeflow.tools import ToolConfig

def get_stock_price(symbol: str, currency: str = "USD") -> dict:
    """Get current stock price for a symbol."""
    # Implementation...
    return {"symbol": symbol, "price": 150.25, "currency": currency}

# Automatically extracts: name, description, parameters, required fields
tool = ToolConfig.from_function(get_stock_price)
```

### Method 3: Using Decorator

```python
from cascadeflow.tools import tool

@tool
def search_documents(query: str, limit: int = 10) -> list:
    """Search documents by keyword."""
    # Implementation...
    return [{"title": "Doc 1", "score": 0.95}]

# search_documents is now a ToolConfig object!
```

### Parameter Types

cascadeflow supports all JSON Schema types:

```python
parameters = {
    "type": "object",
    "properties": {
        # String
        "name": {"type": "string"},
        
        # Number (int or float)
        "age": {"type": "integer"},
        "price": {"type": "number"},
        
        # Boolean
        "active": {"type": "boolean"},
        
        # Enum (constrained values)
        "status": {
            "type": "string",
            "enum": ["pending", "approved", "rejected"]
        },
        
        # Array
        "tags": {
            "type": "array",
            "items": {"type": "string"}
        },
        
        # Nested object
        "address": {
            "type": "object",
            "properties": {
                "street": {"type": "string"},
                "city": {"type": "string"}
            }
        }
    },
    "required": ["name", "age"]  # Required fields
}
```

---

## Tool Execution

### Basic Execution

```python
from cascadeflow.tools import ToolExecutor, ToolCall, ToolCallFormat

# Create executor with tool configs
executor = ToolExecutor([tool1, tool2, tool3])

# Execute a tool call
tool_call = ToolCall(
    id="call_123",
    name="get_weather",
    arguments={"location": "Paris", "unit": "celsius"},
    provider_format=ToolCallFormat.OPENAI
)

result = await executor.execute(tool_call)

if result.success:
    print(f"Result: {result.result}")
else:
    print(f"Error: {result.error}")
```

### Parallel Execution

Execute multiple tools concurrently for better performance:

```python
tool_calls = [call1, call2, call3, call4]

# Execute up to 5 tools in parallel
results = await executor.execute_parallel(
    tool_calls,
    max_parallel=5
)

for result in results:
    if result.success:
        print(f"{result.name}: {result.result}")
```

### Error Handling

```python
result = await executor.execute(tool_call)

if not result.success:
    # Tool execution failed
    error_type = type(result.error).__name__
    error_msg = result.error
    
    if "not found" in error_msg:
        # Tool doesn't exist
        print(f"Unknown tool: {tool_call.name}")
    elif "arguments" in error_msg:
        # Invalid arguments
        print(f"Bad arguments: {tool_call.arguments}")
    else:
        # Other error
        print(f"Tool failed: {error_msg}")
```

### Sync vs Async Functions

ToolExecutor handles both automatically:

```python
# Synchronous function
def sync_tool(x: int) -> int:
    return x * 2

# Asynchronous function
async def async_tool(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# Both work with ToolExecutor!
executor = ToolExecutor([
    ToolConfig.from_function(sync_tool),
    ToolConfig.from_function(async_tool)
])
```

---

## Multi-Turn Conversations

Tools typically require multiple turns: request → execute → respond.

### Complete Multi-Turn Example

```python
async def tool_conversation(agent, executor, query, tools):
    """Run a complete tool conversation."""
    
    messages = [{"role": "user", "content": query}]
    max_turns = 3
    turn = 0
    
    while turn < max_turns:
        turn += 1
        
        # Get model response
        result = await agent.run(
            query=" ".join([m["content"] for m in messages if m["role"] == "user"]),
            tools=tools
        )
        
        # Check if model wants to use tools
        if result.tool_calls:
            # Execute tools
            tool_results = []
            for tool_call in result.tool_calls:
                tool_result = await executor.execute(tool_call)
                tool_results.append(tool_result)
            
            # Add assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": result.content or "",
                "tool_calls": result.tool_calls
            })
            
            # Add tool results
            for tool_result in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_result.call_id,
                    "name": tool_result.name,
                    "content": str(tool_result.result)
                })
            
            # Continue to next turn
            continue
        
        else:
            # Model generated final answer
            return result.content
    
    return "Max turns reached"
```

### Message Format

Different providers use different formats for tool results:

**OpenAI Format:**
```python
{
    "role": "tool",
    "tool_call_id": "call_123",
    "name": "get_weather",
    "content": "{'temp': 22, 'condition': 'sunny'}"
}
```

**Anthropic Format:**
```python
{
    "role": "user",
    "content": [{
        "type": "tool_result",
        "tool_use_id": "toolu_123",
        "content": "{'temp': 22, 'condition': 'sunny'}"
    }]
}
```

**cascadeflow handles this automatically:**
```python
# Automatically converts to correct format
tool_result.to_provider_message("openai")   # OpenAI format
tool_result.to_provider_message("anthropic") # Anthropic format
```

---

# Advanced Usage

Power features for tool calling in production.

---

## Tool Streaming

Watch tool calls form in real-time as the model generates them.

### Basic Tool Streaming

```python
from cascadeflow.streaming import ToolStreamEventType

async for event in agent.stream_events(query, tools=tools):
    match event.type:
        case ToolStreamEventType.TOOL_CALL_START:
            print(f"\n🔧 Calling: {event.tool_call['name']}")
        
        case ToolStreamEventType.TOOL_CALL_DELTA:
            # Arguments streaming in progressively
            print(event.delta, end='')
        
        case ToolStreamEventType.TOOL_CALL_COMPLETE:
            # Full tool call parsed
            tool = event.tool_call
            print(f"\n✓ Complete: {tool['name']}({tool['arguments']})")
        
        case ToolStreamEventType.TEXT_CHUNK:
            # Regular text response
            print(event.content, end='')
```

### Progressive Argument Display

```python
async for event in agent.stream_events(query, tools=tools):
    if event.type == ToolStreamEventType.TOOL_CALL_DELTA:
        # Show arguments as they arrive
        print(f"\rArguments: {event.partial_arguments}", end='')
```

See [`examples/streaming_tools.py`](../../examples/streaming_tools.py) for complete streaming example.

---

## Advanced Patterns

### Dynamic Tool Selection

Select tools based on query or context:

```python
def get_tools_for_query(query: str) -> list:
    """Select relevant tools for query."""
    all_tools = {
        "weather": weather_tools,
        "calculation": math_tools,
        "search": search_tools
    }
    
    # Simple keyword matching (use embedding similarity in production)
    if "weather" in query.lower():
        return all_tools["weather"]
    elif any(word in query.lower() for word in ["calculate", "multiply", "add"]):
        return all_tools["calculation"]
    else:
        return all_tools["search"]

# Use with agent
tools = get_tools_for_query(user_query)
result = await agent.run(user_query, tools=tools)
```

### Tool Chaining

Chain multiple tools together:

```python
async def chain_tools(agent, executor, query):
    """Execute tools in sequence."""
    
    # Step 1: Get weather
    result1 = await agent.run(
        "Get weather for Paris",
        tools=[weather_tool]
    )
    weather_data = await executor.execute(result1.tool_calls[0])
    
    # Step 2: Use weather in next query
    result2 = await agent.run(
        f"Given weather is {weather_data.result}, should I bring an umbrella?",
        tools=[]
    )
    
    return result2.content
```

### Conditional Tool Execution

Execute tools only if certain conditions are met:

```python
async def conditional_execution(agent, executor, query, tools):
    """Execute tools with validation."""
    
    result = await agent.run(query, tools=tools)
    
    for tool_call in result.tool_calls:
        # Validate before execution
        if not validate_tool_call(tool_call):
            print(f"Skipping unsafe tool: {tool_call.name}")
            continue
        
        # Check budget
        if estimate_cost(tool_call) > budget:
            print(f"Tool too expensive: {tool_call.name}")
            continue
        
        # Execute
        tool_result = await executor.execute(tool_call)
```

### Custom Tool Validators

Add custom validation logic:

```python
def validate_tool_arguments(tool_call: ToolCall, tool_config: ToolConfig) -> bool:
    """Custom validation logic."""
    
    # Check required fields
    for required in tool_config.parameters.get("required", []):
        if required not in tool_call.arguments:
            return False
    
    # Custom business logic
    if tool_call.name == "transfer_money":
        amount = tool_call.arguments.get("amount", 0)
        if amount > 10000:
            return False  # Block large transfers
    
    return True
```

---

## Best Practices

### 1. Clear Tool Descriptions

```python
# ❌ Bad
description = "Gets weather"

# ✅ Good
description = "Get current weather information for a specific location, including temperature, conditions, and humidity"
```

### 2. Validate Inputs

```python
def get_weather(location: str, unit: str = "celsius") -> dict:
    # Validate unit
    if unit not in ["celsius", "fahrenheit"]:
        raise ValueError(f"Invalid unit: {unit}. Must be 'celsius' or 'fahrenheit'.")
    
    # Validate location
    if not location or len(location) < 2:
        raise ValueError("Location must be at least 2 characters")
    
    # ... rest of implementation
```

### 3. Return Structured Data

```python
# ❌ Bad - string response
def get_weather(location: str) -> str:
    return "It's 22°C and sunny"

# ✅ Good - structured dict
def get_weather(location: str) -> dict:
    return {
        "location": location,
        "temperature": 22,
        "unit": "celsius",
        "condition": "sunny",
        "humidity": 65,
        "timestamp": "2025-10-21T14:30:00Z"
    }
```

### 4. Handle Errors Gracefully

```python
def call_external_api(url: str) -> dict:
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    
    except requests.Timeout:
        return {"error": "API timeout", "code": "TIMEOUT"}
    
    except requests.HTTPError as e:
        return {"error": f"HTTP {e.response.status_code}", "code": "HTTP_ERROR"}
    
    except Exception as e:
        return {"error": str(e), "code": "UNKNOWN"}
```

### 5. Add Timeouts

```python
async def slow_tool(query: str) -> dict:
    """Tool with timeout protection."""
    try:
        async with asyncio.timeout(10):  # 10 second timeout
            result = await expensive_operation(query)
            return result
    
    except asyncio.TimeoutError:
        return {"error": "Operation timed out", "code": "TIMEOUT"}
```

### 6. Log Tool Executions

```python
import logging

logger = logging.getLogger(__name__)

def get_weather(location: str) -> dict:
    logger.info(f"get_weather called with location={location}")
    
    try:
        result = fetch_weather_data(location)
        logger.info(f"get_weather succeeded: {result['condition']}")
        return result
    
    except Exception as e:
        logger.error(f"get_weather failed: {e}")
        raise
```

---

## Troubleshooting

### Tool Not Found

**Error:** `Tool 'xyz' not found`

**Cause:** Tool name in ToolCall doesn't match any ToolConfig

**Solution:**
```python
# Check available tools
print(f"Available tools: {list(executor.tools.keys())}")

# Verify tool name matches exactly
tool_config = ToolConfig(name="get_weather", ...)  # Must match exactly
```

### Invalid Arguments

**Error:** `TypeError: missing required argument`

**Cause:** Model didn't provide required parameters

**Solution:**
```python
# Add validation
def get_weather(location: str, unit: str = "celsius") -> dict:
    if not location:
        raise ValueError("location is required")
    # ... rest
```

### Tool Execution Timeout

**Error:** Tool hangs indefinitely

**Solution:**
```python
async def safe_tool(param: str) -> dict:
    try:
        async with asyncio.timeout(30):
            return await slow_operation(param)
    except asyncio.TimeoutError:
        return {"error": "Timeout", "code": "TIMEOUT"}
```

### Wrong Tool Schema Format

**Error:** `KeyError: 'name'` or tools not working

**Cause:** Using OpenAI format instead of universal format

**Solution:**
```python
# ❌ Wrong - OpenAI format
tools = [{
    "type": "function",
    "function": {"name": "...", ...}
}]

# ✅ Correct - Universal format
tools = [{
    "name": "get_weather",
    "description": "...",
    "parameters": {...}
}]
```

### Costs Higher Than Expected

**Issue:** Tool queries cost more than expected

**Cause:** Token-based pricing + multiple turns

**Solution:**
```python
# Track per-turn costs
total_cost = 0
for turn in range(max_turns):
    result = await agent.run(query, tools=tools)
    total_cost += result.total_cost
    print(f"Turn {turn}: ${result.total_cost:.6f}")

print(f"Total: ${total_cost:.6f}")
```

---

## Next Steps

- **Examples**: See [`examples/tool_execution.py`](../../examples/tool_execution.py) for complete working code
- **Streaming**: Read [Streaming Guide](streaming.md#tool-streaming) for real-time tool streaming
- **API Reference**: Check API docs for detailed class documentation

---

**Questions?** Open an issue on [GitHub](https://github.com/lemony-ai/cascadeflow/issues).