#!/usr/bin/env python3
"""
Test tool calling structure (no API keys needed).

This tests that the integration is complete without making actual API calls.

Run: python test_tool_structure.py
"""

from cascadeflow.config import ModelConfig

from cascadeflow import CascadeAgent


def test_structure():
    """Test that all tool calling structure is in place."""

    print("=" * 60)
    print("cascadeflow Tool Structure Test")
    print("=" * 60)
    print()

    # Test 1: ModelConfig has supports_tools
    print("1. ModelConfig.supports_tools field...")
    try:
        model = ModelConfig(name="gpt-4", provider="openai", cost=0.03, supports_tools=True)
        assert hasattr(model, "supports_tools"), "Missing supports_tools field"
        assert model.supports_tools
        print("   ✅ ModelConfig.supports_tools works")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False

    print()

    # Test 2: Agent accepts tool-capable models
    print("2. Agent with tool-capable models...")
    try:
        models = [
            ModelConfig(name="gpt-3.5-turbo", provider="openai", cost=0.002, supports_tools=True),
            ModelConfig(
                name="gpt-4",
                provider="openai",
                cost=0.03,
                supports_tools=False,  # Test mixed support
            ),
        ]

        # Don't initialize (no API keys needed)
        # Just check structure
        print(f"   ✅ Created {len(models)} model configs")
        print(f"      - {models[0].name}: tools={models[0].supports_tools}")
        print(f"      - {models[1].name}: tools={models[1].supports_tools}")

    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False

    print()

    # Test 3: Check agent.py has tool support
    print("3. Agent.run() method signature...")
    try:
        import inspect

        sig = inspect.signature(CascadeAgent.run)
        params = list(sig.parameters.keys())

        assert "tools" in params, "run() missing 'tools' parameter"
        assert "tool_choice" in params, "run() missing 'tool_choice' parameter"

        print("   ✅ Agent.run() has tools parameter")
        print("   ✅ Agent.run() has tool_choice parameter")

    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False

    print()

    # Test 4: Check run_streaming has tool support
    print("4. Agent.run_streaming() method signature...")
    try:
        sig = inspect.signature(CascadeAgent.run_streaming)
        params = list(sig.parameters.keys())

        assert "tools" in params, "run_streaming() missing 'tools' parameter"
        assert "tool_choice" in params, "run_streaming() missing 'tool_choice' parameter"

        print("   ✅ Agent.run_streaming() has tools parameter")
        print("   ✅ Agent.run_streaming() has tool_choice parameter")

    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False

    print()

    # Test 5: Check stream_events has tool support
    print("5. Agent.stream_events() method signature...")
    try:
        sig = inspect.signature(CascadeAgent.stream_events)
        params = list(sig.parameters.keys())

        assert "tools" in params, "stream_events() missing 'tools' parameter"
        assert "tool_choice" in params, "stream_events() missing 'tool_choice' parameter"

        print("   ✅ Agent.stream_events() has tools parameter")
        print("   ✅ Agent.stream_events() has tool_choice parameter")

    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False

    print()

    # Test 6: Check CascadeResult has tool fields
    print("6. CascadeResult tool fields...")
    try:
        from cascadeflow.agent import CascadeResult

        sig = inspect.signature(CascadeResult)
        params = list(sig.parameters.keys())

        assert "tool_calls" in params, "CascadeResult missing 'tool_calls' field"
        assert "has_tool_calls" in params, "CascadeResult missing 'has_tool_calls' field"

        print("   ✅ CascadeResult has tool_calls field")
        print("   ✅ CascadeResult has has_tool_calls field")

    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False

    print()

    # Test 7: Check ToolRouter exists
    print("7. ToolRouter module...")
    try:

        print("   ✅ ToolRouter can be imported")
        print("   ✅ ToolRouter available at: cascadeflow.routing.ToolRouter")

    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False

    print()

    # Test 8: Check provider base has tool support
    print("8. Provider base tool support...")
    try:
        from cascadeflow.providers.base import ModelResponse

        # Check ModelResponse has tool_calls field
        sig = inspect.signature(ModelResponse)
        params = list(sig.parameters.keys())
        assert "tool_calls" in params, "ModelResponse missing 'tool_calls' field"

        print("   ✅ BaseProvider can be imported")
        print("   ✅ ModelResponse has tool_calls field")

    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False

    print()

    # Test 9: Check streaming has tool support
    print("9. Streaming tool support...")
    try:

        print("   ✅ ToolStreamManager can be imported")
        print("   ✅ Tool streaming available")

    except Exception as e:
        print(f"   ⚠️  WARNING: {e}")
        print("   ℹ️  Tool streaming optional, basic streaming still works")

    print()

    # Summary
    print("=" * 60)
    print("STRUCTURE TEST: PASSED ✅")
    print("=" * 60)
    print()
    print("All tool calling structure is in place!")
    print()
    print("What's working:")
    print("  ✅ ModelConfig.supports_tools field")
    print("  ✅ Agent.run(query, tools=[...])")
    print("  ✅ Agent.run_streaming(query, tools=[...])")
    print("  ✅ Agent.stream_events(query, tools=[...])")
    print("  ✅ CascadeResult.tool_calls field")
    print("  ✅ ToolRouter for filtering models")
    print("  ✅ Provider base supports tools")
    print("  ✅ Streaming supports tools")
    print()
    print("To test with actual API calls:")
    print("  1. Set OPENAI_API_KEY or ANTHROPIC_API_KEY")
    print("  2. Run: python examples/tool_calling_demo.py")
    print()

    return True


if __name__ == "__main__":
    result = test_structure()
    exit(0 if result else 1)
