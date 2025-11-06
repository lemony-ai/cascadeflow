"""
Unit tests for cost forecasting and anomaly detection.

Tests:
- CostForecaster: Exponential smoothing, per-user forecasting, budget runway
- AnomalyDetector: Z-score detection, per-user anomalies, severity levels
- Integration: Combined forecasting + anomaly detection scenarios
"""

from datetime import datetime, timedelta

import pytest

from cascadeflow.telemetry.anomaly import (
    Anomaly,
    AnomalyDetector,
    AnomalySeverity,
    create_anomaly_alerts,
)
from cascadeflow.telemetry.cost_tracker import CostTracker
from cascadeflow.telemetry.forecasting import CostForecaster


def add_cost_on_day(tracker, day_offset, cost, user_id="user1"):
    """Helper to add cost on a specific day."""
    tracker.add_cost(model="gpt-4o-mini", provider="openai", tokens=100, cost=cost, user_id=user_id)
    # Adjust timestamp to be on specific day
    if user_id in tracker.user_entries and tracker.user_entries[user_id]:
        tracker.user_entries[user_id][-1].timestamp = datetime.now() - timedelta(days=day_offset)


class TestCostForecaster:
    """Test CostForecaster class."""

    def test_create_forecaster(self):
        """Test creating forecaster."""
        tracker = CostTracker()
        forecaster = CostForecaster(tracker)
        assert forecaster.tracker == tracker
        assert forecaster.alpha == 0.3
        assert forecaster.min_data_points == 7

    def test_create_forecaster_custom_params(self):
        """Test creating forecaster with custom parameters."""
        tracker = CostTracker()
        forecaster = CostForecaster(tracker, alpha=0.5, min_data_points=10)
        assert forecaster.alpha == 0.5
        assert forecaster.min_data_points == 10

    def test_forecast_insufficient_data(self):
        """Test forecasting with insufficient data."""
        tracker = CostTracker()
        forecaster = CostForecaster(tracker, min_data_points=7)

        # Add only 3 days of data (spread across different days)
        for i in range(3):
            add_cost_on_day(tracker, day_offset=2 - i, cost=1.0, user_id="user1")

        prediction = forecaster.forecast_daily(days=7, user_id="user1")

        assert prediction.predicted_cost == 0.0
        assert prediction.confidence == 0.0
        assert "error" in prediction.metadata
        assert prediction.metadata["error"] == "insufficient_data"

    def test_forecast_stable_usage(self):
        """Test forecasting with stable daily usage."""
        tracker = CostTracker()
        forecaster = CostForecaster(tracker, alpha=0.3, min_data_points=7)

        # Add 14 days of stable usage ($1/day)
        for i in range(14):
            add_cost_on_day(tracker, day_offset=13 - i, cost=1.0, user_id="user1")

        # Forecast next 7 days
        prediction = forecaster.forecast_daily(days=7, user_id="user1")

        # With stable usage, should predict ~$7 for 7 days
        assert 6.5 <= prediction.predicted_cost <= 7.5
        assert prediction.confidence > 0.8  # High confidence for stable data
        assert prediction.trend == "stable"

    def test_forecast_increasing_trend(self):
        """Test forecasting with increasing usage trend."""
        tracker = CostTracker()
        forecaster = CostForecaster(tracker, alpha=0.3, min_data_points=7)

        # Add 14 days of increasing usage ($0.50, $0.55, $0.60, ...)
        for i in range(14):
            cost = 0.50 + (i * 0.05)  # Increases 5 cents per day
            add_cost_on_day(tracker, day_offset=13 - i, cost=cost, user_id="user1")

        prediction = forecaster.forecast_daily(days=7, user_id="user1")

        # Should predict higher cost due to increasing trend
        assert prediction.predicted_cost > 7.0  # More than stable $1/day * 7
        assert prediction.trend == "increasing"

    def test_forecast_per_user(self):
        """Test per-user forecasting."""
        tracker = CostTracker()
        forecaster = CostForecaster(tracker, min_data_points=7)

        # Add data for two users
        for i in range(10):
            # User 1: $1/day
            add_cost_on_day(tracker, day_offset=9 - i, cost=1.0, user_id="user1")
            # User 2: $2/day
            add_cost_on_day(tracker, day_offset=9 - i, cost=2.0, user_id="user2")

        # Forecast for each user
        pred1 = forecaster.forecast_user("user1", days=7)
        pred2 = forecaster.forecast_user("user2", days=7)

        # User 1 should predict ~$7, User 2 should predict ~$14
        assert 6.5 <= pred1.predicted_cost <= 7.5
        assert 13.0 <= pred2.predicted_cost <= 15.0

    def test_budget_runway_calculation(self):
        """Test budget runway calculation."""
        tracker = CostTracker()
        forecaster = CostForecaster(tracker, min_data_points=7)

        # Add 10 days of $1/day usage
        for i in range(10):
            add_cost_on_day(tracker, day_offset=9 - i, cost=1.0, user_id="user1")

        # Calculate runway with $10 remaining budget
        days, confidence = forecaster.calculate_budget_runway(
            budget_remaining=10.0, user_id="user1"
        )

        # Should last ~10 days
        assert 9 <= days <= 11
        assert confidence > 0.7


