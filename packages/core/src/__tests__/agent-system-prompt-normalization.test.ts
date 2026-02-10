import { beforeAll, describe, expect, it } from 'vitest';

import { CascadeAgent } from '../agent';
import { providerRegistry, type Provider, type ProviderRequest } from '../providers/base';
import type { ModelConfig } from '../config';
import type { ProviderResponse } from '../types';

let lastRequest: ProviderRequest | null = null;

class CaptureProvider implements Provider {
  readonly name = 'custom';

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  constructor(_config: ModelConfig) {}

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    lastRequest = request;
    return {
      content: 'ok',
      model: request.model,
      usage: {
        prompt_tokens: 1,
        completion_tokens: 1,
        total_tokens: 2,
      },
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
  // Make sure this provider exists for all tests in this file.
  providerRegistry.register('custom', CaptureProvider as any);
});

describe('CascadeAgent system prompt normalization', () => {
  it('extracts system messages into systemPrompt and strips them from messages', async () => {
    const agent = new CascadeAgent({
      models: [{ name: 'test-model', provider: 'custom', cost: 0 }],
    });

    await agent.run([
      { role: 'system', content: 'You are a helpful assistant.' },
      { role: 'user', content: 'Hello' },
    ]);

    expect(lastRequest).toBeTruthy();
    expect(lastRequest?.systemPrompt).toBe('You are a helpful assistant.');

    const msgs = lastRequest?.messages as any[];
    expect(msgs.map((m) => m.role)).toEqual(['user']);
  });

  it('combines explicit systemPrompt with system messages (explicit first)', async () => {
    const agent = new CascadeAgent({
      models: [{ name: 'test-model', provider: 'custom', cost: 0 }],
    });

    await agent.run(
      [
        { role: 'system', content: 'System A' },
        { role: 'system', content: 'System B' },
        { role: 'user', content: 'Hi' },
      ],
      { systemPrompt: 'Explicit' }
    );

    expect(lastRequest).toBeTruthy();
    expect(lastRequest?.systemPrompt).toBe('Explicit\n\nSystem A\n\nSystem B');

    const msgs = lastRequest?.messages as any[];
    expect(msgs.map((m) => m.role)).toEqual(['user']);
  });

  it('keeps string input behavior intact', async () => {
    const agent = new CascadeAgent({
      models: [{ name: 'test-model', provider: 'custom', cost: 0 }],
    });

    await agent.run('Ping', { systemPrompt: 'Explicit' });

    expect(lastRequest).toBeTruthy();
    expect(lastRequest?.systemPrompt).toBe('Explicit');

    const msgs = lastRequest?.messages as any[];
    expect(msgs.map((m) => m.role)).toEqual(['user']);
    expect(msgs[0].content).toBe('Ping');
  });
});

