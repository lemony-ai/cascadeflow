"""
Telemetry module for cascadeflow.

Provides metrics collection, cost tracking, cost calculation, and callbacks
for monitoring and observability.

Components:
    - MetricsCollector: Aggregates statistics and performance metrics
    - MetricsSnapshot: Point-in-time metrics snapshot
    - CostCalculator: Calculate costs from results (NEW - Oct 20, 2025)
    - CostBreakdown: Structured cost breakdown data (NEW - Oct 20, 2025)
    - CostTracker: Track costs across queries over time
    - CallbackManager: Event callbacks for monitoring

Architecture:
    CostCalculator (stateless)  → Calculates costs from single results
         ↓
    CostTracker (stateful)      → Tracks costs over time
         ↓
    MetricsCollector            → Aggregates all metrics including costs

Usage:
    >>> from cascadeflow.telemetry import MetricsCollector, CostCalculator
    >>>
    >>> # Create cost calculator
    >>> calculator = CostCalculator(
    ...     drafter=drafter_model,
    ...     verifier=verifier_model
    ... )
    >>>
    >>> # Calculate costs from result
    >>> breakdown = calculator.calculate(spec_result)
    >>> print(f"Total: ${breakdown.total_cost:.6f}")
    >>> print(f"Draft: ${breakdown.draft_cost:.6f}")
    >>> print(f"Verifier: ${breakdown.verifier_cost:.6f}")
    >>>
    >>> # Collect metrics
    >>> collector = MetricsCollector()
    >>> collector.set_cost_calculator(calculator)
    >>> collector.record(result, routing_strategy='cascade', complexity='simple')
    >>>
    >>> # Get summary
    >>> summary = collector.get_summary()
    >>> print(f"Total cost: ${summary['total_cost']:.6f}")

New in v2.4 (Oct 20, 2025):
    - CostCalculator: Single source of truth for cost calculations
    - CostBreakdown: Structured cost data with transparency
    - Fixes cost aggregation bug (cascaded queries now show correct total)
"""

from .collector import MetricsCollector, MetricsSnapshot
from .cost_calculator import CostBreakdown, CostCalculator

# Import existing cost tracker if available
try:
    from .cost_tracker import BudgetConfig, CostEntry, CostTracker

    COST_TRACKER_AVAILABLE = True
except ImportError:
    COST_TRACKER_AVAILABLE = False
    CostTracker = None
    CostEntry = None
    BudgetConfig = None

# Import enforcement if available
try:
    from .enforcement import (
        EnforcementAction,
        EnforcementCallback,
        EnforcementCallbacks,
        EnforcementContext,
        graceful_degradation,
        strict_budget_enforcement,
        tier_based_enforcement,
    )

    ENFORCEMENT_AVAILABLE = True
except ImportError:
    ENFORCEMENT_AVAILABLE = False
    EnforcementAction = None
    EnforcementCallback = None
    EnforcementCallbacks = None
    EnforcementContext = None
    graceful_degradation = None
    strict_budget_enforcement = None
    tier_based_enforcement = None

# Import degradation if available
try:
    from .degradation import (
        DEFAULT_DEGRADATION_MAP,
        estimate_cost_savings,
        get_cheaper_model,
        get_degradation_chain,
    )

    DEGRADATION_AVAILABLE = True
except ImportError:
    DEGRADATION_AVAILABLE = False
    DEFAULT_DEGRADATION_MAP = None
    estimate_cost_savings = None
    get_cheaper_model = None
    get_degradation_chain = None

# Import callbacks if available
try:
    from .callbacks import CallbackManager

    CALLBACKS_AVAILABLE = True
except ImportError:
    CALLBACKS_AVAILABLE = False
    CallbackManager = None

# Import forecasting if available (NEW - Phase 2.3)
try:
    from .forecasting import CostForecaster, CostPrediction

    FORECASTING_AVAILABLE = True
except ImportError:
    FORECASTING_AVAILABLE = False
    CostForecaster = None
    CostPrediction = None

# Import anomaly detection if available (NEW - Phase 2.3)
try:
    from .anomaly import Anomaly, AnomalyDetector, AnomalySeverity, create_anomaly_alerts

    ANOMALY_AVAILABLE = True
except ImportError:
    ANOMALY_AVAILABLE = False
    Anomaly = None
    AnomalyDetector = None
    AnomalySeverity = None
    create_anomaly_alerts = None

# Build __all__ dynamically based on what's available
__all__ = [
    # Core components (always available)
    "MetricsCollector",
    "MetricsSnapshot",
    # Cost calculation (NEW - always available)
    "CostCalculator",
    "CostBreakdown",
]

# Add optional components
if COST_TRACKER_AVAILABLE:
    __all__.extend(["CostTracker", "CostEntry", "BudgetConfig"])

if ENFORCEMENT_AVAILABLE:
    __all__.extend(
        [
            "EnforcementAction",
            "EnforcementCallback",
            "EnforcementCallbacks",
            "EnforcementContext",
            "graceful_degradation",
            "strict_budget_enforcement",
            "tier_based_enforcement",
        ]
    )

if DEGRADATION_AVAILABLE:
    __all__.extend(
        [
            "DEFAULT_DEGRADATION_MAP",
            "get_cheaper_model",
            "get_degradation_chain",
            "estimate_cost_savings",
        ]
    )

if CALLBACKS_AVAILABLE:
    __all__.append("CallbackManager")

if FORECASTING_AVAILABLE:
    __all__.extend(["CostForecaster", "CostPrediction"])

if ANOMALY_AVAILABLE:
    __all__.extend(["Anomaly", "AnomalyDetector", "AnomalySeverity", "create_anomaly_alerts"])


# ============================================================================
# VERSION INFO
# ============================================================================

__version__ = "2.5.0"  # Bumped for Phase 2.3 features
__author__ = "cascadeflow Team"
__updated__ = "2025-10-20"

# Telemetry module capabilities
TELEMETRY_CAPABILITIES = {
    "metrics_collection": True,
    "cost_calculation": True,
    "cost_tracking": COST_TRACKER_AVAILABLE,
    "enforcement": ENFORCEMENT_AVAILABLE,
    "degradation": DEGRADATION_AVAILABLE,
    "callbacks": CALLBACKS_AVAILABLE,
    "forecasting": FORECASTING_AVAILABLE,  # NEW - Phase 2.3
    "anomaly_detection": ANOMALY_AVAILABLE,  # NEW - Phase 2.3
}


def get_telemetry_info():
    """
    Get information about available telemetry components.

    Returns:
        Dict with telemetry module information

    Example:
        >>> from cascadeflow.telemetry import get_telemetry_info
        >>> info = get_telemetry_info()
        >>> print(f"Cost tracking available: {info['cost_tracking']}")
    """
    return {
        "version": __version__,
        "components": __all__,
        "capabilities": TELEMETRY_CAPABILITIES,
        "updated": __updated__,
    }
