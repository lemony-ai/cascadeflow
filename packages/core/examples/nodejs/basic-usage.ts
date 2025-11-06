/**
 * cascadeflow - Basic Usage Example (TypeScript)
 *
 * The simplest way to get started with cascadeflow. This example demonstrates:
 * - Setting up a two-tier cascade (cheap → expensive)
 * - Processing queries with automatic quality-based routing
 * - Cost tracking and savings calculation
 * - Different complexity levels (simple → complex queries)
 *
 * Requirements:
 *     - @cascadeflow/core
 *     - OpenAI API key
 *
 * Setup:
 *     npm install @cascadeflow/core
 *     export OPENAI_API_KEY="your-key-here"
 *     npx tsx basic-usage.ts
 *
 * What You'll Learn:
 *     1. How to configure a basic cascade
 *     2. How cascadeflow automatically routes queries
 *     3. How to track costs and savings
 *     4. How different query complexities are handled
 *
 * Expected Output:
 *     - Simple queries: GPT-4o-mini draft accepted, GPT-4o skipped
 *     - Complex queries: Direct to GPT-4o OR draft rejected and escalated
 *     - Token-based cost comparison showing realistic 40-60% savings
 *
 * Note on Costs:
 *     Costs are calculated using actual token-based pricing from OpenAI:
 *     - GPT-4o-mini: ~$0.000375 per 1K tokens (blended input/output)
 *     - GPT-4o: ~$0.0025 per 1K tokens (blended input/output)
 *
 *     Savings depend on your query mix and response lengths.
 *
 * Note on Latency:
 *     95% of latency comes from provider API calls, NOT from cascadeflow!
 *     - Provider API: 95% (waiting for OpenAI/Anthropic/etc to respond)
 *     - cascadeflow overhead: 5% (routing, quality checks, etc.)
 *
 *     To reduce latency:
 *     1. Choose faster providers (Groq is 5-10x faster than OpenAI)
 *     2. Use streaming for perceived speed improvement
 *     3. Don't worry about cascade overhead (it's minimal)
 *
 * Documentation:
 *     For complete setup instructions and detailed explanations, see:
 *     docs/guides/quickstart.md
 */

import { CascadeAgent, type ModelConfig } from '@cascadeflow/core';

interface TestQuery {
  query: string;
  expected: string;
  reason: string;
}

interface Stats {
  'gpt-4o-mini': { count: number; cost: number };
  'gpt-4o': { count: number; cost: number };
  total_cost: number;
  draft_accepted: number;
  draft_rejected: number;
  direct_routing: number;
}

