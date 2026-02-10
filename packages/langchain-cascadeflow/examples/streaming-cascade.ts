/**
 * Streaming Cascade Example
 *
 * Demonstrates real-time streaming with CascadeFlow:
 * 1. Stream drafter optimistically (user sees output immediately)
 * 2. Check quality after drafter completes
 * 3. If quality insufficient, stream verifier output after drafter output (optimistic streaming)
 */

import { ChatOpenAI } from '@langchain/openai';
import { withCascade } from '../src/index.js';

async function main() {
  console.log('🌊 CascadeFlow Streaming Example\n');

  // Configure cascade with drafter and verifier
  const cascade = withCascade({
    drafter: new ChatOpenAI({
      model: 'gpt-4o-mini',
      temperature: 0.7,
    }),
    verifier: new ChatOpenAI({
      model: 'gpt-4o',
      temperature: 0.7,
    }),
    qualityThreshold: 0.7,
  }).bind({ metadata: { cascadeflow_emit_switch_message: true } });

  // Example 1: Simple query (likely accepted by drafter)
  console.log('Example 1: Simple Query (may cascade)\n');
  console.log('Q: What is 2+2?\n');
  console.log('A: ');

  const stream1 = await cascade.stream('What is 2+2?');

  for await (const chunk of stream1) {
    const content = typeof chunk.content === 'string' ? chunk.content : '';
    process.stdout.write(content);
  }

  console.log('\n\n---\n');

  // Example 2: Complex query (likely escalated to verifier)
  console.log('Example 2: Complex Query (may escalate)\n');
  console.log('Q: Explain quantum entanglement and its implications for quantum computing\n');
  console.log('A: ');

  const stream2 = await cascade.stream(
    'Explain quantum entanglement and its implications for quantum computing'
  );

  for await (const chunk of stream2) {
    const content = typeof chunk.content === 'string' ? chunk.content : '';
    process.stdout.write(content);
  }

  console.log('\n\n---\n');

  // Example 3: Low quality query (forces cascade)
  console.log('Example 3: Ambiguous Query (likely escalates)\n');
  console.log('Q: Tell me about it\n');
  console.log('A: ');

  const stream3 = await cascade.stream('Tell me about it');

  for await (const chunk of stream3) {
    const content = typeof chunk.content === 'string' ? chunk.content : '';
    process.stdout.write(content);
  }

  console.log('\n\n---\n');

  // Show final cascade statistics
  const stats = cascade.getLastCascadeResult();
  if (stats) {
    console.log('\n📊 Cascade Statistics:');
    console.log(`   Model Used: ${stats.modelUsed}`);
    console.log(`   Drafter Quality: ${stats.drafterQuality.toFixed(2)}`);
    console.log(`   Accepted: ${stats.accepted}`);
    console.log(`   Latency: ${stats.latencyMs}ms`);
  }
}

main().catch(console.error);
