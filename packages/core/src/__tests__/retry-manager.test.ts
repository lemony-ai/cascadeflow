/**
 * Retry Manager Tests
 *
 * Comprehensive test suite for RetryManager class.
 * Tests error classification, exponential backoff, retry logic, and metrics.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  RetryManager,
  ErrorType,
  createRetryManager,
  type RetryConfig,
} from '../retry-manager';

describe('RetryManager', () => {
  let manager: RetryManager;

  beforeEach(() => {
    manager = new RetryManager();
  });

  describe('error classification', () => {
    it('should classify rate limit errors', () => {
      const errors = [
        new Error('429 Too Many Requests'),
        new Error('Rate limit exceeded'),
        new Error('quota exceeded'),
        new Error('too many requests'),
      ];

      for (const error of errors) {
        expect(manager.classifyError(error)).toBe(ErrorType.RATE_LIMIT);
      }
    });

    it('should classify timeout errors', () => {
      const errors = [
        new Error('Request timed out'),
        new Error('ETIMEDOUT'),
        new Error('ESOCKETTIMEDOUT'),
        new Error('Connection timeout'),
      ];

      for (const error of errors) {
        expect(manager.classifyError(error)).toBe(ErrorType.TIMEOUT);
      }
    });

    it('should classify server errors', () => {
      const errors = [
        new Error('500 Internal Server Error'),
        new Error('502 Bad Gateway'),
        new Error('503 Service Unavailable'),
        new Error('504 Gateway Timeout'),
        new Error('Internal server error'),
      ];

      for (const error of errors) {
        expect(manager.classifyError(error)).toBe(ErrorType.SERVER_ERROR);
      }
    });

    it('should classify auth errors', () => {
      const errors = [
        new Error('401 Unauthorized'),
        new Error('403 Forbidden'),
        new Error('Invalid API key'),
        new Error('Authentication failed'),
        new Error('Permission denied'),
      ];

      for (const error of errors) {
        expect(manager.classifyError(error)).toBe(ErrorType.AUTH_ERROR);
      }
    });

    it('should classify not found errors', () => {
      const errors = [new Error('404 Not Found'), new Error('Resource not found')];

      for (const error of errors) {
        expect(manager.classifyError(error)).toBe(ErrorType.NOT_FOUND);
      }
    });

    it('should classify bad request errors', () => {
      const errors = [new Error('400 Bad Request'), new Error('Bad request')];

      for (const error of errors) {
        expect(manager.classifyError(error)).toBe(ErrorType.BAD_REQUEST);
      }
    });

    it('should classify network errors', () => {
      const errors = [
        new Error('ECONNREFUSED'),
        new Error('ECONNRESET'),
        new Error('ENOTFOUND'),
        new Error('ENETUNREACH'),
        new Error('Network error'),
        new Error('Connection failed'),
        new Error('DNS lookup failed'),
      ];

      for (const error of errors) {
        expect(manager.classifyError(error)).toBe(ErrorType.NETWORK_ERROR);
      }
    });

    it('should classify unknown errors', () => {
      const error = new Error('Some random error');
      expect(manager.classifyError(error)).toBe(ErrorType.UNKNOWN);
    });
  });

  describe('delay calculation', () => {
    it('should calculate exponential backoff', () => {
      // Default config: initial_delay=1.0, exponential_base=2.0
      // Attempt 1: 2^0 * 1.0 = 1.0
      // Attempt 2: 2^1 * 1.0 = 2.0
      // Attempt 3: 2^2 * 1.0 = 4.0

      const delay1 = manager.calculateDelay(1, ErrorType.TIMEOUT);
      const delay2 = manager.calculateDelay(2, ErrorType.TIMEOUT);
      const delay3 = manager.calculateDelay(3, ErrorType.TIMEOUT);

      // With jitter (±25%), delays should be roughly:
      expect(delay1).toBeGreaterThanOrEqual(0.75); // 1.0 - 25%
      expect(delay1).toBeLessThanOrEqual(1.25); // 1.0 + 25%

      expect(delay2).toBeGreaterThanOrEqual(1.5); // 2.0 - 25%
      expect(delay2).toBeLessThanOrEqual(2.5); // 2.0 + 25%

      expect(delay3).toBeGreaterThanOrEqual(3.0); // 4.0 - 25%
      expect(delay3).toBeLessThanOrEqual(5.0); // 4.0 + 25%
    });

    it('should cap delay at max_delay', () => {
      const managerWithMaxDelay = new RetryManager({ maxDelay: 5.0, jitter: false });

      const delay = managerWithMaxDelay.calculateDelay(10, ErrorType.TIMEOUT);

      // Should not exceed max_delay (without jitter)
      expect(delay).toBeLessThanOrEqual(5.0);
    });

    it('should use special backoff for rate limits', () => {
      const delay = manager.calculateDelay(1, ErrorType.RATE_LIMIT);

      // Default rate limit backoff is 30s
      expect(delay).toBe(30.0);
    });

    it('should apply jitter when enabled', () => {
      const delays: number[] = [];

      // Calculate delay multiple times
      for (let i = 0; i < 100; i++) {
        const delay = manager.calculateDelay(2, ErrorType.TIMEOUT);
        delays.push(delay);
      }

      // With jitter, delays should vary
      const uniqueDelays = new Set(delays);
      expect(uniqueDelays.size).toBeGreaterThan(1);
    });

    it('should not apply jitter when disabled', () => {
      const managerNoJitter = new RetryManager({ jitter: false });

      const delay1 = managerNoJitter.calculateDelay(2, ErrorType.TIMEOUT);
      const delay2 = managerNoJitter.calculateDelay(2, ErrorType.TIMEOUT);
      const delay3 = managerNoJitter.calculateDelay(2, ErrorType.TIMEOUT);

      // Without jitter, all delays should be identical
      expect(delay1).toBe(delay2);
      expect(delay2).toBe(delay3);
    });
  });

  describe('retry decision', () => {
    it('should retry retryable errors', () => {
      expect(manager.shouldRetry(ErrorType.RATE_LIMIT, 1)).toBe(true);
      expect(manager.shouldRetry(ErrorType.TIMEOUT, 1)).toBe(true);
      expect(manager.shouldRetry(ErrorType.SERVER_ERROR, 1)).toBe(true);
      expect(manager.shouldRetry(ErrorType.NETWORK_ERROR, 1)).toBe(true);
    });

    it('should not retry non-retryable errors', () => {
      expect(manager.shouldRetry(ErrorType.AUTH_ERROR, 1)).toBe(false);
      expect(manager.shouldRetry(ErrorType.NOT_FOUND, 1)).toBe(false);
      expect(manager.shouldRetry(ErrorType.BAD_REQUEST, 1)).toBe(false);
      expect(manager.shouldRetry(ErrorType.UNKNOWN, 1)).toBe(false);
    });

    it('should not retry when max attempts exceeded', () => {
      expect(manager.shouldRetry(ErrorType.TIMEOUT, 3)).toBe(false);
      expect(manager.shouldRetry(ErrorType.TIMEOUT, 4)).toBe(false);
    });

    it('should respect custom retryableErrors', () => {
      const customManager = new RetryManager({
        retryableErrors: [ErrorType.TIMEOUT],
      });

      expect(customManager.shouldRetry(ErrorType.TIMEOUT, 1)).toBe(true);
      expect(customManager.shouldRetry(ErrorType.RATE_LIMIT, 1)).toBe(false);
    });
  });

  describe('executeWithRetry', () => {
    it('should execute function successfully on first attempt', async () => {
      const fn = vi.fn().mockResolvedValue('success');

      const result = await manager.executeWithRetry(fn);

      expect(result).toBe('success');
      expect(fn).toHaveBeenCalledTimes(1);

      const metrics = manager.getMetricsSummary();
      expect(metrics.totalAttempts).toBe(1);
      expect(metrics.successful).toBe(1);
      expect(metrics.failed).toBe(0);
    });

    it('should retry on retryable error and succeed', async () => {
      let attempts = 0;
      const fn = vi.fn().mockImplementation(async () => {
        attempts++;
        if (attempts === 1) {
          throw new Error('TIMEOUT');
        }
        return 'success';
      });

      const result = await manager.executeWithRetry(fn);

      expect(result).toBe('success');
      expect(fn).toHaveBeenCalledTimes(2);

      const metrics = manager.getMetricsSummary();
      expect(metrics.totalAttempts).toBe(2);
      expect(metrics.successful).toBe(1);
      expect(metrics.failed).toBe(1);
      expect(metrics.retriesByError.timeout).toBe(1);
    });

    it('should not retry on non-retryable error', async () => {
      const fn = vi.fn().mockRejectedValue(new Error('401 Unauthorized'));

      await expect(manager.executeWithRetry(fn)).rejects.toThrow('401 Unauthorized');

      expect(fn).toHaveBeenCalledTimes(1);

      const metrics = manager.getMetricsSummary();
      expect(metrics.totalAttempts).toBe(1);
      expect(metrics.successful).toBe(0);
      expect(metrics.failed).toBe(1);
    });

    it('should exhaust retries and throw last error', async () => {
      const fn = vi.fn().mockRejectedValue(new Error('TIMEOUT'));

      await expect(manager.executeWithRetry(fn)).rejects.toThrow('TIMEOUT');

      expect(fn).toHaveBeenCalledTimes(3); // max_attempts = 3

      const metrics = manager.getMetricsSummary();
      expect(metrics.totalAttempts).toBe(3);
      expect(metrics.successful).toBe(0);
      expect(metrics.failed).toBe(3);
    });

    it('should track retry delay in metrics', async () => {
      const fn = vi.fn().mockRejectedValue(new Error('TIMEOUT'));

      // Mock sleep to track delays without actually waiting
      const sleepSpy = vi.spyOn(manager as any, 'sleep').mockResolvedValue(undefined);

      await expect(manager.executeWithRetry(fn)).rejects.toThrow();

      const metrics = manager.getMetricsSummary();
      expect(metrics.totalRetryDelaySec).toBeGreaterThan(0);

      sleepSpy.mockRestore();
    });

    it('should handle rate limit with special backoff', async () => {
      // Mock sleep to avoid waiting 30s
      const sleepSpy = vi.spyOn(manager as any, 'sleep').mockResolvedValue(undefined);

      let attempts = 0;
      const fn = vi.fn().mockImplementation(async () => {
        attempts++;
        if (attempts === 1) {
          throw new Error('429 Too Many Requests');
        }
        return 'success';
      });

      const result = await manager.executeWithRetry(fn);

      expect(result).toBe('success');

      const metrics = manager.getMetricsSummary();
      expect(metrics.retriesByError.rate_limit).toBe(1);
      expect(metrics.totalRetryDelaySec).toBe(30.0); // Default rate limit backoff

      sleepSpy.mockRestore();
    });

    it('should use context in log messages', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const fn = vi.fn().mockRejectedValue(new Error('401 Unauthorized'));

      await expect(manager.executeWithRetry(fn, 'TestProvider')).rejects.toThrow();

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('TestProvider')
      );

      consoleSpy.mockRestore();
    });
  });

  describe('metrics', () => {
    it('should track all metrics correctly', async () => {
      let attempts = 0;
      const fn = vi.fn().mockImplementation(async () => {
        attempts++;
        if (attempts === 1) {
          throw new Error('TIMEOUT');
        } else if (attempts === 2) {
          throw new Error('500 Server Error');
        }
        return 'success';
      });

      await manager.executeWithRetry(fn);

      const metrics = manager.getMetricsSummary();

      expect(metrics.totalAttempts).toBe(3);
      expect(metrics.successful).toBe(1);
      expect(metrics.failed).toBe(2);
      expect(metrics.successRate).toBe('33.3%');
      expect(metrics.retriesByError.timeout).toBe(1);
      expect(metrics.retriesByError.server_error).toBe(1);
      expect(metrics.totalRetryDelaySec).toBeGreaterThan(0);
    });

    it('should reset metrics', async () => {
      const fn = vi.fn().mockResolvedValue('success');
      await manager.executeWithRetry(fn);

      manager.resetMetrics();

      const metrics = manager.getMetricsSummary();
      expect(metrics.totalAttempts).toBe(0);
      expect(metrics.successful).toBe(0);
      expect(metrics.failed).toBe(0);
      expect(metrics.totalRetryDelaySec).toBe(0);
    });

    it('should calculate success rate correctly', async () => {
      // 2 successes, 1 failure
      await manager.executeWithRetry(vi.fn().mockResolvedValue('success'));
      await manager.executeWithRetry(vi.fn().mockResolvedValue('success'));

      const fn = vi.fn().mockRejectedValue(new Error('401'));
      await expect(manager.executeWithRetry(fn)).rejects.toThrow();

      const metrics = manager.getMetricsSummary();
      expect(metrics.successRate).toBe('66.7%'); // 2/3
    });
  });

  describe('configuration', () => {
    it('should use default configuration', () => {
      const config = manager.getConfig();

      expect(config.maxAttempts).toBe(3);
      expect(config.initialDelay).toBe(1.0);
      expect(config.maxDelay).toBe(60.0);
      expect(config.exponentialBase).toBe(2.0);
      expect(config.jitter).toBe(true);
      expect(config.rateLimitBackoff).toBe(30.0);
      expect(config.retryableErrors).toContain(ErrorType.RATE_LIMIT);
      expect(config.retryableErrors).toContain(ErrorType.TIMEOUT);
    });

    it('should accept custom configuration', () => {
      const customConfig: Partial<RetryConfig> = {
        maxAttempts: 5,
        initialDelay: 2.0,
        exponentialBase: 3.0,
        rateLimitBackoff: 60.0,
      };

      const customManager = new RetryManager(customConfig);
      const config = customManager.getConfig();

      expect(config.maxAttempts).toBe(5);
      expect(config.initialDelay).toBe(2.0);
      expect(config.exponentialBase).toBe(3.0);
      expect(config.rateLimitBackoff).toBe(60.0);
    });

    it('should merge custom config with defaults', () => {
      const customManager = new RetryManager({ maxAttempts: 5 });
      const config = customManager.getConfig();

      expect(config.maxAttempts).toBe(5); // Custom
      expect(config.initialDelay).toBe(1.0); // Default
      expect(config.jitter).toBe(true); // Default
    });
  });

  describe('createRetryManager factory', () => {
    it('should create retry manager with factory', () => {
      const manager = createRetryManager({ maxAttempts: 4 });

      expect(manager).toBeInstanceOf(RetryManager);
      expect(manager.getConfig().maxAttempts).toBe(4);
    });

    it('should create manager with default config', () => {
      const manager = createRetryManager();

      expect(manager).toBeInstanceOf(RetryManager);
      expect(manager.getConfig().maxAttempts).toBe(3);
    });
  });
});
