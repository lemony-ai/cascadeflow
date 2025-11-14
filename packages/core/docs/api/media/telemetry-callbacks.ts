/**
 * Example: Telemetry and Callbacks
 *
 * Demonstrates how to monitor and track cascade operations using:
 * - CallbackManager for event-driven monitoring
 * - Router statistics tracking
 * - Complexity detection hooks
 * - Quality validation monitoring
 *
 * Run: npx tsx examples/nodejs/telemetry-callbacks.ts
 */

import {
  CascadeAgent,
  CallbackManager,
  CallbackEvent,
  type CallbackData,
} from '@cascadeflow/core';

async function main() {
  console.log('📊 Telemetry & Callbacks Example\n');

  // ============================================================================
  // 1. Setup Callback Manager
  // ============================================================================
  console.log('1️⃣  Setting up callback manager...\n');

  const callbackManager = new CallbackManager(true); // verbose=true

  // Track query lifecycle
  callbackManager.register(CallbackEvent.QUERY_START, (data: CallbackData) => {
    console.log(`🚀 Query started: "${data.query}"`);
    console.log(`   Timestamp: ${new Date(data.timestamp).toISOString()}`);
  });

  callbackManager.register(CallbackEvent.QUERY_COMPLETE, (data: CallbackData) => {
    console.log(`✅ Query completed: "${data.query}"`);
    console.log(`   Duration: ${data.data.duration}ms`);
    console.log(`   Model used: ${data.data.modelUsed}`);
    console.log(`   Cost: $${data.data.cost?.toFixed(6)}`);
  });

  // Track complexity detection
  callbackManager.register(CallbackEvent.COMPLEXITY_DETECTED, (data: CallbackData) => {
    console.log(`🎯 Complexity detected: ${data.data.complexity}`);
    console.log(`   Confidence: ${data.data.confidence?.toFixed(2)}`);
  });

  // Track cascade decisions
  callbackManager.register(CallbackEvent.CASCADE_DECISION, (data: CallbackData) => {
    console.log(`🔄 Cascade decision: ${data.data.shouldCascade ? 'CASCADE' : 'DIRECT'}`);
    console.log(`   Reason: ${data.data.reason}`);
  });

  // Note: QUALITY_CHECK, DRAFT_ACCEPTED, DRAFT_REJECTED events may not exist in the current implementation
  // These would be part of CASCADE_DECISION or MODEL_CALL_COMPLETE events

  // ============================================================================
  // 2. Create Agent with Callbacks
  // ============================================================================
  const models = [
    {
      name: 'gpt-4o-mini',
      provider: 'openai' as const,
      cost: 0.00015,
      supportsTools: true,
    },
    {
      name: 'gpt-4o',
      provider: 'openai' as const,
      cost: 0.00625,
      supportsTools: true,
    },
  ];

  // Create agent with callback manager integration
  const agent = new CascadeAgent({
    models,
    callbacks: callbackManager,
    quality: {
      minConfidence: 0.70,
      useProductionConfidence: true,
      provider: 'openai',
    },
  });

  console.log('\n2️⃣  Running queries with telemetry...\n');
  console.log('─'.repeat(60));

  // ============================================================================
  // 3. Execute Queries with Monitoring
  // ============================================================================

  // Query 1: Simple query
  console.log('\n📝 Query 1: Simple question\n');
  try {
    await agent.run('What is TypeScript?');
  } catch (error) {
    console.log(`Error: ${error instanceof Error ? error.message : error}`);
  }

  console.log('\n' + '─'.repeat(60));

  // Query 2: Complex query
  console.log('\n📝 Query 2: Complex question\n');
  try {
    await agent.run(
      'Explain the theoretical foundations of type systems in programming languages, including the lambda calculus and its relation to modern type inference algorithms.'
    );
  } catch (error) {
    console.log(`Error: ${error instanceof Error ? error.message : error}`);
  }

  console.log('\n' + '─'.repeat(60));

  // Query 3: Tool-based query
  console.log('\n📝 Query 3: Tool-based query\n');
  try {
    await agent.run('What is 25 * 47?');
  } catch (error) {
    console.log(`Error: ${error instanceof Error ? error.message : error}`);
  }

  // ============================================================================
  // 4. Print Statistics
  // ============================================================================
  console.log('\n' + '='.repeat(60));
  console.log('\n3️⃣  Telemetry Statistics\n');

  // Callback statistics
  const callbackStats = callbackManager.getStats();
  console.log('📊 Callback Statistics:');
  console.log(`   Total triggers: ${callbackStats.totalTriggers}`);
  console.log(`   Callback errors: ${callbackStats.callbackErrors}`);
  console.log(`   Registered events: ${callbackStats.registeredEvents.join(', ')}`);
  console.log('\n   Event breakdown:');
  Object.entries(callbackStats.byEvent).forEach(([event, count]) => {
    if (count > 0) {
      console.log(`   - ${event}: ${count}`);
    }
  });

  // Router statistics
  console.log('\n🔀 Router Statistics:');
  const routerStats = agent.getRouterStats();
  console.log('   PreRouter:', JSON.stringify(routerStats.preRouter, null, 2));
  console.log('   ToolRouter:', JSON.stringify(routerStats.toolRouter, null, 2));

  // ============================================================================
  // 5. Custom Event Handlers
  // ============================================================================
  console.log('\n4️⃣  Custom Event Handlers\n');

  // Example: Track costs across queries
  let totalCost = 0;
  let queryCount = 0;

  const costTracker = (data: CallbackData) => {
    if (data.data.cost) {
      totalCost += data.data.cost;
      queryCount++;
      console.log(`💰 Running total: $${totalCost.toFixed(6)} across ${queryCount} queries`);
      console.log(`   Average: $${(totalCost / queryCount).toFixed(6)} per query`);
    }
  };

  callbackManager.register(CallbackEvent.QUERY_COMPLETE, costTracker);

  console.log('\n📝 Running final query to update cost tracking...\n');
  try {
    await agent.run('Hello, how are you?');
  } catch (error) {
    console.log(`Error: ${error instanceof Error ? error.message : error}`);
  }

  // ============================================================================
  // 6. Print Final Summary
  // ============================================================================
  console.log('\n' + '='.repeat(60));
  console.log('\n📋 Final Summary\n');

  callbackManager.printStats();

  console.log('\n✅ Example complete!');
}

main().catch(console.error);
