"""
Comprehensive tests for tool calling functionality (Step 1.3).

Tests cover:
- OpenAI provider tool integration
- Tool schema conversion (universal ↔ OpenAI format)
- Tool call parsing
- Complete end-to-end tool calling workflow
- Error handling
- Multi-turn conversations

Run with: pytest tests/test_tool_calling.py -v -s
"""

import json
import os

import pytest

# Load environment variables from .env
from dotenv import load_dotenv

load_dotenv()

from cascadeflow.exceptions import ModelError, ProviderError

from cascadeflow.providers.openai import OpenAIProvider

# ============================================================================
# Test Data - Universal Tool Format
# ============================================================================

SAMPLE_TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name or location"},
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit",
                },
            },
            "required": ["location"],
        },
    },
    {
        "name": "search_web",
        "description": "Search the web for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "calculate",
        "description": "Perform mathematical calculations",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate",
                }
            },
            "required": ["expression"],
        },
    },
]


# ============================================================================
# Unit Tests - Schema Conversion
# ============================================================================


class TestToolSchemaConversion:
    """Test tool schema conversion between universal and OpenAI formats."""

    @pytest.fixture
    def provider(self):
        """Create OpenAI provider instance."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")
        return OpenAIProvider(api_key=api_key)

    def test_convert_single_tool_to_openai(self, provider):
        """Test converting single tool from universal to OpenAI format."""
        tool = SAMPLE_TOOLS[0]  # get_weather

        openai_tools = provider._convert_tools_to_openai([tool])

        assert len(openai_tools) == 1
        assert openai_tools[0]["type"] == "function"
        assert "function" in openai_tools[0]

        func = openai_tools[0]["function"]
        assert func["name"] == "get_weather"
        assert func["description"] == "Get current weather for a location"
        assert "parameters" in func
        assert func["parameters"]["type"] == "object"
        assert "location" in func["parameters"]["properties"]

    def test_convert_multiple_tools_to_openai(self, provider):
        """Test converting multiple tools to OpenAI format."""
        openai_tools = provider._convert_tools_to_openai(SAMPLE_TOOLS)

        assert len(openai_tools) == 3

        # Check all tools have correct structure
        for openai_tool in openai_tools:
            assert openai_tool["type"] == "function"
            assert "function" in openai_tool
            assert "name" in openai_tool["function"]
            assert "description" in openai_tool["function"]
            assert "parameters" in openai_tool["function"]

    def test_convert_empty_tools_list(self, provider):
        """Test converting empty tools list."""
        openai_tools = provider._convert_tools_to_openai([])
        assert openai_tools == []

    def test_convert_none_tools(self, provider):
        """Test converting None tools."""
        openai_tools = provider._convert_tools_to_openai(None)
        assert openai_tools == []

    def test_openai_format_structure(self, provider):
        """Test that OpenAI format matches expected structure exactly."""
        tool = {
            "name": "test_function",
            "description": "A test function",
            "parameters": {"type": "object", "properties": {"arg1": {"type": "string"}}},
        }

        openai_tools = provider._convert_tools_to_openai([tool])

        # Verify exact structure
        expected = {
            "type": "function",
            "function": {
                "name": "test_function",
                "description": "A test function",
                "parameters": {"type": "object", "properties": {"arg1": {"type": "string"}}},
            },
        }

        assert openai_tools[0] == expected


# ============================================================================
# Unit Tests - Tool Call Parsing
# ============================================================================


class TestToolCallParsing:
    """Test parsing tool calls from OpenAI responses to universal format."""

    @pytest.fixture
    def provider(self):
        """Create OpenAI provider instance."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")
        return OpenAIProvider(api_key=api_key)

    def test_parse_single_tool_call(self, provider):
        """Test parsing single tool call from OpenAI format."""
        choice = {
            "message": {
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location": "Paris", "unit": "celsius"}',
                        },
                    }
                ]
            }
        }

        tool_calls = provider._parse_tool_calls(choice)

        assert tool_calls is not None
        assert len(tool_calls) == 1

        call = tool_calls[0]
        assert call["id"] == "call_abc123"
        assert call["type"] == "function"
        assert call["name"] == "get_weather"
        assert call["arguments"] == {"location": "Paris", "unit": "celsius"}

    def test_parse_multiple_tool_calls(self, provider):
        """Test parsing multiple parallel tool calls."""
        choice = {
            "message": {
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"location": "Paris"}'},
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "search_web",
                            "arguments": '{"query": "Paris weather"}',
                        },
                    },
                ]
            }
        }

        tool_calls = provider._parse_tool_calls(choice)

        assert len(tool_calls) == 2
        assert tool_calls[0]["name"] == "get_weather"
        assert tool_calls[1]["name"] == "search_web"

    def test_parse_no_tool_calls(self, provider):
        """Test parsing response with no tool calls."""
        choice = {"message": {"content": "Just a regular response"}}

        tool_calls = provider._parse_tool_calls(choice)
        assert tool_calls is None

    def test_parse_empty_arguments(self, provider):
        """Test parsing tool call with empty arguments."""
        choice = {
            "message": {
                "tool_calls": [
                    {
                        "id": "call_empty",
                        "type": "function",
                        "function": {"name": "no_args_function", "arguments": "{}"},
                    }
                ]
            }
        }

        tool_calls = provider._parse_tool_calls(choice)

        assert len(tool_calls) == 1
        assert tool_calls[0]["arguments"] == {}

    def test_parse_malformed_json_arguments(self, provider):
        """Test handling of malformed JSON in arguments."""
        choice = {
            "message": {
                "tool_calls": [
                    {
                        "id": "call_bad",
                        "type": "function",
                        "function": {
                            "name": "broken_function",
                            "arguments": '{"invalid": json}',  # Invalid JSON
                        },
                    }
                ]
            }
        }

        # Should handle error gracefully
        tool_calls = provider._parse_tool_calls(choice)

        # Either returns None or skips the broken call
        assert tool_calls is None or len(tool_calls) == 0


