import { beforeAll, describe, expect, it } from 'vitest';

import { CascadeAgent } from '../agent';
import type { ModelConfig } from '../config';
import {
  KnowledgeCache,
  providerKnowledgeCacheOptions,
} from '../knowledge-cache';
import { providerRegistry, type Provider, type ProviderRequest } from '../providers/base';
import type { ProviderResponse } from '../types';

const capturedRequests: ProviderRequest[] = [];

class KnowledgeCaptureProvider implements Provider {
  readonly name = 'knowledge-capture';

  constructor(_config: ModelConfig) {}

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    capturedRequests.push(request);
    return {
      content: 'ok',
      model: request.model,
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
    };
  }

  calculateCost(): number {
    return 0;
  }

  isAvailable(): boolean {
    return true;
  }
}

beforeAll(() => {
  providerRegistry.register('knowledge-capture' as any, KnowledgeCaptureProvider as any);
});

describe('KnowledgeCache', () => {
  it('reuses an immutable version and records a local cache hit', () => {
    const cache = new KnowledgeCache(2);
    const snapshot = { key: 'catalog', version: '2026-08-06', content: 'Current catalog' };

    const first = cache.prepare(snapshot);
    const second = cache.prepare(snapshot);

    expect(first.localCacheHit).toBe(false);
    expect(second.localCacheHit).toBe(true);
    expect(second.prepared).toBe(first.prepared);
    expect(cache.getStats()).toEqual({ size: 1, hits: 1, misses: 1, evictions: 0 });
  });

  it('rejects reusing a version with different content', () => {
    const cache = new KnowledgeCache();
    cache.prepare({ key: 'policy', version: 'v1', content: 'Policy A' });

    expect(() => cache.prepare({ key: 'policy', version: 'v1', content: 'Policy B' })).toThrow(
      /version collision/
    );
  });

  it('keeps provider keys content-bound after local eviction', () => {
    const cache = new KnowledgeCache(1);
    const old = cache.prepare({ key: 'docs', version: 'v1', content: 'old' }).prepared;
    cache.prepare({ key: 'other', version: 'v1', content: 'other' });
    const fresh = cache.prepare({ key: 'docs', version: 'v1', content: 'new' }).prepared;

    expect(fresh.promptCacheKey).not.toBe(old.promptCacheKey);
  });

  it('emits native cache hints only for providers that support them', () => {
    const prepared = new KnowledgeCache().prepare({
      key: 'manual',
      version: 'v3',
      content: 'Manual text',
      cacheTtl: '1h',
    }).prepared;

    expect(providerKnowledgeCacheOptions('openai', prepared)).toEqual({
      prompt_cache_key: prepared.promptCacheKey,
    });
    expect(providerKnowledgeCacheOptions('anthropic', prepared)).toEqual({
      cache_control: { type: 'ephemeral', ttl: '1h' },
    });
    expect(providerKnowledgeCacheOptions('ollama', prepared)).toEqual({});
  });

  it('switches snapshots without leaking previous knowledge into a request', async () => {
    capturedRequests.length = 0;
    const agent = new CascadeAgent({
      models: [{ name: 'capture', provider: 'knowledge-capture' as any, cost: 0 }],
    });

    await agent.run('question', {
      systemPrompt: 'Answer briefly.',
      knowledge: { key: 'tenant', version: 'alpha', content: 'Alpha facts' },
    });
    await agent.run('question', {
      systemPrompt: 'Answer briefly.',
      knowledge: { key: 'tenant', version: 'beta', content: 'Beta facts' },
    });

    expect(capturedRequests).toHaveLength(2);
    expect(capturedRequests[0].systemPrompt).toContain('Alpha facts');
    expect(capturedRequests[0].systemPrompt).not.toContain('Beta facts');
    expect(capturedRequests[1].systemPrompt).toContain('Beta facts');
    expect(capturedRequests[1].systemPrompt).not.toContain('Alpha facts');
    expect(capturedRequests[1].systemPrompt).toContain('Answer briefly.');
  });
});
