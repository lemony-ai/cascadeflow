"""
Comprehensive Telemetry Collector Test
======================================

Tests all features of MetricsCollector including:
1. Direct routing
2. Cascade with acceptance
3. Cascade with rejection
4. Streaming queries
5. Anomaly detection
6. Time-windowed stats
7. Export capabilities
8. Stats by complexity
"""

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cascadeflow.telemetry import MetricsCollector


@dataclass
class MockResult:
    """Mock CascadeResult for testing."""

    content: str
    model_used: str
    total_cost: float
    latency_ms: float
    draft_accepted: bool
    cascaded: bool
    complexity: str
    query: str
    speedup: float = 1.0
    metadata: Optional[dict[str, Any]] = None


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def create_direct_result(complexity: str = "simple", latency_ms: float = 500) -> MockResult:
    """Create a mock direct routing result."""
    return MockResult(
        content="Direct response content",
        model_used="gpt-4",
        total_cost=0.005,
        latency_ms=latency_ms,
        draft_accepted=False,
        cascaded=False,
        complexity=complexity,
        query="What is the capital of France?",
        speedup=1.0,
        metadata={
            "routing_strategy": "direct",
            "cascaded": False,
            "quality_score": None,
        },
    )


def create_cascade_accepted_result(
    complexity: str = "simple", latency_ms: float = 300
) -> MockResult:
    """Create a mock cascade result with draft accepted."""
    return MockResult(
        content="Cascade response content (draft accepted)",
        model_used="gpt-4o-mini",
        total_cost=0.0002,
        latency_ms=latency_ms,
        draft_accepted=True,
        cascaded=True,
        complexity=complexity,
        query="What is 2+2?",
        speedup=1.8,
        metadata={
            "routing_strategy": "cascade",
            "cascaded": True,
            "quality_score": 0.92,
            "draft_time_ms": 150,
            "verification_time_ms": 50,
        },
    )


def create_cascade_rejected_result(
    complexity: str = "moderate", latency_ms: float = 800
) -> MockResult:
    """Create a mock cascade result with draft rejected."""
    return MockResult(
        content="Cascade response content (draft rejected, used verifier)",
        model_used="gpt-4",
        total_cost=0.0045,
        latency_ms=latency_ms,
        draft_accepted=False,
        cascaded=True,
        complexity=complexity,
        query="Explain quantum entanglement in detail",
        speedup=1.0,
        metadata={
            "routing_strategy": "cascade",
            "cascaded": True,
            "quality_score": 0.45,
            "draft_time_ms": 200,
            "verification_time_ms": 500,
        },
    )


def test_initialization():
    """Test 1: Initialization and empty state."""
    print_section("TEST 1: INITIALIZATION")

    collector = MetricsCollector(max_recent_results=50, verbose=True)

    summary = collector.get_summary()

    # Check all keys are present
    required_keys = [
        "total_queries",
        "total_cost",
        "avg_cost",
        "avg_latency_ms",
        "cascade_used",
        "direct_routed",
        "draft_accepted",
        "draft_rejected",
        "cascade_rate",
        "acceptance_rate",
        "streaming_rate",
        "by_complexity",
        "acceptance_by_complexity",
        "quality_stats",
        "timing_stats",
    ]

    print("\n✓ Checking required keys in empty summary:")
    all_present = True
    for key in required_keys:
        present = key in summary
        status = "✓" if present else "✗"
        print(f"  {status} {key}: {summary.get(key, 'MISSING')}")
        if not present:
            all_present = False

    if all_present:
        print("\n✅ PASS: All required keys present in empty state")
        return True
    else:
        print("\n❌ FAIL: Some keys missing in empty state")
        return False


