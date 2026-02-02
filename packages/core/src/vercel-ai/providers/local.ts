import { createProviderAdapter } from './base';

export const localAdapter = createProviderAdapter({
  id: 'local',
  label: 'Local runtimes',
  envKeys: [],
  defaultBaseUrl: 'http://localhost:8000/v1',
  endpoints: [
    {
      name: 'vLLM',
      baseUrl: 'http://localhost:8000/v1',
      description: 'OpenAI-compatible vLLM server',
    },
    {
      name: 'Ollama',
      baseUrl: 'http://localhost:11434/v1',
      description: 'Ollama OpenAI-compatible endpoint',
    },
    {
      name: 'llama.cpp',
      baseUrl: 'http://localhost:8080/v1',
      description: 'llama.cpp server',
    },
  ],
  rateLimit: {
    requestsPerMinute: 240,
    tokensPerMinute: 240000,
    concurrency: 20,
  },
  capabilities: {
    streaming: true,
    tools: true,
  },
  models: [
    {
      id: 'llama-3.1-8b-instruct',
      label: 'Llama 3.1 8B Instruct',
      cost: { input: 0, output: 0 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'llama-3.1-70b-instruct',
      label: 'Llama 3.1 70B Instruct',
      cost: { input: 0, output: 0 },
      contextWindow: 128000,
      supportsTools: true,
    },
    {
      id: 'qwen2.5-7b-instruct',
      label: 'Qwen 2.5 7B Instruct',
      cost: { input: 0, output: 0 },
      contextWindow: 32000,
      supportsTools: true,
    },
  ],
});
