"""Cost forecasting for cascadeflow.

This module provides cost prediction using exponential smoothing to forecast
future spending based on historical usage patterns.

Key Features:
- Exponential smoothing for trend prediction
- Per-user forecasting
- Daily/weekly/monthly predictions
- Confidence intervals
- Budget runway calculations

Example:
    >>> from cascadeflow.telemetry.forecasting import CostForecaster
    >>> from cascadeflow.telemetry.cost_tracker import CostTracker
    >>>
    >>> # Initialize tracker and forecaster
    >>> tracker = CostTracker()
    >>> forecaster = CostForecaster(tracker)
    >>>
    >>> # Record some usage
    >>> for day in range(30):
    ...     tracker.record_cost(0.50, user_id=f"user_{day % 5}")
    >>>
    >>> # Forecast next 7 days
    >>> prediction = forecaster.forecast_daily(days=7)
    >>> print(f"Predicted cost: ${prediction.predicted_cost:.2f}")
    >>> print(f"Confidence: {prediction.confidence:.0%}")
    >>>
    >>> # Per-user forecast
    >>> user_pred = forecaster.forecast_user("user_1", days=7)
    >>> print(f"User will spend ~${user_pred.predicted_cost:.2f}")
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CostPrediction:
    """Cost prediction result.

    Contains the predicted cost along with confidence metrics and
    additional context for decision-making.

    Attributes:
        predicted_cost: Predicted cost in USD
        lower_bound: Lower confidence bound (95% CI)
        upper_bound: Upper confidence bound (95% CI)
        confidence: Confidence score (0-1)
        period_days: Prediction period in days
        method: Forecasting method used
        historical_average: Historical average cost per day
        trend: Trend direction ("increasing", "decreasing", "stable")
        metadata: Additional prediction metadata
    """

    predicted_cost: float
    lower_bound: float
    upper_bound: float
    confidence: float
    period_days: int
    method: str = "exponential_smoothing"
    historical_average: float = 0.0
    trend: str = "stable"
    metadata: dict[str, any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate prediction values."""
        if self.predicted_cost < 0:
            self.predicted_cost = 0
        if self.lower_bound < 0:
            self.lower_bound = 0
        if self.confidence < 0:
            self.confidence = 0
        if self.confidence > 1:
            self.confidence = 1


