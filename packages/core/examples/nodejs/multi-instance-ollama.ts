/**
 * Multi-Instance Ollama Example
 *
 * Demonstrates running draft and verifier models on separate Ollama instances.
 * Perfect for multi-GPU systems or distributed inference.
 *
 * Use Cases:
 * - GPU 0: Fast 1B/3B model for draft (high throughput)
 * - GPU 1: Powerful 70B model for verifier (high quality)
 * - Separate machines for load distribution
 * - Different hardware for different models
 *
 * Setup Options:
 *
 * Option 1: Docker Compose (see examples/docker/multi-instance-ollama/)
 * Option 2: Multiple local instances (different ports)
 * Option 3: Network-distributed instances
 *
 * Requirements:
 *   - Two Ollama instances running
 *   - Models pulled on each instance
 *   - Network connectivity
 */

import { CascadeAgent } from '@cascadeflow/core';

/**
 * Configuration for multi-instance Ollama
 */
interface MultiInstanceConfig {
  draftInstance: {
    url: string;
    model: string;
    description: string;
  };
  verifierInstance: {
    url: string;
    model: string;
    description: string;
  };
}

/**
 * Example configurations for different scenarios
 */
const CONFIGURATIONS = {
  // Scenario 1: Docker Compose with GPU separation
  docker: {
    draftInstance: {
      url: 'http://localhost:11434',
      model: 'llama3.2:1b',
      description: 'Fast 1B model on GPU 0',
    },
    verifierInstance: {
      url: 'http://localhost:11435',
      model: 'llama3.1:70b',
      description: 'Powerful 70B model on GPU 1',
    },
  },

  // Scenario 2: Network-distributed instances
  distributed: {
    draftInstance: {
      url: 'http://ollama-gpu-1:11434',
      model: 'qwen2.5:7b',
      description: 'Fast 7B model on machine 1',
    },
    verifierInstance: {
      url: 'http://ollama-gpu-2:11434',
      model: 'qwen2.5:72b',
      description: 'Powerful 72B model on machine 2',
    },
  },

  // Scenario 3: Environment variables (production)
  fromEnv: {
    draftInstance: {
      url: process.env.OLLAMA_DRAFT_URL || 'http://localhost:11434',
      model: process.env.OLLAMA_DRAFT_MODEL || 'llama3.2:1b',
      description: 'Draft model from environment',
    },
    verifierInstance: {
      url: process.env.OLLAMA_VERIFIER_URL || 'http://localhost:11435',
      model: process.env.OLLAMA_VERIFIER_MODEL || 'llama3.1:70b',
      description: 'Verifier model from environment',
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
        provider: 'ollama',
        cost: 0, // Local execution is free
        baseUrl: config.draftInstance.url,
      },
      {
        name: config.verifierInstance.model,
        provider: 'ollama',
        cost: 0,
        baseUrl: config.verifierInstance.url,
      },
    ],
    quality: {
      threshold: 0.7, // Adjust based on your needs
    },
  });
}

/**
 * Health check for Ollama instances
 */
async function checkInstanceHealth(url: string, modelName: string): Promise<boolean> {
  try {
    // Check if instance is responding
    const response = await fetch(`${url}/api/tags`);
    if (!response.ok) {
      console.error(`Instance at ${url} returned ${response.status}`);
      return false;
    }

    const data = await response.json() as any;
    const models = data.models || [];
    const modelExists = models.some((m: any) => m.name.includes(modelName.split(':')[0]));

    if (!modelExists) {
      console.warn(`Model ${modelName} not found on ${url}`);
      console.warn(`Available models: ${models.map((m: any) => m.name).join(', ')}`);
      return false;
    }

    return true;
  } catch (error) {
    console.error(`Failed to connect to ${url}:`, error);
    return false;
  }
}

/**
 * Main example demonstrating multi-instance usage
 */
