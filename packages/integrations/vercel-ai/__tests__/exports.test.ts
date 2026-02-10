import { describe, expect, it } from 'vitest';

import { createChatHandler, createCompletionHandler, VercelAI } from '../src';

describe('@cascadeflow/vercel-ai exports', () => {
  it('exports handler factories', () => {
    expect(typeof createChatHandler).toBe('function');
    expect(typeof createCompletionHandler).toBe('function');
  });

  it('re-exports VercelAI namespace', () => {
    expect(typeof VercelAI).toBe('object');
    expect(typeof (VercelAI as any).createChatHandler).toBe('function');
  });
});

