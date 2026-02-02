import { createProviderAdapter } from './base';

export const fireworksAdapter = createProviderAdapter({
  id: 'fireworks',
  label: 'Fireworks.ai',
  envKeys: ['FIREWORKS_API_KEY'],
  defaultBaseUrl: 'https://api.fireworks.ai/inference/v1',
  rateLimit: {
    requestsPerMinute: 120,
    tokensPerMinute: 200000,
    concurrency: 20,
  },
  capabilities: {
    streaming: true,
    tools: true,
  },
  models: [
    {
      id: 'accounts/fireworks/models/llama-v3p1-70b-instruct',
      label: 'Llama v3.1 70B Instruct',
      cost: { input: 0.0009, output: 0.0012 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'accounts/fireworks/models/mixtral-8x7b-instruct',
      label: 'Mixtral 8x7B Instruct',
      cost: { input: 0.0007, output: 0.0009 },
      contextWindow: 32000,
      supportsTools: true,
    },
    {
      id: 'accounts/fireworks/models/qwen2-72b-instruct',
      label: 'Qwen 2 72B Instruct',
      cost: { input: 0.0008, output: 0.001 },
      contextWindow: 128000,
      supportsTools: true,
    },
  ],
});
