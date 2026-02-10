/**
 * Tests for Vercel AI SDK provider integration
 */

import { describe, it, expect, vi } from 'vitest';
import { VercelAISDKProvider, VERCEL_AI_PROVIDER_SPECS, VERCEL_AI_PROVIDER_NAMES } from '../providers/vercel-ai';
import type { ModelConfig } from '../config';

vi.mock('ai', () => ({
  generateText: vi.fn(async () => ({
    text: 'Hello from Vercel AI SDK',
    usage: { promptTokens: 4, completionTokens: 6, totalTokens: 10 },
    finishReason: 'stop',
  })),
  streamText: vi.fn(async () => {
    async function* stream() {
      yield 'Hello ';
      yield 'stream';
    }
    return {
      textStream: stream(),
      usage: Promise.resolve({ promptTokens: 2, completionTokens: 3, totalTokens: 5 }),
      finishReason: 'stop',
    };
  }),
}));

describe('Vercel AI SDK Provider', () => {
  it('defines a stable set of supported Vercel AI SDK providers', () => {
    expect(VERCEL_AI_PROVIDER_NAMES).toEqual(
      expect.arrayContaining(['openai', 'anthropic', 'groq', 'google', 'azure', 'bedrock', 'vertex'])
    );
    expect(VERCEL_AI_PROVIDER_NAMES).not.toContain('openrouter');
    expect(VERCEL_AI_PROVIDER_NAMES).not.toContain('ollama');
  });

  it('maps every provider name to a spec', () => {
    for (const providerName of VERCEL_AI_PROVIDER_NAMES) {
      const spec = VERCEL_AI_PROVIDER_SPECS[providerName];
      expect(spec).toBeDefined();
      expect(spec.packageName).toBeTruthy();
      expect(spec.exportName).toBeTruthy();
    }
  });

  it('instantiates for every supported provider name', () => {
    for (const providerName of VERCEL_AI_PROVIDER_NAMES) {
      const spec = VERCEL_AI_PROVIDER_SPECS[providerName];
      const config: ModelConfig = {
        name: 'test-model',
        provider: providerName as ModelConfig['provider'],
        cost: 0.0025,
        apiKey: spec.requiresApiKey === false ? undefined : 'test-key',
        extra: {
          vercelProviderFactory: vi.fn(() => ({ provider: providerName })),
        },
      };

      const provider = new VercelAISDKProvider(config);
      expect(provider.name).toBe(providerName);
      expect(provider.isAvailable()).toBe(true);
    }
  });

  it('generates and streams using injected factory', async () => {
    const config: ModelConfig = {
      name: 'test-model',
      provider: 'openai',
      cost: 0.0025,
      apiKey: 'test-key',
      extra: {
        vercelProviderFactory: vi.fn(() => ({ provider: 'openai' })),
      },
    };

    const provider = new VercelAISDKProvider(config);

    const response = await provider.generate({
      messages: [{ role: 'user', content: 'Hello' }],
      model: 'gpt-4o-mini',
    });

    expect(response.content).toBe('Hello from Vercel AI SDK');
    expect(response.usage?.prompt_tokens).toBe(4);

    const chunks: string[] = [];
    for await (const chunk of provider.stream({
      messages: [{ role: 'user', content: 'Hello' }],
      model: 'gpt-4o-mini',
    })) {
      chunks.push(chunk.content);
    }

    expect(chunks).toContain('Hello ');
    expect(chunks).toContain('stream');
  });
});
