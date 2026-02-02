import { createProviderAdapter } from './base';

export const xaiAdapter = createProviderAdapter({
  id: 'xai',
  label: 'xAI',
  envKeys: ['XAI_API_KEY'],
  defaultBaseUrl: 'https://api.x.ai/v1',
  rateLimit: {
    requestsPerMinute: 60,
    tokensPerMinute: 120000,
    concurrency: 10,
  },
  capabilities: {
    streaming: true,
    tools: true,
  },
  models: [
    {
      id: 'grok-2',
      label: 'Grok 2',
      cost: { input: 0.005, output: 0.015 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'grok-2-mini',
      label: 'Grok 2 Mini',
      cost: { input: 0.0005, output: 0.0015 },
      contextWindow: 128000,
      supportsTools: true,
    },
  ],
});
