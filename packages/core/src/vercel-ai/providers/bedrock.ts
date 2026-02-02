import { createProviderAdapter } from './base';

export const bedrockAdapter = createProviderAdapter({
  id: 'bedrock',
  label: 'AWS Bedrock',
  envKeys: ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION'],
  defaultBaseUrl: 'https://bedrock-runtime.{region}.amazonaws.com',
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
      id: 'anthropic.claude-3-5-sonnet-20241022-v2',
      label: 'Claude 3.5 Sonnet (Bedrock)',
      cost: { input: 0.003, output: 0.015 },
      contextWindow: 200000,
      supportsTools: true,
    },
    {
      id: 'amazon.titan-text-premier-v1',
      label: 'Amazon Titan Text Premier',
      cost: { input: 0.0015, output: 0.003 },
      contextWindow: 32000,
      supportsTools: false,
    },
    {
      id: 'meta.llama3-70b-instruct-v1',
      label: 'Llama 3 70B Instruct',
      cost: { input: 0.0009, output: 0.0011 },
      contextWindow: 128000,
      supportsTools: true,
    },
  ],
});