def test_direct_routing():
    """Test 2: Direct routing."""
    print_section("TEST 2: DIRECT ROUTING")

    collector = MetricsCollector(verbose=False)

    # Record 5 direct queries
    print("\n📊 Recording 5 direct routing queries...")
    for i in range(5):
        result = create_direct_result(
            complexity="hard" if i < 2 else "expert", latency_ms=500 + i * 50
        )

        collector.record(
            result=result,
            routing_strategy="direct",
            complexity=result.complexity,
            timing_breakdown={
                "complexity_detection": 30,
                "verifier_generation": result.latency_ms - 30,
            },
            streaming=False,
        )
        print(f"  Query {i+1}: {result.complexity}, {result.latency_ms}ms, ${result.total_cost}")

    summary = collector.get_summary()

    print("\n📈 Results:")
    print(f"  Total queries:    {summary['total_queries']}")
    print(f"  Direct routed:    {summary['direct_routed']}")
    print(f"  Cascade used:     {summary['cascade_used']}")
    print(f"  Total cost:       ${summary['total_cost']:.6f}")
    print(f"  Avg latency:      {summary['avg_latency_ms']:.1f}ms")
    print(f"  Cascade rate:     {summary['cascade_rate']:.1f}%")

    # Verify
    success = (
        summary["total_queries"] == 5
        and summary["direct_routed"] == 5
        and summary["cascade_used"] == 0
        and summary["cascade_rate"] == 0.0
    )

    if success:
        print("\n✅ PASS: Direct routing tracked correctly")
    else:
        print("\n❌ FAIL: Direct routing counts incorrect")

    return success


def test_cascade_accepted():
    """Test 3: Cascade with accepted drafts."""
    print_section("TEST 3: CASCADE WITH ACCEPTED DRAFTS")

    collector = MetricsCollector(verbose=False)

    # Record 8 cascade queries, all accepted
    print("\n📊 Recording 8 cascade queries (all drafts accepted)...")
    for i in range(8):
        result = create_cascade_accepted_result(
            complexity="simple" if i < 4 else "moderate", latency_ms=250 + i * 20
        )

        collector.record(
            result=result,
            routing_strategy="cascade",
            complexity=result.complexity,
            timing_breakdown={
                "complexity_detection": 30,
                "draft_generation": 150,
                "quality_verification": 50,
            },
            streaming=False,
        )
        print(f"  Query {i+1}: {result.complexity}, accepted, {result.latency_ms}ms")

    summary = collector.get_summary()

    print("\n📈 Results:")
    print(f"  Total queries:      {summary['total_queries']}")
    print(f"  Cascade used:       {summary['cascade_used']}")
    print(f"  Direct routed:      {summary['direct_routed']}")
    print(f"  Draft accepted:     {summary['draft_accepted']}")
    print(f"  Draft rejected:     {summary['draft_rejected']}")
    print(f"  Cascade rate:       {summary['cascade_rate']:.1f}%")
    print(f"  Acceptance rate:    {summary['acceptance_rate']:.1f}%")
    print(f"  Avg latency:        {summary['avg_latency_ms']:.1f}ms")

    # Check quality stats
    if summary["quality_stats"]:
        qs = summary["quality_stats"]
        print(f"\n  Quality score mean: {qs['mean']:.3f}")
        print(f"  Quality score min:  {qs['min']:.3f}")
        print(f"  Quality score max:  {qs['max']:.3f}")

    # Verify
    success = (
        summary["total_queries"] == 8
        and summary["cascade_used"] == 8
        and summary["direct_routed"] == 0
        and summary["draft_accepted"] == 8
        and summary["draft_rejected"] == 0
        and summary["acceptance_rate"] == 100.0
    )

    if success:
        print("\n✅ PASS: Cascade accepted tracked correctly")
    else:
        print("\n❌ FAIL: Cascade acceptance counts incorrect")

    return success


