/**
 * Batch Processing for cascadeflow
 *
 * Efficient batch processing with concurrency control, error handling, and cost tracking.
 *
 * @example
 * ```typescript
 * import { CascadeAgent, BatchConfig } from '@cascadeflow/core';
 *
 * const agent = new CascadeAgent({ models: [...] });
 *
 * const queries = [
 *   'What is TypeScript?',
 *   'What is JavaScript?',
 *   'What is Rust?'
 * ];
 *
 * const result = await agent.runBatch(queries);
 *
 * console.log(`Success: ${result.successCount}/${queries.length}`);
 * console.log(`Total cost: $${result.totalCost.toFixed(4)}`);
 * console.log(`Strategy: ${result.strategyUsed}`);
 * ```
 */

import type { CascadeResult } from './result';
import type { RunOptions } from './agent';

/**
 * Batch processing strategy
 */
export enum BatchStrategy {
  /** Use native batch API if available (preferred) */
  LITELLM_NATIVE = 'litellm_native',
  /** Sequential processing with concurrency control */
  SEQUENTIAL = 'sequential',
  /** Auto-detect best strategy */
  AUTO = 'auto',
}

/**
 * Configuration for batch processing
 *
 * @example
 * ```typescript
 * const config: BatchConfig = {
 *   batchSize: 10,
 *   maxParallel: 3,
 *   timeoutPerQuery: 30,
 *   strategy: BatchStrategy.AUTO
 * };
 * ```
 */
export interface BatchConfig {
  /** Maximum number of queries in a single batch (default: 10) */
  batchSize?: number;

  /** Maximum number of parallel requests (default: 3) */
  maxParallel?: number;

  /** Timeout per query in seconds (default: 30) */
  timeoutPerQuery?: number;

  /** Total timeout for entire batch in seconds (default: timeoutPerQuery * batchSize) */
  totalTimeout?: number;

  /** Batch processing strategy (default: AUTO) */
  strategy?: BatchStrategy;

  /** Stop processing batch if any query fails (default: false) */
  stopOnError?: boolean;

  /** Retry failed queries once (default: true) */
  retryFailed?: boolean;

  /** Track cost for each query in batch (default: true) */
  trackCost?: boolean;

  /** Validate quality for each query in batch (default: true) */
  validateQuality?: boolean;

  /** Preserve query order in results (default: true) */
  preserveOrder?: boolean;

  /** Custom metadata for batch */
  metadata?: Record<string, any>;
}

/**
 * Result from batch processing
 *
 * Contains results for all queries plus statistics about the batch execution.
 *
 * @example
 * ```typescript
 * const result = await agent.runBatch(queries);
 *
 * console.log(`Success rate: ${(result.successRate * 100).toFixed(1)}%`);
 * console.log(`Average cost: $${result.averageCost.toFixed(4)}`);
 * console.log(`Average time: ${result.averageTime.toFixed(2)}s`);
 *
 * result.results.forEach((r, i) => {
 *   if (r) {
 *     console.log(`Query ${i}: ${r.content.slice(0, 100)}...`);
 *   } else {
 *     console.log(`Query ${i} failed: ${result.errors[i]}`);
 *   }
 * });
 * ```
 */
export interface BatchResult {
  /** Results for each query (null if failed) */
  results: (CascadeResult | null)[];

  /** Number of successful queries */
  successCount: number;

  /** Number of failed queries */
  failureCount: number;

  /** Total cost for all queries */
  totalCost: number;

  /** Total processing time in seconds */
  totalTime: number;

  /** Strategy used (litellm_native or sequential) */
  strategyUsed: string;

  /** Error messages for failed queries (null if successful) */
  errors: (string | null)[];

  /** Custom metadata */
  metadata: Record<string, any>;

  /** Success rate (0.0 to 1.0) */
  successRate: number;

  /** Average cost per query */
  averageCost: number;

  /** Average time per query in seconds */
  averageTime: number;
}

