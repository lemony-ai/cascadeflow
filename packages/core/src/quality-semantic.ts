/**
 * Optional Semantic ML Quality Validation
 *
 * This module provides ML-based quality validation using embeddings for semantic
 * similarity checking. It's completely optional and gracefully degrades if
 * dependencies (@cascadeflow/ml) are not installed.
 *
 * Key Features:
 * - Semantic similarity between query and response
 * - Zero-config (auto-downloads models on first use)
 * - Lightweight (uses ONNX models via Transformers.js)
 * - Graceful degradation
 * - Request-scoped caching for 50% latency reduction
 *
 * Example:
 *   import { SemanticQualityChecker } from '@cascadeflow/core';
 *
 *   // Initialize (downloads model on first use)
 *   const checker = new SemanticQualityChecker();
 *
 *   if (await checker.isAvailable()) {
 *     // Check semantic similarity
 *     const result = await checker.checkSimilarity(
 *       'What is machine learning?',
 *       'Machine learning is a subset of AI...'
 *     );
 *     console.log(`Similarity: ${(result.similarity * 100).toFixed(0)}%`);
 *   }
 */

import type { UnifiedEmbeddingService, EmbeddingCache } from '@cascadeflow/ml';

/**
 * Result of semantic quality check
 */
export interface SemanticQualityResult {
  /** Semantic similarity score (0-1) */
  similarity: number;

  /** Whether quality check passed */
  passed: boolean;

  /** Optional failure reason */
  reason?: string;

  /** Additional check metadata */
  metadata?: Record<string, any>;
}

/**
 * Optional ML-based quality validation using embeddings.
 *
 * Uses Transformers.js with BGE-small-en-v1.5 for fast, lightweight semantic
 * similarity checking. Completely optional - gracefully degrades if dependencies
 * not installed.
 *
 * Installation:
 *   npm install @cascadeflow/ml @xenova/transformers
 *
 * The embedding model (~40MB) will auto-download on first use.
 */
export class SemanticQualityChecker {
  private embedder?: UnifiedEmbeddingService;
  private cache?: EmbeddingCache;
  private _available: boolean = false;
  private initializeAttempted: boolean = false;
  private initPromise?: Promise<void>;

  /**
   * Create a new semantic quality checker
   *
   * @param similarityThreshold - Minimum similarity score to pass (0-1, default: 0.5)
   * @param embedder - Optional pre-configured embedder instance
   * @param useCache - Whether to use request-scoped caching (default: true)
   */
  constructor(
    private similarityThreshold: number = 0.5,
    embedder?: UnifiedEmbeddingService,
    private useCache: boolean = true
  ) {
    // Start initialization immediately but don't block constructor
    this.initPromise = this.initializeEmbedder(embedder);
  }

  /**
   * Initialize the embedder (lazy loading)
   *
   * This defers the ~200-500ms model load time until first use,
   * and allows the checker to remain available even if @cascadeflow/ml
   * is not installed.
   */
  private async initializeEmbedder(
    embedder?: UnifiedEmbeddingService
  ): Promise<void> {
    if (this.initializeAttempted) {
      return;
    }

    this.initializeAttempted = true;

    try {
      // Dynamic import for optional dependency
      const ml = await import('@cascadeflow/ml');
      const { UnifiedEmbeddingService, EmbeddingCache } = ml;

      // Use provided embedder or create new one
      if (embedder) {
        this.embedder = embedder;
      } else {
        this.embedder = new UnifiedEmbeddingService();
      }

      // Check availability
      this._available = await this.embedder.isAvailable();

      // Setup caching
      if (this.useCache && this._available && this.embedder) {
        this.cache = new EmbeddingCache(this.embedder);
      }

      if (this._available) {
        console.log('✓ Semantic quality checking enabled (UnifiedEmbeddingService)');
      }
    } catch (error: unknown) {
      const err = error as { code?: string; message?: string };
      if (err?.code === 'ERR_MODULE_NOT_FOUND' || err?.message?.includes('Cannot find module')) {
        console.warn(
          '@cascadeflow/ml not available. Install with: npm install @cascadeflow/ml @xenova/transformers'
        );
      } else {
        const message = error instanceof Error ? error.message : String(error);
        console.error(`Failed to initialize semantic quality checker: ${message}`);
      }
      this._available = false;
    }
  }

  /**
   * Check if semantic quality checking is available
   *
   * @returns Promise resolving to true if ML embeddings are available
   */
  async isAvailable(): Promise<boolean> {
    // Wait for initialization to complete
    if (this.initPromise) {
      await this.initPromise;
    }
    return this._available;
  }

  /**
   * Check semantic similarity between query and response
   *
   * Uses cosine similarity of embeddings to measure how well the
   * response answers the query. Higher scores indicate better alignment.
   *
   * @param query - User's query/question
   * @param response - Model's response
   * @returns Semantic quality result with similarity score and pass/fail
   */
  async checkSimilarity(
    query: string,
    response: string
  ): Promise<SemanticQualityResult> {
    // Ensure initialization is complete
    if (!(await this.isAvailable()) || !this.embedder) {
      return {
        similarity: 0,
        passed: false,
        reason: 'Semantic checking not available (ML dependencies not installed)',
        metadata: {
          available: false,
          threshold: this.similarityThreshold
        }
      };
    }

    try {
      // Use cache if available, otherwise use embedder directly
      const similarity = this.cache
        ? await this.cache.similarity(query, response)
        : await this.embedder.similarity(query, response);

      if (similarity === null) {
        return {
          similarity: 0,
          passed: false,
          reason: 'Failed to compute embeddings',
          metadata: {
            error: 'embedding_failed',
            threshold: this.similarityThreshold
          }
        };
      }

      const passed = similarity >= this.similarityThreshold;

      return {
        similarity,
        passed,
        reason: passed
          ? undefined
          : `Similarity ${similarity.toFixed(2)} below threshold ${this.similarityThreshold}`,
        metadata: {
          threshold: this.similarityThreshold,
          cached: this.cache !== undefined
        }
      };
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      console.error(`Error in semantic similarity check: ${message}`);
      return {
        similarity: 0,
        passed: false,
        reason: `Error: ${message}`,
        metadata: {
          error: message,
          threshold: this.similarityThreshold
        }
      };
    }
  }

  /**
   * Clear the embedding cache (if caching is enabled)
   *
   * Call this at the end of a request to free memory.
   */
  clearCache(): void {
    if (this.cache) {
      this.cache.clear();
    }
  }

  /**
   * Get cache statistics (if caching is enabled)
   *
   * @returns Cache info with size and sample texts
   */
  getCacheInfo(): any {
    return this.cache?.cacheInfo() || { size: 0, texts: [] };
  }
}