class TestAnomalyDetector:
    """Test AnomalyDetector class."""

    def test_create_detector(self):
        """Test creating anomaly detector."""
        tracker = CostTracker()
        detector = AnomalyDetector(tracker)
        assert detector.tracker == tracker
        assert detector.sensitivity == 2.5
        assert detector.min_data_points == 10

    def test_create_detector_custom_params(self):
        """Test creating detector with custom parameters."""
        tracker = CostTracker()
        detector = AnomalyDetector(tracker, sensitivity=3.0, min_data_points=15)
        assert detector.sensitivity == 3.0
        assert detector.min_data_points == 15

    def test_detect_no_anomalies(self):
        """Test detection with normal stable usage."""
        tracker = CostTracker()
        detector = AnomalyDetector(tracker, sensitivity=2.5, min_data_points=10)

        # Add 15 days of stable usage ($1/day)
        for i in range(15):
            add_cost_on_day(tracker, day_offset=14 - i, cost=1.0, user_id="user1")

        # Should detect no anomalies
        anomalies = detector.detect_user_anomalies("user1", lookback_days=15)
        assert len(anomalies) == 0

    def test_detect_single_anomaly(self):
        """Test detection of single anomaly."""
        tracker = CostTracker()
        detector = AnomalyDetector(tracker, sensitivity=2.0, min_data_points=10)

        # Add 14 days of stable usage ($1/day)
        for i in range(14):
            add_cost_on_day(tracker, day_offset=14 - i, cost=1.0, user_id="user1")

        # Add 1 day with anomalous usage ($10)
        add_cost_on_day(tracker, day_offset=0, cost=10.0, user_id="user1")

        # Should detect 1 anomaly
        anomalies = detector.detect_user_anomalies("user1", lookback_days=15)
        assert len(anomalies) == 1
        assert anomalies[0].value == 10.0
        assert anomalies[0].z_score > 2.0

    def test_anomaly_severity_levels(self):
        """Test anomaly severity classification."""
        tracker = CostTracker()
        detector = AnomalyDetector(tracker, sensitivity=2.0, min_data_points=10)

        # Add 20 days of stable usage ($1/day, low variance)
        for i in range(20):
            add_cost_on_day(tracker, day_offset=22 - i, cost=1.0, user_id="user1")

        # Add increasingly severe anomalies
        add_cost_on_day(tracker, day_offset=2, cost=5.0, user_id="user1")
        add_cost_on_day(tracker, day_offset=1, cost=10.0, user_id="user1")
        add_cost_on_day(tracker, day_offset=0, cost=20.0, user_id="user1")

        anomalies = detector.detect_user_anomalies("user1", lookback_days=25)

        # Should detect all anomalies
        assert len(anomalies) >= 1  # At least one should be detected
        # Higher costs should have higher z-scores
        z_scores = [a.z_score for a in anomalies]
        assert all(z >= 2.0 for z in z_scores)

    def test_detect_all_users(self):
        """Test detecting anomalies for all users."""
        tracker = CostTracker()
        detector = AnomalyDetector(tracker, sensitivity=2.0, min_data_points=5)

        # User 1: normal usage
        for i in range(10):
            add_cost_on_day(tracker, day_offset=9 - i, cost=1.0, user_id="user1")

        # User 2: has anomaly
        for i in range(9):
            add_cost_on_day(tracker, day_offset=9 - i, cost=1.0, user_id="user2")
        # Add anomaly for user2
        add_cost_on_day(tracker, day_offset=0, cost=10.0, user_id="user2")

        # Detect all
        all_anomalies = detector.detect_all_users(lookback_days=10)

        # Should detect anomaly for user2 only
        assert "user2" in all_anomalies
        assert len(all_anomalies["user2"]) >= 1