/**
 * Default batch configuration
 */
export const DEFAULT_BATCH_CONFIG: Required<BatchConfig> = {
  batchSize: 10,
  maxParallel: 3,
  timeoutPerQuery: 30,
  totalTimeout: 300, // Will be overridden in normalizeBatchConfig
  strategy: BatchStrategy.AUTO,
  stopOnError: false,
  retryFailed: true,
  trackCost: true,
  validateQuality: true,
  preserveOrder: true,
  metadata: {},
};

/**
 * Normalize batch configuration with defaults
 */
export function normalizeBatchConfig(config?: BatchConfig): Required<BatchConfig> {
  const normalized = {
    ...DEFAULT_BATCH_CONFIG,
    ...config,
  };

  // Calculate total timeout if not provided
  if (config?.totalTimeout === undefined) {
    normalized.totalTimeout = normalized.timeoutPerQuery * normalized.batchSize;
  }

  return normalized;
}

/**
 * Batch processor with concurrency control and error handling
 *
 * Features:
 * - Concurrent execution with semaphore-based rate limiting
 * - Per-query timeout and retry logic
 * - Cost tracking and statistics
 * - Preserve or shuffle result order
 * - Graceful error handling
 *
 * @internal
 */
export class BatchProcessor {
  /**
   * Process a batch of queries
   *
   * @param queries - List of query strings
   * @param runFn - Function to run each query (agent.run)
   * @param config - Batch configuration
   * @param runOptions - Options passed to runFn
   * @returns BatchResult with all results and statistics
   */
  async processBatch(
    queries: string[],
    runFn: (query: string, options?: RunOptions) => Promise<CascadeResult>,
    config?: BatchConfig,
    runOptions?: RunOptions
  ): Promise<BatchResult> {
    const normalizedConfig = normalizeBatchConfig(config);
    const startTime = Date.now();

    // Choose strategy
    const strategy = this.chooseStrategy(normalizedConfig.strategy);

    // Process batch
    const { results, errors } = await this.processSequentialBatch(
      queries,
      runFn,
      normalizedConfig,
      runOptions
    );

    // Calculate statistics
    const successCount = results.filter((r) => r !== null).length;
    const failureCount = results.length - successCount;
    const totalCost = results.reduce((sum, r) => sum + (r?.totalCost ?? 0), 0);
    const totalTime = (Date.now() - startTime) / 1000;

    const total = successCount + failureCount;
    const successRate = total > 0 ? successCount / total : 0;
    const averageCost = total > 0 ? totalCost / total : 0;
    const averageTime = total > 0 ? totalTime / total : 0;

    return {
      results,
      successCount,
      failureCount,
      totalCost,
      totalTime,
      strategyUsed: strategy,
      errors,
      metadata: normalizedConfig.metadata,
      successRate,
      averageCost,
      averageTime,
    };
  }

  /**
   * Choose batch processing strategy
   */
  private chooseStrategy(strategy: BatchStrategy): string {
    if (strategy === BatchStrategy.AUTO) {
      // For now, always use sequential (LiteLLM native batch not widely available)
      return BatchStrategy.SEQUENTIAL;
    }
    return strategy;
  }

