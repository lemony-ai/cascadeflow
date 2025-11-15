/**
 * Response Cache Tests
 *
 * Comprehensive test suite for ResponseCache class.
 * Tests LRU eviction, TTL expiration, cache statistics, and key generation.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  ResponseCache,
  createResponseCache,
} from '../response-cache';

describe('ResponseCache', () => {
  let cache: ResponseCache;

  beforeEach(() => {
    cache = new ResponseCache();
    // Reset time mocking if any
    vi.useRealTimers();
  });

  describe('key generation', () => {
    it('should generate consistent keys for same inputs', () => {
      const key1 = cache.generateKey('What is AI?', 'gpt-4', { temp: 0.7 });
      const key2 = cache.generateKey('What is AI?', 'gpt-4', { temp: 0.7 });

      expect(key1).toBe(key2);
    });

    it('should generate different keys for different queries', () => {
      const key1 = cache.generateKey('What is AI?');
      const key2 = cache.generateKey('What is ML?');

      expect(key1).not.toBe(key2);
    });

    it('should generate different keys for different models', () => {
      const key1 = cache.generateKey('What is AI?', 'gpt-4');
      const key2 = cache.generateKey('What is AI?', 'gpt-3.5');

      expect(key1).not.toBe(key2);
    });

    it('should generate different keys for different params', () => {
      const key1 = cache.generateKey('What is AI?', 'gpt-4', { temp: 0.7 });
      const key2 = cache.generateKey('What is AI?', 'gpt-4', { temp: 0.9 });

      expect(key1).not.toBe(key2);
    });

    it('should handle missing optional parameters', () => {
      const key1 = cache.generateKey('What is AI?');
      const key2 = cache.generateKey('What is AI?', undefined, undefined);

      expect(key1).toBe(key2);
    });

    it('should generate SHA-256 hash (64 hex chars)', () => {
      const key = cache.generateKey('test');

      expect(key).toHaveLength(64);
      expect(key).toMatch(/^[a-f0-9]{64}$/);
    });
  });

  describe('basic operations', () => {
    it('should store and retrieve values', () => {
      const response = { content: 'AI is...', tokens: 100 };

      cache.set('What is AI?', response);
      const cached = cache.get('What is AI?');

      expect(cached).toEqual(response);
    });

    it('should return undefined for cache miss', () => {
      const cached = cache.get('Not cached');

      expect(cached).toBeUndefined();
    });

    it('should handle model-specific caching', () => {
      const response1 = { content: 'GPT-4 response' };
      const response2 = { content: 'GPT-3.5 response' };

      cache.set('What is AI?', response1, { model: 'gpt-4' });
      cache.set('What is AI?', response2, { model: 'gpt-3.5' });

      expect(cache.get('What is AI?', { model: 'gpt-4' })).toEqual(response1);
      expect(cache.get('What is AI?', { model: 'gpt-3.5' })).toEqual(response2);
    });

    it('should handle parameter-specific caching', () => {
      const response1 = { content: 'Temp 0.7' };
      const response2 = { content: 'Temp 0.9' };

      cache.set('What is AI?', response1, { params: { temp: 0.7 } });
      cache.set('What is AI?', response2, { params: { temp: 0.9 } });

      expect(cache.get('What is AI?', { params: { temp: 0.7 } })).toEqual(response1);
      expect(cache.get('What is AI?', { params: { temp: 0.9 } })).toEqual(response2);
    });

    it('should clear all entries', () => {
      cache.set('query1', { content: 'response1' });
      cache.set('query2', { content: 'response2' });
      cache.set('query3', { content: 'response3' });

      cache.clear();

      expect(cache.get('query1')).toBeUndefined();
      expect(cache.get('query2')).toBeUndefined();
      expect(cache.get('query3')).toBeUndefined();
      expect(cache.getStats().size).toBe(0);
    });
  });

  describe('LRU eviction', () => {
    it('should evict oldest entry when max size reached', () => {
      const smallCache = new ResponseCache({ maxSize: 3 });

      smallCache.set('query1', { content: '1' });
      smallCache.set('query2', { content: '2' });
      smallCache.set('query3', { content: '3' });
      smallCache.set('query4', { content: '4' }); // Should evict query1

      expect(smallCache.get('query1')).toBeUndefined(); // Evicted
      expect(smallCache.get('query2')).toBeDefined();
      expect(smallCache.get('query3')).toBeDefined();
      expect(smallCache.get('query4')).toBeDefined();
    });

    it('should update LRU order on access', () => {
      const smallCache = new ResponseCache({ maxSize: 3 });

      smallCache.set('query1', { content: '1' });
      smallCache.set('query2', { content: '2' });
      smallCache.set('query3', { content: '3' });

      // Access query1 (moves to end)
      smallCache.get('query1');

      // Add query4 (should evict query2, not query1)
      smallCache.set('query4', { content: '4' });

      expect(smallCache.get('query1')).toBeDefined(); // Still cached
      expect(smallCache.get('query2')).toBeUndefined(); // Evicted
      expect(smallCache.get('query3')).toBeDefined();
      expect(smallCache.get('query4')).toBeDefined();
    });

    it('should track evictions in stats', () => {
      const smallCache = new ResponseCache({ maxSize: 2 });

      smallCache.set('query1', { content: '1' });
      smallCache.set('query2', { content: '2' });
      smallCache.set('query3', { content: '3' }); // Eviction 1
      smallCache.set('query4', { content: '4' }); // Eviction 2

      const stats = smallCache.getStats();
      expect(stats.evictions).toBe(2);
    });
  });

  describe('TTL expiration', () => {
    it('should expire entries after TTL', async () => {
      const shortCache = new ResponseCache({ defaultTtl: 1 }); // 1 second

      shortCache.set('query', { content: 'response' });

      // Should be cached immediately
      expect(shortCache.get('query')).toBeDefined();

      // Wait for expiration
      await new Promise((resolve) => setTimeout(resolve, 1100));

      // Should be expired
      expect(shortCache.get('query')).toBeUndefined();
    });

    it('should use custom TTL when provided', async () => {
      cache.set('query', { content: 'response' }, { ttl: 1 }); // 1 second

      expect(cache.get('query')).toBeDefined();

      await new Promise((resolve) => setTimeout(resolve, 1100));

      expect(cache.get('query')).toBeUndefined();
    });

    it('should use default TTL when not provided', () => {
      const cache1000 = new ResponseCache({ defaultTtl: 1000 });

      cache1000.set('query', { content: 'response' });

      // Should not be expired immediately
      expect(cache1000.get('query')).toBeDefined();
    });

    it('should count expired entries as misses', async () => {
      const shortCache = new ResponseCache({ defaultTtl: 1 });

      shortCache.set('query', { content: 'response' });
      shortCache.get('query'); // Hit

      await new Promise((resolve) => setTimeout(resolve, 1100));

      shortCache.get('query'); // Miss (expired)

      const stats = shortCache.getStats();
      expect(stats.hits).toBe(1);
      expect(stats.misses).toBe(1);
    });

    it('should remove expired entry on access', async () => {
      const shortCache = new ResponseCache({ defaultTtl: 1, maxSize: 3 });

      shortCache.set('query1', { content: '1' });

      await new Promise((resolve) => setTimeout(resolve, 1100));

      // Access expired entry (should be removed)
      shortCache.get('query1');

      const stats = shortCache.getStats();
      expect(stats.size).toBe(0); // Entry removed
    });
  });

  describe('statistics', () => {
    it('should track hits and misses', () => {
      cache.set('query', { content: 'response' });

      cache.get('query'); // Hit
      cache.get('query'); // Hit
      cache.get('not-cached'); // Miss

      const stats = cache.getStats();
      expect(stats.hits).toBe(2);
      expect(stats.misses).toBe(1);
    });

    it('should calculate hit rate correctly', () => {
      cache.set('query', { content: 'response' });

      cache.get('query'); // Hit
      cache.get('not-cached'); // Miss

      const stats = cache.getStats();
      expect(stats.hitRate).toBe(0.5); // 1 hit / 2 total
    });

    it('should handle zero requests for hit rate', () => {
      const stats = cache.getStats();
      expect(stats.hitRate).toBe(0);
    });

    it('should track number of sets', () => {
      cache.set('query1', { content: '1' });
      cache.set('query2', { content: '2' });
      cache.set('query3', { content: '3' });

      const stats = cache.getStats();
      expect(stats.sets).toBe(3);
    });

    it('should track cache size', () => {
      cache.set('query1', { content: '1' });
      cache.set('query2', { content: '2' });

      const stats = cache.getStats();
      expect(stats.size).toBe(2);
      expect(stats.maxSize).toBe(1000); // Default
    });

    it('should reset statistics', () => {
      cache.set('query', { content: 'response' });
      cache.get('query');
      cache.get('not-cached');

      cache.resetStats();

      const stats = cache.getStats();
      expect(stats.hits).toBe(0);
      expect(stats.misses).toBe(0);
      expect(stats.sets).toBe(0);
      expect(stats.evictions).toBe(0);
      expect(stats.size).toBe(1); // Cache content preserved
    });
  });

  describe('configuration', () => {
    it('should use default configuration', () => {
      const config = cache.getConfig();

      expect(config.maxSize).toBe(1000);
      expect(config.defaultTtl).toBe(3600);
    });

    it('should accept custom configuration', () => {
      const customCache = new ResponseCache({
        maxSize: 500,
        defaultTtl: 1800,
      });

      const config = customCache.getConfig();
      expect(config.maxSize).toBe(500);
      expect(config.defaultTtl).toBe(1800);
    });
  });

  describe('utility methods', () => {
    it('should check if entry exists with has()', () => {
      cache.set('query', { content: 'response' });

      expect(cache.has('query')).toBe(true);
      expect(cache.has('not-cached')).toBe(false);
    });

    it('should not affect LRU order with has()', () => {
      const smallCache = new ResponseCache({ maxSize: 3 });

      smallCache.set('query1', { content: '1' });
      smallCache.set('query2', { content: '2' });
      smallCache.set('query3', { content: '3' });

      // Check without affecting LRU
      smallCache.has('query1');

      // Add new entry (should still evict query1)
      smallCache.set('query4', { content: '4' });

      expect(smallCache.has('query1')).toBe(false); // Evicted
    });

    it('should remove expired entries manually', async () => {
      const shortCache = new ResponseCache({ defaultTtl: 1 });

      shortCache.set('query1', { content: '1' });
      shortCache.set('query2', { content: '2' });

      await new Promise((resolve) => setTimeout(resolve, 1100));

      const removed = shortCache.removeExpired();

      expect(removed).toBe(2);
      expect(shortCache.getStats().size).toBe(0);
    });

    it('should handle partial expiration', async () => {
      const cache2 = new ResponseCache({ defaultTtl: 10 });

      cache2.set('query1', { content: '1' }, { ttl: 1 });
      cache2.set('query2', { content: '2' }, { ttl: 10 });

      await new Promise((resolve) => setTimeout(resolve, 1100));

      const removed = cache2.removeExpired();

      expect(removed).toBe(1);
      expect(cache2.getStats().size).toBe(1);
      expect(cache2.has('query2')).toBe(true);
    });
  });

  describe('createResponseCache factory', () => {
    it('should create cache with factory', () => {
      const cache = createResponseCache({ maxSize: 500 });

      expect(cache).toBeInstanceOf(ResponseCache);
      expect(cache.getConfig().maxSize).toBe(500);
    });

    it('should create cache with default config', () => {
      const cache = createResponseCache();

      expect(cache).toBeInstanceOf(ResponseCache);
      expect(cache.getConfig().maxSize).toBe(1000);
    });
  });

  describe('edge cases', () => {
    it('should handle empty queries', () => {
      cache.set('', { content: 'empty' });
      const cached = cache.get('');

      expect(cached).toEqual({ content: 'empty' });
    });

    it('should handle complex objects in response', () => {
      const complexResponse = {
        nested: { data: [1, 2, 3] },
        array: ['a', 'b', 'c'],
        null: null,
        bool: true,
      };

      cache.set('query', complexResponse);
      const cached = cache.get('query');

      expect(cached).toEqual(complexResponse);
    });

    it('should handle max size of 1', () => {
      const tinyCache = new ResponseCache({ maxSize: 1 });

      tinyCache.set('query1', { content: '1' });
      tinyCache.set('query2', { content: '2' }); // Should evict query1

      expect(tinyCache.get('query1')).toBeUndefined();
      expect(tinyCache.get('query2')).toBeDefined();
      expect(tinyCache.getStats().size).toBe(1);
    });

    it('should handle very short TTL', async () => {
      const cache2 = new ResponseCache({ defaultTtl: 0.1 }); // 100ms

      cache2.set('query', { content: 'response' });

      await new Promise((resolve) => setTimeout(resolve, 150));

      expect(cache2.get('query')).toBeUndefined();
    });

    it('should handle overwriting existing keys', () => {
      cache.set('query', { content: 'first' });
      cache.set('query', { content: 'second' });

      const cached = cache.get('query');
      expect(cached).toEqual({ content: 'second' });

      // Should count as 2 sets, not replace
      const stats = cache.getStats();
      expect(stats.sets).toBe(2);
    });
  });
});
