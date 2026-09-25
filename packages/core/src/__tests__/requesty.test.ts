/**
 * Tests for Requesty provider
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { RequestyProvider } from '../providers/requesty';
import type { ModelConfig } from '../config';

// Mock fetch globally
global.fetch = vi.fn();

describe('Requesty Provider', () => {
  let mockConfig: ModelConfig;

  beforeEach(() => {
    mockConfig = {
      name: 'openai/gpt-4o-mini',
      provider: 'requesty',
      apiKey: 'rqsty-test-key',
      cost: 0.00015,
    };
    vi.clearAllMocks();
  });

  describe('Provider Initialization', () => {
    it('should create provider with valid config', () => {
      const provider = new RequestyProvider(mockConfig);
      expect(provider).toBeDefined();
      expect(provider.name).toBe('requesty');
    });

    it('should accept custom base URL', () => {
      const customConfig = { ...mockConfig, baseUrl: 'https://router.eu.requesty.ai/v1' };
      const provider = new RequestyProvider(customConfig);
      expect(provider).toBeDefined();
    });

    it('should be available when API key is provided', () => {
      const provider = new RequestyProvider(mockConfig);
      expect(provider.isAvailable()).toBe(true);
    });
  });

  describe('Cost Calculation', () => {
    it('should calculate cost for gpt-4o correctly', () => {
      const provider = new RequestyProvider({ ...mockConfig, name: 'openai/gpt-4o' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'openai/gpt-4o');

      // Input: 1M tokens at $2.50/1M = $2.50
      // Output: 1M tokens at $10.00/1M = $10.00
      // Total: $12.50
      expect(cost).toBeCloseTo(12.5, 2);
    });

    it('should calculate cost for gpt-4o-mini correctly', () => {
      const provider = new RequestyProvider(mockConfig);
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'openai/gpt-4o-mini');

      // Input: $0.15/1M, Output: $0.60/1M
      expect(cost).toBeCloseTo(0.75, 2);
    });

    it('should calculate cost for claude-sonnet-4-5 correctly', () => {
      const provider = new RequestyProvider({ ...mockConfig, name: 'anthropic/claude-sonnet-4-5' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'anthropic/claude-sonnet-4-5');

      // Input: $3/1M, Output: $15/1M
      expect(cost).toBeCloseTo(18.0, 2);
    });

    it('should handle unknown models with fallback pricing', () => {
      const provider = new RequestyProvider({ ...mockConfig, name: 'unknown/model' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'unknown/model');

      // Should fallback to gpt-4o-mini pricing ($0.15/$0.60)
      expect(cost).toBeCloseTo(0.75, 2);
    });

    it('should handle case-insensitive model names', () => {
      const provider = new RequestyProvider(mockConfig);
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

      const provider = new RequestyProvider(mockConfig);
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
        'https://router.requesty.ai/v1/chat/completions',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Authorization: 'Bearer rqsty-test-key',
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

      const provider = new RequestyProvider(mockConfig);

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

      const provider = new RequestyProvider(mockConfig);
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

      const provider = new RequestyProvider(mockConfig);
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

      const provider = new RequestyProvider(mockConfig);
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
    it('should fetch managed policies first, then the full catalog', async () => {
      (global.fetch as any)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            data: [{ id: 'claude-sonnet-4-5', api: 'chat', input_price: 0.000003, output_price: 0.000015 }],
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            data: [
              { id: 'openai/gpt-4o', api: 'chat', input_price: 0.0000025, output_price: 0.00001 },
              { id: 'claude-sonnet-4-5', api: 'chat', input_price: 0.000003, output_price: 0.000015 },
            ],
          }),
        });

      const provider = new RequestyProvider(mockConfig);
      const models = await provider.fetchAvailableModels();

      expect(models.map((m) => m.id)).toEqual(['claude-sonnet-4-5', 'openai/gpt-4o']);
      expect((global.fetch as any).mock.calls[0][0]).toBe('https://router.requesty.ai/v1/models/managed');
      expect((global.fetch as any).mock.calls[1][0]).toBe('https://router.requesty.ai/v1/models');
    });

    it('should cache model list for 1 hour', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ data: [{ id: 'openai/gpt-4o', input_price: 0.0000025, output_price: 0.00001 }] }),
      });

      const provider = new RequestyProvider(mockConfig);

      // First call fetches managed policies and the catalog
      await provider.fetchAvailableModels();
      expect(global.fetch).toHaveBeenCalledTimes(2);

      // Second call should use cache
      await provider.fetchAvailableModels();
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('should keep the catalog when managed policies fail', async () => {
      (global.fetch as any)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: [{ id: 'openai/gpt-4o-mini' }] }),
        });

      const provider = new RequestyProvider(mockConfig);
      const models = await provider.fetchAvailableModels();

      expect(models.map((m) => m.id)).toEqual(['openai/gpt-4o-mini']);
    });

    it('should get pricing for specific model', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          data: [{ id: 'openai/gpt-4o', input_price: 0.0000025, output_price: 0.00001 }],
        }),
      });

      const provider = new RequestyProvider(mockConfig);
      const pricing = await provider.getModelPricing('openai/gpt-4o');

      expect(pricing).toBeDefined();
      expect(pricing?.input).toBeCloseTo(2.5, 6); // 0.0000025 * 1M
      expect(pricing?.output).toBeCloseTo(10.0, 6); // 0.00001 * 1M
    });

    it('should return null for unknown model pricing', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ data: [] }),
      });

      const provider = new RequestyProvider(mockConfig);
      const pricing = await provider.getModelPricing('unknown/model');

      expect(pricing).toBeNull();
    });

    it('should handle model fetch errors gracefully', async () => {
      (global.fetch as any).mockRejectedValue(new Error('Network error'));

      const provider = new RequestyProvider(mockConfig);
      const models = await provider.fetchAvailableModels();

      // Should return empty array on error, not throw
      expect(models).toEqual([]);
    });
  });
});
