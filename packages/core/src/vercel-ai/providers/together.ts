import { createProviderAdapter } from './base';

export const togetherAdapter = createProviderAdapter({
  id: 'together',
  label: 'Together.ai',
  envKeys: ['TOGETHER_API_KEY'],
  defaultBaseUrl: 'https://api.together.xyz/v1',
  rateLimit: {
    requestsPerMinute: 120,
    tokensPerMinute: 180000,
    concurrency: 20,
  },
  capabilities: {
    streaming: true,
    tools: true,
  },
  models: [
    {
      id: 'meta-llama/Llama-3.1-70B-Instruct',
      label: 'Llama 3.1 70B Instruct',
      cost: { input: 0.0009, output: 0.0011 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'mistralai/Mixtral-8x7B-Instruct',
      label: 'Mixtral 8x7B Instruct',
      cost: { input: 0.0007, output: 0.0009 },
      contextWindow: 32000,
      supportsTools: true,
    },
    {
      id: 'Qwen/Qwen2.5-72B-Instruct',
      label: 'Qwen 2.5 72B Instruct',
      cost: { input: 0.0008, output: 0.001 },
      contextWindow: 128000,
      supportsTools: true,
    },
  ],
});
