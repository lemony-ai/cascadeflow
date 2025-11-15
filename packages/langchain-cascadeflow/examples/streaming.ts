/**
 * Streaming Example
 *
 * Demonstrates real-time streaming with intelligent pre-routing based on
 * query complexity. The cascade analyzes queries before streaming and routes
 * to the appropriate model.
 */

import { ChatOpenAI } from '@langchain/openai';
import { withCascade } from '../src/index.js';

async function main() {
  console.log('=== CascadeFlow Streaming Demo ===\n');

  const drafter = new ChatOpenAI({ model: 'gpt-4o-mini', temperature: 0.7 });
  const verifier = new ChatOpenAI({ model: 'gpt-4o', temperature: 0.7 });

  const cascade = withCascade({
    drafter,
    verifier,
    qualityThreshold: 0.7,
  });

  // Example 1: Simple query (routed to drafter)
  console.log('--- Example 1: Simple Query (Drafter) ---');
  console.log('Query: "What is TypeScript?"\n');

  const stream1 = await cascade.stream('What is TypeScript?');

  process.stdout.write('Response: ');
  for await (const chunk of stream1) {
    process.stdout.write(chunk.content);
  }

  const metadata1 = cascade.getLastCascadeResult();
  console.log(`\n\nModel used: ${metadata1?.modelUsed}`);
  console.log(`Latency: ${metadata1?.latencyMs}ms`);
  console.log(`Pre-routed: ${metadata1?.preRouted}`);
  console.log('\n');

  // Example 2: Complex query (routed to verifier)
  console.log('--- Example 2: Complex Query (Verifier) ---');
  console.log('Query: "Analyze the architectural differences between microservices and monolithic applications in detail"\n');

  const stream2 = await cascade.stream(
    'Analyze the architectural differences between microservices and monolithic applications in detail'
  );

  process.stdout.write('Response: ');
  for await (const chunk of stream2) {
    process.stdout.write(chunk.content);
  }

  const metadata2 = cascade.getLastCascadeResult();
  console.log(`\n\nModel used: ${metadata2?.modelUsed}`);
  console.log(`Latency: ${metadata2?.latencyMs}ms`);
  console.log(`Pre-routed: ${metadata2?.preRouted}`);
  console.log('\n');

  // Example 3: Query with code block (routed to verifier)
  console.log('--- Example 3: Code Analysis (Verifier) ---');
  console.log('Query: "How can I optimize this code?"\n');

  const codeQuery = `How can I optimize this code?

\`\`\`typescript
function processItems(items: any[]) {
  const result = [];
  for (let i = 0; i < items.length; i++) {
    if (items[i].active) {
      result.push(items[i]);
    }
  }
  return result;
}
\`\`\``;

  const stream3 = await cascade.stream(codeQuery);

  process.stdout.write('Response: ');
  for await (const chunk of stream3) {
    process.stdout.write(chunk.content);
  }

  const metadata3 = cascade.getLastCascadeResult();
  console.log(`\n\nModel used: ${metadata3?.modelUsed}`);
  console.log(`Latency: ${metadata3?.latencyMs}ms`);
  console.log(`Pre-routed: ${metadata3?.preRouted}`);
  console.log('\n');

  // Example 4: Streaming with callbacks
  console.log('--- Example 4: Streaming with Progress Callback ---');
  console.log('Query: "Explain async/await in JavaScript"\n');

  const stream4 = await cascade.stream('Explain async/await in JavaScript');

  let chunkCount = 0;
  process.stdout.write('Response: ');

  for await (const chunk of stream4) {
    chunkCount++;
    process.stdout.write(chunk.content);

    // Show progress every 10 chunks
    if (chunkCount % 10 === 0) {
      process.stderr.write(`[${chunkCount} chunks received] `);
    }
  }

  const metadata4 = cascade.getLastCascadeResult();
  console.log(`\n\nTotal chunks received: ${chunkCount}`);
  console.log(`Model used: ${metadata4?.modelUsed}`);
  console.log(`Latency: ${metadata4?.latencyMs}ms\n`);

  console.log('=== Streaming Demo Complete ===');
  console.log('\n💡 Streaming uses pre-routing to select the best model before streaming begins');
  console.log('💡 Simple queries → drafter (fast, cost-effective)');
  console.log('💡 Complex queries → verifier (accurate, comprehensive)');
}

main().catch(console.error);
