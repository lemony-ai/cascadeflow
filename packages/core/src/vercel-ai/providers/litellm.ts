import { createProviderAdapter } from './base';

export const liteLLMAdapter = createProviderAdapter({
  id: 'litellm',
  label: 'LiteLLM',
  envKeys: ['LITELLM_API_KEY'],
  defaultBaseUrl: 'https://api.litellm.ai/v1',
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
      label: 'OpenAI GPT-4o Mini (via LiteLLM)',
      cost: { input: 0.00015, output: 0.0006 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'anthropic/claude-3-5-sonnet-20241022',
      label: 'Claude 3.5 Sonnet (via LiteLLM)',
      cost: { input: 0.003, output: 0.015 },
      contextWindow: 200000,
      supportsTools: true,
    },
    {
      id: 'google/gemini-1.5-pro',
      label: 'Gemini 1.5 Pro (via LiteLLM)',
      cost: { input: 0.0035, output: 0.0105 },
      contextWindow: 1000000,
      supportsTools: true,
    },
  ],
});
