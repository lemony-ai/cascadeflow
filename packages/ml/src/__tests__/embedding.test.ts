/**
 * Unit tests for UnifiedEmbeddingService and EmbeddingCache
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { UnifiedEmbeddingService, EmbeddingCache } from '../embedding';

describe('UnifiedEmbeddingService', () => {
  let embedder: UnifiedEmbeddingService;

  beforeEach(() => {
    embedder = new UnifiedEmbeddingService();
  });

  it('should initialize with default model', () => {
    expect(embedder).toBeDefined();
  });

  it('should check availability', async () => {
    const available = await embedder.isAvailable();
    expect(typeof available).toBe('boolean');
  });

  it('should generate embeddings for single text', async () => {
    const available = await embedder.isAvailable();
    if (!available) {
      console.warn('Transformers.js not available, skipping test');
      return;
    }

    const embedding = await embedder.embed('Hello world');
    expect(embedding).not.toBeNull();
    expect(embedding?.dimensions).toBe(384);
    expect(embedding?.data).toBeInstanceOf(Float32Array);
    expect(embedding?.data.length).toBe(384);
  });

  it('should generate embeddings for batch texts', async () => {
    const available = await embedder.isAvailable();
    if (!available) {
      console.warn('Transformers.js not available, skipping test');
      return;
    }

    const embeddings = await embedder.embedBatch(['Hello', 'World']);
    expect(embeddings).not.toBeNull();
    expect(embeddings?.length).toBe(2);
    expect(embeddings?.[0].dimensions).toBe(384);
    expect(embeddings?.[1].dimensions).toBe(384);
  });

  it('should compute similarity between texts', async () => {
    const available = await embedder.isAvailable();
    if (!available) {
      console.warn('Transformers.js not available, skipping test');
      return;
    }

    const similarity = await embedder.similarity('cat', 'kitten');
    expect(similarity).not.toBeNull();
    expect(similarity).toBeGreaterThan(0.7); // Should be high similarity
    expect(similarity).toBeLessThanOrEqual(1.0);
  });

  it('should return low similarity for unrelated texts', async () => {
    const available = await embedder.isAvailable();
    if (!available) {
      console.warn('Transformers.js not available, skipping test');
      return;
    }

    const similarity = await embedder.similarity('cat', 'computer');
    expect(similarity).not.toBeNull();
    expect(similarity).toBeGreaterThanOrEqual(0.0);
    expect(similarity).toBeLessThan(0.7); // Should be lower similarity
  });

  it('should handle errors gracefully', async () => {
    const available = await embedder.isAvailable();
    if (!available) {
      const embedding = await embedder.embed('test');
      expect(embedding).toBeNull();
    }
  });
});

describe('EmbeddingCache', () => {
  let embedder: UnifiedEmbeddingService;
  let cache: EmbeddingCache;

  beforeEach(() => {
    embedder = new UnifiedEmbeddingService();
    cache = new EmbeddingCache(embedder);
  });

  it('should initialize cache', () => {
    expect(cache).toBeDefined();
    expect(cache.cacheSize()).toBe(0);
  });

  it('should cache embeddings', async () => {
    const available = await embedder.isAvailable();
    if (!available) {
      console.warn('Transformers.js not available, skipping test');
      return;
    }

    const emb1 = await cache.getOrEmbed('test query');
    expect(cache.cacheSize()).toBe(1);

    const emb2 = await cache.getOrEmbed('test query');
    expect(cache.cacheSize()).toBe(1);
    expect(emb1).toBe(emb2); // Should return same cached object
  });

  it('should compute similarity with caching', async () => {
    const available = await embedder.isAvailable();
    if (!available) {
      console.warn('Transformers.js not available, skipping test');
      return;
    }

    const similarity = await cache.similarity('cat', 'kitten');
    expect(similarity).not.toBeNull();
    expect(cache.cacheSize()).toBe(2); // Both texts should be cached
  });

  it('should clear cache', async () => {
    const available = await embedder.isAvailable();
    if (!available) {
      console.warn('Transformers.js not available, skipping test');
      return;
    }

    await cache.getOrEmbed('test1');
    await cache.getOrEmbed('test2');
    expect(cache.cacheSize()).toBe(2);

    cache.clear();
    expect(cache.cacheSize()).toBe(0);
  });

  it('should return cache info', async () => {
    const available = await embedder.isAvailable();
    if (!available) {
      console.warn('Transformers.js not available, skipping test');
      return;
    }

    await cache.getOrEmbed('test1');
    await cache.getOrEmbed('test2');

    const info = cache.cacheInfo();
    expect(info.size).toBe(2);
    expect(info.texts).toContain('test1');
    expect(info.texts).toContain('test2');
  });

  it('should limit cache info texts to 5', async () => {
    const available = await embedder.isAvailable();
    if (!available) {
      console.warn('Transformers.js not available, skipping test');
      return;
    }

    for (let i = 0; i < 10; i++) {
      await cache.getOrEmbed(`test${i}`);
    }

    const info = cache.cacheInfo();
    expect(info.size).toBe(10);
    expect(info.texts.length).toBe(5); // Limited to first 5
  });
});
