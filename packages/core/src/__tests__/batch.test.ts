/**
 * Tests for Batch Processing
 *
 * Tests batch processing with concurrency control, error handling, and statistics.
 *
 * Run: pnpm test batch.test.ts
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  BatchStrategy,
  BatchProcessor,
  normalizeBatchConfig,
  DEFAULT_BATCH_CONFIG,
} from '../batch';
import type { CascadeResult } from '../result';
import type { RunOptions } from '../agent';

// Mock CascadeResult factory
function createMockResult(content: string, cost: number = 0.001): CascadeResult {
  return {
    content,
    model: 'gpt-4o-mini',
    provider: 'openai',
    totalCost: cost,
    tokensUsed: 100,
    latencyMs: 500,
    cascaded: false,
    savingsPercentage: 0,
    costBreakdown: {
      draftCost: cost,
      verifierCost: 0,
      totalCost: cost,
      savingsPercentage: 0,
      accepted: true,
    },
    timingBreakdown: {
      draftLatencyMs: 500,
      verifierLatencyMs: 0,
      totalLatencyMs: 500,
    },
    qualityValidation: {
      passed: true,
      overallScore: 0.95,
      thresholdUsed: 0.80,
    },
  };
}

describe('BatchProcessor', () => {
  let processor: BatchProcessor;

  beforeEach(() => {
    processor = new BatchProcessor();
  });

  describe('basic batch processing', () => {
    it('should process multiple queries successfully', async () => {
      const queries = ['Query 1', 'Query 2', 'Query 3'];

      const mockRun = vi.fn(async (query: string) => {
        return createMockResult(`Answer to ${query}`, 0.001);
      });

      const result = await processor.processBatch(queries, mockRun);

      expect(result.results).toHaveLength(3);
      expect(result.successCount).toBe(3);
      expect(result.failureCount).toBe(0);
      expect(result.totalCost).toBeCloseTo(0.003, 5);
      expect(result.successRate).toBe(1.0);
      expect(mockRun).toHaveBeenCalledTimes(3);
    });

    it('should preserve query order by default', async () => {
      const queries = ['First', 'Second', 'Third'];

      const mockRun = vi.fn(async (query: string) => {
        // Add delays to ensure ordering matters
        await new Promise((resolve) => setTimeout(resolve, Math.random() * 10));
        return createMockResult(query);
      });

      const result = await processor.processBatch(queries, mockRun);

      expect(result.results[0]?.content).toBe('First');
      expect(result.results[1]?.content).toBe('Second');
      expect(result.results[2]?.content).toBe('Third');
    });

    it('should handle empty queries array', async () => {
      const mockRun = vi.fn();

      const result = await processor.processBatch([], mockRun);

      expect(result.results).toHaveLength(0);
      expect(result.successCount).toBe(0);
      expect(result.failureCount).toBe(0);
      expect(result.totalCost).toBe(0);
      expect(mockRun).not.toHaveBeenCalled();
    });

    it('should pass run options to each query', async () => {
      const queries = ['Test query'];
      const runOptions: RunOptions = {
        maxTokens: 1000,
        temperature: 0.5,
      };

      const mockRun = vi.fn(async () => {
        return createMockResult('Answer');
      });

      await processor.processBatch(queries, mockRun, undefined, runOptions);

      expect(mockRun).toHaveBeenCalledWith('Test query', runOptions);
    });
  });

  describe('concurrency control', () => {
    it('should respect maxParallel limit', async () => {
      const queries = Array.from({ length: 10 }, (_, i) => `Query ${i + 1}`);
      let currentlyRunning = 0;
      let maxConcurrent = 0;

      const mockRun = vi.fn(async (query: string) => {
        currentlyRunning++;
        maxConcurrent = Math.max(maxConcurrent, currentlyRunning);

        await new Promise((resolve) => setTimeout(resolve, 10));

        currentlyRunning--;
        return createMockResult(`Answer to ${query}`);
      });

      await processor.processBatch(queries, mockRun, { maxParallel: 3 });

      // Max concurrent should not exceed 3
      expect(maxConcurrent).toBeLessThanOrEqual(3);
      expect(maxConcurrent).toBeGreaterThan(0);
    });

    it('should allow higher concurrency with larger maxParallel', async () => {
      const queries = Array.from({ length: 20 }, (_, i) => `Query ${i + 1}`);
      let maxConcurrent = 0;
      let currentlyRunning = 0;

      const mockRun = vi.fn(async () => {
        currentlyRunning++;
        maxConcurrent = Math.max(maxConcurrent, currentlyRunning);

        await new Promise((resolve) => setTimeout(resolve, 5));

        currentlyRunning--;
        return createMockResult('Answer');
      });

      await processor.processBatch(queries, mockRun, { maxParallel: 10 });

      expect(maxConcurrent).toBeGreaterThan(5);
      expect(maxConcurrent).toBeLessThanOrEqual(10);
    });
  });

  describe('error handling', () => {
    it('should handle query failures', async () => {
      const queries = ['Good query', 'Bad query', 'Another good query'];

      const mockRun = vi.fn(async (query: string) => {
        if (query === 'Bad query') {
          throw new Error('Query failed');
        }
        return createMockResult(`Answer to ${query}`);
      });

      const result = await processor.processBatch(queries, mockRun, {
        stopOnError: false,
      });

      expect(result.successCount).toBe(2);
      expect(result.failureCount).toBe(1);
      expect(result.results[0]).not.toBeNull();
      expect(result.results[1]).toBeNull();
      expect(result.results[2]).not.toBeNull();
      expect(result.errors[1]).toContain('Query failed');
    });

    it('should retry failed queries when retryFailed is true', async () => {
      const queries = ['Flaky query'];
      let attempts = 0;

      const mockRun = vi.fn(async () => {
        attempts++;
        if (attempts === 1) {
          throw new Error('First attempt failed');
        }
        return createMockResult('Success on retry');
      });

      const result = await processor.processBatch(queries, mockRun, {
        retryFailed: true,
        stopOnError: false,
      });

      expect(result.successCount).toBe(1);
      expect(result.results[0]?.content).toBe('Success on retry');
      expect(mockRun).toHaveBeenCalledTimes(2);
    });

    it('should not retry when retryFailed is false', async () => {
      const queries = ['Failing query'];

      const mockRun = vi.fn(async () => {
        throw new Error('Query failed');
      });

      const result = await processor.processBatch(queries, mockRun, {
        retryFailed: false,
        stopOnError: false,
      });

      expect(result.successCount).toBe(0);
      expect(result.failureCount).toBe(1);
      expect(mockRun).toHaveBeenCalledTimes(1);
    });

    it('should stop on error when stopOnError is true', async () => {
      const queries = ['Query 1', 'Bad query', 'Query 3'];

      const mockRun = vi.fn(async (query: string) => {
        if (query === 'Bad query') {
          throw new Error('Stop here');
        }
        return createMockResult(`Answer to ${query}`);
      });

      await expect(
        processor.processBatch(queries, mockRun, {
          stopOnError: true,
          retryFailed: false,
        })
      ).rejects.toThrow('Stop here');
    });
  });

  describe('timeout handling', () => {
    it('should timeout slow queries', async () => {
      const queries = ['Fast query', 'Slow query'];

      const mockRun = vi.fn(async (query: string) => {
        if (query === 'Slow query') {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return createMockResult(`Answer to ${query}`);
      });

      const result = await processor.processBatch(queries, mockRun, {
        timeoutPerQuery: 0.05, // 50ms timeout
        retryFailed: false,
        stopOnError: false,
      });

      expect(result.successCount).toBe(1);
      expect(result.failureCount).toBe(1);
      expect(result.errors[1]).toContain('Timeout');
    });

    it('should respect total timeout for entire batch', async () => {
      const queries = Array.from({ length: 10 }, (_, i) => `Query ${i + 1}`);

      const mockRun = vi.fn(async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return createMockResult('Answer');
      });

      const result = await processor.processBatch(queries, mockRun, {
        totalTimeout: 0.2, // 200ms total timeout
        timeoutPerQuery: 1, // Individual timeout won't trigger
        stopOnError: false,
      });

      // Some queries should timeout
      expect(result.failureCount).toBeGreaterThan(0);
    });
  });

  describe('statistics and metadata', () => {
    it('should calculate correct cost statistics', async () => {
      const queries = ['Query 1', 'Query 2', 'Query 3'];
      const costs = [0.001, 0.002, 0.003];

      const mockRun = vi.fn(async (query: string, _options?: RunOptions) => {
        const index = queries.indexOf(query);
        return createMockResult(`Answer to ${query}`, costs[index]);
      });

      const result = await processor.processBatch(queries, mockRun);

      expect(result.totalCost).toBeCloseTo(0.006, 5);
      expect(result.averageCost).toBeCloseTo(0.002, 5);
    });

    it('should calculate correct timing statistics', async () => {
      const queries = ['Query 1', 'Query 2'];

      const mockRun = vi.fn(async (query: string) => {
        await new Promise((resolve) => setTimeout(resolve, 10));
        return createMockResult(`Answer to ${query}`);
      });

      const startTime = Date.now();
      const result = await processor.processBatch(queries, mockRun);
      const elapsed = (Date.now() - startTime) / 1000;

      expect(result.totalTime).toBeGreaterThan(0);
      expect(result.totalTime).toBeLessThanOrEqual(elapsed + 0.1); // Small margin
      expect(result.averageTime).toBeGreaterThan(0);
    });

    it('should calculate success rate correctly', async () => {
      const queries = ['Query 1', 'Query 2', 'Query 3', 'Query 4'];

      const mockRun = vi.fn(async (query: string) => {
        if (query === 'Query 2' || query === 'Query 4') {
          throw new Error('Failed');
        }
        return createMockResult(`Answer to ${query}`);
      });

      const result = await processor.processBatch(queries, mockRun, {
        stopOnError: false,
        retryFailed: false,
      });

      expect(result.successCount).toBe(2);
      expect(result.failureCount).toBe(2);
      expect(result.successRate).toBe(0.5);
    });

    it('should include custom metadata', async () => {
      const queries = ['Test query'];
      const metadata = { batchId: '12345', environment: 'test' };

      const mockRun = vi.fn(async () => {
        return createMockResult('Answer');
      });

      const result = await processor.processBatch(queries, mockRun, { metadata });

      expect(result.metadata).toEqual(metadata);
    });

    it('should report strategy used', async () => {
      const queries = ['Test query'];

      const mockRun = vi.fn(async () => {
        return createMockResult('Answer');
      });

      const result = await processor.processBatch(queries, mockRun, {
        strategy: BatchStrategy.SEQUENTIAL,
      });

      expect(result.strategyUsed).toBe(BatchStrategy.SEQUENTIAL);
    });
  });

  describe('configuration', () => {
    it('should use default configuration when not provided', async () => {
      const queries = ['Test query'];

      const mockRun = vi.fn(async () => {
        return createMockResult('Answer');
      });

      const result = await processor.processBatch(queries, mockRun);

      expect(result.strategyUsed).toBe(BatchStrategy.SEQUENTIAL);
      expect(result.metadata).toEqual({});
    });

    it('should merge custom config with defaults', async () => {
      const queries = ['Test query'];
      const customConfig = {
        maxParallel: 5,
        metadata: { custom: 'value' },
      };

      const mockRun = vi.fn(async () => {
        return createMockResult('Answer');
      });

      const result = await processor.processBatch(queries, mockRun, customConfig);

      expect(result.metadata).toEqual({ custom: 'value' });
    });
  });
});

describe('normalizeBatchConfig', () => {
  it('should use defaults when no config provided', () => {
    const normalized = normalizeBatchConfig();

    expect(normalized.batchSize).toBe(DEFAULT_BATCH_CONFIG.batchSize);
    expect(normalized.maxParallel).toBe(DEFAULT_BATCH_CONFIG.maxParallel);
    expect(normalized.strategy).toBe(BatchStrategy.AUTO);
  });

  it('should merge custom config with defaults', () => {
    const customConfig = {
      maxParallel: 10,
      retryFailed: false,
    };

    const normalized = normalizeBatchConfig(customConfig);

    expect(normalized.maxParallel).toBe(10);
    expect(normalized.retryFailed).toBe(false);
    expect(normalized.batchSize).toBe(DEFAULT_BATCH_CONFIG.batchSize);
  });

  it('should calculate totalTimeout from timeoutPerQuery and batchSize', () => {
    const config = {
      timeoutPerQuery: 5,
      batchSize: 10,
    };

    const normalized = normalizeBatchConfig(config);

    expect(normalized.totalTimeout).toBe(50);
  });

  it('should not override explicit totalTimeout', () => {
    const config = {
      timeoutPerQuery: 5,
      batchSize: 10,
      totalTimeout: 100,
    };

    const normalized = normalizeBatchConfig(config);

    expect(normalized.totalTimeout).toBe(100);
  });
});

describe('DEFAULT_BATCH_CONFIG', () => {
  it('should have sensible defaults', () => {
    expect(DEFAULT_BATCH_CONFIG.batchSize).toBe(10);
    expect(DEFAULT_BATCH_CONFIG.maxParallel).toBe(3);
    expect(DEFAULT_BATCH_CONFIG.timeoutPerQuery).toBe(30);
    expect(DEFAULT_BATCH_CONFIG.strategy).toBe(BatchStrategy.AUTO);
    expect(DEFAULT_BATCH_CONFIG.stopOnError).toBe(false);
    expect(DEFAULT_BATCH_CONFIG.retryFailed).toBe(true);
    expect(DEFAULT_BATCH_CONFIG.preserveOrder).toBe(true);
  });
});

describe('BatchStrategy', () => {
  it('should have all expected strategies', () => {
    expect(BatchStrategy.LITELLM_NATIVE).toBe('litellm_native');
    expect(BatchStrategy.SEQUENTIAL).toBe('sequential');
    expect(BatchStrategy.AUTO).toBe('auto');
  });
});
