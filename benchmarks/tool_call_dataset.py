"""
Comprehensive Tool Calling Dataset - 100+ Real-World Scenarios

Based on:
- Berkeley Function Calling Leaderboard (BFCL)
- LangChain 2024 production data (21.9% tool usage)
- Real customer support, data analysis, and automation scenarios

Categories:
- Trivial (30): Single tool, clear parameters
- Simple (40): Single tool, some inference needed
- Moderate (20): 2 tools or conditional logic
- Hard (10): Multi-step tool orchestration
- Expert (5): Complex multi-tool workflows

Total: 105 tool calling scenarios (25% of 420 total queries)
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from tools_real_world import (
    WEATHER_TOOL_SCHEMA,
    CALCULATOR_TOOL_SCHEMA,
    SEARCH_TOOL_SCHEMA,
    DATABASE_TOOL_SCHEMA,
    EMAIL_TOOL_SCHEMA,
    CALENDAR_TOOL_SCHEMA,
    FILE_TOOL_SCHEMA,
    ALL_TOOL_SCHEMAS
)


@dataclass
class ToolCallQuery:
    """Represents a tool calling benchmark query."""
    id: str
    complexity: str  # trivial, simple, moderate, hard, expert
    category: str  # customer_support, data_analysis, automation, productivity
    query: str
    tools: List[Dict[str, Any]]
    expected_tool: str  # Expected tool to be called
    expected_routing: str  # cascade or direct_premium
    min_tokens: int
    max_tokens: int
    description: str = ""


# ═══════════════════════════════════════════════════════════════
# TRIVIAL TOOL CALLS (30) - Score: 0-3
# ═══════════════════════════════════════════════════════════════
# Single tool, clear parameters, obvious choice
# Expected: Cascade to cheap model (Groq)

TRIVIAL_TOOL_CALLS = [
    # Weather queries (10)
    ToolCallQuery("tool_trivial_weather_1", "trivial", "customer_support",
        "What's the weather in San Francisco?",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 20, 100,
        "Simple weather query - clear city parameter"),

    ToolCallQuery("tool_trivial_weather_2", "trivial", "customer_support",
        "Check weather for London",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 20, 100,
        "Direct weather request"),

    ToolCallQuery("tool_trivial_weather_3", "trivial", "customer_support",
        "Get current temperature in Tokyo",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 20, 100,
        "Specific temperature request"),

    ToolCallQuery("tool_trivial_weather_4", "trivial", "customer_support",
        "Is it raining in Seattle?",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 20, 100,
        "Condition-specific query"),

    ToolCallQuery("tool_trivial_weather_5", "trivial", "customer_support",
        "Weather forecast for Paris please",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 20, 100,
        "Polite weather request"),

    ToolCallQuery("tool_trivial_weather_6", "trivial", "customer_support",
        "Show me weather in Berlin in Fahrenheit",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 20, 100,
        "With unit specification"),

    ToolCallQuery("tool_trivial_weather_7", "trivial", "customer_support",
        "Get weather for New York City",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 20, 100,
        "Full city name"),

    ToolCallQuery("tool_trivial_weather_8", "trivial", "customer_support",
        "What's the temperature in Miami?",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 20, 100,
        "Temperature specific"),

    ToolCallQuery("tool_trivial_weather_9", "trivial", "customer_support",
        "Check weather conditions in Chicago",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 20, 100,
        "Conditions request"),

    ToolCallQuery("tool_trivial_weather_10", "trivial", "customer_support",
        "Tell me the weather in Los Angeles",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 20, 100,
        "Conversational style"),

    # Calculator queries (10)
    ToolCallQuery("tool_trivial_calc_1", "trivial", "data_analysis",
        "What is 2 + 2?",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 10, 50,
        "Basic addition"),

    ToolCallQuery("tool_trivial_calc_2", "trivial", "data_analysis",
        "Calculate 15 * 7",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 10, 50,
        "Simple multiplication"),

    ToolCallQuery("tool_trivial_calc_3", "trivial", "data_analysis",
        "What's 100 - 37?",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 10, 50,
        "Subtraction"),

    ToolCallQuery("tool_trivial_calc_4", "trivial", "data_analysis",
        "Divide 50 by 5",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 10, 50,
        "Division"),

    ToolCallQuery("tool_trivial_calc_5", "trivial", "data_analysis",
        "Calculate square root of 16",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 10, 50,
        "Square root function"),

    ToolCallQuery("tool_trivial_calc_6", "trivial", "data_analysis",
        "What's 25% of 80?",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 10, 50,
        "Percentage calculation"),

    ToolCallQuery("tool_trivial_calc_7", "trivial", "data_analysis",
        "2 to the power of 8",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 10, 50,
        "Exponentiation"),

    ToolCallQuery("tool_trivial_calc_8", "trivial", "data_analysis",
        "Add 123 and 456",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 10, 50,
        "Larger numbers"),

    ToolCallQuery("tool_trivial_calc_9", "trivial", "data_analysis",
        "What is 8 times 9?",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 10, 50,
        "Multiplication table"),

    ToolCallQuery("tool_trivial_calc_10", "trivial", "data_analysis",
        "Calculate absolute value of -42",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 10, 50,
        "Absolute value"),

    # Database queries (5)
    ToolCallQuery("tool_trivial_db_1", "trivial", "customer_support",
        "Get user with ID USR-123",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 30, 150,
        "Specific user lookup"),

    ToolCallQuery("tool_trivial_db_2", "trivial", "customer_support",
        "Show me order ORD-456",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 30, 150,
        "Order lookup"),

    ToolCallQuery("tool_trivial_db_3", "trivial", "customer_support",
        "List all products",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 30, 150,
        "Simple list request"),

    ToolCallQuery("tool_trivial_db_4", "trivial", "customer_support",
        "Get recent orders",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 30, 150,
        "Recent records"),

    ToolCallQuery("tool_trivial_db_5", "trivial", "customer_support",
        "Show active users",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 30, 150,
        "Filtered query"),

    # Calendar queries (5)
    ToolCallQuery("tool_trivial_cal_1", "trivial", "productivity",
        "What's on my calendar today?",
        [CALENDAR_TOOL_SCHEMA], "get_calendar_events", "cascade", 30, 150,
        "Today's events"),

    ToolCallQuery("tool_trivial_cal_2", "trivial", "productivity",
        "Show tomorrow's meetings",
        [CALENDAR_TOOL_SCHEMA], "get_calendar_events", "cascade", 30, 150,
        "Tomorrow's schedule"),

    ToolCallQuery("tool_trivial_cal_3", "trivial", "productivity",
        "Check my schedule for next Monday",
        [CALENDAR_TOOL_SCHEMA], "get_calendar_events", "cascade", 30, 150,
        "Specific day"),

    ToolCallQuery("tool_trivial_cal_4", "trivial", "productivity",
        "List this week's events",
        [CALENDAR_TOOL_SCHEMA], "get_calendar_events", "cascade", 30, 150,
        "Week view"),

    ToolCallQuery("tool_trivial_cal_5", "trivial", "productivity",
        "Do I have any meetings this afternoon?",
        [CALENDAR_TOOL_SCHEMA], "get_calendar_events", "cascade", 30, 150,
        "Time-specific query"),
]


# ═══════════════════════════════════════════════════════════════
# SIMPLE TOOL CALLS (40) - Score: 3-6
# ═══════════════════════════════════════════════════════════════
# Single tool, requires some parameter inference
# Expected: Cascade (may need verification)

SIMPLE_TOOL_CALLS = [
    # Weather with inference (10)
    ToolCallQuery("tool_simple_weather_1", "simple", "customer_support",
        "Is it warm enough for the beach today?",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 30, 150,
        "Requires city inference from context"),

    ToolCallQuery("tool_simple_weather_2", "simple", "customer_support",
        "Should I bring an umbrella?",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 30, 150,
        "Implicit weather check"),

    ToolCallQuery("tool_simple_weather_3", "simple", "customer_support",
        "What's the weather like where you are?",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 30, 150,
        "Vague location reference"),

    ToolCallQuery("tool_simple_weather_4", "simple", "customer_support",
        "Will it be cold this evening?",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 30, 150,
        "Time-relative query"),

    ToolCallQuery("tool_simple_weather_5", "simple", "customer_support",
        "What should I wear today based on weather?",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 30, 150,
        "Weather-dependent decision"),

    ToolCallQuery("tool_simple_weather_6", "simple", "customer_support",
        "Check if it's sunny in major US cities",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 50, 200,
        "Multiple cities implied"),

    ToolCallQuery("tool_simple_weather_7", "simple", "customer_support",
        "How's the weather for outdoor activities?",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 30, 150,
        "Activity-based weather check"),

    ToolCallQuery("tool_simple_weather_8", "simple", "customer_support",
        "Is it a good day for a picnic?",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 30, 150,
        "Weather suitability"),

    ToolCallQuery("tool_simple_weather_9", "simple", "customer_support",
        "What's the temperature difference between here and London?",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 50, 200,
        "Comparative weather"),

    ToolCallQuery("tool_simple_weather_10", "simple", "customer_support",
        "Check current conditions for my location",
        [WEATHER_TOOL_SCHEMA], "get_weather", "cascade", 30, 150,
        "Location inference needed"),

    # Calculator with context (10)
    ToolCallQuery("tool_simple_calc_1", "simple", "data_analysis",
        "If I have $100 and spend $37, how much is left?",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 30, 100,
        "Word problem to calculation"),

    ToolCallQuery("tool_simple_calc_2", "simple", "data_analysis",
        "Calculate the tip for a $85 bill at 20%",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 30, 100,
        "Percentage in context"),

    ToolCallQuery("tool_simple_calc_3", "simple", "data_analysis",
        "What's the total if I buy 3 items at $15.99 each?",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 30, 100,
        "Multi-step calculation"),

    ToolCallQuery("tool_simple_calc_4", "simple", "data_analysis",
        "How many hours in 2.5 days?",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 30, 100,
        "Unit conversion calculation"),

    ToolCallQuery("tool_simple_calc_5", "simple", "data_analysis",
        "Calculate monthly payment for $10000 over 12 months",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 30, 100,
        "Financial calculation"),

    ToolCallQuery("tool_simple_calc_6", "simple", "data_analysis",
        "What's 15% more than 200?",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 30, 100,
        "Percentage increase"),

    ToolCallQuery("tool_simple_calc_7", "simple", "data_analysis",
        "If I save $50 per week, how much in 6 months?",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 30, 100,
        "Savings calculation"),

    ToolCallQuery("tool_simple_calc_8", "simple", "data_analysis",
        "What's the average of 10, 20, 30, 40, 50?",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 30, 100,
        "Average calculation"),

    ToolCallQuery("tool_simple_calc_9", "simple", "data_analysis",
        "Calculate area of a circle with radius 5",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 30, 100,
        "Geometric calculation"),

    ToolCallQuery("tool_simple_calc_10", "simple", "data_analysis",
        "What's the compound interest on $1000 at 5% for 2 years?",
        [CALCULATOR_TOOL_SCHEMA], "calculate", "cascade", 50, 150,
        "Complex financial formula"),

    # Database with filtering (10)
    ToolCallQuery("tool_simple_db_1", "simple", "customer_support",
        "Find all pending orders",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 50, 200,
        "Status filter"),

    ToolCallQuery("tool_simple_db_2", "simple", "customer_support",
        "Show users who signed up this month",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 50, 200,
        "Date-based filter"),

    ToolCallQuery("tool_simple_db_3", "simple", "customer_support",
        "List products under $50",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 50, 200,
        "Price filter"),

    ToolCallQuery("tool_simple_db_4", "simple", "customer_support",
        "Get pro tier users",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 50, 200,
        "Tier filter"),

    ToolCallQuery("tool_simple_db_5", "simple", "customer_support",
        "Find orders over $100",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 50, 200,
        "Amount filter"),

    ToolCallQuery("tool_simple_db_6", "simple", "customer_support",
        "Show out of stock products",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 50, 200,
        "Stock status filter"),

    ToolCallQuery("tool_simple_db_7", "simple", "customer_support",
        "List recent orders from user USR-5",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 50, 200,
        "User-specific orders"),

    ToolCallQuery("tool_simple_db_8", "simple", "customer_support",
        "Get all delivered orders",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 50, 200,
        "Delivery status"),

    ToolCallQuery("tool_simple_db_9", "simple", "customer_support",
        "Find users with email containing 'example.com'",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 50, 200,
        "Pattern matching"),

    ToolCallQuery("tool_simple_db_10", "simple", "customer_support",
        "Show top 5 most expensive products",
        [DATABASE_TOOL_SCHEMA], "query_database", "cascade", 50, 200,
        "Sorting and limiting"),

    # Email (5)
    ToolCallQuery("tool_simple_email_1", "simple", "automation",
        "Send confirmation email to customer@example.com",
        [EMAIL_TOOL_SCHEMA], "send_email", "cascade", 50, 200,
        "Email with implied subject/body"),

    ToolCallQuery("tool_simple_email_2", "simple", "automation",
        "Email the team about tomorrow's meeting",
        [EMAIL_TOOL_SCHEMA], "send_email", "cascade", 50, 200,
        "Context-dependent email"),

    ToolCallQuery("tool_simple_email_3", "simple", "automation",
        "Send shipping notification to user",
        [EMAIL_TOOL_SCHEMA], "send_email", "cascade", 50, 200,
        "Template-based email"),

    ToolCallQuery("tool_simple_email_4", "simple", "automation",
        "Email invoice to client",
        [EMAIL_TOOL_SCHEMA], "send_email", "cascade", 50, 200,
        "Business email"),

    ToolCallQuery("tool_simple_email_5", "simple", "automation",
        "Send reminder about password expiry",
        [EMAIL_TOOL_SCHEMA], "send_email", "cascade", 50, 200,
        "Automated reminder"),

    # Search (5)
    ToolCallQuery("tool_simple_search_1", "simple", "productivity",
        "Search for Python tutorials",
        [SEARCH_TOOL_SCHEMA], "search_web", "cascade", 30, 150,
        "General search"),

    ToolCallQuery("tool_simple_search_2", "simple", "productivity",
        "Find documentation for React hooks",
        [SEARCH_TOOL_SCHEMA], "search_web", "cascade", 30, 150,
        "Documentation search"),

    ToolCallQuery("tool_simple_search_3", "simple", "productivity",
        "Look up company information",
        [SEARCH_TOOL_SCHEMA], "search_web", "cascade", 30, 150,
        "Information lookup"),

    ToolCallQuery("tool_simple_search_4", "simple", "productivity",
        "Search for recent news about AI",
        [SEARCH_TOOL_SCHEMA], "search_web", "cascade", 30, 150,
        "News search"),

    ToolCallQuery("tool_simple_search_5", "simple", "productivity",
        "Find best practices for code review",
        [SEARCH_TOOL_SCHEMA], "search_web", "cascade", 30, 150,
        "Best practices search"),
]


# ═══════════════════════════════════════════════════════════════
# MODERATE TOOL CALLS (20) - Score: 6-9
# ═══════════════════════════════════════════════════════════════
# May need 2 tools or conditional logic
# Expected: Cascade with higher quality threshold

MODERATE_TOOL_CALLS = [
    # Two-step workflows (10)
    ToolCallQuery("tool_moderate_1", "moderate", "customer_support",
        "Get weather for San Francisco and calculate if temp is above 70F",
        [WEATHER_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA], "get_weather", "cascade", 100, 300,
        "Weather + conditional calculation"),

    ToolCallQuery("tool_moderate_2", "moderate", "customer_support",
        "Look up user USR-123 and send them a welcome email",
        [DATABASE_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "query_database", "cascade", 100, 300,
        "Database lookup + email"),

    ToolCallQuery("tool_moderate_3", "moderate", "data_analysis",
        "Query pending orders and calculate total value",
        [DATABASE_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA], "query_database", "cascade", 100, 300,
        "Query + aggregation"),

    ToolCallQuery("tool_moderate_4", "moderate", "productivity",
        "Check my calendar for today and send summary email",
        [CALENDAR_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "get_calendar_events", "cascade", 100, 300,
        "Calendar + email notification"),

    ToolCallQuery("tool_moderate_5", "moderate", "automation",
        "Search for product reviews and save to file",
        [SEARCH_TOOL_SCHEMA, FILE_TOOL_SCHEMA], "search_web", "cascade", 100, 300,
        "Search + file operation"),

    ToolCallQuery("tool_moderate_6", "moderate", "customer_support",
        "Get user orders and email order history",
        [DATABASE_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "query_database", "cascade", 100, 300,
        "Query + templated email"),

    ToolCallQuery("tool_moderate_7", "moderate", "productivity",
        "Check calendar conflicts between two date ranges",
        [CALENDAR_TOOL_SCHEMA], "get_calendar_events", "cascade", 100, 300,
        "Multiple calendar queries"),

    ToolCallQuery("tool_moderate_8", "moderate", "data_analysis",
        "Calculate average order value from database",
        [DATABASE_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA], "query_database", "cascade", 100, 300,
        "Query + statistical calculation"),

    ToolCallQuery("tool_moderate_9", "moderate", "automation",
        "Get weather for multiple cities and compare temperatures",
        [WEATHER_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA], "get_weather", "cascade", 100, 300,
        "Multiple weather calls + comparison"),

    ToolCallQuery("tool_moderate_10", "moderate", "customer_support",
        "Search for user complaints and categorize by severity",
        [SEARCH_TOOL_SCHEMA, DATABASE_TOOL_SCHEMA], "search_web", "cascade", 100, 300,
        "Search + categorization"),

    # Conditional logic (10)
    ToolCallQuery("tool_moderate_cond_1", "moderate", "automation",
        "If weather is good, send picnic invitation email",
        [WEATHER_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "get_weather", "cascade", 100, 300,
        "Conditional: weather → email"),

    ToolCallQuery("tool_moderate_cond_2", "moderate", "customer_support",
        "Check order status, if pending send reminder",
        [DATABASE_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "query_database", "cascade", 100, 300,
        "Conditional: status → reminder"),

    ToolCallQuery("tool_moderate_cond_3", "moderate", "data_analysis",
        "Query products, if stock low send alert",
        [DATABASE_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "query_database", "cascade", 100, 300,
        "Conditional: stock → alert"),

    ToolCallQuery("tool_moderate_cond_4", "moderate", "productivity",
        "Check calendar, if meeting today send reminder",
        [CALENDAR_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "get_calendar_events", "cascade", 100, 300,
        "Conditional: meeting → reminder"),

    ToolCallQuery("tool_moderate_cond_5", "moderate", "automation",
        "Calculate total, if over budget send notification",
        [CALCULATOR_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "calculate", "cascade", 100, 300,
        "Conditional: budget → notification"),

    ToolCallQuery("tool_moderate_cond_6", "moderate", "customer_support",
        "Get user tier, if pro send upgrade benefits",
        [DATABASE_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "query_database", "cascade", 100, 300,
        "Conditional: tier → benefits"),

    ToolCallQuery("tool_moderate_cond_7", "moderate", "automation",
        "Search for errors, if found file bug report",
        [SEARCH_TOOL_SCHEMA, FILE_TOOL_SCHEMA], "search_web", "cascade", 100, 300,
        "Conditional: errors → report"),

    ToolCallQuery("tool_moderate_cond_8", "moderate", "data_analysis",
        "Check sales metrics, if down send alert to team",
        [DATABASE_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "query_database", "cascade", 100, 300,
        "Conditional: metrics → alert"),

    ToolCallQuery("tool_moderate_cond_9", "moderate", "automation",
        "Get temperature, if freezing send weather advisory",
        [WEATHER_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "get_weather", "cascade", 100, 300,
        "Conditional: temp → advisory"),

    ToolCallQuery("tool_moderate_cond_10", "moderate", "productivity",
        "Check file exists, if not create new one",
        [FILE_TOOL_SCHEMA], "file_operation", "cascade", 100, 300,
        "Conditional: file check → create"),
]


# ═══════════════════════════════════════════════════════════════
# HARD TOOL CALLS (10) - Score: 9-13
# ═══════════════════════════════════════════════════════════════
# Multi-step orchestration OR complex reasoning
# Expected: Direct to premium model

HARD_TOOL_CALLS = [
    ToolCallQuery("tool_hard_1", "hard", "customer_support",
        "Get all pending orders, calculate total value, then email summary to manager with breakdown by user tier",
        [DATABASE_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "query_database", "direct_premium", 200, 500,
        "3-step: Query → Calculate → Email with segmentation"),

    ToolCallQuery("tool_hard_2", "hard", "data_analysis",
        "Search for Q4 sales reports, analyze trends, calculate growth rate, and save detailed analysis to file",
        [SEARCH_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA, FILE_TOOL_SCHEMA], "search_web", "direct_premium", 200, 500,
        "4-step: Search → Analyze → Calculate → Save"),

    ToolCallQuery("tool_hard_3", "hard", "automation",
        "Check weather for 5 cities, compare temperatures, identify warmest, then send travel recommendation email",
        [WEATHER_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "get_weather", "direct_premium", 200, 500,
        "Multi-city comparison + recommendation"),

    ToolCallQuery("tool_hard_4", "hard", "customer_support",
        "Query users by tier, calculate lifetime value per tier, identify top 10%, then email personalized offers",
        [DATABASE_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "query_database", "direct_premium", 200, 500,
        "Segmentation + calculation + personalization"),

    ToolCallQuery("tool_hard_5", "hard", "productivity",
        "Get next week's calendar, identify conflicts, calculate free time blocks, then email optimized schedule",
        [CALENDAR_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "get_calendar_events", "direct_premium", 200, 500,
        "Schedule optimization workflow"),

    ToolCallQuery("tool_hard_6", "hard", "data_analysis",
        "Query all orders, group by month, calculate monthly revenue trend, compare to last year, and generate report",
        [DATABASE_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA, FILE_TOOL_SCHEMA], "query_database", "direct_premium", 200, 500,
        "Time-series analysis workflow"),

    ToolCallQuery("tool_hard_7", "hard", "automation",
        "Search for competitor pricing, compare with our products, calculate price differences, suggest adjustments, email recommendations",
        [SEARCH_TOOL_SCHEMA, DATABASE_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "search_web", "direct_premium", 250, 600,
        "Competitive analysis workflow"),

    ToolCallQuery("tool_hard_8", "hard", "customer_support",
        "Get pending support tickets, categorize by urgency, assign to team based on load, send notifications to each team member",
        [DATABASE_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "query_database", "direct_premium", 200, 500,
        "Ticket triage and assignment"),

    ToolCallQuery("tool_hard_9", "hard", "data_analysis",
        "Analyze user growth over 6 months, calculate retention rate by cohort, identify churn patterns, email insights to stakeholders",
        [DATABASE_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "query_database", "direct_premium", 250, 600,
        "Cohort analysis workflow"),

    ToolCallQuery("tool_hard_10", "hard", "automation",
        "Monitor system metrics, detect anomalies, calculate impact, search for related issues, file incident report, alert on-call team",
        [DATABASE_TOOL_SCHEMA, CALCULATOR_TOOL_SCHEMA, SEARCH_TOOL_SCHEMA, FILE_TOOL_SCHEMA, EMAIL_TOOL_SCHEMA], "query_database", "direct_premium", 300, 700,
        "Incident detection and response"),
]


# ═══════════════════════════════════════════════════════════════
# EXPERT TOOL CALLS (5) - Score: 13+
# ═══════════════════════════════════════════════════════════════
# Complex multi-tool orchestration with reasoning
# Expected: Direct to premium model

EXPERT_TOOL_CALLS = [
    ToolCallQuery("tool_expert_1", "expert", "data_analysis",
        "Comprehensive sales analysis: Query Q4 sales, segment by product and region, calculate YoY growth by segment, identify underperforming regions, search for market trends in those regions, correlate with competitor activity, generate detailed report with recommendations, and email to executive team with action items",
        ALL_TOOL_SCHEMAS, "query_database", "direct_premium", 400, 1000,
        "Full sales analysis pipeline with external data"),

    ToolCallQuery("tool_expert_2", "expert", "automation",
        "Customer 360 workflow: Get user profile and order history, calculate customer lifetime value and purchase patterns, check calendar for scheduled calls, search for user feedback across platforms, analyze sentiment, identify upsell opportunities based on usage patterns, generate personalized engagement plan, schedule follow-up tasks, and email account team with strategy",
        ALL_TOOL_SCHEMAS, "query_database", "direct_premium", 400, 1000,
        "Complete customer intelligence workflow"),

    ToolCallQuery("tool_expert_3", "expert", "productivity",
        "Executive daily briefing: Get today's calendar with meeting prep notes, query pending decisions from database, calculate team velocity metrics, check weather for travel days, search for relevant industry news, identify calendar conflicts, prioritize meetings by importance, generate time-blocked schedule with breaks, compile briefing document with all context, and email morning brief with recommended focus areas",
        ALL_TOOL_SCHEMAS, "get_calendar_events", "direct_premium", 400, 1000,
        "AI executive assistant workflow"),

    ToolCallQuery("tool_expert_4", "expert", "customer_support",
        "Support crisis management: Query all open high-priority tickets, categorize by issue type, calculate SLA breach risk, identify common patterns, search knowledge base for solutions, match tickets to specialist availability, assign optimal routing, generate resolution templates, send batch notifications to customers with ETAs, alert management of critical issues, and create real-time dashboard file",
        ALL_TOOL_SCHEMAS, "query_database", "direct_premium", 400, 1000,
        "Crisis management orchestration"),

    ToolCallQuery("tool_expert_5", "expert", "data_analysis",
        "Quarterly business review automation: Query all key metrics (revenue, users, engagement), calculate trends and forecasts, compare to targets and industry benchmarks via search, identify growth drivers and blockers, check calendar for stakeholder availability, generate comprehensive slide deck with visualizations, save detailed analysis to file, email preview to leadership, and schedule presentation meeting with calendar invites",
        ALL_TOOL_SCHEMAS, "query_database", "direct_premium", 500, 1200,
        "Full QBR automation pipeline"),
]


# ═══════════════════════════════════════════════════════════════
# COMPILE ALL TOOL CALLS
# ═══════════════════════════════════════════════════════════════

ALL_TOOL_CALLS = (
    TRIVIAL_TOOL_CALLS +    # 30
    SIMPLE_TOOL_CALLS +     # 40
    MODERATE_TOOL_CALLS +   # 20
    HARD_TOOL_CALLS +       # 10
    EXPERT_TOOL_CALLS       # 5
)  # Total: 105 tool calling scenarios

print(f"Total tool calling scenarios: {len(ALL_TOOL_CALLS)}")
print(f"  Trivial:  {len(TRIVIAL_TOOL_CALLS)}")
print(f"  Simple:   {len(SIMPLE_TOOL_CALLS)}")
print(f"  Moderate: {len(MODERATE_TOOL_CALLS)}")
print(f"  Hard:     {len(HARD_TOOL_CALLS)}")
print(f"  Expert:   {len(EXPERT_TOOL_CALLS)}")
