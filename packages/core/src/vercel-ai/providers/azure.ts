import { createProviderAdapter } from './base';

export const azureAdapter = createProviderAdapter({
  id: 'azure',
  label: 'Azure OpenAI',
  envKeys: ['AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT'],
  defaultBaseUrl: 'https://{resource}.openai.azure.com',
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
      label: 'GPT-4o Mini (Azure)',
      cost: { input: 0.00015, output: 0.0006 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'gpt-4o',
      label: 'GPT-4o (Azure)',
      cost: { input: 0.0025, output: 0.01 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'gpt-4',
      label: 'GPT-4 (Azure)',
      cost: { input: 0.03, output: 0.06 },
      contextWindow: 8192,
      supportsTools: true,
    },
  ],
});
