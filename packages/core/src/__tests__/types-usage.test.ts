import { describe, expect, it } from 'vitest';

import { toCanonicalUsage } from '../types';

describe('canonical usage mapping', () => {
  it('maps legacy prompt/completion fields', () => {
    const usage = toCanonicalUsage({ prompt_tokens: 10, completion_tokens: 15, total_tokens: 25 });
    expect(usage.input_tokens).toBe(10);
    expect(usage.output_tokens).toBe(15);
    expect(usage.total_tokens).toBe(25);
  });

  it('preserves canonical fields', () => {
    const usage = toCanonicalUsage({ input_tokens: 8, output_tokens: 12, cached_input_tokens: 4 } as any);
    expect(usage.input_tokens).toBe(8);
    expect(usage.output_tokens).toBe(12);
    expect(usage.cached_input_tokens).toBe(4);
    expect(usage.total_tokens).toBe(20);
  });
});
