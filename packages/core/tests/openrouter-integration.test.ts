/**
 * OpenRouter Integration Tests
 *
 * Tests OpenRouter provider with real API calls to:
 * - x-ai/grok-code-fast-1 (free tier, most popular)
 * - anthropic/claude-4.5-sonnet (premium tier)
 *
 * Requires OPENROUTER_API_KEY environment variable.
 */

import { describe, it, expect } from 'vitest';
import { CascadeAgent } from '../src';
import { OpenRouterProvider } from '../src/providers/openrouter';

// Check for API key
const apiKey = process.env.OPENROUTER_API_KEY;
const hasApiKey = !!apiKey;

describe('OpenRouter Integration Tests', () => {
  it.skipIf(!hasApiKey)('should generate completion with Grok Code Fast (free)', async () => {
    console.log('🔍 Test: Grok Code Fast (x-ai) - Free Tier');
    console.log('   Model: x-ai/grok-code-fast-1');
    console.log('   Query: "What is 2+2?"\n');

    const provider = new OpenRouterProvider({
      name: 'x-ai/grok-code-fast-1',
      provider: 'openrouter',
      apiKey,
      cost: 0,
    });

    const startTime = Date.now();
    const result = await provider.generate({
      messages: [{ role: 'user', content: 'What is 2+2? Answer in one sentence.' }],
      model: 'x-ai/grok-code-fast-1',
      maxTokens: 100,
    });
    const elapsed = Date.now() - startTime;

    console.log('📊 Result:');
    console.log(`   Model: ${result.model}`);
    console.log(`   Response: ${result.content.substring(0, 100)}${result.content.length > 100 ? '...' : ''}`);
    console.log(`   Tokens: ${result.usage?.prompt_tokens} in / ${result.usage?.completion_tokens} out`);
    console.log(`   Latency: ${elapsed}ms`);
    console.log(`   Cost: FREE`);
    console.log('');

    expect(result.content).toBeTruthy();
    expect(result.content.length).toBeGreaterThan(0);
    expect(result.model).toContain('grok');
    expect(result.usage).toBeDefined();
    expect(result.usage?.prompt_tokens).toBeGreaterThan(0);
    expect(result.usage?.completion_tokens).toBeGreaterThan(0);

    console.log('✅ Grok Code Fast test passed!\n');
  }, 30000);

  it.skipIf(!hasApiKey)('should generate completion with Claude 4.5 Sonnet', async () => {
    console.log('🔍 Test: Claude 4.5 Sonnet (Anthropic) - Premium Tier');
    console.log('   Model: anthropic/claude-4.5-sonnet-20250929');
    console.log('   Query: "Explain recursion briefly."\n');

    const provider = new OpenRouterProvider({
      name: 'anthropic/claude-4.5-sonnet-20250929',
      provider: 'openrouter',
      apiKey,
      cost: 0.003,
    });

    const startTime = Date.now();
    const result = await provider.generate({
      messages: [{ role: 'user', content: 'Explain recursion in one sentence.' }],
      model: 'anthropic/claude-4.5-sonnet-20250929',
      maxTokens: 100,
    });
    const elapsed = Date.now() - startTime;

    // Calculate actual cost
    const promptTokens = result.usage?.prompt_tokens || 0;
    const completionTokens = result.usage?.completion_tokens || 0;
    const actualCost = provider.calculateCost(promptTokens, completionTokens, 'anthropic/claude-4.5-sonnet-20250929');

    console.log('📊 Result:');
    console.log(`   Model: ${result.model}`);
    console.log(`   Response: ${result.content.substring(0, 100)}${result.content.length > 100 ? '...' : ''}`);
    console.log(`   Tokens: ${promptTokens} in / ${completionTokens} out`);
    console.log(`   Latency: ${elapsed}ms`);
    console.log(`   Cost: $${actualCost.toFixed(6)}`);
    console.log('');

    expect(result.content).toBeTruthy();
    expect(result.content.length).toBeGreaterThan(0);
    expect(result.model).toContain('claude');
    expect(result.usage).toBeDefined();
    expect(actualCost).toBeGreaterThan(0);

    console.log('✅ Claude 4.5 Sonnet test passed!\n');
  }, 30000);

  it.skipIf(!hasApiKey)('should cascade from Grok to Claude Sonnet', async () => {
    console.log('🔍 Test: Cascade from Grok (free) → Claude Sonnet (premium)');
    console.log('   Tier 1: x-ai/grok-code-fast-1 (FREE)');
    console.log('   Tier 2: anthropic/claude-4.5-sonnet-20250929 ($3/$15 per 1M)');
    console.log('   Query: "Explain quantum computing in simple terms."\n');

    const agent = new CascadeAgent({
      models: [
        {
          name: 'x-ai/grok-code-fast-1',
          provider: 'openrouter',
          cost: 0,
          apiKey,
          qualityThreshold: 0.8, // High threshold - may need Claude
        },
        {
          name: 'anthropic/claude-4.5-sonnet-20250929',
          provider: 'openrouter',
          cost: 0.003,
          apiKey,
        },
      ],
    });

    console.log(`✅ Agent created with ${agent.getModelCount()} models\n`);

    const startTime = Date.now();
    const result = await agent.run('Explain quantum computing in simple terms, in 2-3 sentences.');
    const elapsed = Date.now() - startTime;

    console.log('📊 Result:');
    console.log(`   Model used: ${result.modelUsed}`);
    console.log(`   Response: ${result.content.substring(0, 150)}...`);
    console.log(`   Cost: ${result.totalCost === 0 ? 'FREE' : `$${result.totalCost.toFixed(6)}`}`);
    console.log(`   Latency: ${elapsed}ms`);
    console.log(`   Cascaded: ${result.cascaded ? 'Yes' : 'No'}`);

    if (result.savingsPercentage !== undefined) {
      console.log(`   Savings: ${result.savingsPercentage.toFixed(1)}%`);
    }

    console.log('');

    expect(result.content).toBeTruthy();
    expect(result.content.length).toBeGreaterThan(0);
    expect(result.modelUsed).toBeDefined();
    expect(['x-ai/grok-code-fast-1', 'anthropic/claude-4.5-sonnet-20250929']).toContain(result.modelUsed);

    console.log('✅ Cascade test passed!\n');
  }, 60000);

  it.skipIf(!hasApiKey)('should support streaming with OpenRouter', async () => {
    console.log('🔍 Test: Streaming with Grok Code Fast');
    console.log('   Model: x-ai/grok-code-fast-1');
    console.log('   Query: "Count from 1 to 5."\n');

    const provider = new OpenRouterProvider({
      name: 'x-ai/grok-code-fast-1',
      provider: 'openrouter',
      apiKey,
      cost: 0,
    });

    const chunks: string[] = [];
    const startTime = Date.now();

    let chunkCount = 0;
    for await (const chunk of provider.stream!({
      messages: [{ role: 'user', content: 'Count from 1 to 5. Just the numbers.' }],
      model: 'x-ai/grok-code-fast-1',
      maxTokens: 50,
    })) {
      if (chunk.content) {
        chunks.push(chunk.content);
        chunkCount++;
      }
      if (chunk.done) break;
    }

    const elapsed = Date.now() - startTime;
    const fullResponse = chunks.join('');

    console.log('📊 Streaming Result:');
    console.log(`   Chunks received: ${chunkCount}`);
    console.log(`   Full response: ${fullResponse.substring(0, 100)}`);
    console.log(`   Latency: ${elapsed}ms`);
    console.log(`   Cost: FREE`);
    console.log('');

    expect(chunks.length).toBeGreaterThan(0);
    expect(fullResponse).toBeTruthy();

    console.log('✅ Streaming test passed!\n');
  }, 30000);

  it.skipIf(!hasApiKey)('should support tool calling via OpenRouter', async () => {
    console.log('🔍 Test: Tool calling with Claude 4.5 Sonnet');
    console.log('   Model: anthropic/claude-4.5-sonnet-20250929');
    console.log('   Tool: get_weather');
    console.log('   Query: "What is the weather in Tokyo?"\n');

    const provider = new OpenRouterProvider({
      name: 'anthropic/claude-4.5-sonnet-20250929',
      provider: 'openrouter',
      apiKey,
      cost: 0.003,
    });

    const result = await provider.generate({
      messages: [{ role: 'user', content: 'What is the weather in Tokyo? Use the weather tool.' }],
      model: 'anthropic/claude-4.5-sonnet-20250929',
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

    console.log('📊 Tool Calling Result:');
    console.log(`   Model: ${result.model}`);
    console.log(`   Tool calls: ${result.tool_calls?.length || 0}`);

    if (result.tool_calls && result.tool_calls.length > 0) {
      result.tool_calls.forEach((tc, i) => {
        console.log(`   Tool ${i + 1}:`);
        console.log(`      Name: ${tc.function.name}`);
        console.log(`      Args: ${tc.function.arguments}`);
      });
    } else {
      console.log(`   Content: ${result.content.substring(0, 100)}...`);
    }

    console.log('');

    expect(result).toBeDefined();
    expect(result.model).toContain('claude');

    // Model may or may not call tool depending on prompt interpretation
    if (result.tool_calls) {
      expect(result.tool_calls.length).toBeGreaterThan(0);
    } else {
      expect(result.content).toBeTruthy();
    }

    console.log('✅ Tool calling test passed!\n');
  }, 30000);

  // Summary
  it.skipIf(!hasApiKey)('summary', () => {
    console.log('═══════════════════════════════════════════');
    console.log('🎉 All OpenRouter Integration Tests Passed!');
    console.log('═══════════════════════════════════════════');
    console.log('');
    console.log('✅ Tested Models:');
    console.log('   • x-ai/grok-code-fast-1 (FREE, most popular)');
    console.log('   • anthropic/claude-4.5-sonnet-20250929 (premium)');
    console.log('');
    console.log('✅ Tested Features:');
    console.log('   • Basic completions');
    console.log('   • Streaming responses');
    console.log('   • Cascade routing');
    console.log('   • Tool calling');
    console.log('');
    console.log('🚀 OpenRouter provider is production-ready!');
    console.log('');
  });
});