def test_cascade_rejected():
    """Test 4: Cascade with rejected drafts."""
    print_section("TEST 4: CASCADE WITH REJECTED DRAFTS")

    collector = MetricsCollector(verbose=False)

    # Record 5 cascade queries, all rejected
    print("\n📊 Recording 5 cascade queries (all drafts rejected)...")
    for i in range(5):
        result = create_cascade_rejected_result(
            complexity="moderate" if i < 3 else "hard", latency_ms=700 + i * 50
        )

        collector.record(
            result=result,
            routing_strategy="cascade",
            complexity=result.complexity,
            timing_breakdown={
                "complexity_detection": 40,
                "draft_generation": 200,
                "quality_verification": 100,
                "verifier_generation": 400,
            },
            streaming=False,
        )
        print(f"  Query {i+1}: {result.complexity}, rejected, {result.latency_ms}ms")

    summary = collector.get_summary()

    print("\n📈 Results:")
    print(f"  Total queries:      {summary['total_queries']}")
    print(f"  Cascade used:       {summary['cascade_used']}")
    print(f"  Draft accepted:     {summary['draft_accepted']}")
    print(f"  Draft rejected:     {summary['draft_rejected']}")
    print(f"  Acceptance rate:    {summary['acceptance_rate']:.1f}%")

    # Verify
    success = (
        summary["total_queries"] == 5
        and summary["cascade_used"] == 5
        and summary["draft_accepted"] == 0
        and summary["draft_rejected"] == 5
        and summary["acceptance_rate"] == 0.0
    )

    if success:
        print("\n✅ PASS: Cascade rejection tracked correctly")
    else:
        print("\n❌ FAIL: Cascade rejection counts incorrect")

    return success


def test_mixed_scenario():
    """Test 5: Mixed direct and cascade queries."""
    print_section("TEST 5: MIXED SCENARIO (DIRECT + CASCADE)")

    collector = MetricsCollector(verbose=False)

    print("\n📊 Recording mixed queries:")

    # 3 direct
    for _i in range(3):
        result = create_direct_result("hard", 600)
        collector.record(result, "direct", result.complexity)
    print("  ✓ 3 direct queries")

    # 5 cascade accepted
    for _i in range(5):
        result = create_cascade_accepted_result("simple", 250)
        collector.record(result, "cascade", result.complexity)
    print("  ✓ 5 cascade queries (accepted)")

    # 2 cascade rejected
    for _i in range(2):
        result = create_cascade_rejected_result("moderate", 800)
        collector.record(result, "cascade", result.complexity)
    print("  ✓ 2 cascade queries (rejected)")

    summary = collector.get_summary()

    print("\n📈 Results:")
    print(f"  Total queries:      {summary['total_queries']}")
    print(f"  Direct routed:      {summary['direct_routed']}")
    print(f"  Cascade used:       {summary['cascade_used']}")
    print(f"  Draft accepted:     {summary['draft_accepted']}")
    print(f"  Draft rejected:     {summary['draft_rejected']}")
    print(f"  Cascade rate:       {summary['cascade_rate']:.1f}%")
    print(f"  Acceptance rate:    {summary['acceptance_rate']:.1f}%")

    # Calculate expected values
    total = 10
    direct = 3
    cascade = 7
    accepted = 5
    rejected = 2
    expected_cascade_rate = (cascade / total) * 100
    expected_acceptance_rate = (accepted / cascade) * 100

    # Verify
    success = (
        summary["total_queries"] == total
        and summary["direct_routed"] == direct
        and summary["cascade_used"] == cascade
        and summary["draft_accepted"] == accepted
        and summary["draft_rejected"] == rejected
        and abs(summary["cascade_rate"] - expected_cascade_rate) < 0.1
        and abs(summary["acceptance_rate"] - expected_acceptance_rate) < 0.1
    )

    if success:
        print("\n✅ PASS: Mixed scenario tracked correctly")
    else:
        print("\n❌ FAIL: Mixed scenario counts incorrect")

    return success


