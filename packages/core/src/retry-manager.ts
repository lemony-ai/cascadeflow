/**
 * Retry Manager with Exponential Backoff
 *
 * Provides production-grade retry logic for provider calls with intelligent
 * error classification, exponential backoff, and comprehensive metrics.
 *
 * Port from Python cascadeflow/providers/base.py RetryManager
 *
 * Features:
 * - 8 error types with specific retry strategies
 * - Exponential backoff with jitter
 * - Configurable retry policies per error type
 * - Retry metrics and statistics tracking
 * - Rate limit handling with special backoff
 *
 * @example Basic usage
 * ```typescript
 * import { RetryManager } from '@cascadeflow/core';
 *
 * const retryManager = new RetryManager();
 *
 * const result = await retryManager.executeWithRetry(async () => {
 *   return await someProviderCall();
 * });
 * ```
 *
 * @example Custom configuration
 * ```typescript
 * const retryManager = new RetryManager({
 *   maxAttempts: 5,
 *   initialDelay: 2.0,
 *   exponentialBase: 2.5,
 *   rateLimitBackoff: 60.0,
 * });
 * ```
 */

/**
 * Error types for retry classification
 *
 * Each error type has a specific retry strategy:
 * - RATE_LIMIT: Long backoff (30s default), always retry
 * - TIMEOUT: Exponential backoff, retry
 * - SERVER_ERROR: Exponential backoff, retry
 * - NETWORK_ERROR: Exponential backoff, retry
 * - AUTH_ERROR: No retry (needs user intervention)
 * - NOT_FOUND: No retry (resource doesn't exist)
 * - BAD_REQUEST: No retry (invalid request)
 * - UNKNOWN: No retry (unexpected error)
 */
export enum ErrorType {
  RATE_LIMIT = 'rate_limit',
  TIMEOUT = 'timeout',
  SERVER_ERROR = 'server_error',
  AUTH_ERROR = 'auth_error',
  NOT_FOUND = 'not_found',
  BAD_REQUEST = 'bad_request',
  NETWORK_ERROR = 'network_error',
  UNKNOWN = 'unknown',
}

/**
 * Configuration for retry behavior
 */
export interface RetryConfig {
  /** Maximum number of attempts (including first) */
  maxAttempts: number;

  /** Initial delay in seconds */
  initialDelay: number;

  /** Maximum delay in seconds */
  maxDelay: number;

  /** Base for exponential backoff (e.g., 2.0 = double each retry) */
  exponentialBase: number;

  /** Add randomness to prevent thundering herd */
  jitter: boolean;

  /** Special backoff for rate limits (seconds) */
  rateLimitBackoff: number;

  /** Which error types trigger retries */
  retryableErrors: ErrorType[];
}

/**
 * Default retry configuration
 *
 * Matches Python defaults:
 * - 3 attempts maximum
 * - 1s initial delay
 * - 60s max delay
 * - 2x exponential base
 * - Jitter enabled
 * - 30s rate limit backoff
 * - Retry: rate limits, timeouts, server errors, network errors
 */
export const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxAttempts: 3,
  initialDelay: 1.0,
  maxDelay: 60.0,
  exponentialBase: 2.0,
  jitter: true,
  rateLimitBackoff: 30.0,
  retryableErrors: [
    ErrorType.RATE_LIMIT,
    ErrorType.TIMEOUT,
    ErrorType.SERVER_ERROR,
    ErrorType.NETWORK_ERROR,
  ],
};

/**
 * Retry metrics for monitoring
 *
 * Tracks retry statistics for analysis and debugging
 */
export interface RetryMetrics {
  /** Total number of attempts (including first call) */
  totalAttempts: number;

  /** Number of successful attempts */
  successfulAttempts: number;

  /** Number of failed attempts */
  failedAttempts: number;

  /** Count of retries per error type */
  retriesByError: Record<string, number>;

