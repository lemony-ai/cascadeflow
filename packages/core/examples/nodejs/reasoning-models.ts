/**
 * Example: Using Reasoning Models Across All Providers
 *
 * cascadeflow supports reasoning models from 4 providers with automatic detection:
 *
 * 1. OpenAI (o1-preview, o1-mini)
 *    - Chain-of-thought reasoning with hidden thinking
 *    - reasoning_effort parameter (low/medium/high)
 *    - max_completion_tokens required
 *    - Note: Requires OpenAI Tier 3+ API access (https://platform.openai.com/settings/organization/limits)
 *
 * 2. Anthropic (claude-sonnet-4-5, claude-opus-4-1)
 *    - Extended thinking mode (enable with thinkingBudget)
 *    - Minimum 1024 tokens thinking budget
 *    - Visible reasoning in response
 *    - Claude Sonnet 4.5 and Opus 4.1 released in 2025
 *
 * 3. Ollama (deepseek-r1, deepseek-r1-distill)
 *    - Free local inference
 *    - DeepSeek-R1 reasoning models
 *    - Full privacy, no API costs
 *
 * 4. vLLM (deepseek-r1, deepseek-r1-distill)
 *    - Self-hosted high-performance inference
 *    - 24x faster than standard serving
 *    - Production-ready deployment
 *
 * Zero configuration required - cascadeflow auto-detects capabilities!
 */

import { CascadeAgent } from '@cascadeflow/core';

