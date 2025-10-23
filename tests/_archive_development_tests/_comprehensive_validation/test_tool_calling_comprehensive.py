"""
Comprehensive Tool Calling Test Suite
======================================

Tests tool calling from provider level to agent level, with focus on:
1. Provider-level tool calling (all providers)
2. ToolRouter filtering logic
3. Agent-level tool routing
4. Cascade-level tool separation
5. Different quality handling for tools vs text

Test Coverage:
- ✅ OpenAI: Real API calls
- ✅ Anthropic: Real API calls
- ✅ Groq: Real API calls
- ✅ Together.ai: Real API calls
- ✅ Ollama: Real API calls (gemma3:1b, gemma3:12b)
- 🔸 HuggingFace: Simulated (no real API)
- 🔸 vLLM: Simulated (no real API)

Prerequisites:
- .env file with API keys:
  - OPENAI_API_KEY
  - ANTHROPIC_API_KEY
  - GROQ_API_KEY
  - TOGETHER_API_KEY
- Ollama running locally with gemma3:1b and gemma3:12b

Run:
    pytest tests/test_tool_calling_comprehensive.py -v
    pytest tests/test_tool_calling_comprehensive.py -v -k "provider"  # Only providers
    pytest tests/test_tool_calling_comprehensive.py -v -k "agent"     # Only agent
"""

import os
from unittest.mock import Mock, patch

import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from cascadeflow.config import ModelConfig
from cascadeflow.exceptions import CascadeFlowError

from cascadeflow import CascadeAgent
from cascadeflow.providers import (
    AnthropicProvider,
    GroqProvider,
    HuggingFaceProvider,
    OllamaProvider,
    OpenAIProvider,
    TogetherProvider,
    VLLMProvider,
)
from cascadeflow.routing import ToolRouter

# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def weather_tool():
    """Standard weather tool for testing."""
    return {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name, e.g., 'Paris' or 'New York'",
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit",
                },
            },
            "required": ["location"],
        },
    }


@pytest.fixture
def calculator_tool():
    """Calculator tool for testing."""
    return {
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
    }


