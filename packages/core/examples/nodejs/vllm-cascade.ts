/**
 * vLLM + Cloud Cascade Test
 *
 * Tests cascadeflow cascade logic with vLLM (local draft) + OpenAI (cloud verifier).
 * This demonstrates the same qualityThreshold configuration as basic-usage.ts.
 */

import { CascadeAgent, type ModelConfig } from "@cascadeflow/core";

async function main() {
  console.log("=".repeat(80));
  console.log("vLLM + Cloud Cascade Test (TypeScript)");
  console.log("=".repeat(80));
  console.log();

  // Create agent with vLLM draft + OpenAI verifier (same thresholds as basic-usage.ts)
  const models: ModelConfig[] = [
    // Draft model - vLLM (local, free)
    {
      name: "Qwen/Qwen2.5-7B-Instruct",
      provider: "vllm",
      cost: 0.0, // Free local execution
      baseUrl: "http://localhost:8000/v1",
      qualityThreshold: 0.7, // Accept if confidence >= 70%
    },
    // Verifier model - OpenAI (cloud, expensive)
    {
      name: "gpt-4o",
      provider: "openai",
      cost: 0.00625, // $6.25 per 1M tokens (blended estimate)
      qualityThreshold: 0.95, // Very high quality
    },
  ];

  const agent = new CascadeAgent({ models });

  console.log("✅ Agent created with 2-tier cascade:");
  console.log("   Tier 1: Qwen/Qwen2.5-7B-Instruct (vLLM) - qualityThreshold=0.7");
  console.log("   Tier 2: gpt-4o (OpenAI) - qualityThreshold=0.95");
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
    console.log("✅ SUCCESS: vLLM cascade test passed");
    console.log("=".repeat(80));
  } catch (error) {
    console.error(`❌ ERROR: ${error}`);
    console.error();
    console.error(error);
  }
}

main().catch(console.error);
