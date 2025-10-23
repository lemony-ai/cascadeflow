"""
Comprehensive tests for cascadeflow/tools/ directory.

Tests all tool system components:
- ToolConfig (config.py) ✅
- ToolCall (call.py)
- ToolResult (result.py) ✅
- ToolExecutor (executor.py)

Run with: pytest tests/test_tools_system.py -v -s
"""

from typing import Any

import pytest

# Import the tools system
try:
    from cascadeflow.tools.call import ToolCall
    from cascadeflow.tools.config import ToolConfig
    from cascadeflow.tools.executor import ToolExecutor
    from cascadeflow.tools.result import ToolResult

    TOOLS_AVAILABLE = True
except ImportError as e:
    TOOLS_AVAILABLE = False
    ToolConfig = None
    ToolCall = None
    ToolResult = None
    ToolExecutor = None
    print(f"❌ Tools module import failed: {e}")


# Helper functions (prefixed with _ so pytest doesn't think they're tests)
def _calculator(operation: str, x: float, y: float) -> float:
    """Simple calculator for testing."""
    ops = {
        "add": lambda a, b: a + b,
        "subtract": lambda a, b: a - b,
        "multiply": lambda a, b: a * b,
        "divide": lambda a, b: a / b if b != 0 else float("inf"),
    }
    if operation not in ops:
        raise ValueError(f"Unknown operation: {operation}")
    return ops[operation](x, y)


def _get_weather(location: str, unit: str = "celsius") -> dict[str, Any]:
    """Simple weather function for testing."""
    temp = 22 if unit == "celsius" else 72
    return {
        "location": location,
        "temperature": temp,
        "unit": unit,
        "condition": "sunny",
        "humidity": 65,
    }


# Skip all tests if tools not available
pytestmark = pytest.mark.skipif(
    not TOOLS_AVAILABLE, reason="Tools module not fully implemented yet"
)


SAMPLE_TOOL_SCHEMA = {
    "name": "get_weather",
    "description": "Get weather for a location",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {"type": "string"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["location"],
    },
}


# ============================================================================
# ToolConfig Tests
# ============================================================================


class TestToolConfig:
    """Test ToolConfig class."""

    def test_create_basic_tool_config(self):
        """Test creating basic tool config."""
        tool = ToolConfig(
            name="get_weather",
            description="Get weather",
            parameters=SAMPLE_TOOL_SCHEMA["parameters"],
        )

        assert tool.name == "get_weather"
        assert tool.description == "Get weather"
        print(f"\n✅ Created tool config: {tool.name}")

    def test_create_tool_config_with_function(self):
        """Test creating tool config with actual function."""
        tool = ToolConfig(
            name="get_weather",
            description="Get weather",
            parameters=SAMPLE_TOOL_SCHEMA["parameters"],
            function=_get_weather,
        )

        assert tool.function is not None
        assert callable(tool.function)
        print(f"\n✅ Tool config with function: {tool.name}")

    def test_tool_config_with_calculator(self):
        """Test tool config with calculator."""
        tool = ToolConfig(
            name="calculator",
            description="Perform calculations",
            parameters={
                "type": "object",
                "properties": {
                    "operation": {"type": "string"},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                },
            },
            function=_calculator,
        )

        assert tool.name == "calculator"
        result = tool.function(operation="add", x=5, y=3)
        assert result == 8
        print(f"\n✅ Calculator tool: 5 + 3 = {result}")


# ============================================================================
# ToolCall Tests
# ============================================================================


class TestToolCall:
    """Test ToolCall class."""

    def test_create_tool_call(self):
        """Test creating tool call with provider_format."""
        call = ToolCall(
            id="call_123",
            name="get_weather",
            arguments={"location": "Paris", "unit": "celsius"},
            provider_format="universal",  # Add required parameter
        )

        assert call.id == "call_123"
        assert call.name == "get_weather"
        assert call.arguments["location"] == "Paris"
        print(f"\n✅ Created tool call: {call.name}(location={call.arguments['location']})")

    def test_tool_call_with_openai_format(self):
        """Test tool call with OpenAI format."""
        call = ToolCall(
            id="call_openai",
            name="calculator",
            arguments={"operation": "add", "x": 5, "y": 3},
            provider_format="openai",
        )

        assert call.provider_format == "openai"
        print("\n✅ Tool call with OpenAI format")

    def test_tool_call_with_anthropic_format(self):
        """Test tool call with Anthropic format."""
        call = ToolCall(
            id="call_anthropic",
            name="get_weather",
            arguments={"location": "Tokyo"},
            provider_format="anthropic",
        )

        assert call.provider_format == "anthropic"
        print("\n✅ Tool call with Anthropic format")


