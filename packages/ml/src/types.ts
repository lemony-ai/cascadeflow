/**
 * Type definitions for ML package
 */

/**
 * Embedding vector with dimensions
 */
export interface EmbeddingVector {
  /** Float32Array containing the embedding data */
  data: Float32Array;
  /** Number of dimensions (384 for BGE-small-en-v1.5) */
  dimensions: number;
}

/**
 * Cache information for debugging
 */
export interface CacheInfo {
  /** Number of cached embeddings */
  size: number;
  /** List of cached text keys (limited to first 5 for debugging) */
  texts: string[];
}
