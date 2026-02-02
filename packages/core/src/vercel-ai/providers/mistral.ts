import { createProviderAdapter } from './base';

export const mistralAdapter = createProviderAdapter({
  id: 'mistral',
  label: 'Mistral',
  envKeys: ['MISTRAL_API_KEY'],
  defaultBaseUrl: 'https://api.mistral.ai/v1',
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
      id: 'mistral-large-latest',
      label: 'Mistral Large',
      cost: { input: 0.002, output: 0.006 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'mistral-medium-latest',
      label: 'Mistral Medium',
      cost: { input: 0.001, output: 0.003 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'mistral-small-latest',
      label: 'Mistral Small',
      cost: { input: 0.0002, output: 0.0006 },
      contextWindow: 32000,
      supportsTools: true,
    },
  ],
});
