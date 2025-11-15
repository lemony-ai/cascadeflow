/**
 * Example: Batch Processing
 *
 * Demonstrates batch processing capabilities:
 * - Sequential processing with error handling
 * - Progress tracking and reporting
 * - Batch statistics and cost analysis
 * - Different processing strategies
 *
 * Run: npx tsx examples/nodejs/batch-processing.ts
 */

import { CascadeAgent, BatchStrategy } from '@cascadeflow/core';

async function main() {
  console.log('📦 Batch Processing Example\n');

  const models = [
    {
      name: 'gpt-4o-mini',
      provider: 'openai' as const,
      cost: 0.00015,
    },
    {
      name: 'gpt-4o',
      provider: 'openai' as const,
      cost: 0.00625,
    },
  ];

  const agent = new CascadeAgent({
    models,
    quality: {
      minConfidence: 0.70,
    },
  });

  // ============================================================================
  // 1. Sequential Batch Processing
  // ============================================================================
  console.log('1️⃣  Sequential Batch Processing\n');

  const queries = [
    'What is TypeScript?',
    'Explain async/await in JavaScript.',
    'What are design patterns?',
    'How does garbage collection work?',
    'What is functional programming?',
  ];

  console.log(`Processing ${queries.length} queries sequentially...\n`);

  const startTime = Date.now();
  const batchResult = await agent.runBatch(queries, {
    strategy: BatchStrategy.SEQUENTIAL,
    stopOnError: false,
  });
  const duration = Date.now() - startTime;

  console.log(`\n✅ Batch complete in ${(duration / 1000).toFixed(2)}s\n`);

  // ============================================================================
  // 2. Analyze Results
  // ============================================================================
  console.log('2️⃣  Batch Results Analysis\n');

  console.log(`📊 Summary:`);
  console.log(`   Total queries: ${batchResult.results.length}`);
  console.log(`   Successful: ${batchResult.successCount}`);
  console.log(`   Failed: ${batchResult.failureCount}`);
  console.log(`   Success rate: ${((batchResult.successCount / batchResult.results.length) * 100).toFixed(1)}%`);

  // Calculate costs
  const totalCost = batchResult.results
    .filter((r) => r !== null)
    .reduce((sum, r) => sum + (r?.totalCost || 0), 0);

  const avgCost = totalCost / batchResult.successCount;
  const avgLatency =
    batchResult.results
      .filter((r) => r !== null)
      .reduce((sum, r) => sum + (r?.latencyMs || 0), 0) / batchResult.successCount;

  console.log(`\n💰 Cost Analysis:`);
  console.log(`   Total cost: $${totalCost.toFixed(6)}`);
  console.log(`   Average cost per query: $${avgCost.toFixed(6)}`);
  console.log(`   Average latency: ${avgLatency.toFixed(0)}ms`);

  // Draft acceptance rate
  const draftAccepted = batchResult.results.filter(
    (r) => r !== null && r.draftAccepted
  ).length;

  console.log(`\n🎯 Cascade Performance:`);
  console.log(`   Draft accepted: ${draftAccepted}/${batchResult.successCount}`);
  console.log(
    `   Acceptance rate: ${((draftAccepted / batchResult.successCount) * 100).toFixed(1)}%`
  );

  // ============================================================================
  // 3. Individual Results
  // ============================================================================
  console.log('\n3️⃣  Individual Results\n');

  batchResult.results.forEach((result, index) => {
    if (result !== null) {
      console.log(`   ✅ Query ${index + 1}: ${queries[index].substring(0, 30)}...`);
      console.log(`      Model: ${result.modelUsed}`);
      console.log(`      Cost: $${result.totalCost.toFixed(6)}`);
      console.log(`      Draft: ${result.draftAccepted ? 'Accepted' : 'Rejected'}`);
    } else {
      console.log(`   ❌ Query ${index + 1}: ${queries[index].substring(0, 30)}...`);
      console.log(`      Error: Failed`);
    }
  });

  // ============================================================================
  // 4. Batch with Custom Configuration
  // ============================================================================
  console.log('\n4️⃣  Batch with Custom Configuration\n');

  const shortQueries = [
    'Define API',
    'What is REST?',
    'Explain HTTP',
  ];

  console.log('Processing with lenient quality thresholds...\n');

  const laxAgent = new CascadeAgent({
    models,
    quality: {
      minConfidence: 0.50, // More lenient
      requireMinimumTokens: 3,
    },
  });

  const laxResult = await laxAgent.runBatch(shortQueries, {
    strategy: BatchStrategy.SEQUENTIAL,
    stopOnError: false,
  });

  console.log(`✅ Completed ${laxResult.successCount}/${shortQueries.length} queries`);
  console.log(`   Draft acceptance rate: ${((laxResult.results.filter((r) => r !== null && r.draftAccepted).length / laxResult.successCount) * 100).toFixed(1)}%`);

  // ============================================================================
  // 5. Error Handling
  // ============================================================================
  console.log('\n5️⃣  Error Handling\n');

  // Mix of valid and potentially problematic queries
  const mixedQueries = [
    'What is Python?',
    '', // Empty query (might fail)
    'Explain databases.',
  ];

  console.log('Processing batch with error handling...\n');

  const errorTestResult = await agent.runBatch(mixedQueries, {
    strategy: BatchStrategy.SEQUENTIAL,
    stopOnError: false, // Continue even if some fail
  });

  errorTestResult.results.forEach((result, index) => {
    if (result !== null) {
      console.log(`   ✅ Query ${index + 1}: Success`);
    } else {
      console.log(`   ❌ Query ${index + 1}: Failed`);
    }
  });

  console.log(`\n   Success rate: ${((errorTestResult.successCount / mixedQueries.length) * 100).toFixed(1)}%`);

  console.log('\n✅ Example complete!');
}

main().catch(console.error);
