"""
Cost Forecasting + Anomaly Detection Example

This example demonstrates Phase 2.3 features:
- Cost forecasting with exponential smoothing
- Anomaly detection with z-score analysis
- Per-user analytics
- Budget runway calculations
- Alert creation

Usage:
    python examples/cost_forecasting_anomaly_detection.py
"""

import os
import sys
from datetime import datetime, timedelta

# Add cascadeflow to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cascadeflow.telemetry import (
    CostTracker,
    CostForecaster,
    AnomalyDetector,
    AnomalySeverity,
    create_anomaly_alerts,
)


def simulate_normal_usage(tracker: CostTracker, days: int = 30, user_id: str = "user_1"):
    """Simulate normal daily usage for a user."""
    print(f"\n📊 Simulating {days} days of normal usage for {user_id}...")

    for i in range(days):
        # Normal usage: ~$0.15/day
        tracker.add_cost(
            model="gpt-4o-mini",
            provider="openai",
            tokens=1000,
            cost=0.15,
            user_id=user_id,
        )

        # Adjust timestamp to simulate historical data
        if user_id in tracker.user_entries and tracker.user_entries[user_id]:
            tracker.user_entries[user_id][-1].timestamp = datetime.now() - timedelta(
                days=days - i
            )

    print(f"✅ Recorded ${days * 0.15:.2f} over {days} days")


def simulate_anomalous_spike(tracker: CostTracker, user_id: str = "user_1"):
    """Simulate an anomalous cost spike."""
    print(f"\n⚠️  Simulating anomalous usage spike for {user_id}...")

    # Anomalous spike: 20x normal cost!
    tracker.add_cost(
        model="gpt-4",  # Expensive model
        provider="openai",
        tokens=10000,  # 10x normal tokens
        cost=3.00,  # 20x normal cost!
        user_id=user_id,
    )

    print(f"🔥 Added $3.00 cost (20x normal!)")


def demo_cost_forecasting():
    """Demonstrate cost forecasting capabilities."""
    print("\n" + "=" * 70)
    print("DEMO 1: COST FORECASTING")
    print("=" * 70)

    # Initialize tracker and forecaster
    tracker = CostTracker()
    forecaster = CostForecaster(
        tracker,
        alpha=0.3,  # Smoothing factor (0-1, higher = more reactive)
        min_data_points=7,  # Minimum days of data required
    )

    # Simulate historical usage
    simulate_normal_usage(tracker, days=30, user_id="user_1")

    # Forecast next 7 days
    print("\n📈 Forecasting next 7 days...")
    prediction = forecaster.forecast_daily(days=7, user_id="user_1")

    print(f"\n✨ Prediction Results:")
    print(f"  Predicted cost: ${prediction.predicted_cost:.4f}")
    print(
        f"  Confidence interval: ${prediction.lower_bound:.4f} - ${prediction.upper_bound:.4f}"
    )
    print(f"  Confidence: {prediction.confidence:.1%}")
    print(f"  Trend: {prediction.trend}")
    print(f"  Historical average: ${prediction.historical_average:.4f}/day")
    print(f"  Method: {prediction.method}")

    # Calculate budget runway
    print("\n💰 Budget Runway Calculation:")
    budget_remaining = 10.00
    days_left, confidence = forecaster.calculate_budget_runway(
        budget_remaining=budget_remaining, user_id="user_1"
    )

    print(f"  Remaining budget: ${budget_remaining:.2f}")
    print(f"  Estimated runway: {days_left} days")
    print(f"  Confidence: {confidence:.1%}")

    if days_left < 14:
        print(f"  ⚠️  WARNING: Budget will run out in {days_left} days!")
    else:
        print(f"  ✅ Budget looks healthy ({days_left} days remaining)")


def demo_anomaly_detection():
    """Demonstrate anomaly detection capabilities."""
    print("\n" + "=" * 70)
    print("DEMO 2: ANOMALY DETECTION")
    print("=" * 70)

    # Initialize tracker and detector
    tracker = CostTracker()
    detector = AnomalyDetector(
        tracker,
        sensitivity=2.5,  # Z-score threshold (2.5 = ~98% of normal data)
        min_data_points=10,  # Minimum data points for reliable detection
    )

    # Simulate normal usage
    simulate_normal_usage(tracker, days=30, user_id="user_1")

    # Check for anomalies (should find none)
    print("\n🔍 Detecting anomalies in normal usage...")
    anomalies = detector.detect_user_anomalies("user_1", lookback_days=30)
    print(f"  Anomalies detected: {len(anomalies)}")

    # Simulate anomalous spike
    simulate_anomalous_spike(tracker, user_id="user_1")

    # Detect anomalies (should find the spike)
    print("\n🔍 Re-detecting anomalies after spike...")
    anomalies = detector.detect_user_anomalies("user_1", lookback_days=30)
    print(f"  Anomalies detected: {len(anomalies)}")

    if anomalies:
        print("\n🚨 Anomaly Details:")
        for i, anomaly in enumerate(anomalies, 1):
            print(f"\n  Anomaly #{i}:")
            print(f"    Timestamp: {anomaly.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Value: ${anomaly.value:.4f}")
            print(f"    Expected: ${anomaly.expected:.4f}")
            print(f"    Deviation: {anomaly.deviation_percent:.0f}%")
            print(f"    Z-score: {anomaly.z_score:.2f}")
            print(f"    Severity: {anomaly.severity.value.upper()}")

        # Create alerts for high-severity anomalies
        print("\n📬 Creating alerts for high-severity anomalies...")
        alerts = create_anomaly_alerts(anomalies, min_severity=AnomalySeverity.MEDIUM)

        for alert in alerts:
            print(f"\n  Alert:")
            print(f"    {alert['title']}")
            print(f"    {alert['message']}")
            print(f"    Severity: {alert['severity']}")