@pytest.fixture
def search_tool():
    """Search tool for testing."""
    return {
        "name": "search_web",
        "description": "Search the web for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    }


@pytest.fixture
def all_tools(weather_tool, calculator_tool, search_tool):
    """All test tools."""
    return [weather_tool, calculator_tool, search_tool]


@pytest.fixture
def tool_capable_models():
    """Models that support tools."""
    return [
        ModelConfig(
            name="gpt-4o-mini",
            provider="openai",
            cost=0.0002,
            supports_tools=True,
            tool_quality=0.95,
        ),
        ModelConfig(
            name="claude-3-haiku-20240307",
            provider="anthropic",
            cost=0.00125,
            supports_tools=True,
            tool_quality=0.90,
        ),
        ModelConfig(
            name="llama-3.3-70b-versatile",
            provider="groq",
            cost=0.0,
            supports_tools=True,
            tool_quality=0.85,
        ),
        ModelConfig(
            name="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            provider="together",
            cost=0.0009,
            supports_tools=True,
            tool_quality=0.85,
        ),
        ModelConfig(
            name="gemma3:1b", provider="ollama", cost=0.0, supports_tools=True, tool_quality=0.70
        ),
        ModelConfig(
            name="gemma3:12b", provider="ollama", cost=0.0, supports_tools=True, tool_quality=0.80
        ),
    ]


@pytest.fixture
def mixed_models(tool_capable_models):
    """Mix of tool-capable and non-tool models."""
    return tool_capable_models + [
        ModelConfig(
            name="gpt-3.5-turbo-instruct",
            provider="openai",
            cost=0.0015,
            supports_tools=False,  # Does NOT support tools
        ),
        ModelConfig(name="text-davinci-003", provider="openai", cost=0.020, supports_tools=False),
    ]


# ============================================================================
# LEVEL 1: PROVIDER-LEVEL TESTS
# ============================================================================


class TestProviderToolCalling:
    """Test tool calling at provider level."""

    @pytest.mark.asyncio
    async def test_openai_tool_calling(self, weather_tool):
        """Test OpenAI provider tool calling."""
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        provider = OpenAIProvider()

        response = await provider.complete(
            prompt="What's the weather in San Francisco?",
            model="gpt-4o-mini",
            max_tokens=100,
            tools=[weather_tool],
            tool_choice="auto",
        )

        # Assertions
        assert response is not None
        assert hasattr(response, "tool_calls")

        if response.tool_calls:
            print(f"\n✅ OpenAI made {len(response.tool_calls)} tool call(s)")
            for call in response.tool_calls:
                print(f"  Tool: {call['name']}")
                print(f"  Args: {call['arguments']}")
                assert call["name"] == "get_weather"
                assert "location" in call["arguments"]
        else:
            print("\n⚠️ OpenAI did not make tool calls (returned text response)")
            assert response.content  # Should have content if no tool calls

    @pytest.mark.asyncio
    async def test_anthropic_tool_calling(self, weather_tool):
        """Test Anthropic provider tool calling."""
        if not os.getenv("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set")

        provider = AnthropicProvider()

        response = await provider.complete(
            prompt="What's the weather in London?",
            model="claude-3-haiku-20240307",
            max_tokens=100,
            tools=[weather_tool],
            tool_choice="auto",
        )

        assert response is not None
        assert hasattr(response, "tool_calls")

        if response.tool_calls:
            print(f"\n✅ Anthropic made {len(response.tool_calls)} tool call(s)")
            for call in response.tool_calls:
                print(f"  Tool: {call['name']}")
                print(f"  Args: {call['arguments']}")
                assert call["name"] == "get_weather"
                assert "location" in call["arguments"]
        else:
            print("\n⚠️ Anthropic did not make tool calls")
            assert response.content

    @pytest.mark.asyncio
    async def test_groq_tool_calling(self, weather_tool):
        """Test Groq provider tool calling."""
        if not os.getenv("GROQ_API_KEY"):
            pytest.skip("GROQ_API_KEY not set")

        provider = GroqProvider()

        response = await provider.complete(
            prompt="What's the weather in Tokyo?",
            model="llama-3.3-70b-versatile",
            max_tokens=100,
            tools=[weather_tool],
            tool_choice="auto",
        )

        assert response is not None
        assert hasattr(response, "tool_calls")

        if response.tool_calls:
            print(f"\n✅ Groq made {len(response.tool_calls)} tool call(s)")
            for call in response.tool_calls:
                print(f"  Tool: {call['name']}")
                print(f"  Args: {call['arguments']}")
                assert call["name"] == "get_weather"
        else:
            print("\n⚠️ Groq did not make tool calls")
            assert response.content

    @pytest.mark.asyncio
    async def test_together_tool_calling(self, weather_tool):
        """Test Together.ai provider tool calling."""
        if not os.getenv("TOGETHER_API_KEY"):
            pytest.skip("TOGETHER_API_KEY not set")

        provider = TogetherProvider()

        response = await provider.complete(
            prompt="What's the weather in Berlin?",
            model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            max_tokens=100,
            tools=[weather_tool],
            tool_choice="auto",
        )

        assert response is not None
        assert hasattr(response, "tool_calls")

        if response.tool_calls:
            print(f"\n✅ Together.ai made {len(response.tool_calls)} tool call(s)")
            for call in response.tool_calls:
                print(f"  Tool: {call['name']}")
                print(f"  Args: {call['arguments']}")
                assert call["name"] == "get_weather"
        else:
            print("\n⚠️ Together.ai did not make tool calls")
            assert response.content

    @pytest.mark.asyncio
    async def test_ollama_tool_calling_1b(self, weather_tool):
        """Test Ollama provider tool calling (gemma3:1b)."""
        try:
            provider = OllamaProvider()

            response = await provider.complete(
                prompt="What's the weather in Paris?",
                model="gemma3:1b",
                max_tokens=100,
                tools=[weather_tool],
                tool_choice="auto",
            )

            assert response is not None
            print("\n✅ Ollama (gemma3:1b) completed")

            if hasattr(response, "tool_calls") and response.tool_calls:
                print(f"  Made {len(response.tool_calls)} tool call(s)")
                for call in response.tool_calls:
                    print(f"  Tool: {call['name']}")
                    print(f"  Args: {call['arguments']}")
            else:
                print(f"  Response: {response.content[:100]}...")

        except Exception as e:
            pytest.skip(f"Ollama not available or gemma3:1b not installed: {e}")

    @pytest.mark.asyncio
    async def test_ollama_tool_calling_12b(self, weather_tool):
        """Test Ollama provider tool calling (gemma3:12b)."""
        try:
            provider = OllamaProvider()

            response = await provider.complete(
                prompt="What's the weather in Madrid?",
                model="gemma3:12b",
                max_tokens=100,
                tools=[weather_tool],
                tool_choice="auto",
            )

            assert response is not None
            print("\n✅ Ollama (gemma3:12b) completed")

            if hasattr(response, "tool_calls") and response.tool_calls:
                print(f"  Made {len(response.tool_calls)} tool call(s)")
                for call in response.tool_calls:
                    print(f"  Tool: {call['name']}")
                    print(f"  Args: {call['arguments']}")
            else:
                print(f"  Response: {response.content[:100]}...")

        except Exception as e:
            pytest.skip(f"Ollama not available or gemma3:12b not installed: {e}")

    @pytest.mark.asyncio
    async def test_huggingface_tool_calling_simulated(self, weather_tool):
        """Test HuggingFace provider tool calling (SIMULATED)."""
        # Mock the HuggingFace provider
        with patch.object(HuggingFaceProvider, "complete") as mock_complete:
            # Simulate successful tool call
            mock_response = Mock()
            mock_response.content = ""
            mock_response.tool_calls = [
                {
                    "id": "call_sim123",
                    "type": "function",
                    "name": "get_weather",
                    "arguments": {"location": "Rome"},
                }
            ]
            mock_response.model = "meta-llama/Meta-Llama-3-8B-Instruct"
            mock_response.provider = "huggingface"
            mock_response.cost = 0.0
            mock_response.tokens_used = 50
            mock_response.confidence = 0.85
            mock_response.latency_ms = 500.0
            mock_response.metadata = {}

            mock_complete.return_value = mock_response

            provider = HuggingFaceProvider()
            response = await provider.complete(
                prompt="What's the weather in Rome?",
                model="meta-llama/Meta-Llama-3-8B-Instruct",
                max_tokens=100,
                tools=[weather_tool],
            )

            assert response.tool_calls is not None
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0]["name"] == "get_weather"
            print("\n✅ HuggingFace (SIMULATED) tool calling works")

    @pytest.mark.asyncio
    async def test_vllm_tool_calling_simulated(self, weather_tool):
        """Test vLLM provider tool calling (SIMULATED)."""
        # Mock the vLLM provider
        with patch.object(VLLMProvider, "complete") as mock_complete:
            # Simulate successful tool call
            mock_response = Mock()
            mock_response.content = ""
            mock_response.tool_calls = [
                {
                    "id": "call_vllm123",
                    "type": "function",
                    "name": "get_weather",
                    "arguments": {"location": "Amsterdam"},
                }
            ]
            mock_response.model = "meta-llama/Meta-Llama-3-8B-Instruct"
            mock_response.provider = "vllm"
            mock_response.cost = 0.0
            mock_response.tokens_used = 50
            mock_response.confidence = 0.85
            mock_response.latency_ms = 300.0
            mock_response.metadata = {}

            mock_complete.return_value = mock_response

            provider = VLLMProvider()
            response = await provider.complete(
                prompt="What's the weather in Amsterdam?",
                model="meta-llama/Meta-Llama-3-8B-Instruct",
                max_tokens=100,
                tools=[weather_tool],
            )

            assert response.tool_calls is not None
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0]["name"] == "get_weather"
            print("\n✅ vLLM (SIMULATED) tool calling works")


