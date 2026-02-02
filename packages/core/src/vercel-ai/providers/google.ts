import { createProviderAdapter } from './base';

export const googleAdapter = createProviderAdapter({
  id: 'google',
  label: 'Google',
  envKeys: ['GOOGLE_API_KEY'],
  defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta',
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
      id: 'gemini-1.5-flash',
      label: 'Gemini 1.5 Flash',
      cost: { input: 0.00035, output: 0.00053 },
      contextWindow: 1000000,
      supportsTools: true,
    },
    {
      id: 'gemini-1.5-pro',
      label: 'Gemini 1.5 Pro',
      cost: { input: 0.0035, output: 0.0105 },
      contextWindow: 1000000,
      supportsTools: true,
    },
    {
      id: 'gemini-2.0-flash',
      label: 'Gemini 2.0 Flash',
      cost: { input: 0.0004, output: 0.0006 },
      contextWindow: 1000000,
      supportsTools: true,
    },
    {
      id: 'gemini-2.0-pro',
      label: 'Gemini 2.0 Pro',
      cost: { input: 0.005, output: 0.015 },
      contextWindow: 1000000,
      supportsTools: true,
    },
  ],
});
