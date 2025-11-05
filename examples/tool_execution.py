"""
Tool Execution Example - Complete Workflow
==========================================

Demonstrates actual tool execution with cascadeflow's ToolExecutor.
Shows the complete lifecycle: definition → detection → execution → response.

What it demonstrates:
- Creating executable tools with ToolConfig
- Using ToolExecutor to run tool calls
- Multi-turn conversations with tools
- Feeding tool results back to the model
- Error handling and validation
- Cost tracking for tool-based queries

Requirements:
    - cascadeflow[all]
    - OpenAI API key

Setup:
    pip install cascadeflow[all]
    export OPENAI_API_KEY="sk-..."
    python examples/tool_execution.py

Expected Flow:
    1. User asks question requiring tools
    2. Model generates tool calls
    3. ToolExecutor runs the tools
    4. Results fed back to model
    5. Model generates final answer

Key Differences from streaming_tools.py:
    - streaming_tools.py: Shows tool calls FORMING (detection only)
    - tool_execution.py: Actually EXECUTES the tools (complete workflow)

Documentation:
    📖 Tool Guide: docs/guides/tools.md
    📖 Streaming Guide: docs/guides/streaming.md#tool-execution
    📚 Examples README: examples/README.md
"""

import asyncio
import os
from datetime import datetime

from cascadeflow import CascadeAgent, ModelConfig
from cascadeflow.tools import ToolCall, ToolCallFormat, ToolConfig, ToolExecutor

# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: Define Tool Functions (Actual Implementations)
# ═══════════════════════════════════════════════════════════════════════════
# These are the real Python functions that will be executed when tools are called


def get_weather(location: str, unit: str = "celsius") -> dict:
    """
    Get current weather for a location.

    In production, this would call a real weather API.
    For this example, we return mock data.

    Args:
        location: City name (e.g., "Paris", "Tokyo")
        unit: Temperature unit ("celsius" or "fahrenheit")

    Returns:
        Weather data dictionary
    """
    # Mock weather data (in production, call real API)
    mock_data = {
        "paris": {"temp": 18, "condition": "Cloudy", "humidity": 65},
        "tokyo": {"temp": 24, "condition": "Sunny", "humidity": 50},
        "london": {"temp": 12, "condition": "Rainy", "humidity": 80},
        "new york": {"temp": 22, "condition": "Partly Cloudy", "humidity": 55},
        "san francisco": {"temp": 16, "condition": "Foggy", "humidity": 70},
    }

    location_lower = location.lower()
    data = mock_data.get(location_lower, {"temp": 20, "condition": "Unknown", "humidity": 60})

    # Convert to Fahrenheit if requested
    if unit.lower() == "fahrenheit":
        data["temp"] = int(data["temp"] * 9 / 5 + 32)
        data["unit"] = "°F"
    else:
        data["unit"] = "°C"

    return {
        "location": location,
        "temperature": data["temp"],
        "unit": data["unit"],
        "condition": data["condition"],
        "humidity": data["humidity"],
    }


def calculate(operation: str, x: float, y: float) -> dict:
    """
    Perform mathematical calculations.

    Args:
        operation: Math operation ("add", "subtract", "multiply", "divide")
        x: First number
        y: Second number

    Returns:
        Calculation result
    """
    operations = {
        "add": lambda a, b: a + b,
        "subtract": lambda a, b: a - b,
        "multiply": lambda a, b: a * b,
        "divide": lambda a, b: a / b if b != 0 else None,
    }

    op_func = operations.get(operation.lower())
    if not op_func:
        return {"error": f"Unknown operation: {operation}"}

    result = op_func(x, y)
    if result is None:
        return {"error": "Division by zero"}

    return {"operation": operation, "x": x, "y": y, "result": result}


def get_current_time(timezone: str = "UTC") -> dict:
    """
    Get current time in specified timezone.

    Args:
        timezone: Timezone name (simplified for example)

    Returns:
        Current time information
    """
    now = datetime.now()

    # Simplified timezone offsets (in production, use pytz)
    offsets = {
        "utc": 0,
        "est": -5,
        "pst": -8,
        "cet": 1,
        "jst": 9,
    }

    offset = offsets.get(timezone.lower(), 0)
    adjusted_time = now.replace(hour=(now.hour + offset) % 24)

    return {
        "timezone": timezone.upper(),
        "time": adjusted_time.strftime("%H:%M:%S"),
        "date": adjusted_time.strftime("%Y-%m-%d"),
        "day_of_week": adjusted_time.strftime("%A"),
    }


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2: Create ToolConfig Objects (Schemas + Functions)
# ═══════════════════════════════════════════════════════════════════════════
# ToolConfig combines the schema (what the model sees) with the actual function


