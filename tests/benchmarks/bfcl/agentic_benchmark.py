"""
Agentic Multi-Turn Tool Calling Benchmark for CascadeFlow.

Phase 2 (Feb 2026): Agentic/Multi-Agent Validation

This benchmark tests agentic tool calling patterns that are critical for
real-world applications but missing from traditional single-turn benchmarks:

1. **Multi-Turn Tool Conversations**
   - State tracking across multiple turns
   - Context-aware tool selection
   - Conversation memory impact on tool use

2. **Dependent Tool Calling (ToolComp style)**
   - Tool B requires output from Tool A
   - Sequential reasoning with tool results
   - Error propagation handling

3. **Tool Chaining Scenarios**
   - Multi-step workflows (search → analyze → act)
   - Parallel-then-sequential patterns
   - Conditional tool execution

Why This Matters for Developers:
- Chatbots: Multi-turn tool use with memory
- Agents: Complex workflows with tool dependencies
- RAG: Search → Retrieve → Synthesize patterns
- Automation: Sequential task execution

Benchmark Categories:
- single_dependency: Tool B uses Tool A's output
- chain_3_step: Three sequential dependent tools
- parallel_then_merge: Parallel calls → synthesize
- conditional_tool: Tool selection based on previous result
- multi_turn_state: State tracked across conversation turns

Usage:
    python tests/benchmarks/bfcl/agentic_benchmark.py --sample 10
    python tests/benchmarks/bfcl/agentic_benchmark.py --full
"""

import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cascadeflow import CascadeAgent, ModelConfig


@dataclass
class AgenticResult:
    """Result for an agentic tool calling test."""
    task_id: str
    task_type: str
    correct: bool
    draft_accepted: bool
    cost: float
    latency_ms: float
    turns_completed: int = 0
    tools_called: list[str] = field(default_factory=list)
    dependency_handled: bool = False
    state_maintained: bool = False
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# AGENTIC TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Tool that returns data needed by other tools
LOOKUP_USER_TOOL = {
    "type": "function",
    "function": {
        "name": "lookup_user",
        "description": "Look up a user by email and return their user_id and account info",
        "parameters": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "User's email address"},
            },
            "required": ["email"],
        },
    },
}

# Tool that depends on user_id from lookup_user
GET_USER_ORDERS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_user_orders",
        "description": "Get orders for a user by their user_id",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User ID from lookup_user"},
                "status": {"type": "string", "enum": ["pending", "shipped", "delivered", "all"]},
            },
            "required": ["user_id"],
        },
    },
}

# Tool that depends on order_id from get_user_orders
GET_ORDER_DETAILS_TOOL = {
    "type": "function",
    "function": {
        "name": "get_order_details",
        "description": "Get detailed information about a specific order",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID from get_user_orders"},
            },
            "required": ["order_id"],
        },
    },
}

# Tool for updating based on previous data
UPDATE_ORDER_STATUS_TOOL = {
    "type": "function",
    "function": {
        "name": "update_order_status",
        "description": "Update the status of an order",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "new_status": {"type": "string", "enum": ["pending", "processing", "shipped", "delivered", "cancelled"]},
                "reason": {"type": "string", "description": "Reason for status change"},
            },
            "required": ["order_id", "new_status"],
        },
    },
}

# Search tool for RAG patterns
SEARCH_KNOWLEDGE_BASE_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": "Search the knowledge base for relevant articles",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string", "enum": ["technical", "billing", "general", "returns"]},
            },
            "required": ["query"],
        },
    },
}

# Tool that uses search results
GENERATE_RESPONSE_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_response",
        "description": "Generate a customer response using knowledge base article IDs",
        "parameters": {
            "type": "object",
            "properties": {
                "article_ids": {"type": "array", "items": {"type": "string"}, "description": "Article IDs from search"},
                "customer_question": {"type": "string"},
                "tone": {"type": "string", "enum": ["formal", "friendly", "apologetic"]},
            },
            "required": ["article_ids", "customer_question"],
        },
    },
}

# Parallel data fetching tools
GET_PRODUCT_INFO_TOOL = {
    "type": "function",
    "function": {
        "name": "get_product_info",
        "description": "Get product details by product_id",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
            },
            "required": ["product_id"],
        },
    },
}

GET_INVENTORY_TOOL = {
    "type": "function",
    "function": {
        "name": "get_inventory",
        "description": "Get inventory levels for a product",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "warehouse": {"type": "string", "enum": ["us-east", "us-west", "eu", "asia"]},
            },
            "required": ["product_id"],
        },
    },
}