# ============================================================================
# ToolResult Tests
# ============================================================================


class TestToolResult:
    """Test ToolResult class."""

    def test_create_successful_result(self):
        """Test creating successful tool result."""
        result = ToolResult(
            call_id="call_123", name="get_weather", result={"temperature": 20, "condition": "Sunny"}
        )

        assert result.call_id == "call_123"
        assert result.name == "get_weather"
        assert result.result["temperature"] == 20
        assert result.error is None
        print(f"\n✅ Successful result: {result.result}")

    def test_create_error_result(self):
        """Test creating error tool result."""
        result = ToolResult(
            call_id="call_123", name="get_weather", result=None, error="API unavailable"
        )

        assert result.call_id == "call_123"
        assert result.error == "API unavailable"
        print(f"\n✅ Error result: {result.error}")

    def test_result_with_calculator_output(self):
        """Test result with calculator output."""
        result = ToolResult(call_id="call_calc", name="calculator", result=42.0)

        assert result.result == 42.0
        assert result.error is None
        print(f"\n✅ Calculator result: {result.result}")


# ============================================================================
# ToolExecutor Tests
# ============================================================================


class TestToolExecutor:
    """Test ToolExecutor class."""

    @pytest.fixture
    def executor(self):
        """Create tool executor with test tools."""
        tools = [
            ToolConfig(
                name="get_weather",
                description="Get weather",
                parameters=SAMPLE_TOOL_SCHEMA["parameters"],
                function=_get_weather,
            ),
            ToolConfig(
                name="calculator",
                description="Calculate",
                parameters={
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string"},
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                    },
                },
                function=_calculator,
            ),
        ]
        return ToolExecutor(tools)

    @pytest.mark.asyncio
    async def test_execute_weather_tool(self, executor):
        """Test executing weather tool."""
        call = ToolCall(
            id="call_weather",
            name="get_weather",
            arguments={"location": "Paris", "unit": "celsius"},
            provider_format="universal",
        )

        result = await executor.execute(call)

        assert result.call_id == "call_weather"
        assert result.name == "get_weather"
        assert result.error is None
        assert result.result["location"] == "Paris"
        assert result.result["temperature"] == 22
        print(f"\n✅ Weather tool executed: {result.result}")

    @pytest.mark.asyncio
    async def test_execute_calculator_tool(self, executor):
        """Test executing calculator tool."""
        call = ToolCall(
            id="call_calc",
            name="calculator",
            arguments={"operation": "add", "x": 15, "y": 27},
            provider_format="universal",
        )

        result = await executor.execute(call)

        assert result.call_id == "call_calc"
        assert result.name == "calculator"
        assert result.error is None
        assert result.result == 42.0
        print(f"\n✅ Calculator executed: 15 + 27 = {result.result}")

    @pytest.mark.asyncio
    async def test_execute_multiply(self, executor):
        """Test calculator multiply operation."""
        call = ToolCall(
            id="call_mult",
            name="calculator",
            arguments={"operation": "multiply", "x": 7, "y": 6},
            provider_format="universal",
        )

        result = await executor.execute(call)

        assert result.result == 42.0
        print(f"\n✅ Calculator multiply: 7 × 6 = {result.result}")

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self, executor):
        """Test executing tool that doesn't exist."""
        call = ToolCall(
            id="call_404", name="nonexistent_tool", arguments={}, provider_format="universal"
        )

        result = await executor.execute(call)

        assert result.error is not None
        assert "not found" in result.error.lower()
        print(f"\n✅ Nonexistent tool handled: {result.error}")

    @pytest.mark.asyncio
    async def test_execute_tool_with_error(self, executor):
        """Test executing tool that raises error."""
        call = ToolCall(
            id="call_err",
            name="calculator",
            arguments={"operation": "invalid_op", "x": 1, "y": 2},
            provider_format="universal",
        )

        result = await executor.execute(call)

        assert result.error is not None
        print(f"\n✅ Tool error handled: {result.error}")

    @pytest.mark.asyncio
    async def test_execute_divide_by_zero(self, executor):
        """Test calculator divide by zero handling."""
        call = ToolCall(
            id="call_div0",
            name="calculator",
            arguments={"operation": "divide", "x": 10, "y": 0},
            provider_format="universal",
        )

        result = await executor.execute(call)

        # Should handle gracefully (returns inf)
        assert result.error is None
        assert result.result == float("inf")
        print(f"\n✅ Divide by zero handled: result = {result.result}")

    @pytest.mark.asyncio
    async def test_execute_parallel_tools(self, executor):
        """Test executing multiple tools in parallel."""
        if not hasattr(executor, "execute_parallel"):
            pytest.skip("Parallel execution not implemented")

        calls = [
            ToolCall(
                id="call_p1",
                name="get_weather",
                arguments={"location": "Paris"},
                provider_format="universal",
            ),
            ToolCall(
                id="call_p2",
                name="calculator",
                arguments={"operation": "add", "x": 2, "y": 2},
                provider_format="universal",
            ),
        ]

        results = await executor.execute_parallel(calls)

        assert len(results) == 2
        assert results[0].error is None
        assert results[1].result == 4.0
        print(f"\n✅ Parallel execution: {len(results)} tools executed")


