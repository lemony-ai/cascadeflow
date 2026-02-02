import { createProviderAdapter } from './base';

export const deepseekAdapter = createProviderAdapter({
  id: 'deepseek',
  label: 'DeepSeek',
  envKeys: ['DEEPSEEK_API_KEY'],
  defaultBaseUrl: 'https://api.deepseek.com/v1',
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
      id: 'deepseek-chat',
      label: 'DeepSeek Chat',
      cost: { input: 0.00014, output: 0.00028 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'deepseek-coder',
      label: 'DeepSeek Coder',
      cost: { input: 0.00014, output: 0.00028 },
      contextWindow: 128000,
      supportsTools: true,
    },
  ],
});