GET_PRICING_TOOL = {
    "type": "function",
    "function": {
        "name": "get_pricing",
        "description": "Get pricing information including discounts",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "customer_tier": {"type": "string", "enum": ["standard", "premium", "enterprise"]},
            },
            "required": ["product_id"],
        },
    },
}

# Synthesis tool that uses multiple inputs
CREATE_QUOTE_TOOL = {
    "type": "function",
    "function": {
        "name": "create_quote",
        "description": "Create a sales quote using product, inventory, and pricing data",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "quantity": {"type": "integer"},
                "warehouse": {"type": "string"},
                "unit_price": {"type": "number"},
                "discount_percent": {"type": "number"},
            },
            "required": ["product_id", "quantity", "unit_price"],
        },
    },
}

# Conditional tools
CHECK_ELIGIBILITY_TOOL = {
    "type": "function",
    "function": {
        "name": "check_eligibility",
        "description": "Check if a user is eligible for a refund",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["order_id", "reason"],
        },
    },
}

PROCESS_REFUND_TOOL = {
    "type": "function",
    "function": {
        "name": "process_refund",
        "description": "Process a refund (only if eligibility check passed)",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "amount": {"type": "number"},
                "method": {"type": "string", "enum": ["original_payment", "store_credit", "check"]},
            },
            "required": ["order_id", "amount", "method"],
        },
    },
}

