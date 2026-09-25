/**
 * Requesty Integration Tests
 *
 * Tests the Requesty provider with real API calls to:
 * - openai/gpt-4o-mini (drafter)
 * - anthropic/claude-sonnet-4-5 (verifier)
 *
 * Requires REQUESTY_API_KEY environment variable.
 */

import { describe, it, expect } from 'vitest';
import { CascadeAgent } from '../src';
import { RequestyProvider } from '../src/providers/requesty';

// Check for API key
const apiKey = process.env.REQUESTY_API_KEY;
const hasApiKey = !!apiKey;

describe('Requesty Integration Tests', () => {
  it.skipIf(!hasApiKey)('should initialize Requesty provider', () => {
    const provider = new RequestyProvider({
      name: 'openai/gpt-4o-mini',
      provider: 'requesty',
      apiKey,
      cost: 0.00015,
    });

    expect(provider).toBeDefined();
    expect(provider.name).toBe('requesty');
    expect(provider.isAvailable()).toBe(true);
  });

  it.skipIf(!hasApiKey)('should generate completion with GPT-4o Mini', async () => {
    const provider = new RequestyProvider({
      name: 'openai/gpt-4o-mini',
      provider: 'requesty',
      apiKey,
      cost: 0.00015,
    });

    const result = await provider.generate({
      messages: [{ role: 'user', content: 'What is 2+2? Answer in one sentence.' }],
      model: 'openai/gpt-4o-mini',
      maxTokens: 100,
    });

    console.log(`Requesty generate: model=${result.model} content=${result.content.substring(0, 100)}`);

    expect(result.content).toBeTruthy();
    // Responses echo the upstream model id (e.g. gpt-4o-mini-2024-07-18)
    expect(result.model).toContain('gpt-4o-mini');
    expect(result.usage?.prompt_tokens).toBeGreaterThan(0);
    expect(result.usage?.completion_tokens).toBeGreaterThan(0);
  }, 30000);

  it.skipIf(!hasApiKey)('should cascade from GPT-4o Mini to Claude Sonnet 4.5', async () => {
    const agent = new CascadeAgent({
      models: [
        {
          name: 'openai/gpt-4o-mini',
          provider: 'requesty',
          cost: 0.00015,
          apiKey,
        },
        {
          name: 'anthropic/claude-sonnet-4-5',
          provider: 'requesty',
          cost: 0.003,
          apiKey,
        },
      ],
    });

    const result = await agent.run('Explain quantum computing in simple terms, in 2-3 sentences.');

    console.log(`Requesty cascade: modelUsed=${result.modelUsed} cascaded=${result.cascaded}`);

    expect(result.content).toBeTruthy();
    // modelUsed may be the dated upstream id (e.g. claude-sonnet-4-5-20250929)
    expect(result.modelUsed).toMatch(/gpt-4o-mini|claude-sonnet-4-5/);
  }, 60000);

  it.skipIf(!hasApiKey)('should support streaming with Requesty', async () => {
    const provider = new RequestyProvider({
      name: 'openai/gpt-4o-mini',
      provider: 'requesty',
      apiKey,
      cost: 0.00015,
    });

    const chunks: string[] = [];
    for await (const chunk of provider.stream!({
      messages: [{ role: 'user', content: 'Count from 1 to 5. Just the numbers.' }],
      model: 'openai/gpt-4o-mini',
      maxTokens: 50,
    })) {
      if (chunk.content) {
        chunks.push(chunk.content);
      }
      if (chunk.done) break;
    }

    expect(chunks.length).toBeGreaterThan(0);
    expect(chunks.join('')).toBeTruthy();
  }, 30000);

  it.skipIf(!hasApiKey)('should fetch managed policies and catalog models', async () => {
    const provider = new RequestyProvider({
      name: 'openai/gpt-4o-mini',
      provider: 'requesty',
      apiKey,
      cost: 0.00015,
    });

    const models = await provider.fetchAvailableModels();
    const modelIds = models.map((m: any) => m.id);

    console.log(`Requesty models: ${models.length}`);

    expect(models.length).toBeGreaterThan(0);
    expect(modelIds).toContain('openai/gpt-4o-mini');
  }, 30000);

  it.skipIf(!hasApiKey)('should get dynamic pricing for specific models', async () => {
    const provider = new RequestyProvider({
      name: 'openai/gpt-4o-mini',
      provider: 'requesty',
      apiKey,
      cost: 0.00015,
    });

    const pricing = await provider.getModelPricing('openai/gpt-4o-mini');

    expect(pricing).not.toBeNull();
    expect(pricing!.input).toBeGreaterThan(0);
    expect(pricing!.output).toBeGreaterThan(0);
  }, 30000);

  it.skipIf(!hasApiKey)('should support tool calling via Requesty', async () => {
    const provider = new RequestyProvider({
      name: 'openai/gpt-4o-mini',
      provider: 'requesty',
      apiKey,
      cost: 0.00015,
    });

    const result = await provider.generate({
      messages: [{ role: 'user', content: 'What is the weather in Tokyo? Use the weather tool.' }],
      model: 'openai/gpt-4o-mini',
      tools: [
        {
          type: 'function',
          function: {
            name: 'get_weather',
            description: 'Get current weather for a location',
            parameters: {
              type: 'object',
              properties: {
                location: {
                  type: 'string',
                  description: 'City name',
                },
              },
              required: ['location'],
            },
          },
        },
      ],
      maxTokens: 200,
    });

    expect(result).toBeDefined();

    // Model may or may not call tool depending on prompt interpretation
    if (result.tool_calls) {
      expect(result.tool_calls.length).toBeGreaterThan(0);
      expect(result.tool_calls[0].function.name).toBe('get_weather');
    } else {
      expect(result.content).toBeTruthy();
    }
  }, 30000);
});
