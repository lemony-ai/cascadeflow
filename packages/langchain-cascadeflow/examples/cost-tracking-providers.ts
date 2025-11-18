/**
 * Cost Tracking Providers Example
 *
 * Demonstrates the two cost tracking options:
 * 1. LangSmith (default) - Server-side cost calculation
 * 2. CascadeFlow - Built-in local cost calculation
 */

import { ChatOpenAI } from '@langchain/openai';
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

async function testLangSmithProvider() {
  console.log(`\n${COLORS.cyan}${COLORS.bold}=== Test 1: LangSmith Provider (Default) ===${COLORS.reset}\n`);

  const drafter = new ChatOpenAI({ modelName: 'gpt-5-nano', temperature: 1.0 });
  const verifier = new ChatOpenAI({ modelName: 'gpt-5', temperature: 1.0 });

  // LangSmith provider (default)
  const cascade = new CascadeFlow({
    drafter,
    verifier,
    qualityThreshold: 0.7,
    enableCostTracking: true,
    costTrackingProvider: 'langsmith', // Can be omitted (this is the default)
  });

  console.log(`${COLORS.blue}Configuration:${COLORS.reset}`);
  console.log('  Cost Tracking: LangSmith (server-side)');
  console.log('  Requires: LANGSMITH_API_KEY environment variable');
  console.log('  Benefits:');
  console.log('    ✓ Automatic cost calculation (no pricing table needed)');
  console.log('    ✓ Always up-to-date with latest model pricing');
  console.log('    ✓ Integrated with LangSmith UI for visualization');
  console.log('    ✓ Supports multi-modal costs (text, images, caching)');
  console.log('  Drawbacks:');
  console.log('    ✗ Requires LangSmith account & API key');
  console.log('    ✗ Network dependency (offline usage not supported)\n');

  const result = await cascade.invoke('What is TypeScript?');
  const stats = cascade.getLastCascadeResult();

  console.log(`${COLORS.green}Response:${COLORS.reset} ${result.content.substring(0, 100)}...\n`);
  console.log(`${COLORS.bold}Cascade Metadata:${COLORS.reset}`);
  console.log(`  Model Used: ${stats?.modelUsed}`);
  console.log(`  Quality Score: ${stats?.drafterQuality?.toFixed(2)}`);
  console.log(`  Local Cost (disabled with LangSmith): $${stats?.totalCost.toFixed(6)}`);
  console.log(`  ${COLORS.yellow}Note: Actual costs visible in LangSmith UI${COLORS.reset}`);
  console.log(`  LangSmith Dashboard: https://smith.langchain.com`);
}

async function testCascadeFlowProvider() {
  console.log(`\n${COLORS.cyan}${COLORS.bold}=== Test 2: CascadeFlow Provider ===${COLORS.reset}\n`);

  const drafter = new ChatOpenAI({ modelName: 'gpt-5-nano', temperature: 1.0 });
  const verifier = new ChatOpenAI({ modelName: 'gpt-5', temperature: 1.0 });

  // CascadeFlow provider (built-in pricing)
  const cascade = new CascadeFlow({
    drafter,
    verifier,
    qualityThreshold: 0.7,
    enableCostTracking: true,
    costTrackingProvider: 'cascadeflow', // Use local cost calculation
  });

  console.log(`${COLORS.blue}Configuration:${COLORS.reset}`);
  console.log('  Cost Tracking: CascadeFlow (local calculation)');
  console.log('  Requires: Nothing (works offline)');
  console.log('  Benefits:');
  console.log('    ✓ No external dependencies');
  console.log('    ✓ Works offline');
  console.log('    ✓ Immediate cost feedback');
  console.log('    ✓ No LangSmith account required');
  console.log('  Drawbacks:');
  console.log('    ✗ Pricing table may lag behind provider updates');
  console.log('    ✗ No multi-modal cost tracking (yet)\n');

  const result = await cascade.invoke('What is TypeScript?');
  const stats = cascade.getLastCascadeResult();

  console.log(`${COLORS.green}Response:${COLORS.reset} ${result.content.substring(0, 100)}...\n`);
  console.log(`${COLORS.bold}Cascade Metadata with Costs:${COLORS.reset}`);
  console.log(`  Model Used: ${stats?.modelUsed}`);
  console.log(`  Quality Score: ${stats?.drafterQuality?.toFixed(2)}`);
  console.log(`  Drafter Cost: $${stats?.drafterCost.toFixed(6)}`);
  console.log(`  Verifier Cost: $${stats?.verifierCost.toFixed(6)}`);
  console.log(`  Total Cost: $${stats?.totalCost.toFixed(6)}`);
  console.log(`  Savings: ${stats?.savingsPercentage.toFixed(1)}%`);
}

async function main() {
  console.log(`${COLORS.magenta}${COLORS.bold}╔════════════════════════════════════════════════════╗${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}║     CascadeFlow Cost Tracking Providers Demo     ║${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}╚════════════════════════════════════════════════════╝${COLORS.reset}`);

  // Test 1: LangSmith Provider (default)
  await testLangSmithProvider();

  // Test 2: CascadeFlow Provider
  await testCascadeFlowProvider();

  // Recommendation
  console.log(`\n${COLORS.cyan}${COLORS.bold}=== When to Use Each Provider ===${COLORS.reset}\n`);
  console.log(`${COLORS.green}Use LangSmith (default)${COLORS.reset} when:`);
  console.log('  • You already use LangSmith for observability');
  console.log('  • You want the most accurate, up-to-date pricing');
  console.log('  • You need multi-modal cost tracking (images, audio)');
  console.log('  • You want cost visualization in LangSmith UI\n');

  console.log(`${COLORS.yellow}Use CascadeFlow${COLORS.reset} when:`);
  console.log('  • You don\'t want external dependencies');
  console.log('  • You need offline support');
  console.log('  • You want immediate local cost feedback');
  console.log('  • You\'re prototyping and don\'t have LangSmith yet\n');
}

main().catch(console.error);