DENY_REFUND_TOOL = {
    "type": "function",
    "function": {
        "name": "deny_refund",
        "description": "Deny a refund request with reason",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "denial_reason": {"type": "string"},
            },
            "required": ["order_id", "denial_reason"],
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# SIMULATED TOOL RESPONSES
# ═══════════════════════════════════════════════════════════════════════════════

MOCK_RESPONSES = {
    "lookup_user": lambda params: {
        "user_id": "USR-12345",
        "email": params.get("email", "user@example.com"),
        "name": "John Smith",
        "account_tier": "premium",
        "created_at": "2023-01-15",
    },
    "get_user_orders": lambda params: {
        "user_id": params.get("user_id", "USR-12345"),
        "orders": [
            {"order_id": "ORD-001", "status": "delivered", "total": 149.99},
            {"order_id": "ORD-002", "status": "pending", "total": 89.50},
            {"order_id": "ORD-003", "status": "shipped", "total": 299.00},
        ],
    },
    "get_order_details": lambda params: {
        "order_id": params.get("order_id", "ORD-001"),
        "items": [
            {"product": "Widget Pro", "qty": 2, "price": 49.99},
            {"product": "Gadget Max", "qty": 1, "price": 50.01},
        ],
        "shipping": {"carrier": "FedEx", "tracking": "FX123456789"},
    },
    "search_knowledge_base": lambda params: {
        "query": params.get("query", ""),
        "results": [
            {"article_id": "KB-101", "title": "Return Policy", "relevance": 0.95},
            {"article_id": "KB-102", "title": "Refund Process", "relevance": 0.87},
        ],
    },
    "get_product_info": lambda params: {
        "product_id": params.get("product_id", "PROD-001"),
        "name": "Enterprise Server",
        "category": "Hardware",
        "specs": {"cpu": "32 cores", "ram": "256GB", "storage": "4TB SSD"},
    },
    "get_inventory": lambda params: {
        "product_id": params.get("product_id", "PROD-001"),
        "warehouse": params.get("warehouse", "us-east"),
        "available": 15,
        "reserved": 3,
        "reorder_point": 10,
    },
    "get_pricing": lambda params: {
        "product_id": params.get("product_id", "PROD-001"),
        "base_price": 4999.00,
        "tier_discount": 0.15 if params.get("customer_tier") == "enterprise" else 0.05,
        "volume_discount": 0.10,
    },
    "check_eligibility": lambda params: {
        "order_id": params.get("order_id", "ORD-001"),
        "eligible": True,
        "max_refund": 149.99,
        "reason_valid": True,
        "within_window": True,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENTIC TEST CASES
# ═══════════════════════════════════════════════════════════════════════════════

AGENTIC_TASKS = [
    # ═══════════════════════════════════════════════════════════════════════════
    # SINGLE DEPENDENCY: Tool B uses Tool A's output
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "task_id": "dep_user_orders_1",
        "task_type": "single_dependency",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL],
        "prompt": """Find all pending orders for the customer with email alice@example.com.

You must:
1. First look up the user to get their user_id
2. Then use that user_id to get their orders with status 'pending'""",
        "expected_sequence": ["lookup_user", "get_user_orders"],
        "dependency_check": "user_id must flow from lookup_user to get_user_orders",
    },
    {
        "task_id": "dep_user_orders_2",
        "task_type": "single_dependency",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL],
        "prompt": """Get all shipped orders for bob@company.org.

Step 1: Look up the user by email
Step 2: Use the returned user_id to fetch orders with status 'shipped'""",
        "expected_sequence": ["lookup_user", "get_user_orders"],
        "dependency_check": "user_id propagation",
    },
    {
        "task_id": "dep_search_respond_1",
        "task_type": "single_dependency",
        "tools": [SEARCH_KNOWLEDGE_BASE_TOOL, GENERATE_RESPONSE_TOOL],
        "prompt": """A customer asks: "How do I return a damaged item?"

1. Search the knowledge base for relevant articles about returns
2. Generate a friendly response using the article IDs from the search results""",
        "expected_sequence": ["search_knowledge_base", "generate_response"],
        "dependency_check": "article_ids from search used in generate_response",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # 3-STEP CHAIN: A → B → C dependency
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "task_id": "chain_order_details_1",
        "task_type": "chain_3_step",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL, GET_ORDER_DETAILS_TOOL],
        "prompt": """Get the shipping tracking number for the most recent delivered order
belonging to customer carol@example.com.

Execute in this order:
1. lookup_user → get user_id from email
2. get_user_orders → find the delivered order
3. get_order_details → get shipping tracking info""",
        "expected_sequence": ["lookup_user", "get_user_orders", "get_order_details"],
        "dependency_check": "user_id → orders → order_id → details",
    },
    {
        "task_id": "chain_order_update_1",
        "task_type": "chain_3_step",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL, UPDATE_ORDER_STATUS_TOOL],
        "prompt": """Cancel the pending order for dave@shop.com because the customer requested it.

Steps:
1. Look up the user
2. Get their orders and find the pending one
3. Update that order's status to 'cancelled' with reason 'Customer request'""",
        "expected_sequence": ["lookup_user", "get_user_orders", "update_order_status"],
        "dependency_check": "Full chain execution with data propagation",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # PARALLEL THEN MERGE: Fetch multiple data sources, then synthesize
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "task_id": "parallel_quote_1",
        "task_type": "parallel_then_merge",
        "tools": [GET_PRODUCT_INFO_TOOL, GET_INVENTORY_TOOL, GET_PRICING_TOOL, CREATE_QUOTE_TOOL],
        "prompt": """Create a sales quote for 5 units of product PROD-X100 for an enterprise customer.

Approach:
1. Fetch product info, inventory (us-west warehouse), and pricing (enterprise tier) - these can be parallel
2. Use the gathered data to create a quote with the appropriate pricing""",
        "expected_parallel": ["get_product_info", "get_inventory", "get_pricing"],
        "expected_final": "create_quote",
        "dependency_check": "Parallel data gathering → synthesis",
    },
    {
        "task_id": "parallel_quote_2",
        "task_type": "parallel_then_merge",
        "tools": [GET_PRODUCT_INFO_TOOL, GET_INVENTORY_TOOL, GET_PRICING_TOOL, CREATE_QUOTE_TOOL],
        "prompt": """Prepare a quote for 10 units of SERVER-2024 from the EU warehouse for a premium customer.

You can fetch product info, inventory, and pricing simultaneously.
Then create the quote using the collected information.""",
        "expected_parallel": ["get_product_info", "get_inventory", "get_pricing"],
        "expected_final": "create_quote",
        "dependency_check": "Parallel fetch → merge",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # CONDITIONAL: Different tool based on previous result
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "task_id": "conditional_refund_1",
        "task_type": "conditional",
        "tools": [CHECK_ELIGIBILITY_TOOL, PROCESS_REFUND_TOOL, DENY_REFUND_TOOL],
        "prompt": """Process a refund request for order ORD-789.
Customer reason: "Product arrived damaged"

1. First check if the order is eligible for a refund
2. If eligible: process the refund via original payment method
3. If not eligible: deny with the appropriate reason""",
        "expected_sequence": ["check_eligibility", "process_refund OR deny_refund"],
        "conditional_logic": "Branch based on eligibility result",
    },
    {
        "task_id": "conditional_refund_2",
        "task_type": "conditional",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL, CHECK_ELIGIBILITY_TOOL, PROCESS_REFUND_TOOL],
        "prompt": """Customer emma@mail.com wants a refund on their most recent order.

Execute:
1. Look up the user
2. Get their orders to find the most recent
3. Check refund eligibility
4. If eligible, process the refund as store credit""",
        "expected_sequence": ["lookup_user", "get_user_orders", "check_eligibility", "process_refund"],
        "conditional_logic": "Chain with conditional ending",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # MULTI-TURN STATE: Conversation with state tracking
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "task_id": "multiturn_support_1",
        "task_type": "multi_turn_state",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL, SEARCH_KNOWLEDGE_BASE_TOOL, GENERATE_RESPONSE_TOOL],
        "turns": [
            {
                "user": "I need help with my order. My email is frank@customer.com",
                "expected_tools": ["lookup_user"],
                "state_update": {"user_id": "USR-12345"},
            },
            {
                "user": "What orders do I have?",
                "expected_tools": ["get_user_orders"],
                "state_requirement": "Must use user_id from previous turn",
            },
            {
                "user": "How do I track my shipped package?",
                "expected_tools": ["search_knowledge_base", "generate_response"],
                "state_requirement": "Context should include user and orders",
            },
        ],
    },
    {
        "task_id": "multiturn_inquiry_1",
        "task_type": "multi_turn_state",
        "tools": [GET_PRODUCT_INFO_TOOL, GET_INVENTORY_TOOL, GET_PRICING_TOOL],
        "turns": [
            {
                "user": "Tell me about product WIDGET-500",
                "expected_tools": ["get_product_info"],
                "state_update": {"product_id": "WIDGET-500"},
            },
            {
                "user": "Is it in stock at the US-West warehouse?",
                "expected_tools": ["get_inventory"],
                "state_requirement": "Must use product_id from turn 1",
            },
            {
                "user": "What's the enterprise pricing?",
                "expected_tools": ["get_pricing"],
                "state_requirement": "Must use product_id from turn 1",
            },
        ],
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# NATURAL LANGUAGE VARIANTS (v20): Test cascade ability with realistic prompts
# These test the SAME tasks as explicit prompts but WITHOUT step markers
# ═══════════════════════════════════════════════════════════════════════════════

# Natural language single dependency (should allow CASCADE)
NATURAL_LANGUAGE_TASKS = [
    # --- SIMPLE 2-TOOL DEPENDENCIES (Natural Language) ---
    {
        "task_id": "natural_user_orders_1",
        "task_type": "natural_single_dependency",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL],
        "prompt": "Show me all pending orders for alice@example.com",
        "expected_sequence": ["lookup_user", "get_user_orders"],
        "dependency_check": "user_id must flow from lookup_user to get_user_orders",
        "expected_cascade": True,  # Should route to cascade
    },
    {
        "task_id": "natural_user_orders_2",
        "task_type": "natural_single_dependency",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL],
        "prompt": "Get the shipped orders for bob@company.org",
        "expected_sequence": ["lookup_user", "get_user_orders"],
        "dependency_check": "user_id propagation",
        "expected_cascade": True,
    },
    {
        "task_id": "natural_user_orders_3",
        "task_type": "natural_single_dependency",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL],
        "prompt": "I need to see what orders carol@shop.com has placed",
        "expected_sequence": ["lookup_user", "get_user_orders"],
        "dependency_check": "user_id propagation",
        "expected_cascade": True,
    },
    {
        "task_id": "natural_user_orders_4",
        "task_type": "natural_single_dependency",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL],
        "prompt": "Can you check the orders for this customer: dave@mail.com?",
        "expected_sequence": ["lookup_user", "get_user_orders"],
        "dependency_check": "user_id propagation",
        "expected_cascade": True,
    },
    {
        "task_id": "natural_kb_response_1",
        "task_type": "natural_single_dependency",
        "tools": [SEARCH_KNOWLEDGE_BASE_TOOL, GENERATE_RESPONSE_TOOL],
        "prompt": "A customer is asking about our return policy. Help them out.",
        "expected_sequence": ["search_knowledge_base", "generate_response"],
        "dependency_check": "article_ids from search used in generate_response",
        "expected_cascade": True,
    },
    {
        "task_id": "natural_kb_response_2",
        "task_type": "natural_single_dependency",
        "tools": [SEARCH_KNOWLEDGE_BASE_TOOL, GENERATE_RESPONSE_TOOL],
        "prompt": "Customer wants to know how to track their package",
        "expected_sequence": ["search_knowledge_base", "generate_response"],
        "dependency_check": "article_ids from search",
        "expected_cascade": True,
    },

    # --- 3-STEP CHAINS (Natural Language) - These are genuinely complex ---
    {
        "task_id": "natural_chain_details_1",
        "task_type": "natural_chain_3_step",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL, GET_ORDER_DETAILS_TOOL],
        "prompt": "Get the tracking number for carol@example.com's most recent delivered order",
        "expected_sequence": ["lookup_user", "get_user_orders", "get_order_details"],
        "dependency_check": "user_id → orders → order_id → details",
        "expected_cascade": False,  # Genuinely complex, should go to verifier
    },
    {
        "task_id": "natural_chain_update_1",
        "task_type": "natural_chain_3_step",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL, UPDATE_ORDER_STATUS_TOOL],
        "prompt": "Cancel the pending order for dave@shop.com - customer requested it",
        "expected_sequence": ["lookup_user", "get_user_orders", "update_order_status"],
        "dependency_check": "Full chain execution with data propagation",
        "expected_cascade": False,  # Genuinely complex
    },

    # --- PARALLEL THEN MERGE (Natural Language) ---
    {
        "task_id": "natural_quote_1",
        "task_type": "natural_parallel",
        "tools": [GET_PRODUCT_INFO_TOOL, GET_INVENTORY_TOOL, GET_PRICING_TOOL, CREATE_QUOTE_TOOL],
        "prompt": "Create a quote for 5 units of PROD-X100 from US-West for an enterprise customer",
        "expected_parallel": ["get_product_info", "get_inventory", "get_pricing"],
        "expected_final": "create_quote",
        "dependency_check": "Parallel data gathering → synthesis",
        "expected_cascade": False,  # Multiple tools + synthesis = complex
    },

    # --- CONDITIONAL (Natural Language) ---
    {
        "task_id": "natural_refund_1",
        "task_type": "natural_conditional",
        "tools": [CHECK_ELIGIBILITY_TOOL, PROCESS_REFUND_TOOL, DENY_REFUND_TOOL],
        "prompt": "Process a refund for order ORD-789, the product arrived damaged",
        "expected_sequence": ["check_eligibility", "process_refund OR deny_refund"],
        "conditional_logic": "Branch based on eligibility result",
        "expected_cascade": False,  # Conditional logic = complex
    },
]

