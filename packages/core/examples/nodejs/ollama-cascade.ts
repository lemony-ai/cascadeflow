/**
 * Ollama + Cloud Cascade Test
 *
 * Tests cascadeflow cascade logic with Ollama (local draft) + OpenAI (cloud verifier).
 * This demonstrates the same qualityThreshold configuration as basic-usage.ts.
 *
 * Environment Variables (optional):
 * - OLLAMA_MODEL: Ollama model name (default: mistral:7b-instruct)
 * - OLLAMA_BASE_URL: Ollama server URL (default: http://localhost:11434)
 * - CLOUD_MODEL: Cloud verifier model (default: gpt-4o)
 *
 * Usage:
 *   # Use default models
 *   npx tsx ollama-cascade.ts
 *
 *   # Use your own Ollama model
 *   OLLAMA_MODEL="gemma3:12b" npx tsx ollama-cascade.ts
 *
 *   # Use custom Ollama server
 *   OLLAMA_BASE_URL="http://192.168.0.199:11434" OLLAMA_MODEL="deepseek-r1:7b" npx tsx ollama-cascade.ts
 */

import { CascadeAgent, type ModelConfig } from "@cascadeflow/core";

async function main() {
  console.log("=".repeat(80));
  console.log("Ollama + Cloud Cascade Test (TypeScript)");
  console.log("=".repeat(80));
  console.log();

  // Get model names from environment or use defaults
  const ollamaModel = process.env.OLLAMA_MODEL || "mistral:7b-instruct";
  const ollamaBaseUrl = process.env.OLLAMA_BASE_URL || "http://localhost:11434";
  const cloudModel = process.env.CLOUD_MODEL || "gpt-4o";

  console.log("Configuration:");
  console.log(`  Ollama model: ${ollamaModel}`);
  console.log(`  Ollama URL: ${ollamaBaseUrl}`);
  console.log(`  Cloud model: ${cloudModel}`);
  console.log();

  // Create agent with Ollama draft + OpenAI verifier (same thresholds as basic-usage.ts)
  const models: ModelConfig[] = [
    // Draft model - Ollama (local, free)
    {
      name: ollamaModel,
      provider: "ollama",
      cost: 0.0, // Free local execution
      baseUrl: ollamaBaseUrl,
      qualityThreshold: 0.7, // Accept if confidence >= 70%
    },
    // Verifier model - OpenAI (cloud, expensive)
    {
      name: cloudModel,
      provider: "openai",
      cost: 0.00625, // $6.25 per 1M tokens (blended estimate)
      qualityThreshold: 0.95, // Very high quality
    },
  ];

  const agent = new CascadeAgent({ models });

  console.log("✅ Agent created with 2-tier cascade:");
  console.log(`   Tier 1: ${ollamaModel} (Ollama) - qualityThreshold=0.7`);
  console.log(`   Tier 2: ${cloudModel} (OpenAI) - qualityThreshold=0.95`);
  console.log();

  // Test query
  const query = "What is TypeScript in one sentence?";
  console.log(`Query: ${query}`);
  console.log();

  try {
    const result = await agent.run(query);

    console.log("Result:");
    console.log(`  Model used: ${result.modelUsed}`);
    console.log(`  Cascaded: ${result.cascaded}`);
    console.log(`  Cost: $${result.totalCost.toFixed(6)}`);

    if ("draftAccepted" in result) {
      console.log(`  Draft accepted: ${result.draftAccepted}`);
    }

    if ("complexity" in result) {
      console.log(`  Complexity: ${result.complexity}`);
    }

    console.log();
    console.log(`Response: ${result.content}`);
    console.log();

    console.log("=".repeat(80));
    console.log("✅ SUCCESS: Ollama cascade test passed");
    console.log("=".repeat(80));
  } catch (error) {
    console.error(`❌ ERROR: ${error}`);
    console.error();
    console.error(error);
  }
}

main().catch(console.error);