TOOL_CONFIGS = [
    ToolConfig(
        name="get_weather",
        description="Get current weather information for a specific location",
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name (e.g., 'Paris', 'Tokyo', 'New York')",
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit (default: celsius)",
                },
            },
            "required": ["location"],
        },
        function=get_weather,  # ← Link to actual function
    ),
    ToolConfig(
        name="calculate",
        description="Perform basic mathematical calculations",
        parameters={
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                    "description": "Mathematical operation to perform",
                },
                "x": {"type": "number", "description": "First number"},
                "y": {"type": "number", "description": "Second number"},
            },
            "required": ["operation", "x", "y"],
        },
        function=calculate,
    ),
    ToolConfig(
        name="get_current_time",
        description="Get current time in a specific timezone",
        parameters={
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "enum": ["UTC", "EST", "PST", "CET", "JST"],
                    "description": "Timezone name (default: UTC)",
                }
            },
            "required": [],
        },
        function=get_current_time,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3: Extract Tool Schemas (For Model)
# ═══════════════════════════════════════════════════════════════════════════
# The model needs schemas in universal format (without the function reference)


def extract_tool_schemas(tool_configs):
    """Extract just the schemas (name, description, parameters) for the model."""
    return [
        {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
        for tool in tool_configs
    ]


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4: Execute Tool Calls with ToolExecutor
# ═══════════════════════════════════════════════════════════════════════════


async def execute_tool_calls(tool_calls, executor):
    """
    Execute a list of tool calls and return results.

    Args:
        tool_calls: List of tool call dictionaries from model
        executor: ToolExecutor instance

    Returns:
        List of ToolResult objects
    """
    results = []

    for tool_call in tool_calls:
        print(f"\n  🔧 Executing: {tool_call['name']}")
        print(f"     Arguments: {tool_call['arguments']}")

        # Convert dict to ToolCall object
        tc = ToolCall(
            id=tool_call.get("id", f"call_{len(results)}"),
            name=tool_call["name"],
            arguments=tool_call["arguments"],
            provider_format=ToolCallFormat.OPENAI,
        )

        # Execute the tool
        result = await executor.execute(tc)

        if result.success:
            print(f"     ✅ Result: {result.result}")
        else:
            print(f"     ❌ Error: {result.error}")

        results.append(result)

    return results


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5: Multi-Turn Conversation Loop
# ═══════════════════════════════════════════════════════════════════════════


async def run_tool_conversation(agent, executor, query, tools, max_turns=7):
    """
    Run a complete tool conversation with multiple turns.

    Args:
        agent: CascadeAgent instance
        executor: ToolExecutor instance
        query: Initial user query
        tools: List of tool schemas
        max_turns: Maximum conversation turns

    Returns:
        Final response and metadata
    """
    print(f"\n{'='*70}")
    print(f"🔍 Query: {query}")
    print(f"{'='*70}\n")

    messages = [{"role": "user", "content": query}]
    total_cost = 0.0
    turn = 0

    while turn < max_turns:
        turn += 1
        print(f"\n--- Turn {turn} ---")

        # Get model response with tools
        result = await agent.run(
            query=" ".join([m["content"] for m in messages if m["role"] == "user"]),
            tools=tools,
            max_tokens=500,
            temperature=0.7,
        )

        total_cost += result.total_cost

        # Check if model wants to use tools
        if result.tool_calls and len(result.tool_calls) > 0:
            print(f"\n💭 Model wants to call {len(result.tool_calls)} tool(s):")

            # Execute the tools
            tool_results = await execute_tool_calls(result.tool_calls, executor)

            # Add assistant message with tool calls
            messages.append(
                {
                    "role": "assistant",
                    "content": result.content or "",
                    "tool_calls": result.tool_calls,
                }
            )

            # Add tool results as messages
            for tool_result in tool_results:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_result.call_id,
                        "name": tool_result.name,
                        "content": str(tool_result.result),
                    }
                )

            # Continue to next turn (model will generate final answer)
            continue

        else:
            # Model generated final answer (no more tools)
            print("\n✅ Final Answer:")
            print(f"   {result.content}\n")

            return {
                "answer": result.content,
                "turns": turn,
                "total_cost": total_cost,
                "model_used": result.model_used,
            }

    # Max turns reached
    print(f"\n⚠️  Reached maximum turns ({max_turns})")
    return {
        "answer": "Conversation exceeded maximum turns",
        "turns": turn,
        "total_cost": total_cost,
        "model_used": result.model_used,
    }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════


