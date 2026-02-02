import { createProviderAdapter } from './base';

export const groqAdapter = createProviderAdapter({
  id: 'groq',
  label: 'Groq',
  envKeys: ['GROQ_API_KEY'],
  defaultBaseUrl: 'https://api.groq.com/openai/v1',
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
      id: 'llama-3.3-70b-versatile',
      label: 'Llama 3.3 70B Versatile',
      cost: { input: 0.0002, output: 0.0002 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'llama-3.1-8b-instant',
      label: 'Llama 3.1 8B Instant',
      cost: { input: 0.0001, output: 0.0001 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'mixtral-8x7b-32768',
      label: 'Mixtral 8x7B 32K',
      cost: { input: 0.00015, output: 0.00015 },
      contextWindow: 32768,
      supportsTools: true,
    },
  ],
});
