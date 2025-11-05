/**
 * Example: Using Reasoning Models Across All Providers
 *
 * cascadeflow supports reasoning models from 4 providers with automatic detection:
 *
 * 1. OpenAI (o1, o1-mini, o3-mini)
 *    - Chain-of-thought reasoning with hidden thinking
 *    - reasoning_effort parameter (low/medium/high)
 *    - max_completion_tokens required
 *
 * 2. Anthropic (claude-3-7-sonnet-20250219)
 *    - Extended thinking mode (enable with thinkingBudget)
 *    - Minimum 1024 tokens thinking budget
 *    - Visible reasoning in response
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

import { CascadeAgent } from '../../src/index';

async function reasoningModelsExample() {
  // Example 1: o1-mini (supports streaming, no tools, no system messages)
  console.log('\n=== Example 1: o1-mini (original reasoning model) ===');
  const agent1 = new CascadeAgent({
    models: [
      {
        name: 'o1-mini', // Auto-detected as reasoning model
        provider: 'openai',
      },
    ],
    defaultProvider: 'openai',
  });

  const result1 = await agent1.run({
    query: 'Solve this problem step by step: If a train travels at 80 km/h for 2.5 hours, then slows to 60 km/h for the next hour, what is the total distance traveled?',
    maxTokens: 2000,
  });

  console.log('Response:', result1.content);
  console.log('\nUsage:', {
    promptTokens: result1.usage?.prompt_tokens,
    completionTokens: result1.usage?.completion_tokens,
    reasoningTokens: result1.usage?.reasoning_tokens, // Hidden reasoning tokens
    totalTokens: result1.usage?.total_tokens,
  });
  console.log('Cost:', `$${result1.cost.toFixed(6)}`);

  // Example 2: o1-2024-12-17 (newer model with reasoning_effort)
  console.log('\n=== Example 2: o1-2024-12-17 with reasoning_effort ===');
  const agent2 = new CascadeAgent({
    models: [
      {
        name: 'o1-2024-12-17',
        provider: 'openai',
      },
    ],
    defaultProvider: 'openai',
  });

  // High reasoning effort for complex problem
  const result2 = await agent2.run({
    query: 'Design an efficient algorithm to find all palindromic substrings in a string of length n. Analyze the time and space complexity.',
    maxTokens: 4000,
    extra: {
      reasoning_effort: 'high', // More thorough reasoning
    },
  });

  console.log('Response:', result2.content.substring(0, 500) + '...');
  console.log('\nReasoning tokens used:', result2.usage?.reasoning_tokens);
  console.log('Cost:', `$${result2.cost.toFixed(6)}`);

  // Example 3: Using in cascade (auto-routing to reasoning model)
  console.log('\n=== Example 3: Cascade with reasoning model fallback ===');
  const agent3 = new CascadeAgent({
    models: [
      {
        name: 'gpt-4o-mini', // Fast, cheap model tries first
        provider: 'openai',
      },
      {
        name: 'o1-mini', // Falls back to reasoning model if needed
        provider: 'openai',
      },
    ],
    defaultProvider: 'openai',
    minQuality: 0.8, // High quality threshold
  });

  const result3 = await agent3.run({
    query: 'Prove that the square root of 2 is irrational.',
    maxTokens: 2000,
  });

  console.log('Model used:', result3.model);
  console.log('Response:', result3.content.substring(0, 300) + '...');
  console.log('Quality score:', result3.qualityScore);

  // Example 4: Comparing reasoning efforts
  console.log('\n=== Example 4: Comparing reasoning efforts ===');
  const query = 'What are the implications of quantum entanglement for computing?';

  const efforts: Array<'low' | 'medium' | 'high'> = ['low', 'medium', 'high'];

  for (const effort of efforts) {
    const result = await agent2.run({
      query,
      maxTokens: 1000,
      extra: {
        reasoning_effort: effort,
      },
    });

    console.log(`\n${effort.toUpperCase()} effort:`);
    console.log('  Reasoning tokens:', result.usage?.reasoning_tokens);
    console.log('  Total tokens:', result.usage?.total_tokens);
    console.log('  Cost:', `$${result.cost.toFixed(6)}`);
    console.log('  Response length:', result.content.length, 'chars');
  }

  // Example 5: Anthropic Claude 3.7 Sonnet with Extended Thinking
  console.log('\n=== Example 5: Claude 3.7 Sonnet (Extended Thinking) ===');
  const agent4 = new CascadeAgent({
    models: [
      {
        name: 'claude-3-7-sonnet-20250219',
        provider: 'anthropic',
      },
    ],
    defaultProvider: 'anthropic',
  });

  const result4 = await agent4.run({
    query: 'Design a fault-tolerant distributed consensus algorithm. Explain your reasoning process.',
    maxTokens: 5000,
    extra: {
      thinkingBudget: 2048, // Enable extended thinking (min 1024)
    },
  });

  console.log('Response:', result4.content.substring(0, 500) + '...');
  console.log('\nUsage:', {
    promptTokens: result4.usage?.prompt_tokens,
    completionTokens: result4.usage?.completion_tokens,
    totalTokens: result4.usage?.total_tokens,
  });
  console.log('Cost:', `$${result4.cost.toFixed(6)}`);
  console.log('\nNote: Claude extended thinking produces visible reasoning in the response!');

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
        },
      ],
      defaultProvider: 'ollama',
    });

    const result5 = await agent5.run({
      query: 'Explain the time complexity of quicksort in best, average, and worst cases.',
      maxTokens: 2000,
    });

    console.log('Response:', result5.content.substring(0, 400) + '...');
    console.log('Cost:', `$${result5.cost.toFixed(6)}`, '(FREE - local inference)');
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
        },
      ],
      defaultProvider: 'vllm',
    });

    const result6 = await agent6.run({
      query: 'What is the difference between TCP and UDP? When would you use each?',
      maxTokens: 1500,
    });

    console.log('Response:', result6.content.substring(0, 400) + '...');
    console.log('Cost:', `$${result6.cost.toFixed(6)}`, '(FREE - self-hosted)');
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
      },
      {
        name: 'claude-3-7-sonnet-20250219',
        provider: 'anthropic',
      },
    ],
    minQuality: 0.85,
  });

  console.log('This cascade tries:');
  console.log('  1. DeepSeek-R1 (local, free)');
  console.log('  2. Falls back to o1-mini if quality < 0.85');
  console.log('  3. Falls back to Claude 3.7 as final option');
  console.log();
  console.log('Perfect for cost optimization with reasoning models!');
}

// Run examples
reasoningModelsExample().catch(console.error);