def test_streaming_support():
    """Test 6: Streaming queries."""
    print_section("TEST 6: STREAMING SUPPORT")

    collector = MetricsCollector(verbose=False)

    print("\n📊 Recording streaming queries:")

    # 3 streaming
    for _i in range(3):
        result = create_direct_result("simple", 400)
        collector.record(result, "direct", result.complexity, streaming=True)
    print("  ✓ 3 streaming queries")

    # 2 non-streaming
    for _i in range(2):
        result = create_direct_result("simple", 500)
        collector.record(result, "direct", result.complexity, streaming=False)
    print("  ✓ 2 non-streaming queries")

    summary = collector.get_summary()

    print("\n📈 Results:")
    print(f"  Total queries:      {summary['total_queries']}")
    print(f"  Streaming used:     {summary.get('streaming_used', 0)}")
    print(f"  Streaming rate:     {summary['streaming_rate']:.1f}%")

    # Verify
    success = (
        summary["total_queries"] == 5
        and summary.get("streaming_used", 0) == 3
        and abs(summary["streaming_rate"] - 60.0) < 0.1
    )

    if success:
        print("\n✅ PASS: Streaming tracked correctly")
    else:
        print("\n❌ FAIL: Streaming counts incorrect")

    return success


def test_anomaly_detection():
    """Test 7: Anomaly detection."""
    print_section("TEST 7: ANOMALY DETECTION")

    collector = MetricsCollector(verbose=False)

    print("\n📊 Recording queries with anomalies:")

    # Normal queries
    for _i in range(5):
        result = create_direct_result("simple", 400)
        collector.record(result, "direct", result.complexity)
    print("  ✓ 5 normal queries (400ms)")

    # Anomalous high latency
    for _i in range(2):
        result = create_direct_result("simple", 8000)  # Very high
        collector.record(result, "direct", result.complexity)
    print("  ✓ 2 high-latency queries (8000ms)")

    # Check for anomalies
    anomalies = collector.get_recent_anomalies(latency_threshold_ms=5000, lookback_count=10)

    print(f"\n📈 Anomalies detected: {len(anomalies)}")
    for anomaly in anomalies:
        print(f"  • {anomaly['type']}: {anomaly['latency_ms']:.0f}ms")

    # Verify
    success = len(anomalies) >= 2

    if success:
        print("\n✅ PASS: Anomaly detection working")
    else:
        print("\n❌ FAIL: Anomaly detection not working")

    return success


def test_time_windowed_stats():
    """Test 8: Time-windowed statistics."""
    print_section("TEST 8: TIME-WINDOWED STATS")

    collector = MetricsCollector(verbose=False)

    print("\n📊 Recording queries with timestamps:")

    # Record some queries
    for _i in range(10):
        result = create_cascade_accepted_result("simple", 300)
        collector.record(result, "cascade", result.complexity)
        time.sleep(0.01)  # Small delay for timestamp variation

    print("  ✓ Recorded 10 cascade queries")

    # Get time-windowed stats
    window_stats = collector.get_time_windowed_stats(minutes=60)

    print("\n📈 Stats for last 60 minutes:")
    print(f"  Queries in window:  {window_stats['queries_in_window']}")
    print(f"  Avg latency:        {window_stats['avg_latency_ms']:.1f}ms")
    print(f"  Cascade rate:       {window_stats['cascade_rate']:.1f}%")
    print(f"  Acceptance rate:    {window_stats['acceptance_rate']:.1f}%")

    # Verify
    success = window_stats["queries_in_window"] == 10

    if success:
        print("\n✅ PASS: Time-windowed stats working")
    else:
        print("\n❌ FAIL: Time-windowed stats not working")

    return success


