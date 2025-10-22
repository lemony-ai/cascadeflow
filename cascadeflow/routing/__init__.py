"""
Routing module for CascadeFlow.

Provides routing strategies for deciding how to execute queries:
- PreRouter: Complexity-based pre-execution routing (TEXT queries)
- ConditionalRouter: Custom condition-based routing
- ToolRouter: Tool capability filtering (Phase 3) ← EXISTING
- ComplexityRouter: Tool complexity routing (Phase 4) ← NEW
- RouterChain: Chain multiple routers

Architecture Evolution:

Phase 3 (TEXT + Tool Capability):
    PreRouter     → Complexity-based routing for TEXT (SIMPLE → cascade, HARD → direct)
    ToolRouter    → Capability-based filtering (tools → only tool-capable models)
    Agent         → Orchestrates both routers

Phase 4 (Tool Complexity Routing):
    ToolComplexityAnalyzer → Analyzes TOOL CALL complexity (8 indicators → 5 clusters)
    ComplexityRouter       → Routes TOOL CALLS by complexity (CASCADE vs DIRECT)
    ToolRouter             → Still filters by capability (unchanged)

The separation keeps each router focused on one responsibility:
- PreRouter: TEXT queries - decides HOW to execute (cascade vs direct)
- ToolRouter: TOOL queries - decides WHICH models can execute (capability filtering)
- ComplexityRouter: TOOL queries - decides HOW to execute based on complexity
- All routers can be chained together via RouterChain

Phase 4 Tool Call Flow:
    1. ToolRouter → Filter to tool-capable models (capability check)
    2. ComplexityRouter → Route by complexity (CASCADE for simple, DIRECT for complex)
    3. Execute with appropriate strategy

Phase 4 Benefits:
    - 74-76% cost savings on tool calls
    - Conservative routing (85% cascade, 15% direct)
    - Complexity reuse for adaptive quality thresholds
    - No breaking changes to existing routers

Future routers:
- SemanticRouter: Semantic similarity routing
- DomainRouter: Domain-specific routing (code, math, etc)
- HybridRouter: Combine multiple strategies
- LearnedRouter: ML-based routing decisions
"""

# Base routing classes
from .base import (
    Router,
    RouterChain,
    RoutingDecision,
    RoutingStrategy,
)
from .complexity_router import (
    ComplexityRouter,
    ToolRoutingDecision,
    ToolRoutingStrategy,
)

# Phase 1-3: Existing routers (unchanged)
from .pre_router import (
    ConditionalRouter,
    PreRouter,
)

# Phase 4: Tool complexity routing (NEW)
from .tool_complexity import (
    ToolAnalysisResult,
    ToolComplexityAnalyzer,
    ToolComplexityLevel,
)
from .tool_router import (
    ToolFilterResult,
    ToolRouter,
)

__all__ = [
    # ═══════════════════════════════════════════════════
    # Base Classes
    # ═══════════════════════════════════════════════════
    "Router",
    "RoutingStrategy",
    "RoutingDecision",
    "RouterChain",
    # ═══════════════════════════════════════════════════
    # Phase 1-3: Existing Routers (UNCHANGED)
    # ═══════════════════════════════════════════════════
    "PreRouter",  # TEXT query complexity routing
    "ConditionalRouter",  # Custom condition-based routing
    "ToolRouter",  # Tool capability filtering (Phase 3)
    # ═══════════════════════════════════════════════════
    # Phase 4: Tool Complexity Routing (NEW)
    # ═══════════════════════════════════════════════════
    # Tool Complexity Analysis
    "ToolComplexityAnalyzer",  # Analyzes tool call complexity
    "ToolComplexityLevel",  # 5 complexity levels (TRIVIAL→EXPERT)
    "ToolAnalysisResult",  # Analysis result with score/signals
    # Tool Complexity Routing
    "ComplexityRouter",  # Routes tool calls by complexity
    "ToolRoutingDecision",  # CASCADE or DIRECT_LARGE
    "ToolRoutingStrategy",  # Complete routing strategy
    # ═══════════════════════════════════════════════════
    # Router-Specific Classes
    # ═══════════════════════════════════════════════════
    "ToolFilterResult",  # Tool capability filter result (Phase 3)
]

__version__ = "0.4.0"  # Phase 4

# ═══════════════════════════════════════════════════
# Quick Reference Guide
# ═══════════════════════════════════════════════════
"""
Quick Reference: Which Router When?

┌────────────────────────────────────────────────────────────────┐
│ TEXT QUERIES (no tools parameter)                              │
├────────────────────────────────────────────────────────────────┤
│ Use: PreRouter                                                 │
│ Purpose: Complexity-based routing for text generation          │
│ Example: "Explain quantum physics"                            │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ TOOL QUERIES (has tools parameter)                             │
├────────────────────────────────────────────────────────────────┤
│ Step 1: ToolRouter (capability filtering)                      │
│         → Filters to models with supports_tools=True           │
│                                                                │
│ Step 2: ComplexityRouter (complexity routing)                  │
│         → Analyzes complexity → CASCADE or DIRECT              │
│                                                                │
│ Example: "Analyze Q3 sales and forecast Q4"                   │
└────────────────────────────────────────────────────────────────┘

Usage Examples:

# TEXT ROUTING (Phase 1-3, unchanged)
from cascadeflow.routing import PreRouter
pre_router = PreRouter()
decision = pre_router.route(query="Explain AI")
# Returns: CASCADE or DIRECT based on text complexity

# TOOL CAPABILITY FILTERING (Phase 3, unchanged)
from cascadeflow.routing import ToolRouter
tool_router = ToolRouter(models=all_models)
result = tool_router.filter_tool_capable_models(tools, models)
capable_models = result['models']

# TOOL COMPLEXITY ROUTING (Phase 4, NEW)
from cascadeflow.routing import ToolComplexityAnalyzer, ComplexityRouter
analyzer = ToolComplexityAnalyzer()
router = ComplexityRouter(analyzer=analyzer)
strategy = router.route_tool_call(query="Analyze data", tools=[...])
# Returns: CASCADE or DIRECT_LARGE based on tool call complexity

# COMBINED TOOL FLOW (Phase 3 + 4)
# 1. Filter capability
capable = tool_router.filter_tool_capable_models(tools, models)
# 2. Route by complexity
strategy = complexity_router.route_tool_call(query, tools)
# 3. Execute based on strategy
if strategy.decision == ToolRoutingDecision.TOOL_CASCADE:
    # Use cascade with capable_models
else:
    # Use large model directly
"""
