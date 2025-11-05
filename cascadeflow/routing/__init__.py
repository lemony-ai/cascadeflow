"""
Routing module for cascadeflow.

Provides routing strategies for deciding how to execute queries:
- PreRouter: Complexity-based pre-execution routing (TEXT queries)
- ConditionalRouter: Custom condition-based routing
- ToolRouter: Tool capability filtering (Phase 3) ← EXISTING
- ComplexityRouter: Tool complexity routing (Phase 4) ← EXISTING
- DomainDetector: 15-domain detection for intelligent routing (Phase 3.2) ← NEW
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

Phase 3.2 (Domain Detection):
    DomainDetector → 15-domain classification with 4-tier keyword weighting
    Domain         → Enum for 15 production domains (CODE, DATA, STRUCTURED, etc.)

The separation keeps each router focused on one responsibility:
- PreRouter: TEXT queries - decides HOW to execute (cascade vs direct)
- ToolRouter: TOOL queries - decides WHICH models can execute (capability filtering)
- ComplexityRouter: TOOL queries - decides HOW to execute based on complexity
- DomainDetector: ALL queries - detects domain for intelligent model selection
- All routers can be chained together via RouterChain

Phase 4 Tool Call Flow:
    1. ToolRouter → Filter to tool-capable models (capability check)
    2. ComplexityRouter → Route by complexity (CASCADE for simple, DIRECT for complex)
    3. Execute with appropriate strategy

Phase 3.2 Domain-Based Routing Flow (NEW):
    1. DomainDetector → Detect query domain (CODE, DATA, STRUCTURED, etc.)
    2. Get domain-specific model recommendations
    3. Route to specialized models (e.g., DeepSeek-Coder for CODE, Claude for RAG)
    4. Achieve 60-85% cost savings with domain-specific routing

Phase 3.2 Benefits:
    - 15 production domains with research-validated keywords (88% accuracy)
    - 4-tier keyword weighting (very_strong: 1.5, strong: 1.0, moderate: 0.7, weak: 0.3)
    - Domain-specific model recommendations
    - Multi-domain query detection
    - No external dependencies required

Future routers:
- SemanticRouter: Semantic similarity routing
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

# Phase 4: Tool complexity routing
from .tool_complexity import (
    ToolAnalysisResult,
    ToolComplexityAnalyzer,
    ToolComplexityLevel,
)
from .tool_router import (
    ToolFilterResult,
    ToolRouter,
)

# Phase 3.2: Domain detection
from .domain import (
    Domain,
    DomainDetectionResult,
    DomainDetector,
    DomainKeywords,
)

# Phase 4: Multi-Step Cascade Pipelines (NEW)
from .cascade_pipeline import (
    CascadeStep,
    StepResult,
    StepStatus,
    ValidationMethod,
    DomainCascadeStrategy,
    CascadeExecutionResult,
    get_code_strategy,
    get_medical_strategy,
    get_general_strategy,
    get_data_strategy,
    get_strategy_for_domain,
    list_available_strategies,
)
from .cascade_executor import MultiStepCascadeExecutor

# Phase 5: Tier-based Routing (OPTIONAL - backwards compatibility)
from .tier_routing import TierAwareRouter

__all__ = [
    # ═══════════════════════════════════════════════════
    # Base Classes
    # ═══════════════════════════════════════════════════
    "Router",
    "RoutingStrategy",
    "RoutingDecision",
    "RouterChain",
    # ═══════════════════════════════════════════════════
    # Phase 1-3: Existing Routers
    # ═══════════════════════════════════════════════════
    "PreRouter",  # TEXT query complexity routing
    "ConditionalRouter",  # Custom condition-based routing
    "ToolRouter",  # Tool capability filtering (Phase 3)
    # ═══════════════════════════════════════════════════
    # Phase 4: Tool Complexity Routing
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
    # Phase 3.2: Domain Detection
    # ═══════════════════════════════════════════════════
    "Domain",  # 15 production domains (CODE, DATA, STRUCTURED, etc.)
    "DomainDetector",  # Domain detection with 4-tier keyword weighting
    "DomainDetectionResult",  # Detection result with confidence scores
    "DomainKeywords",  # Keyword weighting configuration
    # ═══════════════════════════════════════════════════
    # Phase 4: Multi-Step Cascade Pipelines (NEW)
    # ═══════════════════════════════════════════════════
    "CascadeStep",  # Individual pipeline step configuration
    "StepResult",  # Result of executing a step
    "StepStatus",  # Execution status enum
    "ValidationMethod",  # Validation method enum
    "DomainCascadeStrategy",  # Domain-specific pipeline strategy
    "CascadeExecutionResult",  # Complete pipeline execution result
    "MultiStepCascadeExecutor",  # Pipeline executor
    # Built-in strategy getters
    "get_code_strategy",
    "get_medical_strategy",
    "get_general_strategy",
    "get_data_strategy",
    "get_strategy_for_domain",
    "list_available_strategies",
    # ═══════════════════════════════════════════════════
    # Router-Specific Classes
    # ═══════════════════════════════════════════════════
    "ToolFilterResult",  # Tool capability filter result (Phase 3)
    # ═══════════════════════════════════════════════════
    # Phase 5: Tier-based Routing (OPTIONAL)
    # ═══════════════════════════════════════════════════
    "TierAwareRouter",  # User tier-based model filtering (backwards compat)
]

__version__ = "0.6.0"  # Phase 4 (Multi-Step Cascading)

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

# TOOL COMPLEXITY ROUTING (Phase 4)
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

# DOMAIN DETECTION ROUTING (Phase 3.2, NEW)
from cascadeflow.routing import DomainDetector, Domain
detector = DomainDetector(confidence_threshold=0.3)

# Detect single domain
domain, confidence = detector.detect("Write a Python function to sort a list")
# Returns: (Domain.CODE, 0.85)

# Detect with scores for all domains
result = detector.detect_with_scores("Extract JSON from this text")
print(f"Domain: {result.domain}")  # Domain.STRUCTURED
print(f"Confidence: {result.confidence:.0%}")  # 92%
print(f"All scores: {result.scores}")  # {Domain.STRUCTURED: 0.92, ...}

# Get domain-specific model recommendations
models = detector.get_recommended_models(Domain.CODE)
print(f"Recommended for CODE: {models[0]['name']}")  # deepseek-coder

# Multi-domain queries
result = detector.detect_with_scores(
    "Implement a medical diagnosis algorithm in Python"
)
high_conf = [d for d, s in result.scores.items() if s > 0.6]
print(f"Domains detected: {high_conf}")  # [Domain.CODE, Domain.MEDICAL]
# Route to most capable model for multi-domain queries
"""
