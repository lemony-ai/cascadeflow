/**
 * Response Cache System
 *
 * Provides in-memory LRU (Least Recently Used) cache for API responses
 * with TTL (Time To Live) support and comprehensive statistics tracking.
 *
 * Port from Python cascadeflow/utils/caching.py
 *
 * Features:
 * - In-memory LRU cache
 * - Hash-based cache key generation
 * - TTL support with automatic expiration
 * - Cache statistics (hits, misses, evictions, hit rate)
 * - Configurable max size
 * - Model and parameter-aware caching
 *
 * @example Basic usage
 * ```typescript
 * import { ResponseCache } from '@cascadeflow/core';
 *
 * const cache = new ResponseCache({ maxSize: 1000, defaultTtl: 3600 });
 *
 * // Store response
 * cache.set('What is TypeScript?', responseData, { ttl: 600 });
 *
 * // Retrieve response
 * const cached = cache.get('What is TypeScript?');
 * if (cached) {
 *   console.log('Cache hit!');
 * }
 *
 * // Check statistics
 * const stats = cache.getStats();
 * console.log(`Hit rate: ${stats.hitRate.toFixed(2)}`);
 * ```
 */
/**
 * Hash helper for cache keys.
 *
 * We intentionally avoid Node-only builtins (`crypto`) so that @cascadeflow/core
 * can be bundled for Edge runtimes (e.g. Next.js `runtime = 'edge'`).
 *
 * FNV-1a 64-bit is fast, deterministic, and sufficiently collision-resistant
 * for an in-memory LRU cache.
 */
function fnv1a64Hex(input: string): string {
  let hash = 0xcbf29ce484222325n;
  const prime = 0x100000001b3n;

  for (let i = 0; i < input.length; i += 1) {
    hash ^= BigInt(input.charCodeAt(i));
    hash = (hash * prime) & 0xffffffffffffffffn;
  }

  // 64-bit hex, fixed width.
  return hash.toString(16).padStart(16, '0');
}

/**
 * Cache entry structure
 */
interface CacheEntry {
  /** Cached response data */
  response: Record<string, any>;

  /** Timestamp when entry was created (Unix timestamp) */
  createdAt: number;

  /** Timestamp when entry expires (Unix timestamp) */
  expiresAt: number;
}

/**
 * Cache statistics
 */
export interface CacheStats {
  /** Number of cache hits */
  hits: number;

  /** Number of cache misses */
  misses: number;

  /** Number of cache sets */
  sets: number;

  /** Number of evictions due to max size */
  evictions: number;

  /** Current cache size */
  size: number;

  /** Maximum cache size */
  maxSize: number;

  /** Hit rate (0-1) */
  hitRate: number;
}

/**
 * Configuration for ResponseCache
 */
export interface ResponseCacheConfig {
  /** Maximum number of cached items (default: 1000) */
  maxSize?: number;

  /** Default TTL in seconds (default: 3600 = 1 hour) */
  defaultTtl?: number;
}

/**
 * Options for cache.set()
 */
export interface CacheSetOptions {
  /** Model name to include in cache key */
  model?: string;

  /** Additional parameters to include in cache key */
  params?: Record<string, any>;

  /** TTL in seconds (overrides default) */
  ttl?: number;
}

/**
 * Options for cache.get()
 */
export interface CacheGetOptions {
  /** Model name to include in cache key */
  model?: string;

  /** Additional parameters to include in cache key */
  params?: Record<string, any>;
}

/**
 * Response Cache
 *
 * In-memory LRU cache with TTL support for API responses.
 * Automatically evicts oldest entries when max size is reached.
 * Expires entries based on TTL.
 *
 * @example
 * ```typescript
 * const cache = new ResponseCache({ maxSize: 500, defaultTtl: 1800 });
 *
 * // Cache a response
 * cache.set(
 *   'Explain quantum computing',
 *   { content: '...', cost: 0.001 },
 *   { model: 'gpt-4o', ttl: 600 }
 * );
 *
 * // Retrieve from cache
 * const cached = cache.get('Explain quantum computing', { model: 'gpt-4o' });
 *
 * // Check statistics
 * const stats = cache.getStats();
 * console.log(`Cache hit rate: ${(stats.hitRate * 100).toFixed(1)}%`);
 * ```
 */