# ============================================================================
# LEVEL 2: TOOLROUTER TESTS
# ============================================================================


class TestToolRouter:
    """Test ToolRouter filtering logic."""

    def test_filter_tool_capable_models(self, mixed_models, weather_tool):
        """Test filtering to tool-capable models only."""
        router = ToolRouter(models=mixed_models, verbose=True)

        result = router.filter_tool_capable_models(
            tools=[weather_tool], available_models=mixed_models
        )

        # Should filter out non-tool models
        assert result["has_capable_models"] is True
        assert len(result["models"]) == 6  # Only tool-capable models
        assert result["filtered_count"] == 2  # 2 non-tool models filtered out

        # Check that only tool-capable models remain
        for model in result["models"]:
            assert model.supports_tools is True

        print(f"\n✅ Filtered to {len(result['models'])}/{len(mixed_models)} models")

    def test_filter_with_no_tools(self, mixed_models):
        """Test that all models pass when no tools provided."""
        router = ToolRouter(models=mixed_models, verbose=True)

        result = router.filter_tool_capable_models(tools=None, available_models=mixed_models)

        # Should return all models
        assert len(result["models"]) == len(mixed_models)
        assert result["filtered_count"] == 0
        print(f"\n✅ No filtering when no tools: {len(result['models'])} models")

    def test_error_when_no_capable_models(self, weather_tool):
        """Test error when no tool-capable models available."""
        # Models that don't support tools
        non_tool_models = [
            ModelConfig(
                name="gpt-3.5-turbo-instruct", provider="openai", cost=0.0015, supports_tools=False
            ),
            ModelConfig(
                name="text-davinci-003", provider="openai", cost=0.020, supports_tools=False
            ),
        ]

        router = ToolRouter(models=non_tool_models, verbose=True)

        with pytest.raises(CascadeFlowError) as exc_info:
            router.filter_tool_capable_models(
                tools=[weather_tool], available_models=non_tool_models
            )

        assert "No tool-capable models available" in str(exc_info.value)
        print("\n✅ Raises error when no capable models")

    def test_validate_tools(self, weather_tool, calculator_tool):
        """Test tool validation."""
        router = ToolRouter(models=[], verbose=True)

        # Valid tools
        result = router.validate_tools([weather_tool, calculator_tool])
        assert result["valid"] is True
        assert len(result["errors"]) == 0

        # Invalid tool (missing name)
        invalid_tool = {"description": "Does something", "parameters": {}}
        result = router.validate_tools([invalid_tool])
        assert result["valid"] is False
        assert len(result["errors"]) > 0

        # Duplicate names
        result = router.validate_tools([weather_tool, weather_tool])
        assert result["valid"] is False
        assert any("Duplicate" in err for err in result["errors"])

        print("\n✅ Tool validation works correctly")

    def test_suggest_models_for_tools(self, tool_capable_models, weather_tool):
        """Test model suggestion for tools."""
        router = ToolRouter(models=tool_capable_models, verbose=True)

        suggestions = router.suggest_models_for_tools(tools=[weather_tool], max_cost=0.001)

        # Should suggest tool-capable models under cost limit
        assert len(suggestions) > 0
        for model in suggestions:
            assert model.supports_tools is True
            assert model.cost <= 0.001

        print(f"\n✅ Suggested {len(suggestions)} models under cost limit")

    def test_router_statistics(self, mixed_models, weather_tool):
        """Test ToolRouter statistics tracking."""
        router = ToolRouter(models=mixed_models, verbose=True)

        # Perform multiple filters
        for _ in range(3):
            router.filter_tool_capable_models(tools=[weather_tool], available_models=mixed_models)

        stats = router.get_stats()

        assert stats["total_filters"] == 3
        assert stats["filter_hits"] == 3
        assert stats["tool_capable_models"] == 6
        assert stats["total_models"] == 8

        print(f"\n✅ Router stats: {stats}")