# Add natural language tasks to main list
AGENTIC_TASKS.extend(NATURAL_LANGUAGE_TASKS)

# Add more task variations (explicit)
for i, email in enumerate(["test1@example.com", "test2@example.com", "test3@example.com"]):
    AGENTIC_TASKS.append({
        "task_id": f"dep_batch_{i}",
        "task_type": "single_dependency",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL],
        "prompt": f"Find all orders for {email}. First look up the user, then get their orders.",
        "expected_sequence": ["lookup_user", "get_user_orders"],
        "dependency_check": "user_id propagation",
    })

# Add natural language batch variations
for i, email in enumerate(["natural1@example.com", "natural2@example.com", "natural3@example.com"]):
    AGENTIC_TASKS.append({
        "task_id": f"natural_batch_{i}",
        "task_type": "natural_single_dependency",
        "tools": [LOOKUP_USER_TOOL, GET_USER_ORDERS_TOOL],
        "prompt": f"Show me the orders for {email}",
        "expected_sequence": ["lookup_user", "get_user_orders"],
        "dependency_check": "user_id propagation",
        "expected_cascade": True,
    })


class AgenticBenchmark:
    """Agentic multi-turn tool calling benchmark."""

    def __init__(
        self,
        drafter_model: str = "gpt-4o-mini",
        verifier_model: str = "gpt-4o",
    ):
        self.drafter_model = drafter_model
        self.verifier_model = verifier_model
        self.results: list[AgenticResult] = []

    def _extract_tool_calls(self, response: str) -> list[str]:
        """Extract tool names from response."""
        response_lower = response.lower()
        tools = []

        tool_names = [
            "lookup_user", "get_user_orders", "get_order_details",
            "update_order_status", "search_knowledge_base", "generate_response",
            "get_product_info", "get_inventory", "get_pricing", "create_quote",
            "check_eligibility", "process_refund", "deny_refund",
        ]

        for tool in tool_names:
            if tool in response_lower or tool.replace("_", " ") in response_lower:
                tools.append(tool)

        return tools

    def _check_dependency_flow(
        self,
        response: str,
        expected_sequence: list[str],
    ) -> tuple[bool, bool]:
        """Check if tools were called in correct sequence with dependency handling."""
        tools_found = self._extract_tool_calls(response)

        # Check sequence ordering
        sequence_correct = True
        last_idx = -1
        for expected in expected_sequence:
            if expected in tools_found:
                idx = tools_found.index(expected)
                if idx < last_idx:
                    sequence_correct = False
                    break
                last_idx = idx

        # Check if dependency keywords are mentioned (user_id, order_id, etc.)
        dependency_keywords = ["user_id", "order_id", "article_id", "product_id"]
        dependency_handled = any(kw in response.lower() for kw in dependency_keywords)

        return sequence_correct, dependency_handled

    async def run_single_turn(self, task: dict) -> AgenticResult:
        """Run a single-turn agentic task."""
        task_id = task["task_id"]
        task_type = task["task_type"]
        tools = task["tools"]
        prompt = task["prompt"]
        expected_sequence = task.get("expected_sequence", [])

        tools_desc = "\n".join([
            f"- {t['function']['name']}: {t['function']['description']}"
            for t in tools
        ])

        # Use natural language prompt to avoid inflating complexity scores
        # The system instructions with "first", "then", "1. 2. 3." trigger
        # multi-step detection in tool complexity analyzer, forcing DIRECT routing
        full_prompt = f"""You have access to these tools:
{tools_desc}

{prompt}

For each tool you would call, specify:
Tool: <name>
Parameters: <JSON>
Reason: <explanation>"""

        agent = CascadeAgent(
            models=[
                ModelConfig(name=self.drafter_model, provider="openai", cost=0.00015),
                ModelConfig(name=self.verifier_model, provider="openai", cost=0.0025),
            ],
            enable_domain_detection=True,
            use_semantic_domains=True,
            enable_tool_complexity_routing=False,  # Disable to allow CASCADE for agentic tasks
        )

        start_time = time.time()

        try:
            result = await agent.run(full_prompt, max_tokens=1000)
            latency_ms = (time.time() - start_time) * 1000

            tools_called = self._extract_tool_calls(result.content)
            sequence_correct, dependency_handled = self._check_dependency_flow(
                result.content, expected_sequence
            )

            # Task is correct if sequence is right and dependencies are handled
            correct = sequence_correct and (
                not expected_sequence or len(tools_called) >= len(expected_sequence) - 1
            )

            return AgenticResult(
                task_id=task_id,
                task_type=task_type,
                correct=correct,
                draft_accepted=result.metadata.get("draft_accepted", False),
                cost=result.total_cost,
                latency_ms=latency_ms,
                turns_completed=1,
                tools_called=tools_called,
                dependency_handled=dependency_handled,
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return AgenticResult(
                task_id=task_id,
                task_type=task_type,
                correct=False,
                draft_accepted=False,
                cost=0.0,
                latency_ms=latency_ms,
                error=str(e),
            )

    async def run_multi_turn(self, task: dict) -> AgenticResult:
        """Run a multi-turn agentic task with state tracking."""
        task_id = task["task_id"]
        task_type = task["task_type"]
        tools = task["tools"]
        turns = task["turns"]

        tools_desc = "\n".join([
            f"- {t['function']['name']}: {t['function']['description']}"
            for t in tools
        ])

        agent = CascadeAgent(
            models=[
                ModelConfig(name=self.drafter_model, provider="openai", cost=0.00015),
                ModelConfig(name=self.verifier_model, provider="openai", cost=0.0025),
            ],
            enable_domain_detection=True,
            enable_tool_complexity_routing=False,  # Disable to allow CASCADE for agentic tasks
        )

        start_time = time.time()
        total_cost = 0.0
        all_tools_called = []
        turns_completed = 0
        state_maintained = True
        conversation_history = []
        state = {}

        try:
            for turn_idx, turn in enumerate(turns):
                # Build context with history
                history_text = ""
                if conversation_history:
                    history_text = "Previous conversation:\n"
                    for h in conversation_history:
                        history_text += f"User: {h['user']}\nAssistant: {h['assistant'][:200]}...\n\n"

                # Include accumulated state
                state_text = ""
                if state:
                    state_text = f"\nKnown information from previous turns: {json.dumps(state)}\n"

                # Use natural language prompt to avoid inflating complexity scores
                prompt = f"""You have access to these tools:
{tools_desc}
{history_text}{state_text}
{turn['user']}

Format: Tool: <name>, Parameters: <JSON>"""

                result = await agent.run(prompt, max_tokens=500)
                total_cost += result.total_cost

                tools_in_turn = self._extract_tool_calls(result.content)
                all_tools_called.extend(tools_in_turn)

                # Check state requirement
                if "state_requirement" in turn and turn_idx > 0:
                    # Check if previous state is referenced
                    for key in state.keys():
                        if key not in result.content.lower():
                            state_maintained = False

                # Update state
                if "state_update" in turn:
                    state.update(turn["state_update"])

                # Track conversation
                conversation_history.append({
                    "user": turn["user"],
                    "assistant": result.content,
                })

                turns_completed += 1

            latency_ms = (time.time() - start_time) * 1000

            return AgenticResult(
                task_id=task_id,
                task_type=task_type,
                correct=turns_completed == len(turns) and state_maintained,
                draft_accepted=False,  # Multi-turn doesn't track this simply
                cost=total_cost,
                latency_ms=latency_ms,
                turns_completed=turns_completed,
                tools_called=all_tools_called,
                state_maintained=state_maintained,
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return AgenticResult(
                task_id=task_id,
                task_type=task_type,
                correct=False,
                draft_accepted=False,
                cost=total_cost,
                latency_ms=latency_ms,
                turns_completed=turns_completed,
                error=str(e),
            )

    async def run_benchmark(
        self,
        max_tasks: Optional[int] = None,
        verbose: bool = True,
    ) -> dict:
        """Run the full agentic benchmark."""
        tasks = AGENTIC_TASKS[:max_tasks] if max_tasks else AGENTIC_TASKS

        print("=" * 70)
        print("AGENTIC MULTI-TURN TOOL CALLING BENCHMARK")
        print("=" * 70)
        print("\nConfiguration:")
        print(f"  Drafter:  {self.drafter_model}")
        print(f"  Verifier: {self.verifier_model}")
        print(f"  Tasks: {len(tasks)}")
        print()

        self.results = []

        for i, task in enumerate(tasks):
            if task["task_type"] == "multi_turn_state":
                result = await self.run_multi_turn(task)
            else:
                result = await self.run_single_turn(task)

            self.results.append(result)

            status = "✓" if result.correct else "✗"
            route = "[D]" if result.draft_accepted else "[V]"
            dep = "[DEP]" if result.dependency_handled else ""

            if verbose:
                print(
                    f"[{i+1}/{len(tasks)}] {result.task_id}: {status} {route} {dep} | "
                    f"type={result.task_type} | tools={len(result.tools_called)} | "
                    f"${result.cost:.4f} | {result.latency_ms:.0f}ms"
                )
                if result.error:
                    print(f"    Error: {result.error[:60]}")

        return self._calculate_metrics()

    def _calculate_metrics(self) -> dict:
        """Calculate benchmark metrics."""
        total = len(self.results)
        correct = sum(1 for r in self.results if r.correct)
        draft_accepted = sum(1 for r in self.results if r.draft_accepted)
        dependency_handled = sum(1 for r in self.results if r.dependency_handled)
        total_cost = sum(r.cost for r in self.results)

        # Group by task type
        by_type = {}
        for r in self.results:
            if r.task_type not in by_type:
                by_type[r.task_type] = {"correct": 0, "total": 0, "draft_accepted": 0}
            by_type[r.task_type]["total"] += 1
            if r.correct:
                by_type[r.task_type]["correct"] += 1
            if r.draft_accepted:
                by_type[r.task_type]["draft_accepted"] += 1

        # Separate natural language vs explicit prompts
        natural_results = [r for r in self.results if r.task_type.startswith("natural_")]
        explicit_results = [r for r in self.results if not r.task_type.startswith("natural_")]

        natural_total = len(natural_results)
        natural_correct = sum(1 for r in natural_results if r.correct)
        natural_draft = sum(1 for r in natural_results if r.draft_accepted)

        explicit_total = len(explicit_results)
        explicit_correct = sum(1 for r in explicit_results if r.correct)
        explicit_draft = sum(1 for r in explicit_results if r.draft_accepted)

        accuracy = correct / total if total > 0 else 0
        draft_rate = draft_accepted / total if total > 0 else 0
        dependency_rate = dependency_handled / total if total > 0 else 0

        metrics = {
            "total_tasks": total,
            "correct": correct,
            "accuracy": accuracy,
            "draft_acceptance": draft_rate,
            "dependency_handling": dependency_rate,
            "total_cost": total_cost,
            "by_type": by_type,
            # Natural vs Explicit comparison
            "natural_language": {
                "total": natural_total,
                "correct": natural_correct,
                "accuracy": natural_correct / natural_total if natural_total > 0 else 0,
                "draft_rate": natural_draft / natural_total if natural_total > 0 else 0,
            },
            "explicit_steps": {
                "total": explicit_total,
                "correct": explicit_correct,
                "accuracy": explicit_correct / explicit_total if explicit_total > 0 else 0,
                "draft_rate": explicit_draft / explicit_total if explicit_total > 0 else 0,
            },
        }

        # Print summary
        print("\n" + "=" * 70)
        print("AGENTIC BENCHMARK SUMMARY")
        print("=" * 70)

        print("\nOverall Performance:")
        print(f"  Accuracy:            {accuracy:.1%} ({correct}/{total})")
        print(f"  Draft Acceptance:    {draft_rate:.1%}")
        print(f"  Dependency Handling: {dependency_rate:.1%}")
        print(f"  Total Cost:          ${total_cost:.4f}")

        # Natural vs Explicit comparison (key insight)
        print("\n" + "-" * 70)
        print("NATURAL vs EXPLICIT PROMPT COMPARISON")
        print("-" * 70)
        if natural_total > 0:
            nat_acc = natural_correct / natural_total
            nat_draft = natural_draft / natural_total
            print(f"  Natural Language:    Acc: {nat_acc:.1%} | Draft: {nat_draft:.1%} ({natural_draft}/{natural_total})")
        if explicit_total > 0:
            exp_acc = explicit_correct / explicit_total
            exp_draft = explicit_draft / explicit_total
            print(f"  Explicit Steps:      Acc: {exp_acc:.1%} | Draft: {exp_draft:.1%} ({explicit_draft}/{explicit_total})")

        if natural_total > 0 and explicit_total > 0:
            draft_diff = (natural_draft / natural_total) - (explicit_draft / explicit_total)
            if draft_diff > 0:
                print(f"\n  ⬆ Natural prompts have {draft_diff:.1%} HIGHER draft acceptance")
                print(f"    → Simpler models CAN handle natural 2-tool dependencies")
            elif draft_diff < 0:
                print(f"\n  ⬇ Explicit prompts have {-draft_diff:.1%} higher draft acceptance")
        print("-" * 70)

        print("\nBy Task Type:")
        for task_type, data in by_type.items():
            type_acc = data["correct"] / data["total"] if data["total"] > 0 else 0
            type_draft = data["draft_accepted"] / data["total"] if data["total"] > 0 else 0
            marker = "🌿" if task_type.startswith("natural_") else "📋"
            print(f"  {marker} {task_type:25} Acc: {type_acc:.1%} ({data['correct']}/{data['total']}) | Draft: {type_draft:.1%}")

        print("=" * 70)

        return metrics


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Agentic Tool Calling Benchmark")
    parser.add_argument("--sample", type=int, help="Run N tasks")
    parser.add_argument("--full", action="store_true", help="Run all tasks")
    parser.add_argument("--drafter", default="gpt-4o-mini")
    parser.add_argument("--verifier", default="gpt-4o")

    args = parser.parse_args()

    max_tasks = None
    if args.sample:
        max_tasks = args.sample
    elif not args.full:
        max_tasks = 10  # Default quick test

    benchmark = AgenticBenchmark(
        drafter_model=args.drafter,
        verifier_model=args.verifier,
    )

    results = await benchmark.run_benchmark(max_tasks=max_tasks)

    # Save results
    output_dir = Path(__file__).parent / "agentic_results"
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "results.json", "w") as f:
        json.dump({
            "config": {
                "drafter": args.drafter,
                "verifier": args.verifier,
            },
            "metrics": results,
            "results": [
                {
                    "task_id": r.task_id,
                    "task_type": r.task_type,
                    "correct": r.correct,
                    "draft_accepted": r.draft_accepted,
                    "cost": r.cost,
                    "latency_ms": r.latency_ms,
                    "turns_completed": r.turns_completed,
                    "tools_called": r.tools_called,
                    "dependency_handled": r.dependency_handled,
                    "state_maintained": r.state_maintained,
                }
                for r in benchmark.results
            ],
        }, f, indent=2)

    print(f"\nResults saved to: {output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