# ============================================================================
# Integration Tests
# ============================================================================


class TestToolsIntegration:
    """Integration tests for complete tool workflows."""

    @pytest.mark.asyncio
    async def test_complete_weather_workflow(self):
        """Test complete workflow with weather tool."""
        tool = ToolConfig(
            name="get_weather",
            description="Get weather",
            parameters=SAMPLE_TOOL_SCHEMA["parameters"],
            function=_get_weather,
        )

        executor = ToolExecutor([tool])

        call = ToolCall(
            id="call_integration",
            name="get_weather",
            arguments={"location": "Tokyo", "unit": "celsius"},
            provider_format="universal",
        )

        result = await executor.execute(call)

        assert result.error is None
        assert result.result["location"] == "Tokyo"
        assert result.result["temperature"] == 22

        print("\n✅ Complete weather workflow:")
        print(f"   Location: {call.arguments['location']}")
        print(f"   Result: {result.result}")

    @pytest.mark.asyncio
    async def test_complete_calculator_workflow(self):
        """Test complete workflow with calculator."""
        tool = ToolConfig(
            name="calculator",
            description="Calculate",
            parameters={"type": "object"},
            function=_calculator,
        )

        executor = ToolExecutor([tool])

        call = ToolCall(
            id="call_calc_workflow",
            name="calculator",
            arguments={"operation": "multiply", "x": 12, "y": 34},
            provider_format="universal",
        )

        result = await executor.execute(call)

        assert result.error is None
        assert result.result == 408.0

        print("\n✅ Complete calculator workflow:")
        print(f"   Calculation: {call.arguments['x']} × {call.arguments['y']}")
        print(f"   Result: {result.result}")

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self):
        """Test error handling throughout the workflow."""
        tool = ToolConfig(
            name="calculator",
            description="Calculate",
            parameters={"type": "object"},
            function=_calculator,
        )

        executor = ToolExecutor([tool])

        call = ToolCall(
            id="call_error_test",
            name="calculator",
            arguments={"operation": "power", "x": 2, "y": 3},
            provider_format="universal",
        )

        result = await executor.execute(call)

        assert result.error is not None
        assert "Unknown operation" in result.error or "operation" in result.error.lower()

        print("\n✅ Error handling workflow:")
        print(f"   Error caught: {result.error[:60]}...")

    @pytest.mark.asyncio
    async def test_multi_tool_workflow(self):
        """Test workflow with multiple different tools."""
        tools = [
            ToolConfig(
                name="get_weather",
                description="Get weather",
                parameters=SAMPLE_TOOL_SCHEMA["parameters"],
                function=_get_weather,
            ),
            ToolConfig(
                name="calculator",
                description="Calculate",
                parameters={"type": "object"},
                function=_calculator,
            ),
        ]

        executor = ToolExecutor(tools)

        # Execute weather
        weather_call = ToolCall(
            id="call_w",
            name="get_weather",
            arguments={"location": "London"},
            provider_format="universal",
        )
        weather_result = await executor.execute(weather_call)

        # Execute calculation
        calc_call = ToolCall(
            id="call_c",
            name="calculator",
            arguments={"operation": "subtract", "x": 100, "y": 42},
            provider_format="universal",
        )
        calc_result = await executor.execute(calc_call)

        assert weather_result.error is None
        assert calc_result.error is None
        assert weather_result.result["location"] == "London"
        assert calc_result.result == 58.0

        print("\n✅ Multi-tool workflow:")
        print(
            f"   Weather: {weather_result.result['location']} - {weather_result.result['temperature']}°C"
        )
        print(f"   Calculation: 100 - 42 = {calc_result.result}")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
