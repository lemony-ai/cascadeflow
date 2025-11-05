"""
Metrics Collector - Extract stats logic from agent.py

This module handles all statistics and metrics collection for cascadeflow,
removing ~150 lines of stats tracking from agent.py.

Features:
- Query-level metrics (cost, latency, complexity)
- Routing metrics (cascade vs direct)
- Quality system metrics (scores, acceptance rates)
- Component-level timing breakdown
- Tool calling metrics (NEW for Phase 3)
- Aggregated statistics and percentiles
- Anomaly detection
- Time-windowed metrics
- Export capabilities (dict, JSON)

Phase 3 Updates:
- Full tool calling metrics (queries, calls, rates)
- Tool usage per complexity level
- Tool call distribution tracking
- Enhanced export with tool data
"""

import json
import logging
import statistics
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricsSnapshot:
    """
    Point-in-time snapshot of metrics.

    Used for monitoring, dashboards, and reporting.
    """

    total_queries: int
    total_cost: float
    avg_latency_ms: float
    by_complexity: dict[str, int]
    by_strategy: dict[str, int]
    acceptance_rate: float
    avg_speedup: float

    # Quality metrics
    quality_mean: Optional[float] = None
    quality_median: Optional[float] = None
    quality_min: Optional[float] = None
    quality_max: Optional[float] = None

    # Timing metrics
    avg_draft_ms: Optional[float] = None
    avg_verification_ms: Optional[float] = None
    p95_draft_ms: Optional[float] = None
    p95_verification_ms: Optional[float] = None

    # Tool metrics (NEW for Phase 3)
    tool_queries: int = 0
    total_tool_calls: int = 0
    avg_tools_per_query: float = 0.0

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert snapshot to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class MetricsCollector:
    """
    Collects and aggregates metrics for cascadeflow agent.

    Tracks:
    - Query counts and costs
    - Routing decisions (cascade vs direct)
    - Quality system performance
    - Component-level timing
    - Acceptance rates by complexity
    - Tool calling usage (NEW for Phase 3)

    Methods:
    - record(result): Record a single query result
    - get_summary(): Get aggregated metrics
    - get_snapshot(): Get point-in-time snapshot
    - get_recent_anomalies(): Detect performance issues
    - get_time_windowed_stats(): Stats for recent time window
    - export_to_dict(): Export all metrics
    - export_to_json(): Export to JSON file
    - reset(): Reset all metrics
    - print_summary(): Pretty-print metrics to console

    Phase 3 Tool Metrics:
    - tool_queries: Count of queries using tools
    - total_tool_calls: Total number of tool invocations
    - avg_tools_per_query: Average tools called per tool-enabled query
    - Tool usage by complexity level
    """

    def __init__(self, max_recent_results: int = 100, verbose: bool = False):
        """
        Initialize metrics collector.

        Args:
            max_recent_results: Max results to keep for rolling stats
            verbose: Enable verbose logging
        """
        self.max_recent_results = max_recent_results
        self.verbose = verbose
        self.start_time = time.time()

        # Core metrics
        # NOTE: Using regular dict (not defaultdict) for by_complexity
        # to match agent expectations and avoid confusion
        self.stats = {
            "total_queries": 0,
            "total_cost": 0.0,
            "total_latency_ms": 0.0,
            "by_complexity": {},  # Regular dict, initialized on demand
            "direct_routed": 0,
            "cascade_used": 0,
            "draft_accepted": 0,
            "draft_rejected": 0,
            "streaming_used": 0,
            # NEW for Phase 3: Tool metrics
            "tool_queries": 0,
            "total_tool_calls": 0,
        }

        # Quality system metrics
        self.quality_scores: list[float] = []

        # Acceptance tracking by complexity
        self.acceptance_by_complexity: dict[str, dict[str, int]] = {}

        # Component timing (for percentile calculations)
        self.timing_by_component = {
            "complexity_detection": [],
            "draft_generation": [],
            "quality_verification": [],
            "verifier_generation": [],
            "cascade_overhead": [],
        }

        # Recent results for rolling metrics (with timestamps)
        self.recent_results: deque = deque(maxlen=max_recent_results)

        logger.info(
            f"MetricsCollector initialized: " f"max_recent={max_recent_results}, verbose={verbose}"
        )

    @property
    def uptime_seconds(self) -> float:
        """Get current uptime in seconds."""
        return time.time() - self.start_time

    def record(
        self,
        result: Any,
        routing_strategy: str,
        complexity: str,
        timing_breakdown: Optional[dict[str, float]] = None,
        streaming: bool = False,
        has_tools: bool = False,  # ← NEW for Phase 3
    ) -> None:
        """
        Record metrics from a query result.

        Args:
            result: CascadeResult or similar result object
            routing_strategy: 'cascade' or 'direct'
            complexity: Complexity level string
            timing_breakdown: Dict of component timings (ms)
            streaming: Whether streaming was used
            has_tools: Whether tools were used (NEW for Phase 3)

        Note:
            This method is designed to handle edge cases:
            - result can be None (tracked but skipped for metrics)
            - timing_breakdown can be None or empty
            - All attribute accesses use getattr with defaults
        """
        # Update core stats
        self.stats["total_queries"] += 1

        if streaming:
            self.stats["streaming_used"] += 1

        # Initialize complexity counter if needed (regular dict)
        if complexity not in self.stats["by_complexity"]:
            self.stats["by_complexity"][complexity] = 0
        self.stats["by_complexity"][complexity] += 1

        # Track cost and latency (with None check)
        if result:
            self.stats["total_cost"] += getattr(result, "total_cost", 0.0)
            self.stats["total_latency_ms"] += getattr(result, "latency_ms", 0.0)

        # Track routing strategy
        use_cascade = routing_strategy == "cascade"

        if use_cascade:
            self.stats["cascade_used"] += 1

            # Track acceptance (with None check)
            if result and getattr(result, "draft_accepted", False):
                self.stats["draft_accepted"] += 1

                # Initialize acceptance tracker if needed
                if complexity not in self.acceptance_by_complexity:
                    self.acceptance_by_complexity[complexity] = {"accepted": 0, "rejected": 0}
                self.acceptance_by_complexity[complexity]["accepted"] += 1
            else:
                self.stats["draft_rejected"] += 1

                # Initialize acceptance tracker if needed
                if complexity not in self.acceptance_by_complexity:
                    self.acceptance_by_complexity[complexity] = {"accepted": 0, "rejected": 0}
                self.acceptance_by_complexity[complexity]["rejected"] += 1

            # Track quality score (with None check)
            if result and hasattr(result, "metadata") and result.metadata:
                quality_score = result.metadata.get("quality_score")
                if quality_score is not None:
                    self.quality_scores.append(quality_score)
        else:
            self.stats["direct_routed"] += 1

        # Track tool usage (NEW for Phase 3)
        tool_calls_count = 0
        if has_tools:
            self.stats["tool_queries"] += 1

            # Count actual tool calls if available
            if result:
                # Try multiple ways to get tool_calls
                tool_calls = None
                if hasattr(result, "tool_calls"):
                    tool_calls = result.tool_calls
                elif hasattr(result, "metadata") and result.metadata:
                    tool_calls = result.metadata.get("tool_calls")

                if tool_calls:
                    tool_calls_count = len(tool_calls)
                    self.stats["total_tool_calls"] += tool_calls_count

        # Track component timing (with None check)
        if timing_breakdown:
            for component, timing_ms in timing_breakdown.items():
                if component in self.timing_by_component and timing_ms > 0:
                    self.timing_by_component[component].append(timing_ms)

        # Keep recent results for rolling metrics (with timestamp)
        if result:
            try:
                self.recent_results.append(
                    {
                        "cost": getattr(result, "total_cost", 0.0),
                        "latency_ms": getattr(result, "latency_ms", 0.0),
                        "complexity": complexity,
                        "cascaded": use_cascade,
                        "accepted": (
                            getattr(result, "draft_accepted", False) if use_cascade else None
                        ),
                        "speedup": getattr(result, "speedup", 1.0),
                        "streaming": streaming,
                        "has_tools": has_tools,  # NEW
                        "tool_calls_count": tool_calls_count,  # NEW
                        "timestamp": datetime.now().isoformat(),
                        "query": str(getattr(result, "content", ""))[:100],  # Truncate for memory
                        "model_used": getattr(result, "model_used", "unknown"),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to append to recent_results: {e}")

        if self.verbose:
            status = "✓ STREAMED" if streaming else "✓ COMPLETE"
            tool_info = f", {tool_calls_count} tools" if has_tools and tool_calls_count > 0 else ""
            cost = getattr(result, "total_cost", 0.0) if result else 0.0
            latency = getattr(result, "latency_ms", 0.0) if result else 0.0
            logger.debug(
                f"{status}: complexity={complexity}, strategy={routing_strategy}, "
                f"cost=${cost:.6f}, latency={latency:.0f}ms{tool_info}"
            )

    def get_summary(self) -> dict[str, Any]:
        """
        Get comprehensive summary of all metrics.

        Returns:
            Dictionary with aggregated metrics including:
            - Basic stats (queries, cost, latency)
            - Routing stats (cascade rate, acceptance rate)
            - Quality stats (mean, median, range)
            - Timing stats (averages, percentiles)
            - Tool stats (usage, call counts) - NEW for Phase 3
        """
        if self.stats["total_queries"] == 0:
            return {
                # Basic stats
                "total_queries": 0,
                "total_cost": 0.0,
                "avg_cost": 0.0,
                "avg_latency_ms": 0.0,
                "uptime_seconds": round(self.uptime_seconds, 1),
                # Routing stats - ALWAYS PRESENT
                "cascade_rate": 0.0,
                "acceptance_rate": 0.0,
                "streaming_rate": 0.0,
                "cascade_used": 0,
                "direct_routed": 0,
                "draft_accepted": 0,
                "draft_rejected": 0,
                "streaming_used": 0,
                # Tool stats - NEW for Phase 3
                "tool_queries": 0,
                "tool_rate": 0.0,
                "total_tool_calls": 0,
                "avg_tools_per_query": 0.0,
                # Distribution
                "by_complexity": {},
                "acceptance_by_complexity": {},
                # Quality and timing
                "quality_stats": {},
                "timing_stats": {},
                # Message
                "message": "No queries executed yet",
            }

        total = self.stats["total_queries"]
        cascade_total = self.stats["cascade_used"]

        # Calculate rates
        cascade_rate = cascade_total / total * 100
        acceptance_rate = (
            self.stats["draft_accepted"] / cascade_total * 100 if cascade_total > 0 else 0
        )
        streaming_rate = self.stats["streaming_used"] / total * 100

        # Calculate tool rates (NEW for Phase 3)
        tool_queries = self.stats["tool_queries"]
        tool_rate = tool_queries / total * 100 if total > 0 else 0
        avg_tools_per_query = (
            self.stats["total_tool_calls"] / tool_queries if tool_queries > 0 else 0
        )

        # Calculate averages
        avg_cost = self.stats["total_cost"] / total
        avg_latency = self.stats["total_latency_ms"] / total

        # Quality statistics
        quality_stats = {}
        if self.quality_scores:
            quality_stats = {
                "mean": statistics.mean(self.quality_scores),
                "median": statistics.median(self.quality_scores),
                "min": min(self.quality_scores),
                "max": max(self.quality_scores),
                "stdev": (
                    statistics.stdev(self.quality_scores) if len(self.quality_scores) > 1 else 0
                ),
            }

        # Timing statistics
        timing_stats = {}
        for component, timings in self.timing_by_component.items():
            if timings:
                timing_stats[f"avg_{component}_ms"] = statistics.mean(timings)
                timing_stats[f"p50_{component}_ms"] = statistics.median(timings)
                timing_stats[f"p95_{component}_ms"] = self._percentile(timings, 0.95)
                timing_stats[f"p99_{component}_ms"] = self._percentile(timings, 0.99)

        return {
            # Basic stats
            "total_queries": total,
            "total_cost": round(self.stats["total_cost"], 6),
            "avg_cost": round(avg_cost, 6),
            "avg_latency_ms": round(avg_latency, 2),
            "uptime_seconds": round(self.uptime_seconds, 1),
            # Routing stats
            "cascade_rate": round(cascade_rate, 1),
            "acceptance_rate": round(acceptance_rate, 1),
            "streaming_rate": round(streaming_rate, 1),
            "cascade_used": self.stats["cascade_used"],
            "direct_routed": self.stats["direct_routed"],
            "draft_accepted": self.stats["draft_accepted"],
            "draft_rejected": self.stats["draft_rejected"],
            "streaming_used": self.stats["streaming_used"],
            # Tool stats (NEW for Phase 3)
            "tool_queries": tool_queries,
            "tool_rate": round(tool_rate, 1),
            "total_tool_calls": self.stats["total_tool_calls"],
            "avg_tools_per_query": round(avg_tools_per_query, 2),
            # Distribution
            "by_complexity": dict(self.stats["by_complexity"]),
            "acceptance_by_complexity": dict(self.acceptance_by_complexity),
            # Quality and timing
            "quality_stats": quality_stats,
            "timing_stats": timing_stats,
        }

    def get_snapshot(self) -> MetricsSnapshot:
        """
        Get point-in-time metrics snapshot.

        Returns:
            MetricsSnapshot with current metrics
        """
        total = self.stats["total_queries"]
        cascade_total = self.stats["cascade_used"]

        if total == 0:
            return MetricsSnapshot(
                total_queries=0,
                total_cost=0.0,
                avg_latency_ms=0.0,
                by_complexity={},
                by_strategy={},
                acceptance_rate=0.0,
                avg_speedup=1.0,
                tool_queries=0,
                total_tool_calls=0,
                avg_tools_per_query=0.0,
            )

        # Calculate acceptance rate
        acceptance_rate = self.stats["draft_accepted"] / cascade_total if cascade_total > 0 else 0

        # Calculate average speedup
        avg_speedup = self._calculate_avg_speedup()

        # Tool metrics (NEW for Phase 3)
        tool_queries = self.stats["tool_queries"]
        total_tool_calls = self.stats["total_tool_calls"]
        avg_tools_per_query = total_tool_calls / tool_queries if tool_queries > 0 else 0.0

        # Quality stats
        quality_mean = None
        quality_median = None
        quality_min = None
        quality_max = None

        if self.quality_scores:
            quality_mean = statistics.mean(self.quality_scores)
            quality_median = statistics.median(self.quality_scores)
            quality_min = min(self.quality_scores)
            quality_max = max(self.quality_scores)

        # Timing stats
        avg_draft_ms = None
        avg_verification_ms = None
        p95_draft_ms = None
        p95_verification_ms = None

        if self.timing_by_component["draft_generation"]:
            avg_draft_ms = statistics.mean(self.timing_by_component["draft_generation"])
            p95_draft_ms = self._percentile(self.timing_by_component["draft_generation"], 0.95)

        if self.timing_by_component["quality_verification"]:
            avg_verification_ms = statistics.mean(self.timing_by_component["quality_verification"])
            p95_verification_ms = self._percentile(
                self.timing_by_component["quality_verification"], 0.95
            )

        return MetricsSnapshot(
            total_queries=total,
            total_cost=round(self.stats["total_cost"], 6),
            avg_latency_ms=round(self.stats["total_latency_ms"] / total, 2),
            by_complexity=dict(self.stats["by_complexity"]),
            by_strategy={
                "direct": self.stats["direct_routed"],
                "cascade": self.stats["cascade_used"],
            },
            acceptance_rate=round(acceptance_rate * 100, 1),
            avg_speedup=round(avg_speedup, 2),
            quality_mean=round(quality_mean, 3) if quality_mean else None,
            quality_median=round(quality_median, 3) if quality_median else None,
            quality_min=round(quality_min, 3) if quality_min else None,
            quality_max=round(quality_max, 3) if quality_max else None,
            avg_draft_ms=round(avg_draft_ms, 1) if avg_draft_ms else None,
            avg_verification_ms=round(avg_verification_ms, 1) if avg_verification_ms else None,
            p95_draft_ms=round(p95_draft_ms, 1) if p95_draft_ms else None,
            p95_verification_ms=round(p95_verification_ms, 1) if p95_verification_ms else None,
            tool_queries=tool_queries,
            total_tool_calls=total_tool_calls,
            avg_tools_per_query=round(avg_tools_per_query, 2),
        )

    def get_recent_anomalies(
        self,
        latency_threshold_ms: float = 5000,
        cost_threshold: float = 0.01,
        lookback_count: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Detect anomalies in recent results.

        Args:
            latency_threshold_ms: Absolute latency threshold for anomaly (default: 5000ms)
            cost_threshold: Absolute cost threshold for anomaly (default: $0.01)
            lookback_count: Number of recent results to check (default: 20)

        Returns:
            List of anomalous results with details
        """
        if not self.recent_results:
            return []

        anomalies = []

        # Calculate average latency for comparison
        avg_latency = (
            self.stats["total_latency_ms"] / self.stats["total_queries"]
            if self.stats["total_queries"] > 0
            else 0
        )

        # Check recent results
        recent = list(self.recent_results)[-lookback_count:]

        for result in recent:
            latency = result.get("latency_ms", 0)
            cost = result.get("cost", 0)

            # Detect high latency (absolute or relative)
            if latency > latency_threshold_ms or (avg_latency > 0 and latency > avg_latency * 3):
                anomalies.append(
                    {
                        "type": "high_latency",
                        "latency_ms": latency,
                        "threshold_ms": latency_threshold_ms,
                        "avg_latency_ms": avg_latency,
                        "query": result.get("query", "")[:80],
                        "model": result.get("model_used", "unknown"),
                        "timestamp": result.get("timestamp", ""),
                    }
                )

            # Detect high cost
            if cost > cost_threshold:
                anomalies.append(
                    {
                        "type": "high_cost",
                        "cost": cost,
                        "threshold": cost_threshold,
                        "query": result.get("query", "")[:80],
                        "model": result.get("model_used", "unknown"),
                        "timestamp": result.get("timestamp", ""),
                    }
                )

        return anomalies

    def get_time_windowed_stats(self, minutes: int = 60) -> dict[str, Any]:
        """
        Get statistics for a specific time window.

        Args:
            minutes: Time window in minutes (default: 60)

        Returns:
            Statistics for queries within the time window
        """
        if not self.recent_results:
            return {
                "time_window_minutes": minutes,
                "queries_in_window": 0,
                "message": "No recent results available",
            }

        cutoff = datetime.now() - timedelta(minutes=minutes)

        windowed = [
            r for r in self.recent_results if datetime.fromisoformat(r["timestamp"]) > cutoff
        ]

        if not windowed:
            return {
                "time_window_minutes": minutes,
                "queries_in_window": 0,
                "message": f"No queries in last {minutes} minutes",
            }

        # Calculate stats for window
        total_cost = sum(r["cost"] for r in windowed)
        total_latency = sum(r["latency_ms"] for r in windowed)
        cascade_count = sum(1 for r in windowed if r["cascaded"])
        streaming_count = sum(1 for r in windowed if r["streaming"])
        accepted_count = sum(1 for r in windowed if r.get("accepted", False))

        # Tool stats (NEW for Phase 3)
        tool_count = sum(1 for r in windowed if r.get("has_tools", False))
        total_tools = sum(r.get("tool_calls_count", 0) for r in windowed)

        return {
            "time_window_minutes": minutes,
            "queries_in_window": len(windowed),
            "total_cost": round(total_cost, 6),
            "avg_cost": round(total_cost / len(windowed), 6),
            "avg_latency_ms": round(total_latency / len(windowed), 1),
            "cascade_used": cascade_count,
            "cascade_rate": round(cascade_count / len(windowed) * 100, 1),
            "streaming_used": streaming_count,
            "streaming_rate": round(streaming_count / len(windowed) * 100, 1),
            "acceptance_rate": round(
                accepted_count / cascade_count * 100 if cascade_count > 0 else 0, 1
            ),
            # Tool stats (NEW)
            "tool_queries": tool_count,
            "tool_rate": round(tool_count / len(windowed) * 100, 1),
            "total_tool_calls": total_tools,
            "avg_tools_per_query": round(total_tools / tool_count if tool_count > 0 else 0, 2),
        }

    def get_stats_by_complexity(self, complexity: str) -> dict[str, Any]:
        """
        Get detailed stats for a specific complexity level.

        Args:
            complexity: Complexity level (e.g., 'simple', 'moderate', 'hard')

        Returns:
            Statistics filtered by complexity
        """
        matching = [r for r in self.recent_results if r["complexity"] == complexity]

        if not matching:
            return {
                "complexity": complexity,
                "total_queries": 0,
                "message": "No queries found for this complexity level",
            }

        cascade_count = sum(1 for r in matching if r["cascaded"])
        accepted_count = sum(1 for r in matching if r.get("accepted", False))
        tool_count = sum(1 for r in matching if r.get("has_tools", False))
        total_tools = sum(r.get("tool_calls_count", 0) for r in matching)

        return {
            "complexity": complexity,
            "total_queries": len(matching),
            "cascade_used": cascade_count,
            "cascade_rate": round(cascade_count / len(matching) * 100, 1),
            "acceptance_rate": round(
                accepted_count / cascade_count * 100 if cascade_count > 0 else 0, 1
            ),
            "avg_cost": round(sum(r["cost"] for r in matching) / len(matching), 6),
            "avg_latency_ms": round(sum(r["latency_ms"] for r in matching) / len(matching), 1),
            "avg_speedup": (
                round(statistics.mean([r["speedup"] for r in matching if r.get("speedup")]), 2)
                if any(r.get("speedup") for r in matching)
                else 1.0
            ),
            # Tool stats (NEW)
            "tool_queries": tool_count,
            "tool_rate": round(tool_count / len(matching) * 100, 1),
            "total_tool_calls": total_tools,
            "avg_tools_per_query": round(total_tools / tool_count if tool_count > 0 else 0, 2),
        }

    def export_to_dict(self) -> dict[str, Any]:
        """
        Export all metrics to dictionary.

        Returns:
            Complete metrics export including:
            - Summary statistics
            - Current snapshot
            - Recent results
            - Anomalies
            - Configuration
        """
        return {
            "metadata": {
                "export_timestamp": datetime.now().isoformat(),
                "uptime_seconds": round(self.uptime_seconds, 1),
                "max_recent_results": self.max_recent_results,
            },
            "summary": self.get_summary(),
            "snapshot": self.get_snapshot().to_dict(),
            "recent_results": list(self.recent_results)[-50:],  # Last 50
            "anomalies": self.get_recent_anomalies(),
            "time_windowed": {
                "last_60_min": self.get_time_windowed_stats(60),
                "last_24_hours": self.get_time_windowed_stats(1440),
            },
        }

    def export_to_json(self, filepath: Optional[str] = None, pretty: bool = True) -> str:
        """
        Export metrics to JSON.

        Args:
            filepath: Optional file path to save JSON
            pretty: Whether to format JSON with indentation

        Returns:
            JSON string
        """
        data = self.export_to_dict()

        indent = 2 if pretty else None
        json_str = json.dumps(data, indent=indent, default=str)

        if filepath:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_str)

            logger.info(f"Metrics exported to {filepath}")
            if self.verbose:
                print(f"[Metrics] Exported to {filepath}")

        return json_str

    def reset(self) -> None:
        """Reset all metrics to initial state."""
        self.stats = {
            "total_queries": 0,
            "total_cost": 0.0,
            "total_latency_ms": 0.0,
            "by_complexity": {},  # Regular dict
            "direct_routed": 0,
            "cascade_used": 0,
            "draft_accepted": 0,
            "draft_rejected": 0,
            "streaming_used": 0,  # ← FIXED: Include in reset
            # NEW for Phase 3: Tool metrics
            "tool_queries": 0,
            "total_tool_calls": 0,
        }

        self.quality_scores.clear()
        self.acceptance_by_complexity.clear()

        for component in self.timing_by_component:
            self.timing_by_component[component].clear()

        self.recent_results.clear()
        self.start_time = time.time()

        logger.info("Metrics reset")
        if self.verbose:
            print("[Metrics] All metrics reset")

    def _calculate_avg_speedup(self) -> float:
        """Calculate average speedup from recent results."""
        if not self.recent_results:
            return 1.0

        speedups = [
            r["speedup"]
            for r in self.recent_results
            if r["cascaded"] and r.get("accepted") and "speedup" in r
        ]

        if not speedups:
            return 1.0

        return statistics.mean(speedups)

    def _percentile(self, data: list[float], percentile: float) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile)
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]

    def print_summary(self) -> None:
        """Print formatted metrics summary to console."""
        summary = self.get_summary()

        if summary.get("total_queries", 0) == 0:
            print("\n" + "=" * 80)
            print("TELEMETRY METRICS SUMMARY")
            print("=" * 80)
            print("No metrics available - No queries executed yet")
            print("=" * 80 + "\n")
            return

        print("\n" + "=" * 80)
        print("TELEMETRY METRICS SUMMARY (Phase 3: Tool Support)")
        print("=" * 80)
        print(f"Total Queries:        {summary['total_queries']}")
        print(f"Total Cost:           ${summary['total_cost']:.6f}")
        print(f"Avg Cost/Query:       ${summary['avg_cost']:.6f}")
        print(f"Avg Latency:          {summary['avg_latency_ms']:.1f}ms")
        print(f"Uptime:               {summary['uptime_seconds']:.1f}s")
        print()
        print("ROUTING:")
        print(f"  Cascade Used:       {summary['cascade_used']} ({summary['cascade_rate']:.1f}%)")
        print(f"  Direct Routed:      {summary['direct_routed']}")
        print(
            f"  Streaming Used:     {summary['streaming_used']} ({summary['streaming_rate']:.1f}%)"
        )
        print()
        print("CASCADE PERFORMANCE:")
        print(f"  Draft Accepted:     {summary['draft_accepted']}")
        print(f"  Draft Rejected:     {summary['draft_rejected']}")
        print(f"  Acceptance Rate:    {summary['acceptance_rate']:.1f}%")

        # Tool stats (NEW for Phase 3)
        if summary.get("tool_queries", 0) > 0:
            print()
            print("TOOL CALLING (Phase 3):")
            print(f"  Queries with Tools: {summary['tool_queries']} ({summary['tool_rate']:.1f}%)")
            print(f"  Total Tool Calls:   {summary['total_tool_calls']}")
            print(f"  Avg Tools/Query:    {summary['avg_tools_per_query']:.2f}")

        if summary.get("quality_stats"):
            qs = summary["quality_stats"]
            print()
            print("QUALITY SYSTEM:")
            print(f"  Mean Score:         {qs['mean']:.3f}")
            print(f"  Median Score:       {qs['median']:.3f}")
            print(f"  Range:              {qs['min']:.3f} - {qs['max']:.3f}")
            if qs.get("stdev"):
                print(f"  Std Dev:            {qs['stdev']:.3f}")

        if summary.get("timing_stats"):
            ts = summary["timing_stats"]
            print()
            print("TIMING BREAKDOWN (ms):")

            # Group by component
            components = set()
            for key in ts.keys():
                if key.startswith("avg_"):
                    component = key.replace("avg_", "").replace("_ms", "")
                    components.add(component)

            for component in sorted(components):
                avg_key = f"avg_{component}_ms"
                p95_key = f"p95_{component}_ms"
                p99_key = f"p99_{component}_ms"

                avg_val = ts.get(avg_key, 0)
                p95_val = ts.get(p95_key, 0)
                p99_val = ts.get(p99_key, 0)

                print(
                    f"  {component:25s}: avg={avg_val:6.1f}  p95={p95_val:6.1f}  p99={p99_val:6.1f}"
                )

        print()
        print("BY COMPLEXITY:")
        for complexity, count in sorted(summary["by_complexity"].items()):
            if count > 0:
                pct = count / summary["total_queries"] * 100
                print(f"  {complexity:12s}: {count:4d} ({pct:5.1f}%)")

        # Show acceptance by complexity
        if summary.get("acceptance_by_complexity"):
            print()
            print("ACCEPTANCE BY COMPLEXITY:")
            for complexity, stats in sorted(summary["acceptance_by_complexity"].items()):
                total = stats["accepted"] + stats["rejected"]
                if total > 0:
                    rate = stats["accepted"] / total * 100
                    print(f"  {complexity:12s}: {stats['accepted']}/{total} ({rate:.1f}%)")

        # Show anomalies if any
        anomalies = self.get_recent_anomalies()
        if anomalies:
            print()
            print(f"⚠️  RECENT ANOMALIES: {len(anomalies)} detected")
            for anomaly in anomalies[:3]:  # Show top 3
                if anomaly["type"] == "high_latency":
                    print(
                        f"  • High latency: {anomaly['latency_ms']:.0f}ms "
                        f"({anomaly['query'][:40]}...)"
                    )
                elif anomaly["type"] == "high_cost":
                    print(f"  • High cost: ${anomaly['cost']:.6f} " f"({anomaly['query'][:40]}...)")

        print("=" * 80 + "\n")


__all__ = [
    "MetricsCollector",
    "MetricsSnapshot",
]
