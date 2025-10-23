/**
 * Streaming Example
 *
 * Demonstrates real-time streaming with CascadeFlow
 *
 * Run with:
 *   npx tsx examples/streaming.ts
 */

import {
  CascadeAgent,
  StreamEventType,
  isChunkEvent,
  isCompleteEvent,
  type StreamEvent,
} from '../src/index';

async function main() {
  // Create agent with cascade models
  const agent = new CascadeAgent({
    models: [
      // Draft model (cheap, fast)
      {
        name: 'gpt-4o-mini',
        provider: 'openai',
        cost: 0.00015,
        apiKey: process.env.OPENAI_API_KEY,
      },
      // Verifier model (expensive, high-quality)
      {
        name: 'gpt-4o',
        provider: 'openai',
        cost: 0.00625,
        apiKey: process.env.OPENAI_API_KEY,
      },
    ],
  });

  console.log('🚀 CascadeFlow Streaming Demo\n');
  console.log('Query: "Explain how cascading works in AI systems"\n');
  console.log('─'.repeat(60));
  console.log();

  // Track events
  let chunkCount = 0;
  let totalContent = '';
  const events: StreamEvent[] = [];

  try {
    // Stream the query
    for await (const event of agent.runStream(
      'Explain how cascading works in AI systems',
      {
        maxTokens: 200,
        temperature: 0.7,
      }
    )) {
      events.push(event);

      switch (event.type) {
        case StreamEventType.ROUTING:
          console.log(`📍 ROUTING: ${event.data.strategy} (complexity: ${event.data.complexity})`);
          console.log();
          break;

        case StreamEventType.CHUNK:
          // Print content as it streams
          process.stdout.write(event.content);
          totalContent += event.content;
          chunkCount++;
          break;

        case StreamEventType.DRAFT_DECISION:
          console.log('\n');
          console.log('─'.repeat(60));
          console.log(
            `⚖️  DRAFT DECISION: ${event.data.accepted ? '✅ ACCEPTED' : '❌ REJECTED'}`
          );
          console.log(`   Model: ${event.data.draft_model}`);
          console.log(`   Confidence: ${event.data.confidence?.toFixed(2)}`);
          console.log(`   Quality Score: ${event.data.score?.toFixed(2)}`);
          console.log(`   Reason: ${event.data.reason}`);
          console.log('─'.repeat(60));
          console.log();
          break;

        case StreamEventType.SWITCH:
          console.log(`🔄 SWITCH: ${event.content}`);
          console.log(`   From: ${event.data.from_model} → To: ${event.data.to_model}`);
          console.log(`   Reason: ${event.data.reason}`);
          console.log();
          break;

        case StreamEventType.COMPLETE:
          console.log('\n');
          console.log('─'.repeat(60));
          console.log('✅ COMPLETE');

          const result = event.data.result;
          if (result) {
            console.log();
            console.log('📊 Results:');
            console.log(`   Model Used: ${result.modelUsed}`);
            console.log(`   Total Cost: $${result.totalCost.toFixed(6)}`);
            console.log(`   Latency: ${result.latencyMs}ms`);
            console.log(`   Cascaded: ${result.cascaded ? 'Yes' : 'No'}`);
            console.log(`   Draft Accepted: ${result.draftAccepted ? 'Yes' : 'No'}`);
            console.log(`   Savings: ${result.savingsPercentage?.toFixed(1)}%`);
            console.log();
            console.log('💰 Cost Breakdown:');
            console.log(`   Draft Cost: $${result.draftCost?.toFixed(6)}`);
            console.log(`   Verifier Cost: $${result.verifierCost?.toFixed(6)}`);
            console.log(`   Cost Saved: $${result.costSaved?.toFixed(6)}`);
            console.log();
            console.log('⏱️  Timing Breakdown:');
            console.log(`   Draft Latency: ${result.draftLatencyMs}ms`);
            console.log(`   Verifier Latency: ${result.verifierLatencyMs}ms`);
          }
          console.log('─'.repeat(60));
          break;

        case StreamEventType.ERROR:
          console.error('\n❌ ERROR:', event.content);
          console.error('   Details:', event.data.error);
          break;
      }
    }

    // Summary
    console.log();
    console.log('📈 Streaming Summary:');
    console.log(`   Total Chunks: ${chunkCount}`);
    console.log(`   Total Events: ${events.length}`);
    console.log(`   Content Length: ${totalContent.length} chars`);
    console.log();
    console.log('Event Types:');
    const eventTypes = events.reduce((acc: Record<string, number>, e) => {
      acc[e.type] = (acc[e.type] || 0) + 1;
      return acc;
    }, {});
    Object.entries(eventTypes).forEach(([type, count]) => {
      console.log(`   ${type}: ${count}`);
    });
  } catch (error) {
    console.error('\n❌ Streaming failed:', error);
    process.exit(1);
  }
}

// Helper to demonstrate event filtering
async function demoEventFiltering() {
  const agent = new CascadeAgent({
    models: [
      { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
      { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
    ],
  });

  console.log('\n\n🎯 Demo: Event Filtering (chunks only)');
  console.log('─'.repeat(60));
  console.log();

  // Only print chunks, ignore other events
  for await (const event of agent.runStream('What is TypeScript?', {
    maxTokens: 100,
  })) {
    if (isChunkEvent(event)) {
      process.stdout.write(event.content);
    } else if (isCompleteEvent(event)) {
      console.log('\n\n✅ Done!');
    }
  }
}

// Helper to demonstrate helper functions
async function demoHelperFunctions() {
  const { collectStream, collectResult } = await import('../src/streaming');

  const agent = new CascadeAgent({
    models: [{ name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 }],
  });

  console.log('\n\n🛠️  Demo: Helper Functions');
  console.log('─'.repeat(60));
  console.log();

  const stream = agent.runStream('Count to 10', { maxTokens: 50 });

  // Collect all content from stream
  console.log('Using collectStream():');
  const content = await collectStream(stream);
  console.log('Collected:', content);

  // Or collect final result
  const stream2 = agent.runStream('Count to 5', { maxTokens: 30 });
  console.log('\nUsing collectResult():');
  const result = await collectResult(stream2);
  console.log('Result:', result);
}

// Run all demos
(async () => {
  try {
    await main();
    await demoEventFiltering();
    await demoHelperFunctions();
  } catch (error) {
    console.error('Demo failed:', error);
    process.exit(1);
  }
})();
