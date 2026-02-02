import { createProviderAdapter } from './base';

export const perplexityAdapter = createProviderAdapter({
  id: 'perplexity',
  label: 'Perplexity',
  envKeys: ['PERPLEXITY_API_KEY'],
  defaultBaseUrl: 'https://api.perplexity.ai',
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
      id: 'pplx-70b-online',
      label: 'PPLX 70B Online',
      cost: { input: 0.002, output: 0.006 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'sonar-medium-online',
      label: 'Sonar Medium Online',
      cost: { input: 0.001, output: 0.003 },
      contextWindow: 128000,
      supportsTools: true,
    },
  ],
});