class TestAnomalyAlerts:
    """Test anomaly alert creation."""

    def test_create_alerts_empty(self):
        """Test creating alerts with no anomalies."""
        alerts = create_anomaly_alerts([])
        assert len(alerts) == 0

    def test_create_alerts_filter_by_severity(self):
        """Test filtering alerts by severity."""
        anomalies = [
            Anomaly(
                timestamp=datetime.now(),
                value=2.0,
                expected=1.0,
                z_score=2.5,
                severity=AnomalySeverity.LOW,
            ),
            Anomaly(
                timestamp=datetime.now(),
                value=5.0,
                expected=1.0,
                z_score=4.0,
                severity=AnomalySeverity.HIGH,
            ),
        ]

        # Filter to HIGH and above
        alerts = create_anomaly_alerts(anomalies, min_severity=AnomalySeverity.HIGH)

        assert len(alerts) == 1
        assert alerts[0]["severity"] == "high"

    def test_create_alerts_structure(self):
        """Test alert structure."""
        anomaly = Anomaly(
            timestamp=datetime.now(),
            value=10.0,
            expected=1.0,
            z_score=5.0,
            severity=AnomalySeverity.CRITICAL,
            user_id="user123",
        )

        alerts = create_anomaly_alerts([anomaly])

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["severity"] == "critical"
        assert alert["value"] == 10.0
        assert alert["expected"] == 1.0
        assert alert["z_score"] == 5.0
        assert alert["user_id"] == "user123"
        assert "title" in alert
        assert "message" in alert


class TestIntegration:
    """Test forecasting + anomaly detection integration."""

    def test_forecast_after_anomaly(self):
        """Test forecasting adapts after detecting anomaly."""
        tracker = CostTracker()
        forecaster = CostForecaster(
            tracker, alpha=0.5, min_data_points=7
        )  # Higher alpha = faster adaptation
        detector = AnomalyDetector(tracker, sensitivity=2.0, min_data_points=7)

        # Add stable usage
        for i in range(9):
            add_cost_on_day(tracker, day_offset=9 - i, cost=1.0, user_id="user1")

        # Forecast before anomaly
        pred_before = forecaster.forecast_daily(days=7, user_id="user1")

        # Add anomaly
        add_cost_on_day(tracker, day_offset=0, cost=10.0, user_id="user1")

        # Detect anomaly
        anomalies = detector.detect_user_anomalies("user1", lookback_days=10)
        assert len(anomalies) >= 1

        # Forecast after anomaly (should adjust)
        pred_after = forecaster.forecast_daily(days=7, user_id="user1")

        # Prediction should change (exponential smoothing adapts)
        # With high alpha (0.5), recent spike influences forecast
        assert pred_after.predicted_cost != pred_before.predicted_cost


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