async function main() {
  console.log('='.repeat(80));
  console.log('Multi-Instance Ollama Cascade Example');
  console.log('='.repeat(80));
  console.log();

  // Choose configuration (change to 'docker', 'distributed', or 'fromEnv')
  const configName = 'fromEnv';
  const config = CONFIGURATIONS[configName];

  console.log(`Configuration: ${configName}`);
  console.log(`Draft:    ${config.draftInstance.description}`);
  console.log(`          ${config.draftInstance.url} → ${config.draftInstance.model}`);
  console.log(`Verifier: ${config.verifierInstance.description}`);
  console.log(`          ${config.verifierInstance.url} → ${config.verifierInstance.model}`);
  console.log();

  // Health checks
  console.log('Health Checks:');
  const draftHealthy = await checkInstanceHealth(
    config.draftInstance.url,
    config.draftInstance.model
  );
  const verifierHealthy = await checkInstanceHealth(
    config.verifierInstance.url,
    config.verifierInstance.model
  );

  if (!draftHealthy || !verifierHealthy) {
    console.error('');
    console.error('Setup Instructions:');
    console.error('1. Start both Ollama instances (see Docker Compose example)');
    console.error('2. Pull models:');
    console.error(`   docker exec ollama-draft ollama pull ${config.draftInstance.model}`);
    console.error(`   docker exec ollama-verifier ollama pull ${config.verifierInstance.model}`);
    process.exit(1);
  }

  console.log(`  ✅ Draft instance: ${config.draftInstance.url}`);
  console.log(`  ✅ Verifier instance: ${config.verifierInstance.url}`);
  console.log();

  // Create agent
  const agent = createMultiInstanceAgent(config);
  console.log(`✅ Agent created with ${agent.getModelCount()}-tier cascade`);
  console.log();

  // Test queries with varying complexity
  const queries = [
    {
      prompt: 'What is TypeScript?',
      expected: 'Draft should handle (simple explanation)',
    },
    {
      prompt: 'Explain the difference between async/await and Promises in JavaScript',
      expected: 'Draft might handle or escalate',
    },
    {
      prompt: 'Design a distributed rate limiter with Redis. Include edge cases and failure modes.',
      expected: 'Likely escalates to verifier (complex design)',
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
    console.log(`  Instance: ${result.modelUsed.includes(config.draftInstance.model.split(':')[0]) ? config.draftInstance.url : config.verifierInstance.url}`);
    console.log(`  Cascaded: ${result.cascaded}`);
    console.log(`  Draft accepted: ${result.draftAccepted}`);
    console.log(`  Latency: ${elapsed}ms`);
    console.log(`  Response length: ${result.content.length} chars`);
    console.log();
    console.log(`Response: ${result.content.substring(0, 200)}...`);
    console.log();
  }

  // Summary
  console.log('='.repeat(80));
  console.log('SESSION SUMMARY');
  console.log('='.repeat(80));
  console.log();

  const draftCount = results.filter(r =>
    r.modelUsed.includes(config.draftInstance.model.split(':')[0])
  ).length;
  const verifierCount = results.length - draftCount;
  const avgLatency = results.reduce((sum, r) => sum + (r.latencyMs || 0), 0) / results.length;

  console.log(`Total queries: ${results.length}`);
  console.log(`Draft instance (${config.draftInstance.model}): ${draftCount} queries`);
  console.log(`Verifier instance (${config.verifierInstance.model}): ${verifierCount} queries`);
  console.log(`Average latency: ${avgLatency.toFixed(0)}ms`);
  console.log();

  console.log('Benefits of Multi-Instance:');
  console.log('  ✅ No resource contention between models');
  console.log('  ✅ Independent GPU utilization');
  console.log('  ✅ Parallel inference possible');
  console.log('  ✅ Easy horizontal scaling');
  console.log('  ✅ Better fault isolation');
  console.log();

  console.log('Performance Notes:');
  console.log(`  • Draft handled ${(draftCount / results.length * 100).toFixed(0)}% of queries`);
  console.log('  • No API costs (100% local)');
  console.log('  • Full privacy (no data leaves your infrastructure)');
  console.log();
}

main().catch(console.error);