export class ResponseCache {
  private maxSize: number;
  private defaultTtl: number;
  private cache: Map<string, CacheEntry>;
  private stats: {
    hits: number;
    misses: number;
    sets: number;
    evictions: number;
  };

  constructor(config: ResponseCacheConfig = {}) {
    this.maxSize = config.maxSize ?? 1000;
    this.defaultTtl = config.defaultTtl ?? 3600; // 1 hour default
    this.cache = new Map();
    this.stats = {
      hits: 0,
      misses: 0,
      sets: 0,
      evictions: 0,
    };
  }

  /**
   * Generate cache key from query and parameters
   *
   * Uses SHA-256 hash of sorted key components to create deterministic keys.
   * Includes query, model, and params in the hash.
   *
   * @param query - Query string
   * @param model - Optional model name
   * @param params - Optional additional parameters
   * @returns SHA-256 hash as cache key
   *
   * @example
   * ```typescript
   * const key1 = cache.generateKey('What is AI?', 'gpt-4', { temp: 0.7 });
   * const key2 = cache.generateKey('What is AI?', 'gpt-4', { temp: 0.7 });
   * console.log(key1 === key2); // true (deterministic)
   * ```
   */
  generateKey(
    query: string,
    model?: string,
    params?: Record<string, any>
  ): string {
    // Helper to recursively sort object keys
    const sortObject = (obj: any): any => {
      if (obj === null || typeof obj !== 'object') {
        return obj;
      }
      if (Array.isArray(obj)) {
        return obj.map(sortObject);
      }
      const sorted: Record<string, any> = {};
      Object.keys(obj)
        .sort()
        .forEach((key) => {
          sorted[key] = sortObject(obj[key]);
        });
      return sorted;
    };

    // Create key data object
    const keyData = sortObject({
      query,
      model: model || null,
      params: params || {},
    });

    // Stringify with sorted keys
    const keyStr = JSON.stringify(keyData);

    return fnv1a64Hex(keyStr);
  }

  /**
   * Get cached response
   *
   * Returns cached response if found and not expired.
   * Updates LRU order on cache hit.
   *
   * @param query - Query string
   * @param options - Cache get options
   * @returns Cached response or undefined
   *
   * @example
   * ```typescript
   * const cached = cache.get('What is TypeScript?');
   * if (cached) {
   *   console.log('Cache hit:', cached);
   * } else {
   *   console.log('Cache miss');
   * }
   * ```
   */
  get(
    query: string,
    options: CacheGetOptions = {}
  ): Record<string, any> | undefined {
    const key = this.generateKey(query, options.model, options.params);

    // Not in cache
    if (!this.cache.has(key)) {
      this.stats.misses++;
      return undefined;
    }

    const entry = this.cache.get(key)!;

    // Check if expired
    const now = Date.now() / 1000; // Convert to seconds
    if (now > entry.expiresAt) {
      // Expired - remove and count as miss
      this.cache.delete(key);
      this.stats.misses++;
      return undefined;
    }

    // Move to end for LRU (re-insert)
    this.cache.delete(key);
    this.cache.set(key, entry);

    this.stats.hits++;
    return entry.response;
  }

  /**
   * Set cache entry
   *
   * Stores response in cache with TTL.
   * Evicts oldest entry if cache is full.
   *
   * @param query - Query string
   * @param response - Response data to cache
   * @param options - Cache set options
   *
   * @example
   * ```typescript
   * cache.set(
   *   'What is AI?',
   *   { content: 'AI is...', tokens: 100 },
   *   { model: 'gpt-4o', ttl: 1800 }
   * );
   * ```
   */
  set(
    query: string,
    response: Record<string, any>,
    options: CacheSetOptions = {}
  ): void {
    const key = this.generateKey(query, options.model, options.params);

    // Evict if at max size
    if (this.cache.size >= this.maxSize) {
      // Remove oldest (first entry)
      const firstKey = this.cache.keys().next().value;
      if (firstKey !== undefined) {
        this.cache.delete(firstKey);
        this.stats.evictions++;
      }
    }

    // Create cache entry
    const now = Date.now() / 1000; // Convert to seconds
    const ttl = options.ttl ?? this.defaultTtl;

    const entry: CacheEntry = {
      response,
      createdAt: now,
      expiresAt: now + ttl,
    };

    this.cache.set(key, entry);
    this.stats.sets++;
  }

