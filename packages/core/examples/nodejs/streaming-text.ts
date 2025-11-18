/**
 * cascadeflow - Text Streaming Example (TypeScript)
 *
 * Real-time text streaming with cascade events.
 *
 * Setup:
 *   npm install @cascadeflow/core
 *   export OPENAI_API_KEY="sk-..."
 *
 * Run:
 *   npx tsx streaming-text.ts
 *
 * What You'll See:
 *   - Tokens appearing in real-time (like ChatGPT)
 *   - Draft decisions (accepted = cheap, rejected = expensive)
 *   - Cost and speed metrics after each response
 *
 * Documentation:
 *   📖 Streaming Guide: docs/guides/streaming.md#text-streaming
 *   📖 Quick Start: docs/guides/quickstart.md
 *   📚 Examples README: examples/README.md
 */

import { CascadeAgent, StreamEventType } from '@cascadeflow/core';

async function main() {
  // ═══════════════════════════════════════════════════════════════════════
  // STEP 1: Check API Key
  // ═══════════════════════════════════════════════════════════════════════
  // Verify the OpenAI API key is set before we start

  if (!process.env.OPENAI_API_KEY) {
    console.log("❌ Set OPENAI_API_KEY first: export OPENAI_API_KEY='sk-...'");
    return;
  }

  console.log('🌊 cascadeflow Text Streaming\n');

  // ═══════════════════════════════════════════════════════════════════════
  // STEP 2: Setup Agent with Cascade
  // ═══════════════════════════════════════════════════════════════════════
  // Create agent with 2 models:
  // - Tier 1 (gpt-4o-mini): Fast & cheap, tries first
  // - Tier 2 (gpt-4o): Slower & expensive, only if needed
  //
  // This is called "cascading" - start cheap, escalate if needed

  const agent = new CascadeAgent({
    models: [
      {
        name: 'gpt-4o-mini',
        provider: 'openai',
        cost: 0.00015, // ~$0.15 per 1M tokens
      },
      {
        name: 'gpt-4o',
        provider: 'openai',
        cost: 0.00625, // ~$6.25 per 1M tokens (40x more!)
      },
    ],
  });

  // ═══════════════════════════════════════════════════════════════════════
  // STEP 3: Agent Ready
  // ═══════════════════════════════════════════════════════════════════════
  // The agent is configured with 2 models for cascading
  // Streaming is automatically available

  console.log('✓ Agent ready with 2-tier cascade');
  console.log('✓ Streaming enabled\n');

  // ═══════════════════════════════════════════════════════════════════════
  // EXAMPLE 1: Simple Query (Usually Stays on Tier 1)
  // ═══════════════════════════════════════════════════════════════════════
  // Simple questions usually get accepted by the cheap model
  // You'll see: draft accepted = verifier skipped = money saved!

  console.log('='.repeat(60));
  console.log('Example 1: Simple question (fast & cheap)\n');
  process.stdout.write('Q: What is TypeScript?\nA: ');

  // Stream the response with real-time events
  for await (const event of agent.stream('What is TypeScript? Answer in one sentence.', {
    maxTokens: 100,
  })) {
    // ───────────────────────────────────────────────────────────────────
    // EVENT: CHUNK - New text token arrived
    // ───────────────────────────────────────────────────────────────────
    // This is fired for each piece of text (could be a word or character)
    // Print it immediately for real-time streaming effect

    if (event.type === StreamEventType.CHUNK) {
      process.stdout.write(event.content);
    }

    // ───────────────────────────────────────────────────────────────────
    // EVENT: DRAFT_DECISION - Quality check complete
    // ───────────────────────────────────────────────────────────────────
    // After the draft finishes, cascadeflow checks quality:
    // - Accepted = Good enough! Skip expensive model (save money)
    // - Rejected = Not good enough, need better model (ensure quality)

    else if (event.type === StreamEventType.DRAFT_DECISION) {
      if (event.data.accepted) {
        // Draft passed quality check - we're done!
        const confidence = event.data.confidence ?? 0;
        console.log(`\n✓ Draft accepted (${(confidence * 100).toFixed(0)}% confidence)`);
        console.log('  → Verifier skipped (saved money!)');
      } else {
        // Draft failed quality check - escalating to better model
        console.log('\n✗ Draft quality insufficient');
        console.log('  → Cascading to better model...');
      }
    }

    // ───────────────────────────────────────────────────────────────────
    // EVENT: COMPLETE - Stream finished
    // ───────────────────────────────────────────────────────────────────
    // All done! Show final statistics (cost, speed, model used)

    else if (event.type === StreamEventType.COMPLETE) {
      const result = event.data.result;
      console.log(`💰 Cost: $${result.totalCost.toFixed(6)}`);
      console.log(`⚡ Speed: ${result.latencyMs.toFixed(0)}ms`);
      console.log(`🎯 Model: ${result.modelUsed}`);
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // EXAMPLE 2: Complex Query (Usually Cascades to Tier 2)
  // ═══════════════════════════════════════════════════════════════════════
  // Complex questions often need the better model
  // You'll see: draft rejected → switch to verifier → better quality

  console.log('\n' + '='.repeat(60));
  console.log('Example 2: Complex question (may cascade)\n');
  process.stdout.write('Q: Explain quantum computing and its implications.\nA: ');

  // Stream with the same event handling
  for await (const event of agent.stream(
    'Explain quantum computing and its implications for cryptography.',
    { maxTokens: 200 }
  )) {
    // ───────────────────────────────────────────────────────────────────
    // CHUNK Event - Print tokens in real-time
    // ───────────────────────────────────────────────────────────────────

    if (event.type === StreamEventType.CHUNK) {
      process.stdout.write(event.content);
    }

    // ───────────────────────────────────────────────────────────────────
    // DRAFT_DECISION Event - Check if cascading happens
    // ───────────────────────────────────────────────────────────────────
    // For complex queries, you'll often see the draft get rejected
    // This means BOTH models run (costs more but ensures quality)

    else if (event.type === StreamEventType.DRAFT_DECISION) {
      if (event.data.accepted) {
        const confidence = event.data.confidence ?? 0;
        console.log(`\n✓ Draft accepted (${(confidence * 100).toFixed(0)}%)`);
      } else {
        // Draft rejected - now we'll see the SWITCH event next
        const confidence = event.data.confidence ?? 0;
        const reason = event.data.reason || 'quality_insufficient';
        console.log(`\n✗ Draft rejected (${(confidence * 100).toFixed(0)}%): ${reason}`);
      }
    }

    // ───────────────────────────────────────────────────────────────────
    // SWITCH Event - Cascading to better model
    // ───────────────────────────────────────────────────────────────────
    // This only fires when draft is rejected
    // Shows which models are being used (tier 1 → tier 2)

    else if (event.type === StreamEventType.SWITCH) {
      const fromModel = event.data.fromModel || 'tier-1';
      const toModel = event.data.toModel || 'tier-2';
      console.log(`⤴️  Cascading: ${fromModel} → ${toModel}`);
      process.stdout.write('A: '); // Start new answer line
    }

    // ───────────────────────────────────────────────────────────────────
    // COMPLETE Event - Show final stats
    // ───────────────────────────────────────────────────────────────────

    else if (event.type === StreamEventType.COMPLETE) {
      const result = event.data.result;
      console.log(`\n💰 Cost: $${result.totalCost.toFixed(6)}`);
      console.log(`⚡ Speed: ${result.latencyMs.toFixed(0)}ms`);
      console.log(`🎯 Model: ${result.modelUsed}`);
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // Summary - What You Learned
  // ═══════════════════════════════════════════════════════════════════════

  console.log('\n' + '='.repeat(60));
  console.log('\n✅ Done! Key takeaways:');
  console.log('\n  How Cascading Works:');
  console.log('  ├─ Simple queries → Draft accepted → Cheap & fast');
  console.log('  └─ Complex queries → Draft rejected → Expensive but quality');
  console.log('\n  Event Flow:');
  console.log('  ├─ CHUNK: New text arrives (print immediately)');
  console.log('  ├─ DRAFT_DECISION: Quality check (accepted or rejected)');
  console.log('  ├─ SWITCH: Cascading to better model (if rejected)');
  console.log('  └─ COMPLETE: All done (show stats)');
  console.log('\n  Cost Optimization:');
  console.log('  ├─ Accepted drafts: ~40x cheaper (gpt-4o-mini only)');
  console.log('  └─ Rejected drafts: Both models used (ensures quality)');

  console.log('\n📚 Learn more: docs/guides/streaming.md\n');
}

main().catch((error) => {
  console.error('\n\n❌ Error:', error);
  console.log('💡 Tip: Make sure OPENAI_API_KEY is set correctly');
});
