import { beforeAll, describe, expect, it, vi } from 'vitest';

import { CascadeAgent } from '../agent';
import type { ModelConfig } from '../config';
import {
  KnowledgeCache,
  providerKnowledgeCacheOptions,
} from '../knowledge-cache';
import { providerRegistry, type Provider, type ProviderRequest } from '../providers/base';
import { OpenAIProvider } from '../providers/openai';
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
      _cascadeflow_knowledge_cache_prefix: prepared.systemPrefix,
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

  it('places a GPT-5.6 breakpoint after stable knowledge without leaking internal fields', async () => {
    const snapshot = new KnowledgeCache().prepare({
      key: 'manual',
      version: 'v1',
      content: 'Stable manual content',
    }).prepared;
    const create = vi.fn().mockResolvedValue({
      choices: [{ message: { content: 'ok' }, finish_reason: 'stop' }],
      model: 'gpt-5.6-terra',
      usage: {
        prompt_tokens: 1100,
        completion_tokens: 1,
        total_tokens: 1101,
        prompt_tokens_details: { cached_tokens: 1024 },
        cache_write_tokens: 0,
      },
    });
    const provider = new OpenAIProvider({
      name: 'gpt-5.6-terra',
      provider: 'openai',
      cost: 0,
      apiKey: 'test',
    });
    (provider as any).useSDK = true;
    (provider as any).client = { chat: { completions: { create } } };

    const extra = providerKnowledgeCacheOptions('openai', snapshot);
    const result = await provider.generate({
      model: 'gpt-5.6-terra',
      messages: [{ role: 'user', content: 'Changing question' }],
      systemPrompt: snapshot.systemPrefix,
      extra,
    });

    const payload = create.mock.calls[0][0];
    expect(payload.prompt_cache_options).toEqual({ mode: 'explicit' });
    expect(payload.messages[0].content[0].prompt_cache_breakpoint).toEqual({ mode: 'explicit' });
    expect(payload.messages[0].content[0].text).toBe(snapshot.systemPrefix);
    expect(JSON.stringify(payload)).not.toContain('_cascadeflow_knowledge_cache_prefix');
    expect(result.usage?.cached_input_tokens).toBe(1024);
    expect(result.usage?.cache_write_input_tokens).toBe(0);
  });
});