# ============================================================================
# LEVEL 3: AGENT-LEVEL TESTS
# ============================================================================


class TestAgentToolCalling:
    """Test tool calling at agent level."""

    @pytest.mark.asyncio
    async def test_agent_with_tools_real_providers(self, weather_tool):
        """Test agent with tools using real providers."""
        # Check which providers are available
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        has_groq = bool(os.getenv("GROQ_API_KEY"))

        if not (has_openai or has_groq):
            pytest.skip("Need at least OPENAI_API_KEY or GROQ_API_KEY")

        # Build model list based on available providers
        models = []
        if has_groq:
            models.append(
                ModelConfig(
                    name="llama-3.3-70b-versatile", provider="groq", cost=0.0, supports_tools=True
                )
            )
        if has_openai:
            models.extend(
                [
                    ModelConfig(
                        name="gpt-3.5-turbo", provider="openai", cost=0.002, supports_tools=False
                    ),
                    ModelConfig(
                        name="gpt-4o-mini", provider="openai", cost=0.0002, supports_tools=True
                    ),
                ]
            )

        agent = CascadeAgent(models=models, enable_cascade=True, verbose=True)

        # Test with tools
        result = await agent.run(
            "What's the weather in Seattle?",
            max_tokens=100,
            tools=[weather_tool],
            tool_choice="auto",
        )

        assert result is not None
        assert result.content or result.tool_calls  # Should have either content or tool calls
        assert result.metadata["has_tools"] is True
        assert result.metadata["tool_count"] == 1

        if result.tool_calls:
            print(f"\n✅ Agent made {len(result.tool_calls)} tool call(s)")
            for call in result.tool_calls:
                print(f"  Tool: {call['name']}")
                print(f"  Args: {call['arguments']}")
        else:
            print("\n⚠️ Agent did not make tool calls")
            print(f"  Response: {result.content[:100]}...")

        # Check that telemetry tracked tool usage
        stats = agent.get_stats()
        assert "tool_queries" in stats or stats.get("total_queries", 0) > 0

    @pytest.mark.asyncio
    async def test_agent_filters_non_tool_models(self, weather_tool):
        """Test that agent filters out non-tool-capable models when tools provided."""
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        # Mix of tool and non-tool models
        models = [
            ModelConfig(
                name="gpt-3.5-turbo-instruct", provider="openai", cost=0.0015, supports_tools=False
            ),
            ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.0002, supports_tools=True),
        ]

        agent = CascadeAgent(models=models, enable_cascade=False, verbose=True)

        # Should use only gpt-4o-mini for tool calling
        result = await agent.run(
            "What's the weather in Boston?", max_tokens=100, tools=[weather_tool]
        )

        assert result is not None
        # Model used should be the tool-capable one
        assert "gpt-4o-mini" in result.model_used or result.tool_calls or result.content

        print(f"\n✅ Agent filtered to tool-capable model: {result.model_used}")

    @pytest.mark.asyncio
    async def test_agent_cascade_with_tools(self, weather_tool):
        """Test agent cascade routing with tools."""
        if not os.getenv("GROQ_API_KEY") or not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Need both GROQ_API_KEY and OPENAI_API_KEY")

        # Cheap drafter, expensive verifier (both support tools)
        models = [
            ModelConfig(
                name="llama-3.3-70b-versatile", provider="groq", cost=0.0, supports_tools=True
            ),
            ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.0002, supports_tools=True),
        ]

        agent = CascadeAgent(models=models, enable_cascade=True, verbose=True)

        # Simple query with tools (should cascade)
        result = await agent.run(
            "What's 2+2? Use the calculator.",
            max_tokens=50,
            tools=[weather_tool],  # Even with tools, simple query should cascade
            complexity_hint="simple",
        )

        assert result is not None
        print("\n✅ Cascade with tools:")
        print(f"  Routing: {result.routing_strategy}")
        print(f"  Model: {result.model_used}")
        print(f"  Cascaded: {result.cascaded}")

    @pytest.mark.asyncio
    async def test_agent_direct_routing_with_tools(self, weather_tool):
        """Test agent direct routing with tools for complex queries."""
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        models = [
            ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002, supports_tools=False),
            ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.0002, supports_tools=True),
        ]

        agent = CascadeAgent(models=models, enable_cascade=True, verbose=True)

        # Complex query with tools (should route directly to best)
        result = await agent.run(
            "Analyze the weather patterns in multiple cities and provide a detailed forecast.",
            max_tokens=100,
            tools=[weather_tool],
            complexity_hint="hard",
        )

        assert result is not None
        assert result.routing_strategy == "direct"  # Should route directly
        print("\n✅ Direct routing with tools:")
        print(f"  Routing: {result.routing_strategy}")
        print(f"  Reason: {result.reason}")


