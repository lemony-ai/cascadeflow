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
      id: 'claude-3-5-haiku-20241022',
      label: 'Claude 3.5 Haiku',
      cost: { input: 0.0008, output: 0.004 },
      contextWindow: 200000,
      supportsTools: true,
    },
    {
      id: 'claude-3-5-sonnet-20241022',
      label: 'Claude 3.5 Sonnet',
      cost: { input: 0.003, output: 0.015 },
      contextWindow: 200000,
      supportsTools: true,
    },
    {
      id: 'claude-3-opus-20240229',
      label: 'Claude 3 Opus',
      cost: { input: 0.015, output: 0.075 },
      contextWindow: 200000,
      supportsTools: true,
    },
  ],
});
