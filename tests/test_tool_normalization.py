from cascadeflow.tools.formats import normalize_tools


def test_normalize_openai_tool_format():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            },
        }
    ]
    normalized = normalize_tools(tools)
    assert normalized is not None
    assert normalized[0]["name"] == "get_weather"
    assert "parameters" in normalized[0]


def test_normalize_anthropic_tool_format():
    tools = [
        {
            "name": "search_web",
            "description": "Search the web",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
        }
    ]
    normalized = normalize_tools(tools)
    assert normalized is not None
    assert normalized[0]["name"] == "search_web"
    assert "parameters" in normalized[0]


def test_normalize_universal_tool_format_passthrough():
    tools = [
        {
            "name": "calculate",
            "description": "Calculator",
            "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}},
        }
    ]
    normalized = normalize_tools(tools)
    assert normalized == tools
