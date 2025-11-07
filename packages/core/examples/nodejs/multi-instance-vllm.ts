/**
 * Multi-Instance vLLM Example
 *
 * Demonstrates running draft and verifier models on separate vLLM instances.
 * vLLM provides high-performance inference with PagedAttention and continuous batching.
 *
 * Use Cases:
 * - GPU 0: Fast 7B model for draft (200+ tokens/sec)
 * - GPU 1: Powerful 70B model for verifier (50+ tokens/sec)
 * - Kubernetes pods with different model sizes
 * - Load-balanced inference clusters
 * - Production-scale deployments
 *
 * Setup Options:
 *
 * Option 1: Multiple local vLLM servers
 * Option 2: Kubernetes StatefulSets
 * Option 3: Docker containers (manual setup)
 *
 * Requirements:
 *   - Two vLLM instances running
 *   - Models downloaded locally or from HuggingFace
 *   - Sufficient GPU memory for each model
 */

import { CascadeAgent } from '@cascadeflow/core';

/**
 * Configuration for multi-instance vLLM
 */
interface MultiInstanceConfig {
  draftInstance: {
    url: string;
    model: string;
    description: string;
    apiKey?: string;
  };
  verifierInstance: {
    url: string;
    model: string;
    description: string;
    apiKey?: string;
  };
}

/**
 * Example configurations for different scenarios
 */
const CONFIGURATIONS = {
  // Scenario 1: Local servers with GPU separation
  local: {
    draftInstance: {
      url: 'http://localhost:8000/v1',
      model: 'Qwen/Qwen2.5-7B-Instruct',
      description: 'Fast 7B model on GPU 0 (200 tok/s)',
    },
    verifierInstance: {
      url: 'http://localhost:8001/v1',
      model: 'Qwen/Qwen2.5-72B-Instruct',
      description: 'Powerful 72B model on GPU 1 (50 tok/s)',
    },
  },

  // Scenario 2: Kubernetes pods
  kubernetes: {
    draftInstance: {
      url: 'http://vllm-draft.default.svc.cluster.local:8000/v1',
      model: 'mistralai/Mistral-7B-Instruct-v0.2',
      description: 'Fast 7B model in draft pod',
    },
    verifierInstance: {
      url: 'http://vllm-verifier.default.svc.cluster.local:8000/v1',
      model: 'mistralai/Mixtral-8x7B-Instruct-v0.1',
      description: 'Powerful Mixtral in verifier pod',
    },
  },

  // Scenario 3: Environment variables (production)
  fromEnv: {
    draftInstance: {
      url: process.env.VLLM_DRAFT_URL || 'http://localhost:8000/v1',
      model: process.env.VLLM_DRAFT_MODEL || 'Qwen/Qwen2.5-7B-Instruct',
      description: 'Draft model from environment',
      apiKey: process.env.VLLM_DRAFT_API_KEY,
    },
    verifierInstance: {
      url: process.env.VLLM_VERIFIER_URL || 'http://localhost:8001/v1',
      model: process.env.VLLM_VERIFIER_MODEL || 'Qwen/Qwen2.5-72B-Instruct',
      description: 'Verifier model from environment',
      apiKey: process.env.VLLM_VERIFIER_API_KEY,
    },
  },
};

/**
 * Create agent with multi-instance configuration
 */
function createMultiInstanceAgent(config: MultiInstanceConfig): CascadeAgent {
  return new CascadeAgent({
    models: [
      {
        name: config.draftInstance.model,
        provider: 'vllm',
        cost: 0, // Self-hosted is free (no API costs)
        baseUrl: config.draftInstance.url,
        apiKey: config.draftInstance.apiKey,
      },
      {
        name: config.verifierInstance.model,
        provider: 'vllm',
        cost: 0,
        baseUrl: config.verifierInstance.url,
        apiKey: config.verifierInstance.apiKey,
      },
    ],
    quality: {
      threshold: 0.7,
    },
  });
}

/**
 * Health check for vLLM instances
 */
async function checkInstanceHealth(url: string, apiKey?: string): Promise<{
  healthy: boolean;
  models: string[];
}> {
  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (apiKey) {
      headers['Authorization'] = `Bearer ${apiKey}`;
    }

    const response = await fetch(`${url}/models`, { headers });

    if (!response.ok) {
      console.error(`Instance at ${url} returned ${response.status}`);
      return { healthy: false, models: [] };
    }

    const data = await response.json() as any;
    const models = data.data?.map((m: any) => m.id) || [];

    return { healthy: true, models };
  } catch (error) {
    console.error(`Failed to connect to ${url}:`, error);
    return { healthy: false, models: [] };
  }
}

/**
 * Main example demonstrating multi-instance usage
 */
