import { createProviderAdapter } from './base';

export const openAIAdapter = createProviderAdapter({
  id: 'openai',
  label: 'OpenAI',
  envKeys: ['OPENAI_API_KEY'],
  defaultBaseUrl: 'https://api.openai.com/v1',
  rateLimit: {
    requestsPerMinute: 60,
    tokensPerMinute: 90000,
    concurrency: 10,
  },
  capabilities: {
    streaming: true,
    tools: true,
  },
  models: [
    {
      id: 'gpt-4o-mini',
      label: 'GPT-4o Mini',
      cost: { input: 0.00015, output: 0.0006 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'gpt-4o',
      label: 'GPT-4o',
      cost: { input: 0.0025, output: 0.01 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'gpt-4',
      label: 'GPT-4',
      cost: { input: 0.03, output: 0.06 },
      contextWindow: 8192,
      supportsTools: true,
    },
  ],
});