async function reasoningModelsExample() {
  // Example 1: o1-mini (fast reasoning model)
  console.log('\n=== Example 1: o1-mini (fast reasoning model) ===');
  console.log('Note: Requires OpenAI Tier 3+ API access');
  console.log('Check your tier at: https://platform.openai.com/settings/organization/limits\n');

  try {
    const agent1 = new CascadeAgent({
      models: [
        {
          name: 'o1-mini', // Auto-detected as reasoning model
          provider: 'openai',
          cost: 0.003, // $3 per 1M input tokens, $12 per 1M output tokens
        },
      ],
    });

    const result1 = await agent1.run(
      'Solve this problem step by step: If a train travels at 80 km/h for 2.5 hours, then slows to 60 km/h for the next hour, what is the total distance traveled?',
      { maxTokens: 2000 }
    );

    console.log('Response:', result1.content);
    console.log('Cost:', `$${result1.totalCost.toFixed(6)}`);
  } catch (error) {
    console.log('Skipping - API access required:', (error as Error).message);
    console.log('Solution: Upgrade to Tier 3+ or use different models');
  }

  // Example 2: o1-preview (advanced reasoning model)
  console.log('\n=== Example 2: o1-preview (advanced reasoning) ===');
  console.log('Note: Requires OpenAI Tier 5 API access\n');

  try {
    const agent2 = new CascadeAgent({
      models: [
        {
          name: 'o1-preview',
          provider: 'openai',
          cost: 0.015, // $15 per 1M input tokens, $60 per 1M output tokens
        },
      ],
    });

    // High reasoning effort for complex problem
    const result2 = await agent2.run(
      'Design an efficient algorithm to find all palindromic substrings in a string of length n. Analyze the time and space complexity.',
      { maxTokens: 4000 }
    );

    console.log('Response:', result2.content.substring(0, 500) + '...');
    console.log('Cost:', `$${result2.totalCost.toFixed(6)}`);
  } catch (error) {
    console.log('Skipping - API access required:', (error as Error).message);
  }

  // Example 3: Using in cascade (auto-routing to reasoning model)
  console.log('\n=== Example 3: Cascade with reasoning model fallback ===');
  const agent3 = new CascadeAgent({
    models: [
      {
        name: 'gpt-4o-mini', // Fast, cheap model tries first
        provider: 'openai',
        cost: 0.00015,
      },
      {
        name: 'o1-mini', // Falls back to reasoning model if needed
        provider: 'openai',
        cost: 0.004,
      },
    ],
    quality: {
      threshold: 0.8, // High quality threshold
    },
  });

  const result3 = await agent3.run(
    'Prove that the square root of 2 is irrational.',
    { maxTokens: 2000 }
  );

  console.log('Model used:', result3.modelUsed);
  console.log('Response:', result3.content.substring(0, 300) + '...');
  console.log('Quality score:', result3.qualityScore);

  // Example 4: Comparing reasoning efforts (skipped - requires Tier 5 access)
  console.log('\n=== Example 4: Comparing reasoning efforts ===');
  console.log('Skipped - Requires o1-preview access (Tier 5)');
  console.log('This example would compare low/medium/high reasoning effort settings\n');

  // Example 5: Anthropic Claude Sonnet 4.5 with Extended Thinking
  console.log('\n=== Example 5: Claude Sonnet 4.5 (Extended Thinking) ===');

  try {
    const agent4 = new CascadeAgent({
      models: [
        {
          name: 'claude-sonnet-4-5',
          provider: 'anthropic',
          cost: 0.003,
        },
      ],
    });

    const result4 = await agent4.run(
      'Design a fault-tolerant distributed consensus algorithm. Explain your reasoning process.',
      { maxTokens: 5000 }
    );

    console.log('Response:', result4.content.substring(0, 500) + '...');
    console.log('Cost:', `$${result4.totalCost.toFixed(6)}`);
    console.log('\nNote: Claude extended thinking produces visible reasoning in the response!');
  } catch (error) {
    console.log('Skipping - Anthropic API error:', (error as Error).message);
  }

  // Example 6: DeepSeek-R1 via Ollama (Free Local Inference)
  console.log('\n=== Example 6: DeepSeek-R1 via Ollama (Local) ===');
  console.log('Prerequisites: Install Ollama (https://ollama.ai) and run:');
  console.log('  ollama pull deepseek-r1:8b');
  console.log();

  try {
    const agent5 = new CascadeAgent({
      models: [
        {
          name: 'deepseek-r1:8b', // Auto-detected as reasoning model
          provider: 'ollama',
          cost: 0,
        },
      ],
    });

    const result5 = await agent5.run(
      'Explain the time complexity of quicksort in best, average, and worst cases.',
      { maxTokens: 2000 }
    );

    console.log('Response:', result5.content.substring(0, 400) + '...');
    console.log('Cost:', `$${result5.totalCost.toFixed(6)}`, '(FREE - local inference)');
  } catch (error) {
    console.log('Skipping - Ollama not available:', (error as Error).message);
    console.log('Install from: https://ollama.ai');
  }

  // Example 7: DeepSeek-R1 via vLLM (High-Performance Self-Hosted)
  console.log('\n=== Example 7: DeepSeek-R1 via vLLM (Self-Hosted) ===');
  console.log('Prerequisites: Start vLLM server:');
  console.log('  python -m vllm.entrypoints.openai.api_server \\');
  console.log('    --model deepseek-ai/DeepSeek-R1-Distill-Llama-8B \\');
  console.log('    --port 8000');
  console.log();

  try {
    const agent6 = new CascadeAgent({
      models: [
        {
          name: 'deepseek-ai/DeepSeek-R1-Distill-Llama-8B',
          provider: 'vllm',
          baseUrl: process.env.VLLM_BASE_URL || 'http://localhost:8000/v1',
          cost: 0,
        },
      ],
    });

    const result6 = await agent6.run(
      'What is the difference between TCP and UDP? When would you use each?',
      { maxTokens: 1500 }
    );

    console.log('Response:', result6.content.substring(0, 400) + '...');
    console.log('Cost:', `$${result6.totalCost.toFixed(6)}`, '(FREE - self-hosted)');
    console.log('Note: vLLM provides 24x faster inference than standard serving!');
  } catch (error) {
    console.log('Skipping - vLLM server not available:', (error as Error).message);
    console.log('See: https://docs.vllm.ai');
  }

  // Example 8: Multi-Provider Reasoning Cascade
  console.log('\n=== Example 8: Multi-Provider Reasoning Cascade ===');
  const agent7 = new CascadeAgent({
    models: [
      {
        name: 'deepseek-r1:8b',
        provider: 'ollama',
        cost: 0, // Free local inference
      },
      {
        name: 'o1-mini',
        provider: 'openai',
        cost: 0.004,
      },
      {
        name: 'claude-sonnet-4-5',
        provider: 'anthropic',
        cost: 0.003,
      },
    ],
    quality: {
      threshold: 0.85,
    },
  });

  console.log('This cascade tries:');
  console.log('  1. DeepSeek-R1 (local, free)');
  console.log('  2. Falls back to o1-mini if quality < 0.85');
  console.log('  3. Falls back to Claude Sonnet 4.5 as final option');
  console.log();
  console.log('Perfect for cost optimization with reasoning models!');
}

// Run examples
reasoningModelsExample().catch(console.error);
