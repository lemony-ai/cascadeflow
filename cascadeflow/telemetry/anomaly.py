"""Anomaly detection for cascadeflow cost tracking.

This module provides anomaly detection using statistical methods (z-score)
to identify unusual spending patterns that may indicate issues or abuse.

Key Features:
- Z-score based anomaly detection
- Per-user anomaly detection
- Configurable sensitivity
- Anomaly severity levels
- Historical context

Example:
    >>> from cascadeflow.telemetry.anomaly import AnomalyDetector
    >>> from cascadeflow.telemetry.cost_tracker import CostTracker
    >>>
    >>> # Initialize tracker and detector
    >>> tracker = CostTracker()
    >>> detector = AnomalyDetector(tracker, sensitivity=2.0)
    >>>
    >>> # Record normal usage
    >>> for day in range(30):
    ...     tracker.record_cost(0.50, user_id="user_1")
    >>>
    >>> # Record anomalous usage
    >>> tracker.record_cost(5.00, user_id="user_1")  # 10x normal!
    >>>
    >>> # Detect anomalies
    >>> anomalies = detector.detect_user_anomalies("user_1")
    >>> if anomalies:
    ...     print(f"Found {len(anomalies)} anomalies!")
    ...     for anomaly in anomalies:
    ...         print(f"  {anomaly.severity}: ${anomaly.value:.2f} (expected ${anomaly.expected:.2f})")
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class AnomalySeverity(Enum):
    """Anomaly severity levels."""

    LOW = "low"  # 2-3 standard deviations
    MEDIUM = "medium"  # 3-4 standard deviations
    HIGH = "high"  # 4-5 standard deviations
    CRITICAL = "critical"  # 5+ standard deviations


@dataclass
class Anomaly:
    """Detected anomaly.

    Represents a detected anomaly with context about what was observed,
    what was expected, and how severe the anomaly is.

    Attributes:
        timestamp: When the anomaly occurred
        value: Observed value that triggered anomaly
        expected: Expected value based on historical data
        z_score: Number of standard deviations from mean
        severity: Anomaly severity level
        metric: Metric type ("cost", "tokens", "latency")
        user_id: Optional user ID if per-user anomaly
        metadata: Additional anomaly context
    """

    timestamp: datetime
    value: float
    expected: float
    z_score: float
    severity: AnomalySeverity
    metric: str = "cost"
    user_id: Optional[str] = None
    metadata: dict[str, any] = field(default_factory=dict)

    @property
    def deviation_percent(self) -> float:
        """Calculate percentage deviation from expected."""
        if self.expected == 0:
            return 0.0
        return abs((self.value - self.expected) / self.expected) * 100

    def __str__(self) -> str:
        """String representation."""
        user_str = f" (user: {self.user_id})" if self.user_id else ""
        return (
            f"{self.severity.value.upper()}: {self.metric} anomaly{user_str} - "
            f"observed ${self.value:.4f}, expected ${self.expected:.4f} "
            f"(z-score: {self.z_score:.2f}, {self.deviation_percent:.0f}% deviation)"
        )


class AnomalyDetector:
    """Anomaly detection using z-score method.

    This class detects anomalies in cost/usage patterns using statistical
    z-score analysis. Anomalies are flagged when values exceed a threshold
    number of standard deviations from the mean.

    The detector works with a CostTracker to access historical data and
    identifies unusual patterns that may indicate:
    - Budget abuse or misuse
    - Application bugs causing excessive API calls
    - Unusual user behavior
    - System issues

    Attributes:
        tracker: CostTracker instance with historical data
        sensitivity: Z-score threshold for anomaly detection (default: 2.5)
                    Lower = more sensitive (more false positives)
                    Higher = less sensitive (may miss anomalies)
        min_data_points: Minimum data points for reliable detection
    """

    def __init__(
        self,
        tracker,
        sensitivity: float = 2.5,
        min_data_points: int = 10,
    ):
        """Initialize anomaly detector.

        Args:
            tracker: CostTracker instance with historical data
            sensitivity: Z-score threshold (default: 2.5)
                        2.0 = ~95% of data (more sensitive)
                        2.5 = ~98% of data (balanced)
                        3.0 = ~99.7% of data (less sensitive)
            min_data_points: Minimum historical points needed (default: 10)
        """
        self.tracker = tracker
        self.sensitivity = max(1.0, sensitivity)
        self.min_data_points = max(3, min_data_points)

    def detect_global_anomalies(
        self,
        lookback_days: int = 7,
    ) -> list[Anomaly]:
        """Detect anomalies in global (all users) costs.

        Args:
            lookback_days: Number of days to analyze (default: 7)

        Returns:
            List of detected anomalies

        Example:
            >>> anomalies = detector.detect_global_anomalies(lookback_days=7)
            >>> for anomaly in anomalies:
            ...     print(anomaly)
        """
        daily_costs = self._get_daily_costs(user_id=None, lookback_days=lookback_days)

        if len(daily_costs) < self.min_data_points:
            logger.debug(
                f"Insufficient data for global anomaly detection: "
                f"{len(daily_costs)} < {self.min_data_points}"
            )
            return []

        return self._detect_anomalies_in_series(daily_costs, metric="cost", user_id=None)

    def detect_user_anomalies(
        self,
        user_id: str,
        lookback_days: int = 7,
    ) -> list[Anomaly]:
        """Detect anomalies for a specific user.

        Args:
            user_id: User ID to analyze
            lookback_days: Number of days to analyze (default: 7)

        Returns:
            List of detected anomalies for the user

        Example:
            >>> anomalies = detector.detect_user_anomalies("user_123")
            >>> if anomalies:
            ...     print(f"User has {len(anomalies)} anomalies!")
        """
        daily_costs = self._get_daily_costs(user_id=user_id, lookback_days=lookback_days)

        if len(daily_costs) < self.min_data_points:
            logger.debug(
                f"Insufficient data for user {user_id} anomaly detection: "
                f"{len(daily_costs)} < {self.min_data_points}"
            )
            return []

        return self._detect_anomalies_in_series(daily_costs, metric="cost", user_id=user_id)

    def detect_all_users(
        self,
        lookback_days: int = 7,
    ) -> dict[str, list[Anomaly]]:
        """Detect anomalies for all users.

        Args:
            lookback_days: Number of days to analyze

        Returns:
            Dict mapping user_id to list of anomalies

        Example:
            >>> all_anomalies = detector.detect_all_users()
            >>> for user_id, anomalies in all_anomalies.items():
            ...     if anomalies:
            ...         print(f"{user_id}: {len(anomalies)} anomalies")
        """
        results = {}

        # Get all users from tracker
        if hasattr(self.tracker, "by_user"):
            user_ids = list(self.tracker.by_user.keys())
        else:
            # Fallback: extract from entries
            user_ids = set()
            for entry in self.tracker.entries:
                if hasattr(entry, "user_id") and entry.user_id:
                    user_ids.add(entry.user_id)
            user_ids = list(user_ids)

        for user_id in user_ids:
            anomalies = self.detect_user_anomalies(user_id, lookback_days)
            if anomalies:
                results[user_id] = anomalies

        return results

    def _get_daily_costs(
        self,
        user_id: Optional[str],
        lookback_days: int,
    ) -> list[tuple[datetime, float]]:
        """Get daily costs for analysis.

        Args:
            user_id: Optional user ID to filter
            lookback_days: Number of days to look back

        Returns:
            List of (timestamp, cost) tuples
        """
        # Get entries from tracker
        if user_id:
            entries = self.tracker.user_entries.get(user_id, [])
        else:
            entries = self.tracker.entries

        if not entries:
            return []

        # Filter by lookback period
        cutoff = datetime.now() - timedelta(days=lookback_days)
        entries = [e for e in entries if e.timestamp >= cutoff]

        # Group by day
        daily_totals: dict[str, tuple[datetime, float]] = {}
        for entry in entries:
            day_key = entry.timestamp.strftime("%Y-%m-%d")
            if day_key not in daily_totals:
                daily_totals[day_key] = (entry.timestamp, 0.0)

            ts, total = daily_totals[day_key]
            daily_totals[day_key] = (ts, total + entry.cost)

        # Sort by date and return
        sorted_days = sorted(daily_totals.keys())
        return [daily_totals[day] for day in sorted_days]

    def _detect_anomalies_in_series(
        self,
        data: list[tuple[datetime, float]],
        metric: str,
        user_id: Optional[str],
    ) -> list[Anomaly]:
        """Detect anomalies in a time series using z-score.

        Args:
            data: List of (timestamp, value) tuples
            metric: Metric name
            user_id: Optional user ID

        Returns:
            List of detected anomalies
        """
        if len(data) < self.min_data_points:
            return []

        # Extract values
        values = [v for _, v in data]

        # Calculate mean and standard deviation
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            # No variance means no anomalies
            return []

        # Detect anomalies
        anomalies = []

        for i, (timestamp, value) in enumerate(data):
            z_score = abs((value - mean) / std_dev)

            if z_score >= self.sensitivity:
                # Determine severity
                severity = self._calculate_severity(z_score)

                anomaly = Anomaly(
                    timestamp=timestamp,
                    value=value,
                    expected=mean,
                    z_score=z_score,
                    severity=severity,
                    metric=metric,
                    user_id=user_id,
                    metadata={
                        "std_dev": std_dev,
                        "mean": mean,
                        "data_points": len(data),
                        "index": i,
                    },
                )

                anomalies.append(anomaly)
                logger.info(f"Anomaly detected: {anomaly}")

        return anomalies

    def _calculate_severity(self, z_score: float) -> AnomalySeverity:
        """Calculate anomaly severity from z-score.

        Args:
            z_score: Absolute z-score

        Returns:
            AnomalySeverity level
        """
        if z_score >= 5.0:
            return AnomalySeverity.CRITICAL
        elif z_score >= 4.0:
            return AnomalySeverity.HIGH
        elif z_score >= 3.0:
            return AnomalySeverity.MEDIUM
        else:
            return AnomalySeverity.LOW


def create_anomaly_alerts(
    anomalies: list[Anomaly],
    min_severity: AnomalySeverity = AnomalySeverity.MEDIUM,
) -> list[dict[str, any]]:
    """Create alert notifications from anomalies.

    Filters anomalies by severity and formats them for alerting systems
    (e.g., Slack, email, PagerDuty).

    Args:
        anomalies: List of detected anomalies
        min_severity: Minimum severity to alert on (default: MEDIUM)

    Returns:
        List of alert dicts ready for notification systems

    Example:
        >>> alerts = create_anomaly_alerts(anomalies, min_severity=AnomalySeverity.HIGH)
        >>> for alert in alerts:
        ...     send_to_slack(alert)
    """
    # Severity ordering
    severity_order = {
        AnomalySeverity.LOW: 1,
        AnomalySeverity.MEDIUM: 2,
        AnomalySeverity.HIGH: 3,
        AnomalySeverity.CRITICAL: 4,
    }

    min_level = severity_order[min_severity]

    alerts = []
    for anomaly in anomalies:
        if severity_order[anomaly.severity] >= min_level:
            alert = {
                "severity": anomaly.severity.value,
                "title": f"{anomaly.severity.value.upper()} Cost Anomaly Detected",
                "message": str(anomaly),
                "timestamp": anomaly.timestamp.isoformat(),
                "metric": anomaly.metric,
                "value": anomaly.value,
                "expected": anomaly.expected,
                "deviation_percent": anomaly.deviation_percent,
                "z_score": anomaly.z_score,
            }

            if anomaly.user_id:
                alert["user_id"] = anomaly.user_id

            alerts.append(alert)

    return alerts