# ============================================================================
# Integration Tests - Real API Calls
# ============================================================================


class TestToolCallingIntegration:
    """Integration tests with real OpenAI API calls."""

    @pytest.fixture
    async def provider(self):
        """Create and cleanup OpenAI provider."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")

        provider = OpenAIProvider(api_key=api_key)
        yield provider
        await provider.client.aclose()

    @pytest.mark.asyncio
    async def test_simple_tool_call(self, provider):
        """Test basic tool calling with weather function."""
        tools = [
            {
                "name": "get_weather",
                "description": "Get current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            }
        ]

        messages = [{"role": "user", "content": "What's the weather in Paris?"}]

        response = await provider.complete_with_tools(
            messages=messages,
            tools=tools,
            model="gpt-4o-mini",
            temperature=0.0,  # Deterministic for testing
        )

        # Verify response structure
        assert response.provider == "openai"
        assert response.model == "gpt-4o-mini"
        assert response.tokens_used > 0
        assert response.cost > 0

        # Should have tool calls
        assert hasattr(response, "tool_calls")
        assert response.tool_calls is not None
        assert len(response.tool_calls) > 0

        # Check tool call structure
        tool_call = response.tool_calls[0]
        assert tool_call["name"] == "get_weather"
        assert "location" in tool_call["arguments"]
        assert "paris" in tool_call["arguments"]["location"].lower()

        print(f"\n✅ Tool called: {tool_call['name']}")
        print(f"   Arguments: {tool_call['arguments']}")

    @pytest.mark.asyncio
    async def test_parallel_tool_calls(self, provider):
        """Test multiple parallel tool calls."""
        tools = [
            {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            },
            {
                "name": "get_time",
                "description": "Get current time for a location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            },
        ]

        messages = [{"role": "user", "content": "What's the weather and time in Tokyo?"}]

        response = await provider.complete_with_tools(
            messages=messages, tools=tools, model="gpt-4o-mini", temperature=0.0
        )

        # May call one or both tools
        assert response.tool_calls is not None
        assert len(response.tool_calls) >= 1

        print(f"\n✅ Tools called: {[tc['name'] for tc in response.tool_calls]}")

    @pytest.mark.asyncio
    async def test_no_tool_needed(self, provider):
        """Test when model decides not to use tools."""
        tools = [
            {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            }
        ]

        messages = [{"role": "user", "content": "What is 2+2?"}]

        response = await provider.complete_with_tools(
            messages=messages, tools=tools, model="gpt-4o-mini", temperature=0.0
        )

        # Should respond without tool calls
        assert response.content  # Has regular text response
        assert response.tool_calls is None or len(response.tool_calls) == 0

        print(f"\n✅ No tools needed, response: {response.content[:50]}...")

    @pytest.mark.asyncio
    async def test_force_tool_usage(self, provider):
        """Test forcing specific tool usage with tool_choice."""
        tools = [
            {
                "name": "calculate",
                "description": "Perform a calculation",
                "parameters": {
                    "type": "object",
                    "properties": {"expression": {"type": "string"}},
                    "required": ["expression"],
                },
            }
        ]

        messages = [{"role": "user", "content": "What is 15 * 23?"}]

        response = await provider.complete_with_tools(
            messages=messages,
            tools=tools,
            model="gpt-4o-mini",
            tool_choice={"type": "function", "function": {"name": "calculate"}},
            temperature=0.0,
        )

        # Should force tool usage
        assert response.tool_calls is not None
        assert len(response.tool_calls) > 0
        assert response.tool_calls[0]["name"] == "calculate"

        print(f"\n✅ Forced tool call: {response.tool_calls[0]}")

    @pytest.mark.asyncio
    async def test_prevent_tool_usage(self, provider):
        """Test preventing tool usage with tool_choice='none'."""
        tools = [
            {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            }
        ]

        messages = [{"role": "user", "content": "What's the weather in Paris?"}]

        response = await provider.complete_with_tools(
            messages=messages,
            tools=tools,
            model="gpt-4o-mini",
            tool_choice="none",  # Prevent tool usage
            temperature=0.0,
        )

        # Should not call tools
        assert response.tool_calls is None or len(response.tool_calls) == 0
        assert response.content  # Should have text response instead

        print(f"\n✅ Tools prevented, text response: {response.content[:50]}...")


# ============================================================================
# Multi-Turn Conversation Tests
# ============================================================================


class TestMultiTurnToolConversations:
    """Test complete multi-turn conversations with tool calling."""

    @pytest.fixture
    async def provider(self):
        """Create and cleanup OpenAI provider."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")

        provider = OpenAIProvider(api_key=api_key)
        yield provider
        await provider.client.aclose()

    @pytest.mark.asyncio
    async def test_complete_tool_workflow(self, provider):
        """Test complete workflow: query → tool call → tool result → final answer."""
        tools = [
            {
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
        ]

        # Step 1: Initial query
        messages = [{"role": "user", "content": "What's the weather in London?"}]

        response1 = await provider.complete_with_tools(
            messages=messages, tools=tools, model="gpt-4o-mini", temperature=0.0
        )

        assert response1.tool_calls is not None
        tool_call = response1.tool_calls[0]

        print("\n📞 Step 1 - Tool call requested:")
        print(f"   Tool: {tool_call['name']}")
        print(f"   Args: {tool_call['arguments']}")

        # Step 2: Simulate tool execution
        tool_result = {"temperature": 18, "condition": "Partly cloudy", "humidity": 65}

        # Step 3: Add tool result to conversation
        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tool_call["id"],
                        "type": "function",
                        "function": {
                            "name": tool_call["name"],
                            "arguments": json.dumps(tool_call["arguments"]),
                        },
                    }
                ],
            }
        )

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": tool_call["name"],
                "content": json.dumps(tool_result),
            }
        )

        # Step 4: Get final answer
        response2 = await provider.complete_with_tools(
            messages=messages, tools=tools, model="gpt-4o-mini", temperature=0.0
        )

        # Should have text response now
        assert response2.content
        assert "18" in response2.content or "cloud" in response2.content.lower()

        print("\n✅ Step 2 - Final answer:")
        print(f"   {response2.content[:100]}...")

    @pytest.mark.asyncio
    async def test_multi_step_workflow(self, provider):
        """Test workflow with multiple tool calls."""
        tools = [
            {
                "name": "search_web",
                "description": "Search for information",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
            {
                "name": "summarize",
                "description": "Summarize text",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
        ]

        messages = [{"role": "user", "content": "Search for AI news and summarize it"}]

        # First call - should request search
        response = await provider.complete_with_tools(
            messages=messages, tools=tools, model="gpt-4o-mini", temperature=0.0
        )

        assert response.tool_calls is not None
        print("\n✅ Multi-step workflow:")
        print(f"   Tools called: {[tc['name'] for tc in response.tool_calls]}")


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestToolCallingErrors:
    """Test error handling in tool calling."""

    @pytest.fixture
    async def provider(self):
        """Create and cleanup OpenAI provider."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")

        provider = OpenAIProvider(api_key=api_key)
        yield provider
        await provider.client.aclose()

    @pytest.mark.asyncio
    async def test_invalid_tool_schema(self, provider):
        """Test handling of invalid tool schema."""
        invalid_tools = [
            {
                "name": "bad_tool",
                # Missing required fields
            }
        ]

        messages = [{"role": "user", "content": "Test"}]

        # Should handle gracefully or raise clear error
        try:
            response = await provider.complete_with_tools(
                messages=messages, tools=invalid_tools, model="gpt-4o-mini"
            )
            # If it doesn't raise, check response is valid
            assert response is not None
        except (ProviderError, ModelError, KeyError) as e:
            # Expected - invalid schema should fail
            print(f"\n✅ Invalid schema caught: {type(e).__name__}")

    @pytest.mark.asyncio
    async def test_empty_messages(self, provider):
        """Test handling of empty messages."""
        tools = [SAMPLE_TOOLS[0]]

        # Empty messages should raise error
        with pytest.raises((ProviderError, ModelError, ValueError)):
            await provider.complete_with_tools(messages=[], tools=tools, model="gpt-4o-mini")


# ============================================================================
# Performance Tests
# ============================================================================


class TestToolCallingPerformance:
    """Test performance characteristics of tool calling."""

    @pytest.fixture
    async def provider(self):
        """Create and cleanup OpenAI provider."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")

        provider = OpenAIProvider(api_key=api_key)
        yield provider
        await provider.client.aclose()

    @pytest.mark.asyncio
    async def test_latency_tracking(self, provider):
        """Test that latency is tracked for tool calls."""
        tools = [SAMPLE_TOOLS[0]]
        messages = [{"role": "user", "content": "What's the weather in NYC?"}]

        response = await provider.complete_with_tools(
            messages=messages, tools=tools, model="gpt-4o-mini"
        )

        assert response.latency_ms > 0
        assert response.latency_ms < 60000  # Should be under 60s

        print(f"\n✅ Latency: {response.latency_ms:.0f}ms")

    @pytest.mark.asyncio
    async def test_cost_tracking(self, provider):
        """Test that costs are tracked for tool calls."""
        tools = [SAMPLE_TOOLS[0]]
        messages = [{"role": "user", "content": "What's the weather in Tokyo?"}]

        response = await provider.complete_with_tools(
            messages=messages, tools=tools, model="gpt-4o-mini"
        )

        assert response.cost > 0
        assert response.tokens_used > 0
        assert "prompt_tokens" in response.metadata
        assert "completion_tokens" in response.metadata

        print(f"\n✅ Cost: ${response.cost:.6f}")
        print(f"   Tokens: {response.tokens_used}")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
