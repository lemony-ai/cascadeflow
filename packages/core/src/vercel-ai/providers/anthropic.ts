import { createProviderAdapter } from './base';

export const anthropicAdapter = createProviderAdapter({
  id: 'anthropic',
  label: 'Anthropic',
  envKeys: ['ANTHROPIC_API_KEY'],
  defaultBaseUrl: 'https://api.anthropic.com',
  rateLimit: {
    requestsPerMinute: 50,
    tokensPerMinute: 80000,
    concurrency: 8,
  },
  capabilities: {
    streaming: true,
    tools: true,
  },
  models: [
    {
      id: 'claude-haiku-4-5-20251001',
      label: 'Claude Haiku 4.5',
      cost: { input: 0.0008, output: 0.004 },
      contextWindow: 200000,
      supportsTools: true,
    },
    {
      id: 'claude-sonnet-4-6',
      label: 'Claude Sonnet 4.6',
      cost: { input: 0.003, output: 0.015 },
      contextWindow: 200000,
      supportsTools: true,
    },
    {
      id: 'claude-opus-4-6',
      label: 'Claude Opus 4.6',
      cost: { input: 0.015, output: 0.075 },
      contextWindow: 200000,
      supportsTools: true,
    },
  ],
});
