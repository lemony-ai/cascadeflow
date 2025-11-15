/**
 * Example: Enhanced Streaming
 *
 * Demonstrates enhanced streaming capabilities:
 * - streamEvents() with event-driven processing
 * - Real-time progress monitoring
 * - Collecting results from streams
 * - Different event types and handling
 *
 * Run: npx tsx examples/nodejs/enhanced-streaming.ts
 */

import {
  CascadeAgent,
  StreamEventType,
  collectResult,
  type StreamEvent,
} from '@cascadeflow/core';

async function main() {
  console.log('🌊 Enhanced Streaming Example\n');

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
  });

  // ============================================================================
  // 1. Basic Streaming with Event Handling
  // ============================================================================
  console.log('1️⃣  Basic Streaming with Event Handling\n');

  const stream = agent.streamEvents('What is TypeScript?', {
    forceDirect: true, // Direct to best model for faster streaming
  });

  let chunkCount = 0;
  const chunks: string[] = [];

  for await (const event of stream) {
    switch (event.type) {
      case StreamEventType.ROUTING:
        console.log('📡 Stream started');
        console.log(`   Model: ${event.data.model}`);
        break;

      case StreamEventType.CHUNK:
        if (event.content) {
          chunkCount++;
          chunks.push(event.content);
          process.stdout.write(event.content);
        }
        break;

      case StreamEventType.COMPLETE:
        console.log(`\n\n✅ Stream complete`);
        console.log(`   Chunks received: ${chunkCount}`);
        console.log(`   Total length: ${chunks.join('').length} chars`);
        console.log(`   Cost: $${event.data.totalCost?.toFixed(6)}`);
        console.log(`   Time: ${event.data.latencyMs}ms`);
        break;

      case StreamEventType.ERROR:
        console.log(`\n❌ Stream error: ${event.data.error}`);
        break;
    }
  }

  // ============================================================================
  // 2. Streaming with Cascade
  // ============================================================================
  console.log('\n\n2️⃣  Streaming with Cascade\n');

  console.log('Attempting cascade stream (draft then verifier if needed)...\n');

  const cascadeStream = agent.streamEvents(
    'Explain async/await in simple terms.'
  );

  let currentModel = '';
  for await (const event of cascadeStream) {
    if (event.type === StreamEventType.ROUTING) {
      currentModel = event.data.model || 'unknown';
      console.log(`\n📡 Streaming from: ${currentModel}`);
    } else if (event.type === StreamEventType.CHUNK && event.content) {
      process.stdout.write(event.content);
    } else if (event.type === StreamEventType.COMPLETE) {
      console.log(`\n\n✅ Complete with ${currentModel}`);
      console.log(`   Draft accepted: ${event.data.draftAccepted || false}`);
    }
  }

  // ============================================================================
  // 3. Collecting Results from Stream
  // ============================================================================
  console.log('\n\n3️⃣  Collecting Results from Stream\n');

  console.log('Streaming and collecting result...');

  const collectStream = agent.streamEvents('What are design patterns?', {
    forceDirect: true,
  });

  const result = await collectResult(collectStream);

  console.log('\n✅ Collected result:');
  console.log(`   Content length: ${result.content.length} chars`);
  console.log(`   Model: ${result.modelUsed}`);
  console.log(`   Cost: $${result.totalCost.toFixed(6)}`);
  console.log(`   Timing: ${result.latencyMs}ms`);

  // ============================================================================
  // 4. Progress Monitoring
  // ============================================================================
  console.log('\n4️⃣  Progress Monitoring\n');

  console.log('Streaming with real-time progress...\n');

  const progressStream = agent.streamEvents(
    'Explain the benefits of TypeScript in detail.',
    { forceDirect: true }
  );

  let totalChars = 0;
  let startTime = Date.now();

  for await (const event of progressStream) {
    if (event.type === StreamEventType.CHUNK && event.content) {
      totalChars += event.content.length;
      const elapsed = Date.now() - startTime;
      const charsPerSec = totalChars / (elapsed / 1000);
      process.stdout.write(
        `\r📊 Progress: ${totalChars} chars | ${charsPerSec.toFixed(0)} chars/sec`
      );
    } else if (event.type === StreamEventType.COMPLETE) {
      const totalTime = Date.now() - startTime;
      console.log(`\n\n✅ Complete in ${totalTime}ms`);
      console.log(`   Average: ${(totalChars / (totalTime / 1000)).toFixed(0)} chars/sec`);
    }
  }

  // ============================================================================
  // 5. Error Handling in Streams
  // ============================================================================
  console.log('\n5️⃣  Error Handling in Streams\n');

  console.log('Testing error handling...');

  try {
    const errorStream = agent.streamEvents('', { // Empty query
      forceDirect: true,
    });

    for await (const event of errorStream) {
      if (event.type === StreamEventType.ERROR) {
        console.log(`❌ Caught error: ${event.data.error}`);
      }
    }
  } catch (error) {
    console.log(`❌ Exception: ${error instanceof Error ? error.message : error}`);
  }

  // ============================================================================
  // 6. Comparison: Streaming vs Non-Streaming
  // ============================================================================
  console.log('\n6️⃣  Comparison: Streaming vs Non-Streaming\n');

  console.log('Benefits of Streaming:');
  console.log('   ✅ Real-time feedback to users');
  console.log('   ✅ Lower perceived latency');
  console.log('   ✅ Progressive content display');
  console.log('   ✅ Better user experience for long responses');

  console.log('\nWhen to use Streaming:');
  console.log('   - Interactive chat applications');
  console.log('   - Real-time content generation');
  console.log('   - Long-form content (articles, essays)');
  console.log('   - User-facing applications');

  console.log('\nWhen to use Non-Streaming:');
  console.log('   - Batch processing');
  console.log('   - API integrations');
  console.log('   - Background tasks');
  console.log('   - When full response needed before processing');

  console.log('\n✅ Example complete!');
}

main().catch(console.error);