def test_complexity_breakdown():
    """Test 9: Stats by complexity level."""
    print_section("TEST 9: COMPLEXITY BREAKDOWN")

    collector = MetricsCollector(verbose=False)

    print("\n📊 Recording queries across complexity levels:")

    # Simple queries
    for _i in range(5):
        result = create_cascade_accepted_result("simple", 250)
        collector.record(result, "cascade", result.complexity)
    print("  ✓ 5 simple queries (cascade, accepted)")

    # Moderate queries
    for _i in range(3):
        result = create_cascade_rejected_result("moderate", 700)
        collector.record(result, "cascade", result.complexity)
    print("  ✓ 3 moderate queries (cascade, rejected)")

    # Hard queries
    for _i in range(2):
        result = create_direct_result("hard", 600)
        collector.record(result, "direct", result.complexity)
    print("  ✓ 2 hard queries (direct)")

    # Get stats by complexity
    simple_stats = collector.get_stats_by_complexity("simple")
    moderate_stats = collector.get_stats_by_complexity("moderate")
    hard_stats = collector.get_stats_by_complexity("hard")

    print("\n📈 Simple complexity:")
    print(f"  Total: {simple_stats['total_queries']}")
    print(f"  Acceptance rate: {simple_stats['acceptance_rate']:.1f}%")

    print("\n📈 Moderate complexity:")
    print(f"  Total: {moderate_stats['total_queries']}")
    print(f"  Acceptance rate: {moderate_stats['acceptance_rate']:.1f}%")

    print("\n📈 Hard complexity:")
    print(f"  Total: {hard_stats['total_queries']}")
    print(f"  Cascade rate: {hard_stats['cascade_rate']:.1f}%")

    # Verify
    success = (
        simple_stats["total_queries"] == 5
        and moderate_stats["total_queries"] == 3
        and hard_stats["total_queries"] == 2
        and simple_stats["acceptance_rate"] == 100.0
        and moderate_stats["acceptance_rate"] == 0.0
    )

    if success:
        print("\n✅ PASS: Complexity breakdown working")
    else:
        print("\n❌ FAIL: Complexity breakdown incorrect")

    return success


def test_export_capabilities():
    """Test 10: Export to dict and JSON."""
    print_section("TEST 10: EXPORT CAPABILITIES")

    collector = MetricsCollector(verbose=False)

    # Add some data
    for _i in range(5):
        result = create_cascade_accepted_result("simple", 300)
        collector.record(result, "cascade", result.complexity)

    print("\n📊 Testing export functions:")

    # Export to dict
    export_dict = collector.export_to_dict()
    print(f"  ✓ Exported to dict: {len(export_dict)} top-level keys")
    print(f"    Keys: {', '.join(export_dict.keys())}")

    # Export to JSON
    json_str = collector.export_to_json(filepath=None, pretty=True)
    print(f"  ✓ Exported to JSON: {len(json_str)} characters")

    # Test snapshot
    snapshot = collector.get_snapshot()
    snapshot_json = snapshot.to_json()
    print(f"  ✓ Snapshot to JSON: {len(snapshot_json)} characters")

    # Verify
    success = (
        "metadata" in export_dict
        and "summary" in export_dict
        and "snapshot" in export_dict
        and "recent_results" in export_dict
        and len(json_str) > 100
    )

    if success:
        print("\n✅ PASS: Export capabilities working")
    else:
        print("\n❌ FAIL: Export capabilities not working")

    return success


def run_all_tests():
    """Run all telemetry tests."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "TELEMETRY COLLECTOR TEST SUITE" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")

    tests = [
        ("Initialization", test_initialization),
        ("Direct Routing", test_direct_routing),
        ("Cascade Accepted", test_cascade_accepted),
        ("Cascade Rejected", test_cascade_rejected),
        ("Mixed Scenario", test_mixed_scenario),
        ("Streaming Support", test_streaming_support),
        ("Anomaly Detection", test_anomaly_detection),
        ("Time-Windowed Stats", test_time_windowed_stats),
        ("Complexity Breakdown", test_complexity_breakdown),
        ("Export Capabilities", test_export_capabilities),
    ]

    results = []

    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ EXCEPTION in {name}: {e}")
            results.append((name, False))

    # Summary
    print_section("TEST SUMMARY")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    print(f"\nResults: {passed}/{total} tests passed\n")

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}: {name}")

    print("\n" + "=" * 80)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Telemetry collector is working correctly.\n")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed. Check the output above.\n")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