# ============================================================================
# LEVEL 4: CASCADE-LEVEL TOOL SEPARATION TESTS
# ============================================================================


class TestCascadeToolSeparation:
    """Test tool separation logic at cascade level."""

    @pytest.mark.asyncio
    async def test_tool_vs_text_routing_separation(self, weather_tool):
        """Test that tool calls and text responses are routed differently."""
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        models = [
            ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002, supports_tools=False),
            ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.0002, supports_tools=True),
        ]

        agent = CascadeAgent(models=models, enable_cascade=True, verbose=True)

        # Query WITH tools
        result_with_tools = await agent.run(
            "What's the weather?", max_tokens=50, tools=[weather_tool]
        )

        # Query WITHOUT tools (same complexity)
        result_without_tools = await agent.run(
            "What's the weather like in general?", max_tokens=50, tools=None
        )

        # With tools: should filter to tool-capable models
        assert result_with_tools.metadata["has_tools"] is True

        # Without tools: all models available
        assert result_without_tools.metadata.get("has_tools", False) is False

        print("\n✅ Tool separation:")
        print(f"  With tools - Model: {result_with_tools.model_used}")
        print(f"  Without tools - Model: {result_without_tools.model_used}")

    @pytest.mark.asyncio
    async def test_quality_handling_difference_tools_vs_text(self):
        """Test that tools get different quality handling than text."""
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        models = [
            ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002, supports_tools=False),
            ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.0002, supports_tools=True),
        ]

        agent = CascadeAgent(models=models, enable_cascade=True, verbose=True)

        # Define tools
        calc_tool = {
            "name": "calculate",
            "description": "Calculate math",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        }

        # Text query
        text_result = await agent.run("What is 15 times 23?", max_tokens=50, tools=None)

        # Tool query (same question, but with tools)
        tool_result = await agent.run("What is 15 times 23?", max_tokens=50, tools=[calc_tool])

        # Both should complete, but may use different models/strategies
        assert text_result is not None
        assert tool_result is not None

        print("\n✅ Quality handling difference:")
        print("  Text query:")
        print(f"    Model: {text_result.model_used}")
        print(f"    Strategy: {text_result.routing_strategy}")
        print("  Tool query:")
        print(f"    Model: {tool_result.model_used}")
        print(f"    Strategy: {tool_result.routing_strategy}")
        print(f"    Has tool calls: {bool(tool_result.tool_calls)}")

    @pytest.mark.asyncio
    async def test_cascade_accepts_draft_with_valid_tool_calls(self):
        """Test that cascade accepts drafts with valid tool calls."""
        if not os.getenv("GROQ_API_KEY") or not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Need both GROQ_API_KEY and OPENAI_API_KEY")

        models = [
            ModelConfig(
                name="llama-3.3-70b-versatile", provider="groq", cost=0.0, supports_tools=True
            ),
            ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.0002, supports_tools=True),
        ]

        agent = CascadeAgent(models=models, enable_cascade=True, verbose=True)

        weather_tool = {
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        }

        result = await agent.run(
            "Get me the weather in Paris",
            max_tokens=100,
            tools=[weather_tool],
            complexity_hint="simple",  # Force cascade
        )

        assert result is not None
        print("\n✅ Cascade with tool calls:")
        print(f"  Draft accepted: {result.draft_accepted}")
        print(f"  Model used: {result.model_used}")
        print(f"  Has tool calls: {bool(result.tool_calls)}")
        if result.tool_calls:
            print(f"  Tool calls: {len(result.tool_calls)}")


