import { createProviderAdapter } from './base';

export const openRouterAdapter = createProviderAdapter({
  id: 'openrouter',
  label: 'OpenRouter',
  envKeys: ['OPENROUTER_API_KEY'],
  defaultBaseUrl: 'https://openrouter.ai/api/v1',
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
      label: 'OpenAI GPT-4o Mini (via OpenRouter)',
      cost: { input: 0.00015, output: 0.0006 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'anthropic/claude-3.5-sonnet',
      label: 'Claude 3.5 Sonnet (via OpenRouter)',
      cost: { input: 0.003, output: 0.015 },
      contextWindow: 200000,
      supportsTools: true,
    },
    {
      id: 'google/gemini-1.5-pro',
      label: 'Gemini 1.5 Pro (via OpenRouter)',
      cost: { input: 0.0035, output: 0.0105 },
      contextWindow: 1000000,
      supportsTools: true,
    },
  ],
});