  /**
   * Clear all cache entries
   *
   * Removes all cached items. Statistics are preserved.
   *
   * @example
   * ```typescript
   * cache.clear();
   * console.log(cache.getStats().size); // 0
   * ```
   */
  clear(): void {
    this.cache.clear();
  }

  /**
   * Get cache statistics
   *
   * Returns comprehensive statistics about cache performance.
   *
   * @returns Cache statistics object
   *
   * @example
   * ```typescript
   * const stats = cache.getStats();
   * console.log(`Hit rate: ${(stats.hitRate * 100).toFixed(1)}%`);
   * console.log(`Cache size: ${stats.size}/${stats.maxSize}`);
   * console.log(`Evictions: ${stats.evictions}`);
   * ```
   */
  getStats(): CacheStats {
    const totalRequests = this.stats.hits + this.stats.misses;
    const hitRate = totalRequests > 0 ? this.stats.hits / totalRequests : 0;

    return {
      hits: this.stats.hits,
      misses: this.stats.misses,
      sets: this.stats.sets,
      evictions: this.stats.evictions,
      size: this.cache.size,
      maxSize: this.maxSize,
      hitRate,
    };
  }

  /**
   * Reset statistics
   *
   * Clears all statistics counters. Cache contents are preserved.
   *
   * @example
   * ```typescript
   * cache.resetStats();
   * console.log(cache.getStats().hits); // 0
   * ```
   */
  resetStats(): void {
    this.stats = {
      hits: 0,
      misses: 0,
      sets: 0,
      evictions: 0,
    };
  }

  /**
   * Get current configuration
   *
   * @returns Current cache configuration
   */
  getConfig(): ResponseCacheConfig {
    return {
      maxSize: this.maxSize,
      defaultTtl: this.defaultTtl,
    };
  }

  /**
   * Remove expired entries
   *
   * Manually clean up expired entries to free memory.
   * Normally not needed as expiration is checked on get().
   *
   * @returns Number of entries removed
   *
   * @example
   * ```typescript
   * const removed = cache.removeExpired();
   * console.log(`Removed ${removed} expired entries`);
   * ```
   */
  removeExpired(): number {
    const now = Date.now() / 1000;
    let removed = 0;

    for (const [key, entry] of this.cache.entries()) {
      if (now > entry.expiresAt) {
        this.cache.delete(key);
        removed++;
      }
    }

    return removed;
  }

  /**
   * Check if query is cached (without affecting LRU order)
   *
   * @param query - Query string
   * @param options - Cache get options
   * @returns True if cached and not expired
   *
   * @example
   * ```typescript
   * if (cache.has('What is AI?')) {
   *   console.log('Response is cached');
   * }
   * ```
   */
  has(query: string, options: CacheGetOptions = {}): boolean {
    const key = this.generateKey(query, options.model, options.params);

    if (!this.cache.has(key)) {
      return false;
    }

    const entry = this.cache.get(key)!;
    const now = Date.now() / 1000;

    return now <= entry.expiresAt;
  }
}

/**
 * Create a response cache with configuration
 *
 * @param config - Cache configuration
 * @returns Configured ResponseCache instance
 *
 * @example
 * ```typescript
 * import { createResponseCache } from '@cascadeflow/core';
 *
 * const cache = createResponseCache({
 *   maxSize: 500,
 *   defaultTtl: 1800,
 * });
 * ```
 */
export function createResponseCache(
  config?: ResponseCacheConfig
): ResponseCache {
  return new ResponseCache(config);
}