  /** Total time spent waiting in retries (seconds) */
  totalRetryDelay: number;
}

/**
 * Summary of retry metrics
 */
export interface RetryMetricsSummary {
  totalAttempts: number;
  successful: number;
  failed: number;
  successRate: string;
  totalRetryDelaySec: number;
  retriesByError: Record<string, number>;
}

/**
 * Retry Manager
 *
 * Handles automatic retry logic with exponential backoff for provider calls.
 * Classifies errors and applies appropriate retry strategies.
 *
 * @example
 * ```typescript
 * const manager = new RetryManager();
 *
 * // Execute with automatic retry
 * const result = await manager.executeWithRetry(async () => {
 *   const response = await fetch('https://api.example.com/data');
 *   return response.json();
 * });
 *
 * // Check metrics
 * console.log(manager.getMetricsSummary());
 * // { totalAttempts: 2, successful: 1, failed: 1, successRate: "50.0%", ... }
 * ```
 */
export class RetryManager {
  private config: RetryConfig;
  private metrics: RetryMetrics;

  constructor(config?: Partial<RetryConfig>) {
    this.config = {
      ...DEFAULT_RETRY_CONFIG,
      ...config,
    };

    this.metrics = {
      totalAttempts: 0,
      successfulAttempts: 0,
      failedAttempts: 0,
      retriesByError: {},
      totalRetryDelay: 0,
    };
  }

  /**
   * Classify error by type
   *
   * Examines error message and properties to determine error type.
   * This enables appropriate retry strategies.
   *
   * @param error - Error to classify
   * @returns ErrorType enum value
   *
   * @example
   * ```typescript
   * const error = new Error('429 Too Many Requests');
   * const type = manager.classifyError(error);
   * console.log(type); // ErrorType.RATE_LIMIT
   * ```
   */
  classifyError(error: Error | any): ErrorType {
    const errorMsg = error.message?.toLowerCase() || String(error).toLowerCase();

    // Rate limit (429, rate limit messages)
    if (
      errorMsg.includes('429') ||
      errorMsg.includes('rate limit') ||
      errorMsg.includes('too many requests') ||
      errorMsg.includes('quota exceeded')
    ) {
      return ErrorType.RATE_LIMIT;
    }

    // Server errors (500, 502, 503, 504) - check before timeout to avoid "504 Gateway Timeout" being classified as timeout
    if (
      errorMsg.includes('500') ||
      errorMsg.includes('502') ||
      errorMsg.includes('503') ||
      errorMsg.includes('504') ||
      errorMsg.includes('internal server error') ||
      errorMsg.includes('bad gateway') ||
      errorMsg.includes('service unavailable') ||
      errorMsg.includes('gateway timeout')
    ) {
      return ErrorType.SERVER_ERROR;
    }

    // Timeout - check after server errors
    if (
      errorMsg.includes('timeout') ||
      errorMsg.includes('timed out') ||
      errorMsg.includes('etimedout') ||
      errorMsg.includes('esockettimedout')
    ) {
      return ErrorType.TIMEOUT;
    }

    // Auth errors (401, 403)
    if (
      errorMsg.includes('401') ||
      errorMsg.includes('403') ||
      errorMsg.includes('unauthorized') ||
      errorMsg.includes('forbidden') ||
      errorMsg.includes('invalid api key') ||
      errorMsg.includes('authentication') ||
      errorMsg.includes('permission denied')
    ) {
      return ErrorType.AUTH_ERROR;
    }

    // Not found (404)
    if (errorMsg.includes('404') || errorMsg.includes('not found')) {
      return ErrorType.NOT_FOUND;
    }

    // Bad request (400)
    if (errorMsg.includes('400') || errorMsg.includes('bad request')) {
      return ErrorType.BAD_REQUEST;
    }

    // Network errors
    if (
      errorMsg.includes('connection') ||
      errorMsg.includes('network') ||
      errorMsg.includes('dns') ||
      errorMsg.includes('econnrefused') ||
      errorMsg.includes('econnreset') ||
      errorMsg.includes('enotfound') ||
      errorMsg.includes('enetunreach')
    ) {
      return ErrorType.NETWORK_ERROR;
    }

    return ErrorType.UNKNOWN;
  }