async function main() {
  console.log('='.repeat(80));
  console.log('🌊 CASCADEFLOW - BASIC USAGE EXAMPLE');
  console.log('='.repeat(80));
  console.log();
  console.log('This example shows how cascadeflow automatically routes queries');
  console.log('between a cheap model (GPT-4o-mini) and expensive model (GPT-4o).');
  console.log();
  console.log('💡 Key Concept: cascadeflow uses TOKEN-BASED pricing, not flat rates.');
  console.log('   This means costs depend on how long your queries and responses are.');
  console.log();

  // ========================================================================
  // STEP 1: Configure Your Cascade
  // ========================================================================

  console.log('📋 Step 1: Configuring cascade with two models...');
  console.log();

  const models: ModelConfig[] = [
    // Cheap model - tries first
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.000375, // $0.375 per 1M tokens (blended estimate)
    },
    // Expensive model - only if needed
    {
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.00625, // $6.25 per 1M tokens (blended estimate)
    },
  ];

  const agent = new CascadeAgent({
    models,
    quality: {
      threshold: 0.40,  // CASCADE-OPTIMIZED: Much lower than production (0.7)
      requireMinimumTokens: 5,  // Relaxed from 10 for short answers
    },
  });

  console.log('   ✅ Tier 1: gpt-4o-mini (~$0.375/1M tokens) - Tries first');
  console.log('   ✅ Tier 2: gpt-4o (~$6.25/1M tokens) - Escalates if needed');
  console.log();

  // ========================================================================
  // STEP 2: Test with Different Query Types
  // ========================================================================

  console.log('📝 Step 2: Testing with various query types...\n');

  // Test queries ranging from simple to complex
  const testQueries: TestQuery[] = [
    // SIMPLE queries - should stay on GPT-4o-mini
    {
      query: 'What color is the sky?',
      expected: 'gpt-4o-mini',
      reason: 'Simple factual question - cheap model handles easily',
    },
    {
      query: "What's the capital of France?",
      expected: 'gpt-4o-mini',
      reason: 'Simple factual - cheap model knows this',
    },
    {
      query: "Translate 'hello' to Spanish",
      expected: 'gpt-4o-mini',
      reason: 'Simple translation - cheap model sufficient',
    },
    // MODERATE queries - might escalate
    {
      query: 'Explain the difference between lists and tuples in Python',
      expected: 'gpt-4o-mini',
      reason: 'Moderate complexity - cheap model likely handles it',
    },
    {
      query: 'Write a function to reverse a string in Python',
      expected: 'gpt-4o-mini',
      reason: 'Standard coding task - cheap model can do it',
    },
    // COMPLEX queries - likely escalate to GPT-4o
    {
      query:
        'Explain quantum entanglement and its implications for quantum computing in detail',
      expected: 'gpt-4o',
      reason: 'Complex scientific topic - needs better model',
    },
    {
      query:
        'Design a microservices architecture for a large-scale e-commerce platform with high availability',
      expected: 'gpt-4o',
      reason: 'Complex architecture design - benefits from GPT-4o',
    },
    {
      query:
        'Analyze the philosophical implications of consciousness and free will in the context of determinism',
      expected: 'gpt-4o',
      reason: 'Deep philosophical analysis - needs sophisticated reasoning',
    },
  ];

  // Track statistics
  const stats: Stats = {
    'gpt-4o-mini': { count: 0, cost: 0.0 },
    'gpt-4o': { count: 0, cost: 0.0 },
    total_cost: 0.0,
    draft_accepted: 0,
    draft_rejected: 0,
    direct_routing: 0,
  };

  // Track savings from core calculations
  let totalCostSaved = 0;
  let totalBigonlyCost = 0;

  // Process each query
  for (let i = 0; i < testQueries.length; i++) {
    const test = testQueries[i];
    console.log('─'.repeat(80));
    console.log(`Query ${i + 1}/${testQueries.length}`);
    console.log('─'.repeat(80));
    console.log(`❓ Question: ${test.query}`);
    console.log(`🎯 Expected: ${test.expected}`);
    console.log(`💡 Why: ${test.reason}`);
    console.log();

    // Run the query through cascade
    const result = await agent.run(test.query, { maxTokens: 150 });

    // Determine which model was used
    const modelUsed = result.modelUsed.toLowerCase().includes('4o-mini')
      ? 'gpt-4o-mini'
      : 'gpt-4o';

    // Update statistics
    stats[modelUsed].count += 1;
    stats[modelUsed].cost += result.totalCost;
    stats.total_cost += result.totalCost;

    // Track cascade status
    if (result.routingStrategy === 'direct') {
      stats.direct_routing += 1;
    } else if (result.draftAccepted) {
      stats.draft_accepted += 1;
    } else if (result.cascaded) {
      stats.draft_rejected += 1;
    }

    // Accumulate savings from core calculations
    if (result.costSaved !== undefined) {
      totalCostSaved += result.costSaved;
    }
    // Calculate bigonly cost (actual cost + savings)
    const bigonly = result.totalCost + (result.costSaved || 0);
    totalBigonlyCost += bigonly;

    // Show result
    const tier = modelUsed === 'gpt-4o-mini' ? 'Tier 1 (Cheap)' : 'Tier 2 (Expensive)';
    const icon = modelUsed === 'gpt-4o-mini' ? '💚' : '💛';

    console.log('✅ Result:');

    // Show actual model(s) used with clear status
    if (result.draftAccepted) {
      // Only draft was used
      console.log(`   ${icon} Model Used: gpt-4o-mini only (${tier})`);
    } else if (result.cascaded && !result.draftAccepted) {
      // Both models were used
      console.log('   💚💛 Models Used: gpt-4o-mini + gpt-4o (Both Tiers)');
    } else {
      // Direct routing
      console.log(`   ${icon} Model Used: ${result.modelUsed} (${tier})`);
    }

    console.log(`   💰 Cost: $${result.totalCost.toFixed(6)}`);

    // Latency breakdown
    const totalLatency = result.latencyMs || 0;
    const draftLatency = result.draftLatencyMs || 0;
    const verifierLatency = result.verifierLatencyMs || 0;

    // Calculate provider vs cascade latency
    const providerLatency = draftLatency + verifierLatency;
    const cascadeLatency = Math.max(0, totalLatency - providerLatency);

    if (providerLatency > 0) {
      const providerPct = totalLatency > 0 ? (providerLatency / totalLatency) * 100 : 0;
      const cascadePct = totalLatency > 0 ? (cascadeLatency / totalLatency) * 100 : 0;
      console.log('   ⚡ Latency Breakdown:');
      console.log(`      Total: ${totalLatency.toFixed(0)}ms`);
      console.log(
        `      ├─ Provider API: ${providerLatency.toFixed(0)}ms (${providerPct.toFixed(1)}%)`
      );
      console.log(
        `      └─ cascadeflow: ${cascadeLatency.toFixed(0)}ms (${cascadePct.toFixed(1)}%)`
      );
    } else {
      console.log(`   ⚡ Latency: ${totalLatency.toFixed(0)}ms`);
    }

    console.log(`   📊 Complexity: ${result.complexity}`);

    // Show cascade status more clearly
    // TypeScript now has PreRouter logic like Python:
    // - routingStrategy='direct' means query was routed directly to expensive model (HARD/EXPERT complexity)
    // - draftAccepted=true means draft passed quality check (cascade used, verifier skipped)
    // - cascaded=true with draftAccepted=false means both models were used (draft rejected, escalated)
    if (result.routingStrategy === 'direct') {
      console.log('   🎯 Direct Route: Query sent directly to GPT-4o (no cascade)');
      console.log(`   💡 Reason: ${result.complexity} complexity detected by PreRouter`);
    } else if (result.draftAccepted) {
      console.log('   ✅ Draft Accepted: GPT-4o-mini response passed quality check');
      console.log('   💡 Verifier Skipped: GPT-4o was not called (cost saved!)');
    } else if (result.cascaded) {
      console.log('   ❌ Draft Rejected: Quality check failed, escalated to GPT-4o');
      console.log('   💸 Both Models Used: Paid for GPT-4o-mini + GPT-4o');
    }

    // Show first part of response
    const responsePreview = result.content.substring(0, 100).replace(/\n/g, ' ');
    console.log(`   📝 Response: ${responsePreview}...`);
    console.log();
  }

  // ========================================================================
  // STEP 3: Show Cost Analysis
  // ========================================================================

  console.log('='.repeat(80));
  console.log('💰 COST ANALYSIS');
  console.log('='.repeat(80));
  console.log();

  // Calculate statistics
  const totalQueries = testQueries.length;
  const gpt4miniCount = stats['gpt-4o-mini'].count;
  const gpt4oCount = stats['gpt-4o'].count;

  const gpt4miniPct = (gpt4miniCount / totalQueries) * 100;
  const gpt4oPct = (gpt4oCount / totalQueries) * 100;

  console.log('📊 Query Distribution:');
  console.log(
    `   GPT-4o-mini: ${gpt4miniCount}/${totalQueries} (${gpt4miniPct.toFixed(0)}%)`
  );
  console.log(`   GPT-4o:      ${gpt4oCount}/${totalQueries} (${gpt4oPct.toFixed(0)}%)`);
  console.log();

  console.log('🔄 Cascade Behavior:');
  console.log(`   Draft Accepted:  ${stats.draft_accepted} (verifier skipped)`);
  console.log(`   Draft Rejected:  ${stats.draft_rejected} (both models used)`);
  console.log(`   Direct Routing:  ${stats.direct_routing} (no cascade)`);
  console.log();

  console.log('💵 Cost Breakdown:');
  console.log(`   GPT-4o-mini: $${stats['gpt-4o-mini'].cost.toFixed(6)}`);
  console.log(`   GPT-4o:      $${stats['gpt-4o'].cost.toFixed(6)}`);
  console.log(`   Total Cost:  $${stats.total_cost.toFixed(6)}`);
  console.log();

  // Calculate savings using core's calculations (actual token-based pricing)
  const savingsPct = totalBigonlyCost > 0 ? (totalCostSaved / totalBigonlyCost) * 100 : 0.0;

  console.log('💎 Savings Compared to All-GPT-4o (Token-Based):');
  console.log(`   All-GPT-4o Cost:     $${totalBigonlyCost.toFixed(6)}`);
  console.log(`   cascadeflow Cost:    $${stats.total_cost.toFixed(6)}`);
  console.log(`   💰 SAVINGS:          $${totalCostSaved.toFixed(6)} (${savingsPct.toFixed(1)}%)`);
  console.log();
  console.log(
    '   ℹ️  Note: Savings calculated from actual API token usage and split pricing'
  );
  console.log(
    '       Your savings will vary based on query complexity and response length.'
  );
  console.log();

  // Extrapolate to realistic scale
  console.log('📈 Extrapolated to 10,000 Queries/Month:');
  if (totalBigonlyCost > 0) {
    const scaleFactor = 10_000 / totalQueries;
    const monthlyCascade = stats.total_cost * scaleFactor;
    const monthlyGpt4o = totalBigonlyCost * scaleFactor;
    const monthlySavings = monthlyGpt4o - monthlyCascade;

    console.log(
      `   All-GPT-4o:     $${monthlyGpt4o.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}/month`
    );
    console.log(
      `   cascadeflow:    $${monthlyCascade.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}/month`
    );
    console.log(
      `   💵 SAVE:        $${monthlySavings.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}/month`
    );
    console.log();
  }

  // ========================================================================
  // STEP 4: Key Takeaways
  // ========================================================================

  console.log('='.repeat(80));
  console.log('🎯 KEY TAKEAWAYS');
  console.log('='.repeat(80));
  console.log();
  console.log('✅ What You Learned:');
  console.log('   1. cascadeflow automatically routes queries by complexity');
  console.log('   2. Simple queries use cheap models (GPT-4o-mini)');
  console.log('   3. Complex queries escalate to expensive models (GPT-4o)');
  console.log('   4. When draft is accepted, verifier is SKIPPED (saves cost!)');
  console.log('   5. Token-based pricing means actual costs depend on query/response length');
  console.log(`   6. You achieved ${savingsPct.toFixed(1)}% savings on this query mix`);
  console.log();

  console.log('🚀 Next Steps:');
  console.log('   • Try with your own queries');
  console.log('   • Adjust quality threshold to tune cascade behavior');
  console.log('   • Add more models (Ollama for local, Groq for free)');
  console.log('   • Monitor your own query patterns and optimize');
  console.log('   • Deploy to production');
  console.log();

  console.log('📚 Resources:');
  console.log('   • Full Guide: docs/guides/quickstart.md');
  console.log('   • API Reference: docs/api/');
  console.log('   • GitHub: https://github.com/lemony-ai/cascadeflow');
  console.log();

  console.log('='.repeat(80));
}

main().catch(console.error);
