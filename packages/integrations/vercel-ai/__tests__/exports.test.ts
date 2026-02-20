import { describe, expect, it, vi } from 'vitest';

vi.mock('@cascadeflow/core', () => ({
  VercelAI: {
    createChatHandler: vi.fn(),
    createCompletionHandler: vi.fn(),
  },
}));

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