  /**
   * Calculate delay with exponential backoff and jitter
   *
   * Implements exponential backoff: delay = base^attempt * initial_delay
   * Special handling for rate limits (uses rateLimitBackoff)
   * Optional jitter (±25%) to prevent thundering herd
   *
   * @param attempt - Current attempt number (1-indexed)
   * @param errorType - Type of error that occurred
   * @returns Delay in seconds
   *
   * @example
   * ```typescript
   * const delay1 = manager.calculateDelay(1, ErrorType.TIMEOUT);
   * // ~1s (initial delay)
   *
   * const delay2 = manager.calculateDelay(2, ErrorType.TIMEOUT);
   * // ~2s (exponential backoff)
   *
   * const delay3 = manager.calculateDelay(1, ErrorType.RATE_LIMIT);
   * // ~30s (special rate limit backoff)
   * ```
   */
  calculateDelay(attempt: number, errorType: ErrorType): number {
    // Special handling for rate limits
    if (errorType === ErrorType.RATE_LIMIT) {
      return this.config.rateLimitBackoff;
    }

    // Exponential backoff: base^(attempt-1) * initial_delay
    const baseDelay =
      Math.pow(this.config.exponentialBase, attempt - 1) * this.config.initialDelay;

    // Cap at max delay
    let delay = Math.min(baseDelay, this.config.maxDelay);

    // Add jitter (±25%) to prevent thundering herd
    if (this.config.jitter) {
      const jitterAmount = delay * 0.25;
      delay += Math.random() * jitterAmount * 2 - jitterAmount;
    }

    return Math.max(0, delay);
  }

  /**
   * Determine if error should trigger a retry
   *
   * Checks if:
   * 1. Max attempts not exhausted
   * 2. Error type is in retryableErrors list
   *
   * @param errorType - Type of error that occurred
   * @param attempt - Current attempt number (1-indexed)
   * @returns True if should retry, false otherwise
   *
   * @example
   * ```typescript
   * const shouldRetry1 = manager.shouldRetry(ErrorType.TIMEOUT, 1);
   * // true (timeout is retryable, under max attempts)
   *
   * const shouldRetry2 = manager.shouldRetry(ErrorType.AUTH_ERROR, 1);
   * // false (auth errors not retryable)
   *
   * const shouldRetry3 = manager.shouldRetry(ErrorType.TIMEOUT, 5);
   * // false (exceeded max attempts of 3)
   * ```
   */
  shouldRetry(errorType: ErrorType, attempt: number): boolean {
    // Exhausted max attempts?
    if (attempt >= this.config.maxAttempts) {
      return false;
    }

    // Is this error type retryable?
    return this.config.retryableErrors.includes(errorType);
  }