  /**
   * Process batch sequentially with concurrency control
   */
  private async processSequentialBatch(
    queries: string[],
    runFn: (query: string, options?: RunOptions) => Promise<CascadeResult>,
    config: Required<BatchConfig>,
    runOptions?: RunOptions
  ): Promise<{ results: (CascadeResult | null)[]; errors: (string | null)[] }> {
    type ProcessResult = {
      index: number;
      result: CascadeResult | null;
      error: string | null;
    };

    // Create a semaphore for concurrency control
    let activeCount = 0;
    const pending: (() => void)[] = [];

    const acquire = async (): Promise<void> => {
      if (activeCount < config.maxParallel) {
        activeCount++;
        return;
      }
      return new Promise<void>((resolve) => {
        pending.push(resolve);
      });
    };

    const release = (): void => {
      activeCount--;
      const next = pending.shift();
      if (next) {
        activeCount++;
        next();
      }
    };

    // Process one query with timeout and retry
    const processOne = async (query: string, index: number): Promise<ProcessResult> => {
      await acquire();

      try {
        // Run with timeout
        const timeoutPromise = new Promise<never>((_, reject) =>
          setTimeout(
            () => reject(new Error('Timeout')),
            config.timeoutPerQuery * 1000
          )
        );

        const resultPromise = runFn(query, runOptions);
        const result = await Promise.race([resultPromise, timeoutPromise]);

        release();
        return { index, result, error: null };
      } catch (error) {
        // Try retry if enabled
        if (config.retryFailed) {
          try {
            const timeoutPromise = new Promise<never>((_, reject) =>
              setTimeout(
                () => reject(new Error('Timeout')),
                config.timeoutPerQuery * 1000
              )
            );

            const resultPromise = runFn(query, runOptions);
            const result = await Promise.race([resultPromise, timeoutPromise]);

            release();
            return { index, result, error: null };
          } catch (retryError) {
            const errorMsg =
              retryError instanceof Error
                ? `Error: ${retryError.message}`
                : 'Unknown error';

            release();

            if (config.stopOnError) {
              throw retryError;
            }

            return { index, result: null, error: errorMsg };
          }
        } else {
          const errorMsg =
            error instanceof Error ? error.message : 'Unknown error';

          release();

          if (config.stopOnError) {
            throw error;
          }

          return { index, result: null, error: errorMsg };
        }
      }
    };

    // Create tasks for all queries
    const tasks = queries.map((query, i) => processOne(query, i));

    // Process with total timeout
    try {
      const totalTimeoutPromise = new Promise<never>((_, reject) =>
        setTimeout(
          () => reject(new Error('Total timeout exceeded')),
          config.totalTimeout * 1000
        )
      );

      // Use Promise.all instead of allSettled if stopOnError is true
      // This will throw on first error
      if (config.stopOnError) {
        const resultsPromise = Promise.all(tasks);
        const results = await Promise.race([resultsPromise, totalTimeoutPromise]);

        // Sort by index to preserve order (if requested)
        const processed = results;
        if (config.preserveOrder) {
          processed.sort((a, b) => a.index - b.index);
        }

        const finalResults = processed.map((p) => p.result);
        const finalErrors = processed.map((p) => p.error);

        return { results: finalResults, errors: finalErrors };
      }

      // Use allSettled for non-stop-on-error mode
      const resultsPromise = Promise.allSettled(tasks);
      const settled = await Promise.race([resultsPromise, totalTimeoutPromise]);

      // Process settled results
      const processed: ProcessResult[] = settled.map((item, i) => {
        if (item.status === 'fulfilled') {
          return item.value;
        } else {
          return {
            index: i,
            result: null,
            error: item.reason instanceof Error ? item.reason.message : 'Unknown error',
          };
        }
      });

      // Sort by index to preserve order (if requested)
      if (config.preserveOrder) {
        processed.sort((a, b) => a.index - b.index);
      }

      // Extract results and errors
      const results = processed.map((p) => p.result);
      const errors = processed.map((p) => p.error);

      return { results, errors };
    } catch (error) {
      // Check if this is a timeout error or a stopOnError propagation
      if (error instanceof Error && error.message !== 'Total timeout exceeded') {
        // This is a real error from stopOnError mode - re-throw it
        throw error;
      }

      // Total timeout exceeded - return partial results
      const results: (CascadeResult | null)[] = new Array(queries.length).fill(null);
      const errors: (string | null)[] = new Array(queries.length).fill(
        'Total timeout exceeded'
      );

      return { results, errors };
    }
  }
}

/**
 * Error during batch processing
 */
export class BatchProcessingError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'BatchProcessingError';
  }
}