async def main():
    """
    Main example demonstrating complete tool execution workflow.
    """

    print("🌊 cascadeflow Tool Execution Example")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────────────
    # Setup: Check API key
    # ─────────────────────────────────────────────────────────────────────

    if not os.getenv("OPENAI_API_KEY"):
        print("\n❌ Error: OPENAI_API_KEY not found")
        print("   Set it with: export OPENAI_API_KEY='sk-...'")
        return

    print("\n✓ OpenAI API key found")

    # ─────────────────────────────────────────────────────────────────────
    # Setup: Create Agent
    # ─────────────────────────────────────────────────────────────────────

    print("\n📋 Setting up agent with 2-tier cascade...")

    agent = CascadeAgent(
        models=[
            ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.00015),
            ModelConfig(name="gpt-4o", provider="openai", cost=0.00625),
        ]
    )

    print("   ✓ Tier 1: gpt-4o-mini (fast & cheap)")
    print("   ✓ Tier 2: gpt-4o (powerful)")

    # ─────────────────────────────────────────────────────────────────────
    # Setup: Create ToolExecutor
    # ─────────────────────────────────────────────────────────────────────

    print("\n🔧 Creating tool executor with 3 tools...")

    executor = ToolExecutor(TOOL_CONFIGS)

    print("   ✓ get_weather - Get weather for any city")
    print("   ✓ calculate - Basic math operations")
    print("   ✓ get_current_time - Get time in timezone")

    # ─────────────────────────────────────────────────────────────────────
    # Setup: Extract Tool Schemas
    # ─────────────────────────────────────────────────────────────────────

    tools = extract_tool_schemas(TOOL_CONFIGS)

    print(f"\n📝 Tool schemas ready ({len(tools)} tools)")

    # ─────────────────────────────────────────────────────────────────────
    # Example 1: Single Tool Call
    # ─────────────────────────────────────────────────────────────────────

    print("\n\n" + "=" * 70)
    print("Example 1: Single Tool Call")
    print("=" * 70)

    result1 = await run_tool_conversation(
        agent=agent,
        executor=executor,
        query="What's the weather in Paris?",
        tools=tools,
    )

    print("\n📊 Example 1 Stats:")
    print(f"   Turns: {result1['turns']}")
    print(f"   Model: {result1['model_used']}")
    print(f"   Cost: ${result1['total_cost']:.6f}")

    # ─────────────────────────────────────────────────────────────────────
    # Example 2: Multiple Tool Calls
    # ─────────────────────────────────────────────────────────────────────

    print("\n\n" + "=" * 70)
    print("Example 2: Multiple Tool Calls")
    print("=" * 70)

    result2 = await run_tool_conversation(
        agent=agent,
        executor=executor,
        query="Compare the weather in Paris and Tokyo, then tell me the time in JST.",
        tools=tools,
    )

    print("\n📊 Example 2 Stats:")
    print(f"   Turns: {result2['turns']}")
    print(f"   Model: {result2['model_used']}")
    print(f"   Cost: ${result2['total_cost']:.6f}")

    # ─────────────────────────────────────────────────────────────────────
    # Example 3: Calculation Tool
    # ─────────────────────────────────────────────────────────────────────

    print("\n\n" + "=" * 70)
    print("Example 3: Calculation Tool")
    print("=" * 70)

    result3 = await run_tool_conversation(
        agent=agent,
        executor=executor,
        query="What is 12.5 multiplied by 8.3?",
        tools=tools,
    )

    print("\n📊 Example 3 Stats:")
    print(f"   Turns: {result3['turns']}")
    print(f"   Model: {result3['model_used']}")
    print(f"   Cost: ${result3['total_cost']:.6f}")

    # ─────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────

    total_cost = result1["total_cost"] + result2["total_cost"] + result3["total_cost"]

    print("\n\n" + "=" * 70)
    print("📊 Overall Summary")
    print("=" * 70)
    print("\n✓ Completed 3 examples with tool execution")
    print(f"✓ Total cost: ${total_cost:.6f}")
    print("✓ Tools executed: Weather, Time, Calculate")
    print("✓ Multi-turn conversations handled automatically")

    # ─────────────────────────────────────────────────────────────────────
    # Key Takeaways
    # ─────────────────────────────────────────────────────────────────────

    print("\n\n🎓 Key takeaways:")
    print("\n  Tool Execution Workflow:")
    print("  ├─ Define functions: Real Python functions")
    print("  ├─ Create ToolConfig: Link function + schema")
    print("  ├─ Create ToolExecutor: Manages execution")
    print("  ├─ Extract schemas: For model (universal format)")
    print("  └─ Run conversation: Multi-turn with tools")

    print("\n  ToolConfig vs Tool Schema:")
    print("  ├─ ToolConfig: Python object with function reference")
    print("  │  → Used by ToolExecutor to run tools")
    print("  └─ Tool Schema: JSON dict (name, description, parameters)")
    print("     → Sent to model (no function reference)")

    print("\n  Multi-Turn Flow:")
    print("  ├─ Turn 1: User query → Model generates tool calls")
    print("  ├─ Turn 2: Execute tools → Feed results back")
    print("  └─ Turn 3: Model generates final answer with tool data")

    print("\n  Error Handling:")
    print("  ├─ Tool not found → Clear error message")
    print("  ├─ Invalid arguments → Function raises exception")
    print("  ├─ Division by zero → Handled gracefully")
    print("  └─ Max turns reached → Prevents infinite loops")

    print("\n  Cost Optimization:")
    print("  ├─ Cascade still works with tools")
    print("  ├─ Simple queries → Cheap model")
    print("  └─ Complex queries → Expensive model")

    print("\n📚 Learn more:")
    print("  • docs/guides/tools.md - Complete tool guide")
    print("  • examples/streaming_tools.py - Tool call streaming")
    print("  • tests/test_tools.py - Tool system tests\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        print("\n💡 Tip: Make sure OPENAI_API_KEY is set correctly")
