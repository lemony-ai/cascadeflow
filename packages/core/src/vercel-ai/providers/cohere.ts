import { createProviderAdapter } from './base';

export const cohereAdapter = createProviderAdapter({
  id: 'cohere',
  label: 'Cohere',
  envKeys: ['COHERE_API_KEY'],
  defaultBaseUrl: 'https://api.cohere.ai/v1',
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
      id: 'command-r',
      label: 'Command R',
      cost: { input: 0.0005, output: 0.0015 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'command-r-plus',
      label: 'Command R+',
      cost: { input: 0.0015, output: 0.0025 },
      contextWindow: 128000,
      supportsTools: true,
    },
  ],
});
