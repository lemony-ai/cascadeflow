import { describe, expect, it } from 'vitest';
import {
  buildFallbackCascade,
  createDraftVerifierCascade,
  groqAdapter,
  openAIAdapter,
  ProviderRateLimiter,
} from '../index';



describe('Vercel AI cascade planning', () => {
  it('mixes providers in a draft/verifier cascade', () => {
    const plan = createDraftVerifierCascade(
      {
        providerId: groqAdapter.id,
        model: groqAdapter.models[0].id,
      },
      {
        providerId: openAIAdapter.id,
        model: openAIAdapter.models[0].id,
      }
    );

    expect(plan.models).toHaveLength(2);
    expect(plan.roles).toEqual(['drafter', 'verifier']);
    expect(plan.fallbackOrder[0]).toContain(groqAdapter.id);
  });

  it('builds fallback chains in order', () => {
    const plan = buildFallbackCascade(
      {
        providerId: groqAdapter.id,
        model: groqAdapter.models[1].id,
        role: 'drafter',
      },
      [
        {
          providerId: openAIAdapter.id,
          model: openAIAdapter.models[1].id,
          role: 'verifier',
        },
      ]
    );

    expect(plan.fallbackOrder).toEqual([
      `${groqAdapter.id}:${groqAdapter.models[1].id}`,
      `${openAIAdapter.id}:${openAIAdapter.models[1].id}`,
    ]);
  });
});

describe('Provider rate limiting', () => {
  it('blocks requests that exceed per-minute limits', () => {
    const limiter = new ProviderRateLimiter({ requestsPerMinute: 1, concurrency: 1 });

    const first = limiter.startRequest();
    expect(first.allowed).toBe(true);

    const second = limiter.startRequest();
    expect(second.allowed).toBe(false);

    limiter.endRequest();
  });
});
