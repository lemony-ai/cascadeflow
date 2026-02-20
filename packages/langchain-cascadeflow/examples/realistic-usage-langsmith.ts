/**
 * Realistic LangChain CascadeFlow Usage with LangSmith Tracking
 *
 * This example demonstrates how developers would ACTUALLY use the integration:
 * 1. Create LangChain models once (reuse existing instances)
 * 2. Wrap with CascadeFlow
 * 3. Use the wrapped model multiple times
 * 4. See BOTH chat model calls AND cascade metadata in LangSmith
 *
 * Requirements:
 *   - OPENAI_API_KEY
 *   - ANTHROPIC_API_KEY (optional)
 *   - LANGSMITH_API_KEY
 *   - LANGSMITH_PROJECT
 *   - LANGSMITH_TRACING=true
 */

import { ChatOpenAI } from '@langchain/openai';
import { ChatAnthropic } from '@langchain/anthropic';
import { CascadeFlow } from '../src/index.js';

const COLORS = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
  bold: '\x1b[1m',
};

async function main() {
  console.log(`${COLORS.magenta}${COLORS.bold}╔════════════════════════════════════════════════════════════════════╗${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}║   REALISTIC LANGCHAIN USAGE - LangSmith Integration Demo          ║${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}╚════════════════════════════════════════════════════════════════════╝${COLORS.reset}\n`);

  // ========================================================================
  // STEP 1: Check LangSmith Configuration
  // ========================================================================

  if (!process.env.LANGSMITH_API_KEY) {
    console.log(`${COLORS.yellow}❌ LANGSMITH_API_KEY not set${COLORS.reset}`);
    console.log('Set LANGSMITH_API_KEY to see traces in https://smith.langchain.com\n');
    return;
  }

  console.log(`${COLORS.green}✓ LangSmith Configuration${COLORS.reset}`);
  console.log(`  API Key: Set`);
  console.log(`  Project: ${process.env.LANGSMITH_PROJECT || 'default'}`);
  console.log(`  Tracing: ${process.env.LANGSMITH_TRACING || 'false'}`);
  console.log(`  Dashboard: ${COLORS.cyan}https://smith.langchain.com${COLORS.reset}\n`);

  // ========================================================================
  // STEP 2: Developer Creates Their LangChain Models ONCE
  // ========================================================================

  console.log(`${COLORS.bold}📦 Step 1: Creating LangChain Models (Like Any Developer Would)${COLORS.reset}\n`);

  // Developers create these models ONCE and reuse them
  const drafterModel = new ChatOpenAI({
    model: 'gpt-5-nano',
    temperature: 1.0,
  });

  const verifierModel = new ChatOpenAI({
    model: 'gpt-5',
    temperature: 1.0,
  });

  console.log(`${COLORS.green}✓ Created ChatOpenAI models${COLORS.reset}`);
  console.log(`  Drafter: gpt-5-nano (cheap, fast)`);
  console.log(`  Verifier: gpt-5 (accurate, expensive)\n`);

  // ========================================================================
  // STEP 3: Wrap Models with CascadeFlow ONCE
  // ========================================================================

  console.log(`${COLORS.bold}🌊 Step 2: Wrapping with CascadeFlow${COLORS.reset}\n`);

  const cascade = new CascadeFlow({
    drafter: drafterModel,
    verifier: verifierModel,
    qualityThreshold: 0.7,
    enableCostTracking: true,
    costTrackingProvider: 'langsmith', // Use LangSmith for cost tracking
  });

  console.log(`${COLORS.green}✓ Wrapped models with CascadeFlow${COLORS.reset}`);
  console.log(`  Quality Threshold: 0.7`);
  console.log(`  Cost Tracking: LangSmith (server-side)\n`);

  // ========================================================================
  // STEP 4: Use the Wrapped Model Multiple Times (Like Developers Would)
  // ========================================================================

  console.log(`${COLORS.bold}🚀 Step 3: Using the Cascade Model (Multiple Queries)${COLORS.reset}\n`);
  console.log(`${COLORS.cyan}Watch LangSmith for:${COLORS.reset}`);
  console.log(`  • ChatOpenAI model traces (gpt-5-nano, gpt-5)`);
  console.log(`  • Cascade decision metadata`);
  console.log(`  • Token usage and costs\n`);
  console.log(`${COLORS.cyan}${'='.repeat(80)}${COLORS.reset}\n`);

  const queries = [
    { q: 'What is TypeScript?', type: 'Simple' },
    { q: 'Explain the event loop in Node.js', type: 'Medium' },
    { q: 'Design a distributed cache with Redis', type: 'Complex' },
    { q: 'What is async/await in JavaScript?', type: 'Medium' },
    { q: 'How do I reverse a string in Python?', type: 'Simple' },
  ];

  for (let i = 0; i < queries.length; i++) {
    const { q, type } = queries[i];

    console.log(`${COLORS.blue}Query ${i + 1}/${queries.length}${COLORS.reset} [${type}]: ${q}`);

    const startTime = Date.now();
    const result = await cascade.invoke(q);
    const elapsed = Date.now() - startTime;

    const stats = cascade.getLastCascadeResult();

    const preview = result.content.toString().substring(0, 100);
    console.log(`  Response: ${preview}...`);

    if (stats) {
      const icon = stats.modelUsed === 'drafter' ? '✓' : '⚠';
      const color = stats.modelUsed === 'drafter' ? COLORS.green : COLORS.yellow;
      const decision = stats.modelUsed === 'drafter' ? 'CASCADED' : 'ESCALATED';

      console.log(`  ${color}${icon} ${decision}${COLORS.reset} (quality: ${stats.drafterQuality?.toFixed(2)}, ${elapsed}ms)`);
      console.log(`  Model: ${stats.modelUsed === 'drafter' ? 'gpt-5-nano' : 'gpt-5'}`);
    }

    console.log();

    // Small delay to make traces easier to follow in LangSmith
    await new Promise(resolve => setTimeout(resolve, 500));
  }

  // ========================================================================
  // STEP 5: Optional - Test Cross-Provider Cascade
  // ========================================================================

  if (process.env.ANTHROPIC_API_KEY) {
    console.log(`${COLORS.cyan}${'='.repeat(80)}${COLORS.reset}\n`);
    console.log(`${COLORS.bold}🔀 Bonus: Cross-Provider Cascade (Anthropic → OpenAI)${COLORS.reset}\n`);

    const claudeDrafter = new ChatAnthropic({
      model: 'claude-haiku-4-5-20251001',
    });

    const crossProviderCascade = new CascadeFlow({
      drafter: claudeDrafter,
      verifier: verifierModel, // Reuse existing OpenAI verifier
      qualityThreshold: 0.7,
      enableCostTracking: true,
      costTrackingProvider: 'langsmith',
    });

    console.log(`${COLORS.green}✓ Created cross-provider cascade${COLORS.reset}`);
    console.log(`  Drafter: Claude 3 Haiku (Anthropic)`);
    console.log(`  Verifier: GPT-5 (OpenAI)\n`);

    const crossQuery = 'Explain the benefits of TypeScript';
    console.log(`${COLORS.blue}Cross-Provider Query:${COLORS.reset} ${crossQuery}`);

    const result = await crossProviderCascade.invoke(crossQuery);
    const stats = crossProviderCascade.getLastCascadeResult();

    const preview = result.content.toString().substring(0, 100);
    console.log(`  Response: ${preview}...`);

    if (stats) {
      const decision = stats.modelUsed === 'drafter' ? 'CASCADED' : 'ESCALATED';
      const model = stats.modelUsed === 'drafter' ? 'Claude 3 Haiku' : 'GPT-5';

      console.log(`  ${decision} (quality: ${stats.drafterQuality?.toFixed(2)})`);
      console.log(`  Model: ${model}\n`);
    }
  }

  // ========================================================================
  // STEP 6: Summary and LangSmith Instructions
  // ========================================================================

  console.log(`${COLORS.cyan}${'='.repeat(80)}${COLORS.reset}\n`);
  console.log(`${COLORS.magenta}${COLORS.bold}📊 VIEW RESULTS IN LANGSMITH${COLORS.reset}\n`);

  console.log(`${COLORS.bold}What to Look For:${COLORS.reset}\n`);

  console.log(`${COLORS.green}1. Chat Model Traces:${COLORS.reset}`);
  console.log(`   • Look for "ChatOpenAI" runs in your project`);
  console.log(`   • You should see calls to both gpt-5-nano and gpt-5`);
  console.log(`   • Each run shows token usage, latency, and costs\n`);

  console.log(`${COLORS.green}2. Cascade Metadata:${COLORS.reset}`);
  console.log(`   • Click on any ChatOpenAI run`);
  console.log(`   • Look in "Outputs" → "response_metadata" → "cascade"`);
  console.log(`   • You'll see:`);
  console.log(`     - cascade_decision: "cascaded" or "escalated"`);
  console.log(`     - drafter_quality: 0-1 quality score`);
  console.log(`     - model_used: "drafter" or "verifier"`);
  console.log(`     - savings_percentage: % saved vs always using verifier\n`);

  console.log(`${COLORS.green}3. Cost Analysis:${COLORS.reset}`);
  console.log(`   • LangSmith calculates costs server-side`);
  console.log(`   • Compare total cost of cascade vs. always using verifier`);
  console.log(`   • You should see ~50-70% savings on average\n`);

  console.log(`${COLORS.cyan}${COLORS.bold}🔗 Quick Links:${COLORS.reset}`);
  console.log(`   Dashboard: ${COLORS.cyan}https://smith.langchain.com${COLORS.reset}`);
  console.log(`   Project: ${COLORS.yellow}${process.env.LANGSMITH_PROJECT || 'default'}${COLORS.reset}`);
  console.log(`   Filter: Last 1 hour\n`);

  console.log(`${COLORS.green}${COLORS.bold}✓ Demo Complete!${COLORS.reset}`);
  console.log(`${COLORS.cyan}${'='.repeat(80)}${COLORS.reset}\n`);
}

main().catch(console.error);