def demo_multi_user_analytics():
    """Demonstrate per-user analytics."""
    print("\n" + "=" * 70)
    print("DEMO 3: MULTI-USER ANALYTICS")
    print("=" * 70)

    # Initialize tracker, forecaster, and detector
    tracker = CostTracker()
    forecaster = CostForecaster(tracker, alpha=0.3, min_data_points=7)
    detector = AnomalyDetector(tracker, sensitivity=2.0, min_data_points=5)

    # Simulate different usage patterns for 3 users
    users = {
        "free_tier_user": {"days": 14, "daily_cost": 0.05},
        "pro_tier_user": {"days": 14, "daily_cost": 0.50},
        "enterprise_user": {"days": 14, "daily_cost": 2.00},
    }

    for user_id, config in users.items():
        print(f"\n👤 Simulating {user_id} (${config['daily_cost']}/day)...")
        for day in range(config["days"]):
            tracker.add_cost(
                model="gpt-4o-mini",
                provider="openai",
                tokens=int(config["daily_cost"] * 1000),
                cost=config["daily_cost"],
                user_id=user_id,
            )

            # Adjust timestamp
            if user_id in tracker.user_entries and tracker.user_entries[user_id]:
                tracker.user_entries[user_id][-1].timestamp = datetime.now() - timedelta(
                    days=config["days"] - day
                )

    # Add anomaly for enterprise user
    print("\n⚠️  Adding cost spike for enterprise_user...")
    tracker.add_cost(
        model="gpt-4",
        provider="openai",
        tokens=50000,
        cost=15.00,  # 7.5x normal!
        user_id="enterprise_user",
    )

    # Forecast for each user
    print("\n📈 Per-User Forecasts (next 7 days):")
    for user_id in users.keys():
        pred = forecaster.forecast_user(user_id, days=7)
        print(f"\n  {user_id}:")
        print(f"    Predicted: ${pred.predicted_cost:.4f}")
        print(f"    Confidence: {pred.confidence:.1%}")
        print(f"    Trend: {pred.trend}")

    # Detect anomalies for all users
    print("\n🔍 Detecting Anomalies Across All Users:")
    all_anomalies = detector.detect_all_users(lookback_days=14)

    if all_anomalies:
        print(f"\n  Found anomalies for {len(all_anomalies)} user(s):")
        for user_id, anomalies in all_anomalies.items():
            print(f"\n    {user_id}: {len(anomalies)} anomalie(s)")
            for anomaly in anomalies:
                print(f"      - ${anomaly.value:.2f} (z-score: {anomaly.z_score:.2f})")
    else:
        print("\n  ✅ No anomalies detected across all users")


def demo_integration():
    """Demonstrate integrated forecasting + anomaly detection workflow."""
    print("\n" + "=" * 70)
    print("DEMO 4: INTEGRATED WORKFLOW")
    print("=" * 70)

    # Initialize all components
    tracker = CostTracker()
    forecaster = CostForecaster(tracker, alpha=0.5, min_data_points=7)  # More reactive
    detector = AnomalyDetector(tracker, sensitivity=2.0, min_data_points=7)

    # Simulate normal usage
    simulate_normal_usage(tracker, days=10, user_id="api_user")

    # Initial forecast
    print("\n📊 Initial Forecast:")
    pred_before = forecaster.forecast_daily(days=7, user_id="api_user")
    print(f"  Predicted 7-day cost: ${pred_before.predicted_cost:.4f}")

    # Simulate anomaly
    simulate_anomalous_spike(tracker, user_id="api_user")

    # Detect anomaly
    print("\n🔍 Checking for anomalies...")
    anomalies = detector.detect_user_anomalies("api_user", lookback_days=10)

    if anomalies:
        print(f"  ⚠️  Detected {len(anomalies)} anomaly!")

        # Re-forecast after anomaly
        print("\n📈 Updated Forecast (post-anomaly):")
        pred_after = forecaster.forecast_daily(days=7, user_id="api_user")
        print(f"  NEW predicted cost: ${pred_after.predicted_cost:.4f}")
        print(
            f"  Change: ${pred_after.predicted_cost - pred_before.predicted_cost:+.4f}"
        )

        # With high alpha (0.5), recent spike significantly affects forecast
        print("\n💡 Insight:")
        print(
            f"  The forecaster adapted to the anomaly due to high alpha ({forecaster.alpha})"
        )
        print(
            "  This means recent data is weighted heavily in predictions"
        )

        # Create alerts
        alerts = create_anomaly_alerts(anomalies, min_severity=AnomalySeverity.MEDIUM)
        if alerts:
            print(f"\n📬 Generated {len(alerts)} alert(s) for monitoring system")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("CASCADEFLOW: COST FORECASTING + ANOMALY DETECTION")
    print("Phase 2.3 Feature Demonstration")
    print("=" * 70)

    # Run all demos
    demo_cost_forecasting()
    demo_anomaly_detection()
    demo_multi_user_analytics()
    demo_integration()

    print("\n" + "=" * 70)
    print("✅ ALL DEMOS COMPLETE")
    print("=" * 70)
    print("\n💡 Key Takeaways:")
    print("  - Cost forecasting predicts future spending with confidence intervals")
    print("  - Anomaly detection identifies unusual patterns automatically")
    print("  - Per-user analytics enable fine-grained cost management")
    print("  - Integration allows predictive alerting and budget planning")
    print("\n🚀 Ready for production use!")
    print()
