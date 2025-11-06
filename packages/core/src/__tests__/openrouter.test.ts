/**
 * Tests for OpenRouter provider
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { OpenRouterProvider } from '../providers/openrouter';
import type { ModelConfig } from '../config';

// Mock fetch globally
global.fetch = vi.fn();

describe('OpenRouter Provider', () => {
  let mockConfig: ModelConfig;

  beforeEach(() => {
    mockConfig = {
      name: 'openai/gpt-4o-mini',
      provider: 'openrouter',
      apiKey: 'sk-or-test-key',
      cost: 0.00015,
    };
    vi.clearAllMocks();
  });

  describe('Provider Initialization', () => {
    it('should create provider with valid config', () => {
      const provider = new OpenRouterProvider(mockConfig);
      expect(provider).toBeDefined();
      expect(provider.name).toBe('openrouter');
    });

    it('should accept custom base URL', () => {
      const customConfig = { ...mockConfig, baseUrl: 'https://custom.openrouter.ai/api/v1' };
      const provider = new OpenRouterProvider(customConfig);
      expect(provider).toBeDefined();
    });

    it('should be available when API key is provided', () => {
      const provider = new OpenRouterProvider(mockConfig);
      expect(provider.isAvailable()).toBe(true);
    });
  });

  describe('Cost Calculation', () => {
    it.each([
      ['openai/gpt-4o', 1_000_000, 1_000_000, 12.50],
      ['anthropic/claude-opus-4', 1_000_000, 1_000_000, 90.00],
      ['anthropic/claude-4.5-sonnet-20250929', 1_000_000, 1_000_000, 18.00],
      ['google/gemini-2.5-flash', 1_000_000, 1_000_000, 0.75],
      ['meta-llama/llama-3.1-8b-instruct', 1_000_000, 1_000_000, 0.10],
      ['deepseek/deepseek-chat', 1_000_000, 1_000_000, 0], // free
      ['x-ai/grok-code-fast-1', 1_000_000, 1_000_000, 0], // free
      ['deepseek/deepseek-coder-v2', 1_000_000, 1_000_000, 1.37],
      ['minimax/minimax-m2', 1_000_000, 1_000_000, 0.20],
    ])('should calculate cost for %s correctly', (model, promptTokens, completionTokens, expected) => {
      const provider = new OpenRouterProvider({ ...mockConfig, name: model });
      const cost = provider.calculateCost(promptTokens, completionTokens, model);
      expect(cost).toBeCloseTo(expected, 2);
    });

    it('should handle unknown models with fallback pricing', () => {
      const provider = new OpenRouterProvider({ ...mockConfig, name: 'unknown/model' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'unknown/model');

      // Should fallback to gpt-4o-mini pricing ($0.15/$0.60)
      expect(cost).toBeCloseTo(0.75, 2);
    });

    it('should handle case-insensitive model names', () => {
      const provider = new OpenRouterProvider(mockConfig);
      const cost1 = provider.calculateCost(1_000_000, 1_000_000, 'openai/gpt-4o');
      const cost2 = provider.calculateCost(1_000_000, 1_000_000, 'OpenAI/GPT-4O');

      expect(cost1).toBeCloseTo(cost2, 6);
    });
  });

  describe('Generate Method', () => {
    it('should make correct API request', async () => {
      const mockResponse = {
        choices: [
          {
            message: {
              content: 'Test response',
              role: 'assistant',
            },
            finish_reason: 'stop',
          },
        ],
        model: 'openai/gpt-4o-mini',
        usage: {
          prompt_tokens: 10,
          completion_tokens: 20,
          total_tokens: 30,
        },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const provider = new OpenRouterProvider(mockConfig);
      const result = await provider.generate({
        messages: [{ role: 'user', content: 'Hello' }],
        model: 'openai/gpt-4o-mini',
      });

      expect(result.content).toBe('Test response');
      expect(result.model).toBe('openai/gpt-4o-mini');
      expect(result.usage?.prompt_tokens).toBe(10);
      expect(result.usage?.completion_tokens).toBe(20);

      // Verify fetch was called with correct parameters
      expect(global.fetch).toHaveBeenCalledWith(
        'https://openrouter.ai/api/v1/chat/completions',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Authorization: 'Bearer sk-or-test-key',
            'HTTP-Referer': 'https://github.com/lemony-ai/cascadeflow',
            'X-Title': 'CascadeFlow',
          }),
        })
      );
    });

    it('should handle API errors gracefully', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        text: async () => 'Invalid API key',
      });

      const provider = new OpenRouterProvider(mockConfig);

      await expect(
        provider.generate({
          messages: [{ role: 'user', content: 'Hello' }],
          model: 'openai/gpt-4o-mini',
        })
      ).rejects.toThrow();
    });

    it('should support tool calling', async () => {
      const mockResponse = {
        choices: [
          {
            message: {
              content: null,
              role: 'assistant',
              tool_calls: [
                {
                  id: 'call_123',
                  type: 'function',
                  function: {
                    name: 'get_weather',
                    arguments: '{"location": "San Francisco"}',
                  },
                },
              ],
            },
            finish_reason: 'tool_calls',
          },
        ],
        model: 'openai/gpt-4o-mini',
        usage: {
          prompt_tokens: 50,
          completion_tokens: 20,
          total_tokens: 70,
        },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const provider = new OpenRouterProvider(mockConfig);
      const result = await provider.generate({
        messages: [{ role: 'user', content: 'What is the weather in SF?' }],
        model: 'openai/gpt-4o-mini',
        tools: [
          {
            type: 'function',
            function: {
              name: 'get_weather',
              description: 'Get weather for a location',
              parameters: {
                type: 'object',
                properties: {
                  location: { type: 'string' },
                },
              },
            },
          },
        ],
      });

      expect(result.tool_calls).toBeDefined();
      expect(result.tool_calls?.length).toBe(1);
      expect(result.tool_calls?.[0].function.name).toBe('get_weather');
    });

    it('should include system prompt in messages', async () => {
      const mockResponse = {
        choices: [{ message: { content: 'Response', role: 'assistant' }, finish_reason: 'stop' }],
        model: 'openai/gpt-4o-mini',
        usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const provider = new OpenRouterProvider(mockConfig);
      await provider.generate({
        messages: [{ role: 'user', content: 'Hello' }],
        model: 'openai/gpt-4o-mini',
        systemPrompt: 'You are a helpful assistant',
      });

      const fetchCall = (global.fetch as any).mock.calls[0];
      const requestBody = JSON.parse(fetchCall[1].body);

      expect(requestBody.messages[0].role).toBe('system');
      expect(requestBody.messages[0].content).toBe('You are a helpful assistant');
    });
  });

  describe('Streaming', () => {
    it('should support streaming responses', async () => {
      const mockStream = `data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{"content":" world"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n`;

      const encoder = new TextEncoder();
      const mockReader = {
        read: vi
          .fn()
          .mockResolvedValueOnce({ done: false, value: encoder.encode(mockStream) })
          .mockResolvedValueOnce({ done: true, value: undefined }),
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      });

      const provider = new OpenRouterProvider(mockConfig);
      const chunks: string[] = [];

      for await (const chunk of provider.stream!({
        messages: [{ role: 'user', content: 'Hello' }],
        model: 'openai/gpt-4o-mini',
      })) {
        chunks.push(chunk.content);
      }

      expect(chunks).toContain('Hello');
      expect(chunks).toContain(' world');
    });
  });

  describe('Model Discovery', () => {
    it('should fetch available models from API', async () => {
      const mockModels = {
        data: [
          {
            id: 'openai/gpt-4o',
            name: 'GPT-4o',
            pricing: {
              prompt: '0.0000025',
              completion: '0.00001',
            },
            context_length: 128000,
          },
          {
            id: 'anthropic/claude-opus-4',
            name: 'Claude Opus 4',
            pricing: {
              prompt: '0.000015',
              completion: '0.000075',
            },
            context_length: 200000,
          },
        ],
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockModels,
      });

      const provider = new OpenRouterProvider(mockConfig);
      const models = await provider.fetchAvailableModels();

      expect(models).toHaveLength(2);
      expect(models[0].id).toBe('openai/gpt-4o');
      expect(models[1].id).toBe('anthropic/claude-opus-4');
    });

    it('should cache model list for 1 hour', async () => {
      const mockModels = {
        data: [{ id: 'openai/gpt-4o', pricing: { prompt: '0.0000025', completion: '0.00001' } }],
      };

      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => mockModels,
      });

      const provider = new OpenRouterProvider(mockConfig);

      // First call should fetch
      await provider.fetchAvailableModels();
      expect(global.fetch).toHaveBeenCalledTimes(1);

      // Second call should use cache
      await provider.fetchAvailableModels();
      expect(global.fetch).toHaveBeenCalledTimes(1); // Still 1, not 2
    });

    it('should get pricing for specific model', async () => {
      const mockModels = {
        data: [
          {
            id: 'openai/gpt-4o',
            pricing: {
              prompt: '0.0000025',
              completion: '0.00001',
            },
          },
        ],
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockModels,
      });

      const provider = new OpenRouterProvider(mockConfig);
      const pricing = await provider.getModelPricing('openai/gpt-4o');

      expect(pricing).toBeDefined();
      expect(pricing?.input).toBe(2.5); // 0.0000025 * 1M
      expect(pricing?.output).toBe(10.0); // 0.00001 * 1M
    });

    it('should return null for unknown model pricing', async () => {
      const mockModels = {
        data: [],
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockModels,
      });

      const provider = new OpenRouterProvider(mockConfig);
      const pricing = await provider.getModelPricing('unknown/model');

      expect(pricing).toBeNull();
    });

    it('should handle model fetch errors gracefully', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

      const provider = new OpenRouterProvider(mockConfig);
      const models = await provider.fetchAvailableModels();

      // Should return empty array on error, not throw
      expect(models).toEqual([]);
    });
  });
});