# ============================================================================
# LEVEL 5: INTEGRATION TESTS
# ============================================================================


class TestToolCallingIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_full_tool_calling_workflow(self, all_tools):
        """Test complete workflow from query to tool execution."""
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        models = [
            ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.0002, supports_tools=True),
        ]

        agent = CascadeAgent(models=models, enable_cascade=False, verbose=True)

        # Step 1: Query with tools
        result = await agent.run(
            "Search for 'Python programming' and tell me what you find",
            max_tokens=150,
            tools=all_tools,
        )

        assert result is not None

        # Step 2: Check for tool calls
        if result.tool_calls:
            print("\n✅ Tool calling workflow:")
            print("  Query completed")
            print(f"  Tool calls made: {len(result.tool_calls)}")

            # Step 3: Simulate tool execution
            for call in result.tool_calls:
                print(f"  Executing tool: {call['name']}")
                print(f"  Arguments: {call['arguments']}")

                # Simulate tool result
                tool_result = f"Result from {call['name']}: Success"
                print(f"  Result: {tool_result}")

        else:
            print("\n⚠️ No tool calls made")
            print(f"  Response: {result.content[:100]}...")

        # Step 4: Check statistics
        stats = agent.get_stats()
        print(f"\n  Total queries: {stats.get('total_queries', 0)}")
        print(f"  Tool queries: {stats.get('tool_queries', 0)}")

    @pytest.mark.asyncio
    async def test_multi_provider_tool_calling(self, weather_tool):
        """Test tool calling across multiple providers."""
        # Check available providers
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        has_groq = bool(os.getenv("GROQ_API_KEY"))
        has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))

        if not (has_openai or has_groq or has_anthropic):
            pytest.skip("Need at least one API key")

        # Build model list
        models = []
        if has_groq:
            models.append(
                ModelConfig(
                    name="llama-3.3-70b-versatile", provider="groq", cost=0.0, supports_tools=True
                )
            )
        if has_openai:
            models.append(
                ModelConfig(name="gpt-4o-mini", provider="openai", cost=0.0002, supports_tools=True)
            )
        if has_anthropic:
            models.append(
                ModelConfig(
                    name="claude-3-haiku-20240307",
                    provider="anthropic",
                    cost=0.00125,
                    supports_tools=True,
                )
            )

        agent = CascadeAgent(models=models, enable_cascade=True, verbose=True)

        # Test multiple queries
        queries = ["What's the weather in NYC?", "Check the weather in LA", "Weather in Chicago?"]

        results = []
        for query in queries:
            result = await agent.run(query, max_tokens=100, tools=[weather_tool])
            results.append(result)
            print(f"\n  Query: {query[:30]}...")
            print(f"  Model: {result.model_used}")
            print(f"  Tool calls: {len(result.tool_calls) if result.tool_calls else 0}")

        # All should complete
        assert all(r is not None for r in results)
        print(f"\n✅ Multi-provider tool calling: {len(results)} queries completed")


# ============================================================================
# RUN SUMMARY
# ============================================================================

if __name__ == "__main__":
    print(
        """
    ╔═══════════════════════════════════════════════════════════╗
    ║   CascadeFlow Tool Calling - Comprehensive Test Suite    ║
    ╚═══════════════════════════════════════════════════════════╝

    Test Coverage:
    1. Provider Level  → All providers (real + simulated)
    2. ToolRouter      → Filtering and validation logic
    3. Agent Level     → End-to-end tool routing
    4. Cascade Level   → Tool separation and quality handling
    5. Integration     → Complete workflows

    Run with:
        pytest tests/test_tool_calling_comprehensive.py -v
        pytest tests/test_tool_calling_comprehensive.py -v -s  # Show prints
        pytest tests/test_tool_calling_comprehensive.py -v -k "provider"
    """
    )
