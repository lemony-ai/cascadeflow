import { createProviderAdapter } from './base';

export const requestyAdapter = createProviderAdapter({
  id: 'requesty',
  label: 'Requesty',
  envKeys: ['REQUESTY_API_KEY'],
  defaultBaseUrl: 'https://router.requesty.ai/v1',
  rateLimit: {
    requestsPerMinute: 120,
    tokensPerMinute: 150000,
    concurrency: 15,
  },
  capabilities: {
    streaming: true,
    tools: true,
  },
  models: [
    {
      id: 'openai/gpt-4o-mini',
      label: 'OpenAI GPT-4o Mini (via Requesty)',
      cost: { input: 0.00015, output: 0.0006 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'anthropic/claude-sonnet-4-5',
      label: 'Claude Sonnet 4.5 (via Requesty)',
      cost: { input: 0.003, output: 0.015 },
      contextWindow: 1000000,
      supportsTools: true,
    },
    {
      id: 'google/gemini-2.5-flash',
      label: 'Gemini 2.5 Flash (via Requesty)',
      cost: { input: 0.0003, output: 0.0025 },
      contextWindow: 1048576,
      supportsTools: true,
    },
  ],
});