  /**
   * Execute function with automatic retry logic
   *
   * This is the core retry mechanism. Wraps an async function with:
   * - Automatic retry on retryable errors
   * - Exponential backoff with jitter
   * - Metrics tracking
   * - Logging
   *
   * @param fn - Async function to execute
   * @param context - Optional context for logging (e.g., "OpenAI", "Anthropic")
   * @returns Result from function
   * @throws Last exception if all retries exhausted
   *
   * @example
   * ```typescript
   * const result = await manager.executeWithRetry(
   *   async () => {
   *     return await openai.chat.completions.create({...});
   *   },
   *   'OpenAI'
   * );
   * ```
   */
  async executeWithRetry<T>(
    fn: () => Promise<T>,
    context: string = 'Provider'
  ): Promise<T> {
    let lastException: Error | undefined;

    for (let attempt = 1; attempt <= this.config.maxAttempts; attempt++) {
      this.metrics.totalAttempts++;

      try {
        // Execute the actual function
        const result = await fn();

        // Success!
        this.metrics.successfulAttempts++;

        if (attempt > 1) {
          console.log(
            `${context}: ✓ Succeeded on attempt ${attempt}/${this.config.maxAttempts}`
          );
        }

        return result;
      } catch (error: any) {
        lastException = error;
        const errorType = this.classifyError(error);

        // Update metrics
        this.metrics.failedAttempts++;
        const errorName = errorType;
        this.metrics.retriesByError[errorName] =
          (this.metrics.retriesByError[errorName] || 0) + 1;

        // Should we retry?
        if (!this.shouldRetry(errorType, attempt)) {
          console.error(
            `${context}: ✗ Not retrying ${errorType} ` +
              `on attempt ${attempt}/${this.config.maxAttempts}: ${error.message || error}`
          );
          throw error;
        }

        // Calculate delay
        const delay = this.calculateDelay(attempt, errorType);
        this.metrics.totalRetryDelay += delay;

        console.warn(
          `${context}: ⚠️  ${errorType} on attempt ${attempt}/${this.config.maxAttempts}, ` +
            `retrying in ${delay.toFixed(1)}s: ${error.message || error}`
        );

        // Wait before retry
        await this.sleep(delay);
      }
    }

    // All retries exhausted
    throw lastException || new Error('All retries exhausted');
  }

  /**
   * Get metrics summary
   *
   * Returns human-readable summary of retry statistics
   *
   * @returns RetryMetricsSummary object
   *
   * @example
   * ```typescript
   * const summary = manager.getMetricsSummary();
   * console.log(summary);
   * // {
   * //   totalAttempts: 5,
   * //   successful: 3,
   * //   failed: 2,
   * //   successRate: "60.0%",
   * //   totalRetryDelaySec: 3.5,
   * //   retriesByError: { timeout: 2 }
   * // }
   * ```
   */
  getMetricsSummary(): RetryMetricsSummary {
    const successRate =
      this.metrics.totalAttempts > 0
        ? (this.metrics.successfulAttempts / this.metrics.totalAttempts) * 100
        : 0;

    return {
      totalAttempts: this.metrics.totalAttempts,
      successful: this.metrics.successfulAttempts,
      failed: this.metrics.failedAttempts,
      successRate: `${successRate.toFixed(1)}%`,
      totalRetryDelaySec: Math.round(this.metrics.totalRetryDelay * 100) / 100,
      retriesByError: { ...this.metrics.retriesByError },
    };
  }

  /**
   * Reset metrics
   *
   * Clears all tracked statistics. Useful for testing or periodic resets.
   */
  resetMetrics(): void {
    this.metrics = {
      totalAttempts: 0,
      successfulAttempts: 0,
      failedAttempts: 0,
      retriesByError: {},
      totalRetryDelay: 0,
    };
  }

  /**
   * Get current metrics
   *
   * @returns Current RetryMetrics object
   */
  getMetrics(): RetryMetrics {
    return { ...this.metrics };
  }

  /**
   * Get current configuration
   *
   * @returns Current RetryConfig object
   */
  getConfig(): RetryConfig {
    return { ...this.config };
  }

  /**
   * Helper: Sleep for specified seconds
   *
   * @param seconds - Number of seconds to sleep
   */
  private async sleep(seconds: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, seconds * 1000));
  }
}

/**
 * Create a retry manager with custom configuration
 *
 * @param config - Partial retry configuration
 * @returns Configured RetryManager instance
 *
 * @example
 * ```typescript
 * import { createRetryManager } from '@cascadeflow/core';
 *
 * const manager = createRetryManager({
 *   maxAttempts: 5,
 *   initialDelay: 2.0,
 * });
 * ```
 */
export function createRetryManager(config?: Partial<RetryConfig>): RetryManager {
  return new RetryManager(config);
}
