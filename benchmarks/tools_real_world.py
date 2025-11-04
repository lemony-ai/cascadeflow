"""
Real-World Tool Implementations for Benchmark Testing

Simulates 7 common tools used in production LLM applications:
1. Weather API
2. Calculator
3. Web Search
4. Database Query
5. Email
6. Calendar
7. File Operations

These are mock implementations that return realistic data for testing.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════
# 1. WEATHER TOOL
# ═══════════════════════════════════════════════════════════════

WEATHER_TOOL_SCHEMA = {
    "name": "get_weather",
    "description": "Get current weather information for a city",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name (e.g., 'San Francisco', 'London')"
            },
            "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "Temperature unit",
                "default": "celsius"
            }
        },
        "required": ["city"]
    }
}

def get_weather(city: str, unit: str = "celsius") -> Dict[str, Any]:
    """Mock weather API - returns realistic weather data."""
    # Simulate realistic weather data
    weather_conditions = ["sunny", "cloudy", "rainy", "partly cloudy", "foggy"]
    temps_celsius = {"San Francisco": 18, "New York": 15, "London": 12, "Paris": 14, "Tokyo": 20}

    temp_c = temps_celsius.get(city, random.randint(10, 25))
    temp_f = (temp_c * 9/5) + 32

    return {
        "city": city,
        "temperature": temp_f if unit == "fahrenheit" else temp_c,
        "unit": unit,
        "condition": random.choice(weather_conditions),
        "humidity": random.randint(40, 80),
        "wind_speed": random.randint(5, 25),
        "timestamp": datetime.now().isoformat()
    }


# ═══════════════════════════════════════════════════════════════
# 2. CALCULATOR TOOL
# ═══════════════════════════════════════════════════════════════

CALCULATOR_TOOL_SCHEMA = {
    "name": "calculate",
    "description": "Perform mathematical calculations",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression (e.g., '2 + 2', '10 * 5', 'sqrt(16)')"
            }
        },
        "required": ["expression"]
    }
}

def calculate(expression: str) -> Dict[str, Any]:
    """Mock calculator - safely evaluates mathematical expressions."""
    try:
        # Simple safe eval for basic math
        # In production, use a proper math expression parser
        import math
        safe_dict = {"sqrt": math.sqrt, "pow": math.pow, "abs": abs}
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return {
            "expression": expression,
            "result": result,
            "success": True
        }
    except Exception as e:
        return {
            "expression": expression,
            "error": str(e),
            "success": False
        }


# ═══════════════════════════════════════════════════════════════
# 3. WEB SEARCH TOOL
# ═══════════════════════════════════════════════════════════════

SEARCH_TOOL_SCHEMA = {
    "name": "search_web",
    "description": "Search the web for information",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return",
                "default": 5
            }
        },
        "required": ["query"]
    }
}

def search_web(query: str, num_results: int = 5) -> Dict[str, Any]:
    """Mock web search - returns realistic search results."""
    # Simulate search results
    results = []
    for i in range(min(num_results, 5)):
        results.append({
            "title": f"Result {i+1} for '{query}'",
            "url": f"https://example.com/result-{i+1}",
            "snippet": f"This is a relevant snippet about {query}...",
            "relevance_score": random.uniform(0.7, 0.99)
        })

    return {
        "query": query,
        "num_results": len(results),
        "results": results,
        "timestamp": datetime.now().isoformat()
    }


# ═══════════════════════════════════════════════════════════════
# 4. DATABASE QUERY TOOL
# ═══════════════════════════════════════════════════════════════

DATABASE_TOOL_SCHEMA = {
    "name": "query_database",
    "description": "Query customer database for orders, users, or products",
    "parameters": {
        "type": "object",
        "properties": {
            "table": {
                "type": "string",
                "enum": ["orders", "users", "products"],
                "description": "Database table to query"
            },
            "filter": {
                "type": "object",
                "description": "Filter criteria (e.g., {'user_id': '123', 'status': 'active'})"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results",
                "default": 10
            }
        },
        "required": ["table"]
    }
}

def query_database(table: str, filter: Optional[Dict] = None, limit: int = 10) -> Dict[str, Any]:
    """Mock database query - returns realistic data."""
    # Simulate database records
    if table == "orders":
        records = [
            {"order_id": f"ORD-{1000+i}", "user_id": f"USR-{i%5}", "amount": random.randint(10, 500),
             "status": random.choice(["pending", "shipped", "delivered"])}
            for i in range(limit)
        ]
    elif table == "users":
        records = [
            {"user_id": f"USR-{i}", "name": f"User {i}", "email": f"user{i}@example.com",
             "tier": random.choice(["free", "pro", "enterprise"])}
            for i in range(limit)
        ]
    else:  # products
        records = [
            {"product_id": f"PROD-{i}", "name": f"Product {i}", "price": random.randint(10, 200),
             "stock": random.randint(0, 100)}
            for i in range(limit)
        ]

    return {
        "table": table,
        "filter": filter,
        "num_results": len(records),
        "records": records
    }


# ═══════════════════════════════════════════════════════════════
# 5. EMAIL TOOL
# ═══════════════════════════════════════════════════════════════

EMAIL_TOOL_SCHEMA = {
    "name": "send_email",
    "description": "Send an email to a recipient",
    "parameters": {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address"
            },
            "subject": {
                "type": "string",
                "description": "Email subject"
            },
            "body": {
                "type": "string",
                "description": "Email body content"
            },
            "cc": {
                "type": "array",
                "items": {"type": "string"},
                "description": "CC recipients (optional)"
            }
        },
        "required": ["to", "subject", "body"]
    }
}

def send_email(to: str, subject: str, body: str, cc: Optional[List[str]] = None) -> Dict[str, Any]:
    """Mock email sender - simulates sending email."""
    return {
        "to": to,
        "subject": subject,
        "body_length": len(body),
        "cc": cc or [],
        "message_id": f"MSG-{random.randint(100000, 999999)}",
        "status": "sent",
        "timestamp": datetime.now().isoformat()
    }


# ═══════════════════════════════════════════════════════════════
# 6. CALENDAR TOOL
# ═══════════════════════════════════════════════════════════════

CALENDAR_TOOL_SCHEMA = {
    "name": "get_calendar_events",
    "description": "Get calendar events for a date range",
    "parameters": {
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "Start date (YYYY-MM-DD)"
            },
            "end_date": {
                "type": "string",
                "description": "End date (YYYY-MM-DD)"
            },
            "calendar": {
                "type": "string",
                "description": "Calendar name",
                "default": "primary"
            }
        },
        "required": ["start_date", "end_date"]
    }
}

def get_calendar_events(start_date: str, end_date: str, calendar: str = "primary") -> Dict[str, Any]:
    """Mock calendar - returns simulated events."""
    # Simulate calendar events
    events = []
    event_types = ["Meeting", "Call", "Review", "Planning", "Training"]

    for i in range(random.randint(1, 5)):
        event_date = datetime.now() + timedelta(days=random.randint(0, 7))
        events.append({
            "event_id": f"EVT-{random.randint(1000, 9999)}",
            "title": f"{random.choice(event_types)} {i+1}",
            "start": event_date.isoformat(),
            "end": (event_date + timedelta(hours=1)).isoformat(),
            "attendees": random.randint(1, 10),
            "location": random.choice(["Office", "Remote", "Conference Room A"])
        })

    return {
        "calendar": calendar,
        "start_date": start_date,
        "end_date": end_date,
        "num_events": len(events),
        "events": events
    }


# ═══════════════════════════════════════════════════════════════
# 7. FILE OPERATIONS TOOL
# ═══════════════════════════════════════════════════════════════

FILE_TOOL_SCHEMA = {
    "name": "file_operation",
    "description": "Perform file operations (read, write, list)",
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["read", "write", "list", "delete"],
                "description": "File operation to perform"
            },
            "path": {
                "type": "string",
                "description": "File path"
            },
            "content": {
                "type": "string",
                "description": "Content to write (for write operation)"
            }
        },
        "required": ["operation", "path"]
    }
}

def file_operation(operation: str, path: str, content: Optional[str] = None) -> Dict[str, Any]:
    """Mock file operations - simulates file system access."""
    if operation == "read":
        return {
            "operation": "read",
            "path": path,
            "content": f"Mock content from {path}",
            "size": random.randint(100, 10000),
            "success": True
        }
    elif operation == "write":
        return {
            "operation": "write",
            "path": path,
            "bytes_written": len(content) if content else 0,
            "success": True
        }
    elif operation == "list":
        return {
            "operation": "list",
            "path": path,
            "files": [f"file-{i}.txt" for i in range(random.randint(3, 10))],
            "success": True
        }
    elif operation == "delete":
        return {
            "operation": "delete",
            "path": path,
            "success": True
        }
    else:
        return {"operation": operation, "error": "Unknown operation", "success": False}


# ═══════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ═══════════════════════════════════════════════════════════════

ALL_TOOLS = {
    "get_weather": {
        "schema": WEATHER_TOOL_SCHEMA,
        "function": get_weather
    },
    "calculate": {
        "schema": CALCULATOR_TOOL_SCHEMA,
        "function": calculate
    },
    "search_web": {
        "schema": SEARCH_TOOL_SCHEMA,
        "function": search_web
    },
    "query_database": {
        "schema": DATABASE_TOOL_SCHEMA,
        "function": query_database
    },
    "send_email": {
        "schema": EMAIL_TOOL_SCHEMA,
        "function": send_email
    },
    "get_calendar_events": {
        "schema": CALENDAR_TOOL_SCHEMA,
        "function": get_calendar_events
    },
    "file_operation": {
        "schema": FILE_TOOL_SCHEMA,
        "function": file_operation
    }
}

ALL_TOOL_SCHEMAS = [tool["schema"] for tool in ALL_TOOLS.values()]


def execute_tool_call(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool call by name with parameters.

    Args:
        tool_name: Name of the tool to execute
        parameters: Parameters to pass to the tool

    Returns:
        Tool execution result
    """
    if tool_name not in ALL_TOOLS:
        return {"error": f"Unknown tool: {tool_name}", "success": False}

    try:
        tool_func = ALL_TOOLS[tool_name]["function"]
        result = tool_func(**parameters)
        return result
    except Exception as e:
        return {"error": str(e), "success": False}


def validate_tool_call(tool_name: str, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate a tool call before execution.

    Returns:
        (is_valid, error_message)
    """
    if tool_name not in ALL_TOOLS:
        return False, f"Unknown tool: {tool_name}"

    schema = ALL_TOOLS[tool_name]["schema"]
    # FIX: Use universal format (not OpenAI nested format)
    required_params = schema.get("parameters", {}).get("required", [])

    # Check required parameters
    for param in required_params:
        if param not in parameters:
            return False, f"Missing required parameter: {param}"

    return True, None
