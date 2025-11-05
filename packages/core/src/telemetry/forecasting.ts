/**
 * Cost Forecasting for cascadeflow (TypeScript)
 *
 * This module provides cost prediction using exponential smoothing to forecast
 * future spending based on historical usage patterns.
 *
 * Key Features:
 * - Exponential smoothing for trend prediction
 * - Per-user forecasting
 * - Daily/weekly/monthly predictions
 * - Confidence intervals
 * - Budget runway calculations
 *
 * Example:
 * ```typescript
 * import { CostTracker, CostForecaster } from '@cascadeflow/core/telemetry';
 *
 * // Initialize
 * const tracker = new CostTracker();
 * const forecaster = new CostForecaster(tracker);
 *
 * // Record usage
 * for (let day = 0; day < 30; day++) {
 *   tracker.addCost({
 *     model: 'gpt-4o-mini',
 *     provider: 'openai',
 *     tokens: 1000,
 *     cost: 0.15,
 *     userId: 'user_1'
 *   });
 * }
 *
 * // Forecast next 7 days
 * const prediction = forecaster.forecastDaily(7, 'user_1');
 * console.log(`Predicted cost: $${prediction.predictedCost.toFixed(2)}`);
 * console.log(`Confidence: ${(prediction.confidence * 100).toFixed(0)}%`);
 * ```
 */

/**
 * Cost prediction result
 */
export interface CostPrediction {
  /** Predicted cost in USD */
  predictedCost: number;
  /** Lower confidence bound (95% CI) */
  lowerBound: number;
  /** Upper confidence bound (95% CI) */
  upperBound: number;
  /** Confidence score (0-1) */
  confidence: number;
  /** Prediction period in days */
  periodDays: number;
  /** Forecasting method used */
  method: string;
  /** Historical average cost per day */
  historicalAverage: number;
  /** Trend direction */
  trend: 'increasing' | 'decreasing' | 'stable';
  /** Additional prediction metadata */
  metadata: Record<string, any>;
}

/**
 * Cost tracker interface (minimal interface for forecaster)
 */
export interface CostEntry {
  cost: number;
  tokens: number;
  model: string;
  provider: string;
  timestamp: Date;
  userId?: string;
}

export interface ICostTracker {
  entries: CostEntry[];
  userEntries: Map<string, CostEntry[]>;
}

/**
 * Cost forecaster using exponential smoothing
 *
 * This class provides cost predictions based on historical usage patterns.
 * Uses exponential smoothing to weight recent data more heavily while
 * considering longer-term trends.
 */
export class CostForecaster {
  private tracker: ICostTracker;
  private alpha: number;
  private minDataPoints: number;

  /**
   * Initialize cost forecaster
   *
   * @param tracker - CostTracker instance with historical data
   * @param alpha - Smoothing factor (0-1). Default 0.3 balances
   *                recent vs historical data. Higher values react
   *                faster to changes but may be more volatile.
   * @param minDataPoints - Minimum historical data points needed
   *                       for forecasting. Default 7 days.
   */
  constructor(
    tracker: ICostTracker,
    alpha: number = 0.3,
    minDataPoints: number = 7
  ) {
    this.tracker = tracker;
    this.alpha = Math.max(0, Math.min(1, alpha)); // Clamp to [0, 1]
    this.minDataPoints = Math.max(1, minDataPoints);
  }

  /**
   * Forecast daily costs for the next N days
   *
   * Uses exponential smoothing to predict future daily costs based
   * on historical patterns. Provides confidence intervals.
   *
   * @param days - Number of days to forecast (default: 7)
   * @param userId - Optional user ID for per-user forecast
   * @returns CostPrediction with forecast and confidence metrics
   */
  forecastDaily(days: number = 7, userId?: string): CostPrediction {
    // Get historical daily costs
    const dailyCosts = this.getDailyCosts(userId);

    if (dailyCosts.length < this.minDataPoints) {
      return {
        predictedCost: 0,
        lowerBound: 0,
        upperBound: 0,
        confidence: 0,
        periodDays: days,
        method: 'exponential_smoothing',
        historicalAverage: 0,
        trend: 'stable',
        metadata: {
          error: 'insufficient_data',
          dataPoints: dailyCosts.length,
          required: this.minDataPoints
        }
      };
    }

    // Calculate exponential smoothing
    const smoothedValues = this.exponentialSmoothing(dailyCosts);

    // Get most recent smoothed value as base prediction
    const baseDailyCost = smoothedValues[smoothedValues.length - 1];

    // Calculate trend
    const [trendDirection, trendStrength] = this.calculateTrend(smoothedValues);

    // Apply trend to prediction
    const predictedDaily = baseDailyCost * (1 + trendStrength * days * 0.01);
    const predictedTotal = predictedDaily * days;

    // Calculate confidence based on data stability
    const confidence = this.calculateConfidence(dailyCosts, smoothedValues);

    // Calculate confidence intervals (95% CI)
    const stdError = this.calculateStdError(dailyCosts, smoothedValues);
    const margin = 1.96 * stdError * Math.sqrt(days); // 95% CI for N days

    const lowerBound = Math.max(0, predictedTotal - margin);
    const upperBound = predictedTotal + margin;

    return {
      predictedCost: predictedTotal,
      lowerBound,
      upperBound,
      confidence,
      periodDays: days,
      method: 'exponential_smoothing',
      historicalAverage: dailyCosts.reduce((a, b) => a + b, 0) / dailyCosts.length,
      trend: trendDirection,
      metadata: {
        baseDailyCost,
        trendStrength,
        dataPoints: dailyCosts.length,
        smoothingAlpha: this.alpha
      }
    };
  }