class CostForecaster:
    """Cost forecasting using exponential smoothing.

    This class provides cost predictions based on historical usage patterns.
    Uses exponential smoothing to weight recent data more heavily while
    considering longer-term trends.

    The forecaster works with a CostTracker to access historical data and
    produces predictions with confidence intervals.

    Attributes:
        tracker: CostTracker instance with historical data
        alpha: Smoothing factor (0-1, higher = more weight on recent data)
        min_data_points: Minimum data points required for prediction
    """

    def __init__(
        self,
        tracker,
        alpha: float = 0.3,
        min_data_points: int = 7,
    ):
        """Initialize cost forecaster.

        Args:
            tracker: CostTracker instance with historical data
            alpha: Smoothing factor (0-1). Default 0.3 balances
                   recent vs historical data. Higher values react
                   faster to changes but may be more volatile.
            min_data_points: Minimum historical data points needed
                            for forecasting. Default 7 days.
        """
        self.tracker = tracker
        self.alpha = max(0.0, min(1.0, alpha))  # Clamp to [0, 1]
        self.min_data_points = max(1, min_data_points)

    def forecast_daily(
        self,
        days: int = 7,
        user_id: Optional[str] = None,
    ) -> CostPrediction:
        """Forecast daily costs for the next N days.

        Uses exponential smoothing to predict future daily costs based
        on historical patterns. Provides confidence intervals.

        Args:
            days: Number of days to forecast (default: 7)
            user_id: Optional user ID for per-user forecast

        Returns:
            CostPrediction with forecast and confidence metrics

        Example:
            >>> prediction = forecaster.forecast_daily(days=7)
            >>> print(f"Next 7 days: ${prediction.predicted_cost:.2f}")
            >>> print(f"Range: ${prediction.lower_bound:.2f} - ${prediction.upper_bound:.2f}")
        """
        # Get historical daily costs
        daily_costs = self._get_daily_costs(user_id)

        if len(daily_costs) < self.min_data_points:
            return CostPrediction(
                predicted_cost=0.0,
                lower_bound=0.0,
                upper_bound=0.0,
                confidence=0.0,
                period_days=days,
                metadata={
                    "error": "insufficient_data",
                    "data_points": len(daily_costs),
                    "required": self.min_data_points,
                },
            )

        # Calculate exponential smoothing
        smoothed_values = self._exponential_smoothing(daily_costs)

        # Get most recent smoothed value as base prediction
        base_daily_cost = smoothed_values[-1]

        # Calculate trend
        trend_direction, trend_strength = self._calculate_trend(smoothed_values)

        # Apply trend to prediction
        predicted_daily = base_daily_cost * (1 + trend_strength * days * 0.01)
        predicted_total = predicted_daily * days

        # Calculate confidence based on data stability
        confidence = self._calculate_confidence(daily_costs, smoothed_values)

        # Calculate confidence intervals (95% CI)
        std_error = self._calculate_std_error(daily_costs, smoothed_values)
        margin = 1.96 * std_error * math.sqrt(days)  # 95% CI for N days

        lower_bound = max(0, predicted_total - margin)
        upper_bound = predicted_total + margin

        return CostPrediction(
            predicted_cost=predicted_total,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            confidence=confidence,
            period_days=days,
            historical_average=sum(daily_costs) / len(daily_costs),
            trend=trend_direction,
            metadata={
                "base_daily_cost": base_daily_cost,
                "trend_strength": trend_strength,
                "data_points": len(daily_costs),
                "smoothing_alpha": self.alpha,
            },
        )

    def forecast_user(
        self,
        user_id: str,
        days: int = 7,
    ) -> CostPrediction:
        """Forecast costs for a specific user.

        Convenience method for per-user forecasting.

        Args:
            user_id: User ID to forecast
            days: Number of days to forecast

        Returns:
            CostPrediction for the user
        """
        return self.forecast_daily(days=days, user_id=user_id)

    def calculate_budget_runway(
        self,
        budget_remaining: float,
        user_id: Optional[str] = None,
    ) -> tuple[int, float]:
        """Calculate how many days until budget is exhausted.

        Args:
            budget_remaining: Remaining budget in USD
            user_id: Optional user ID for per-user calculation

        Returns:
            Tuple of (days_remaining, confidence)

        Example:
            >>> days, confidence = forecaster.calculate_budget_runway(
            ...     budget_remaining=10.00
            ... )
            >>> print(f"Budget will last {days} days (confidence: {confidence:.0%})")
        """
        # Get predicted daily cost
        prediction = self.forecast_daily(days=1, user_id=user_id)

        if prediction.predicted_cost == 0:
            return (999999, 0.0)  # Effectively infinite

        daily_cost = prediction.predicted_cost
        days_remaining = int(budget_remaining / daily_cost)

        return (days_remaining, prediction.confidence)

    def _get_daily_costs(self, user_id: Optional[str] = None) -> list[float]:
        """Get historical daily costs from tracker.

        Args:
            user_id: Optional user ID to filter by

        Returns:
            List of daily costs (most recent last)
        """
        # Get entries from tracker
        if user_id:
            entries = self.tracker.user_entries.get(user_id, [])
        else:
            entries = self.tracker.entries

        if not entries:
            return []

        # Group by day and sum
        daily_totals: dict[str, float] = {}
        for entry in entries:
            day_key = entry.timestamp.strftime("%Y-%m-%d")
            daily_totals[day_key] = daily_totals.get(day_key, 0.0) + entry.cost

        # Sort by date and return values
        sorted_days = sorted(daily_totals.keys())
        return [daily_totals[day] for day in sorted_days]

    def _exponential_smoothing(self, values: list[float]) -> list[float]:
        """Apply exponential smoothing to time series.

        Args:
            values: Time series values

        Returns:
            Smoothed values
        """
        if not values:
            return []

        smoothed = [values[0]]  # First value unchanged

        for i in range(1, len(values)):
            # S_t = α * x_t + (1 - α) * S_{t-1}
            s_t = self.alpha * values[i] + (1 - self.alpha) * smoothed[-1]
            smoothed.append(s_t)

        return smoothed

    def _calculate_trend(self, smoothed_values: list[float]) -> tuple[str, float]:
        """Calculate trend direction and strength.

        Args:
            smoothed_values: Smoothed time series

        Returns:
            Tuple of (direction, strength)
            - direction: "increasing", "decreasing", or "stable"
            - strength: Trend strength (0-1)
        """
        if len(smoothed_values) < 2:
            return ("stable", 0.0)

        # Calculate slope using linear regression
        n = len(smoothed_values)
        x = list(range(n))
        y = smoothed_values

        # Calculate means
        x_mean = sum(x) / n
        y_mean = sum(y) / n

        # Calculate slope
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return ("stable", 0.0)

        slope = numerator / denominator

        # Determine direction and strength
        if abs(slope) < 0.01 * y_mean:  # Less than 1% change per day
            return ("stable", 0.0)

        direction = "increasing" if slope > 0 else "decreasing"
        strength = min(1.0, abs(slope) / (y_mean + 0.0001))  # Normalize

        return (direction, strength)

    def _calculate_confidence(
        self,
        actual: list[float],
        smoothed: list[float],
    ) -> float:
        """Calculate confidence score based on prediction accuracy.

        Args:
            actual: Actual values
            smoothed: Smoothed (predicted) values

        Returns:
            Confidence score (0-1)
        """
        if len(actual) != len(smoothed) or len(actual) < 2:
            return 0.0

        # Calculate mean absolute percentage error (MAPE)
        mape = 0.0
        count = 0

        for i in range(len(actual)):
            if actual[i] > 0:
                mape += abs((actual[i] - smoothed[i]) / actual[i])
                count += 1

        if count == 0:
            return 0.0

        mape = mape / count

        # Convert MAPE to confidence (lower error = higher confidence)
        # MAPE of 0% = confidence 1.0
        # MAPE of 50% = confidence 0.5
        # MAPE of 100%+ = confidence 0.0
        confidence = max(0.0, 1.0 - mape)

        return confidence

    def _calculate_std_error(
        self,
        actual: list[float],
        smoothed: list[float],
    ) -> float:
        """Calculate standard error of prediction.

        Args:
            actual: Actual values
            smoothed: Smoothed (predicted) values

        Returns:
            Standard error
        """
        if len(actual) != len(smoothed) or len(actual) < 2:
            return 0.0

        # Calculate residuals
        residuals = [actual[i] - smoothed[i] for i in range(len(actual))]

        # Calculate variance
        variance = sum(r**2 for r in residuals) / len(residuals)

        # Standard error
        std_error = math.sqrt(variance)

        return std_error