async function main() {
  console.log('='.repeat(80));
  console.log('Multi-Instance vLLM Cascade Example');
  console.log('='.repeat(80));
  console.log();

  // Choose configuration (change to 'docker', 'kubernetes', or 'fromEnv')
  const configName = 'fromEnv';
  const config = CONFIGURATIONS[configName];

  console.log(`Configuration: ${configName}`);
  console.log(`Draft:    ${config.draftInstance.description}`);
  console.log(`          ${config.draftInstance.url}`);
  console.log(`          Model: ${config.draftInstance.model}`);
  console.log(`Verifier: ${config.verifierInstance.description}`);
  console.log(`          ${config.verifierInstance.url}`);
  console.log(`          Model: ${config.verifierInstance.model}`);
  console.log();

  // Health checks
  console.log('Health Checks:');
  const draftHealth = await checkInstanceHealth(
    config.draftInstance.url,
    config.draftInstance.apiKey
  );
  const verifierHealth = await checkInstanceHealth(
    config.verifierInstance.url,
    config.verifierInstance.apiKey
  );

  if (!draftHealth.healthy || !verifierHealth.healthy) {
    console.error('');
    console.error('Setup Instructions:');
    console.error('1. Start draft vLLM instance:');
    console.error(`   python -m vllm.entrypoints.openai.api_server \\`);
    console.error(`     --model ${config.draftInstance.model} \\`);
    console.error(`     --port 8000`);
    console.error('');
    console.error('2. Start verifier vLLM instance:');
    console.error(`   python -m vllm.entrypoints.openai.api_server \\`);
    console.error(`     --model ${config.verifierInstance.model} \\`);
    console.error(`     --port 8001`);
    process.exit(1);
  }

  console.log(`  ✅ Draft instance: ${config.draftInstance.url}`);
  console.log(`     Available models: ${draftHealth.models.join(', ')}`);
  console.log(`  ✅ Verifier instance: ${config.verifierInstance.url}`);
  console.log(`     Available models: ${verifierHealth.models.join(', ')}`);
  console.log();

  // Create agent
  const agent = createMultiInstanceAgent(config);
  console.log(`✅ Agent created with ${agent.getModelCount()}-tier cascade`);
  console.log();

  // Test queries with varying complexity
  const queries = [
    {
      prompt: 'Write a Hello World program in Python',
      expected: 'Draft should handle (simple code)',
    },
    {
      prompt: 'Implement a binary search tree with insert, delete, and search operations in TypeScript',
      expected: 'Draft might handle or escalate',
    },
    {
      prompt: 'Design a distributed consensus algorithm handling network partitions and Byzantine failures',
      expected: 'Likely escalates to verifier (complex system design)',
    },
  ];

  const results = [];

  for (let i = 0; i < queries.length; i++) {
    const { prompt, expected } = queries[i];

    console.log('='.repeat(80));
    console.log(`Query ${i + 1}: ${prompt}`);
    console.log(`Expected: ${expected}`);
    console.log('='.repeat(80));

    const start = Date.now();
    const result = await agent.run(prompt);
    const elapsed = Date.now() - start;

    results.push(result);

    console.log();
    console.log('Result:');
    console.log(`  Model used: ${result.modelUsed}`);
    console.log(`  Instance: ${result.modelUsed === config.draftInstance.model ? 'Draft' : 'Verifier'}`);
    console.log(`  URL: ${result.modelUsed === config.draftInstance.model ? config.draftInstance.url : config.verifierInstance.url}`);
    console.log(`  Cascaded: ${result.cascaded}`);
    console.log(`  Draft accepted: ${result.draftAccepted}`);
    console.log(`  Latency: ${elapsed}ms`);

    console.log();
    console.log(`Response preview: ${result.content.substring(0, 300)}...`);
    console.log();
  }

  // Summary
  console.log('='.repeat(80));
  console.log('SESSION SUMMARY');
  console.log('='.repeat(80));
  console.log();

  const draftCount = results.filter(r => r.modelUsed === config.draftInstance.model).length;
  const verifierCount = results.length - draftCount;
  const avgLatency = results.reduce((sum, r) => sum + (r.latencyMs || 0), 0) / results.length;

  console.log(`Total queries: ${results.length}`);
  console.log(`Draft instance: ${draftCount} queries (${(draftCount/results.length*100).toFixed(0)}%)`);
  console.log(`Verifier instance: ${verifierCount} queries (${(verifierCount/results.length*100).toFixed(0)}%)`);
  console.log(`Average latency: ${avgLatency.toFixed(0)}ms`);
  console.log();

  console.log('Multi-Instance Benefits:');
  console.log('  ✅ Parallel inference (no GPU contention)');
  console.log('  ✅ Optimized model serving per instance');
  console.log('  ✅ Independent scaling and monitoring');
  console.log('  ✅ Better resource utilization');
  console.log('  ✅ Fault isolation and reliability');
  console.log();

  console.log('vLLM Performance Features:');
  console.log('  • PagedAttention for memory efficiency');
  console.log('  • Continuous batching for high throughput');
  console.log('  • 10-24x faster than standard serving');
  console.log('  • Full OpenAI API compatibility');
  console.log();

  console.log('Production Considerations:');
  console.log('  • Set up health checks and monitoring');
  console.log('  • Configure auto-scaling based on load');
  console.log('  • Implement circuit breakers for failover');
  console.log('  • Use load balancers for high availability');
  console.log('  • Monitor GPU memory and utilization');
  console.log();
}

main().catch(console.error);