  /**
   * Forecast costs for a specific user
   *
   * Convenience method for per-user forecasting.
   *
   * @param userId - User ID to forecast
   * @param days - Number of days to forecast
   * @returns CostPrediction for the user
   */
  forecastUser(userId: string, days: number = 7): CostPrediction {
    return this.forecastDaily(days, userId);
  }

  /**
   * Calculate how many days until budget is exhausted
   *
   * @param budgetRemaining - Remaining budget in USD
   * @param userId - Optional user ID for per-user calculation
   * @returns Tuple of [daysRemaining, confidence]
   */
  calculateBudgetRunway(
    budgetRemaining: number,
    userId?: string
  ): [number, number] {
    // Get predicted daily cost
    const prediction = this.forecastDaily(1, userId);

    if (prediction.predictedCost === 0) {
      return [999999, 0]; // Effectively infinite
    }

    const dailyCost = prediction.predictedCost;
    const daysRemaining = Math.floor(budgetRemaining / dailyCost);

    return [daysRemaining, prediction.confidence];
  }

  /**
   * Get historical daily costs from tracker
   *
   * @param userId - Optional user ID to filter by
   * @returns List of daily costs (most recent last)
   */
  private getDailyCosts(userId?: string): number[] {
    // Get entries from tracker
    const entries = userId
      ? (this.tracker.userEntries.get(userId) || [])
      : this.tracker.entries;

    if (entries.length === 0) {
      return [];
    }

    // Group by day and sum
    const dailyTotals = new Map<string, number>();

    for (const entry of entries) {
      const dayKey = entry.timestamp.toISOString().split('T')[0];
      dailyTotals.set(dayKey, (dailyTotals.get(dayKey) || 0) + entry.cost);
    }

    // Sort by date and return values
    const sortedDays = Array.from(dailyTotals.keys()).sort();
    return sortedDays.map(day => dailyTotals.get(day)!);
  }

  /**
   * Apply exponential smoothing to time series
   *
   * @param values - Time series values
   * @returns Smoothed values
   */
  private exponentialSmoothing(values: number[]): number[] {
    if (values.length === 0) {
      return [];
    }

    const smoothed: number[] = [values[0]]; // First value unchanged

    for (let i = 1; i < values.length; i++) {
      // S_t = α * x_t + (1 - α) * S_{t-1}
      const st = this.alpha * values[i] + (1 - this.alpha) * smoothed[i - 1];
      smoothed.push(st);
    }

    return smoothed;
  }

  /**
   * Calculate trend direction and strength
   *
   * @param smoothedValues - Smoothed time series
   * @returns Tuple of [direction, strength]
   */
  private calculateTrend(
    smoothedValues: number[]
  ): ['increasing' | 'decreasing' | 'stable', number] {
    if (smoothedValues.length < 2) {
      return ['stable', 0];
    }

    // Calculate slope using linear regression
    const n = smoothedValues.length;
    const x = Array.from({ length: n }, (_, i) => i);
    const y = smoothedValues;

    // Calculate means
    const xMean = x.reduce((a, b) => a + b, 0) / n;
    const yMean = y.reduce((a, b) => a + b, 0) / n;

    // Calculate slope
    const numerator = x.reduce((sum, xi, i) => sum + (xi - xMean) * (y[i] - yMean), 0);
    const denominator = x.reduce((sum, xi) => sum + (xi - xMean) ** 2, 0);

    if (denominator === 0) {
      return ['stable', 0];
    }

    const slope = numerator / denominator;

    // Determine direction and strength
    if (Math.abs(slope) < 0.01 * yMean) {
      // Less than 1% change per day
      return ['stable', 0];
    }

    const direction: 'increasing' | 'decreasing' = slope > 0 ? 'increasing' : 'decreasing';
    const strength = Math.min(1, Math.abs(slope) / (yMean + 0.0001)); // Normalize

    return [direction, strength];
  }

  /**
   * Calculate confidence score based on prediction accuracy
   *
   * @param actual - Actual values
   * @param smoothed - Smoothed (predicted) values
   * @returns Confidence score (0-1)
   */
  private calculateConfidence(actual: number[], smoothed: number[]): number {
    if (actual.length !== smoothed.length || actual.length < 2) {
      return 0;
    }

    // Calculate mean absolute percentage error (MAPE)
    let mape = 0;
    let count = 0;

    for (let i = 0; i < actual.length; i++) {
      if (actual[i] > 0) {
        mape += Math.abs((actual[i] - smoothed[i]) / actual[i]);
        count++;
      }
    }

    if (count === 0) {
      return 0;
    }

    mape = mape / count;

    // Convert MAPE to confidence (lower error = higher confidence)
    // MAPE of 0% = confidence 1.0
    // MAPE of 50% = confidence 0.5
    // MAPE of 100%+ = confidence 0.0
    const confidence = Math.max(0, 1 - mape);

    return confidence;
  }

  /**
   * Calculate standard error of prediction
   *
   * @param actual - Actual values
   * @param smoothed - Smoothed (predicted) values
   * @returns Standard error
   */
  private calculateStdError(actual: number[], smoothed: number[]): number {
    if (actual.length !== smoothed.length || actual.length < 2) {
      return 0;
    }

    // Calculate residuals
    const residuals = actual.map((a, i) => a - smoothed[i]);

    // Calculate variance
    const variance = residuals.reduce((sum, r) => sum + r ** 2, 0) / residuals.length;

    // Standard error
    const stdError = Math.sqrt(variance);

    return stdError;
  }
}
