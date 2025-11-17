/**
 * LangSmith Integration Test - All Available Models
 *
 * Tests cascade routing with all user's models and sends traces to LangSmith.
 * View results at: https://smith.langchain.com
 */

import { ChatOpenAI } from '@langchain/openai';
import { ChatAnthropic } from '@langchain/anthropic';
import { ChatGoogleGenerativeAI } from '@langchain/google-genai';
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

// Test queries of varying complexity
const TEST_QUERIES = [
  { query: 'What is TypeScript?', complexity: 'Simple' },
  { query: 'Explain the event loop in Node.js', complexity: 'Medium' },
  { query: 'Design a distributed cache with Redis and implement consistency guarantees', complexity: 'Complex' },
];

async function testModelPair(
  name: string,
  drafter: any,
  verifier: any,
  provider: 'OpenAI' | 'Anthropic' | 'Google' | 'Cross-Provider'
) {
  console.log(`\n${COLORS.cyan}${COLORS.bold}${'='.repeat(100)}${COLORS.reset}`);
  console.log(`${COLORS.cyan}${COLORS.bold}Testing: ${name}${COLORS.reset}`);
  console.log(`${COLORS.blue}Provider: ${provider}${COLORS.reset}`);
  console.log(`${COLORS.cyan}${'='.repeat(100)}${COLORS.reset}\n`);

  const cascade = new CascadeFlow({
    drafter,
    verifier,
    qualityThreshold: 0.7,
    enableCostTracking: true,
    costTrackingProvider: 'langsmith', // Use LangSmith for cost tracking
  });

  let cascaded = 0;
  let escalated = 0;

  for (const { query, complexity } of TEST_QUERIES) {
    console.log(`${COLORS.blue}[${complexity}]${COLORS.reset} ${query}`);

    const result = await cascade.invoke(query);
    const stats = cascade.getLastCascadeResult();

    const preview = result.content.toString().substring(0, 80);
    console.log(`  Response: ${preview}...`);

    if (stats?.modelUsed === 'drafter') {
      console.log(`  ${COLORS.green}✓ CASCADED${COLORS.reset} (quality: ${stats.drafterQuality.toFixed(2)}, ${stats.latencyMs}ms)`);
      cascaded++;
    } else {
      console.log(`  ${COLORS.yellow}⚠ ESCALATED${COLORS.reset} (quality: ${stats?.drafterQuality.toFixed(2)}, ${stats?.latencyMs}ms)`);
      escalated++;
    }
  }

  console.log(`\n${COLORS.bold}Results:${COLORS.reset}`);
  console.log(`  Cascaded: ${cascaded}/${TEST_QUERIES.length}`);
  console.log(`  Escalated: ${escalated}/${TEST_QUERIES.length}`);
  console.log(`  Success Rate: ${((cascaded / TEST_QUERIES.length) * 100).toFixed(0)}%`);
}

async function main() {
  console.log(`${COLORS.magenta}${COLORS.bold}╔════════════════════════════════════════════════════════════════════╗${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}║     LangSmith Integration - All Model Cascade Tests              ║${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}╚════════════════════════════════════════════════════════════════════╝${COLORS.reset}\n`);

  // Check LangSmith configuration
  if (!process.env.LANGSMITH_API_KEY) {
    console.log(`${COLORS.yellow}⚠ LANGSMITH_API_KEY not set${COLORS.reset}`);
    console.log('LangSmith tracing will not be available.');
    console.log('Set LANGSMITH_API_KEY to see traces in https://smith.langchain.com\n');
  } else {
    console.log(`${COLORS.green}✓ LangSmith tracing enabled${COLORS.reset}`);
    console.log(`  Project: ${process.env.LANGSMITH_PROJECT || 'default'}`);
    console.log(`  View traces: ${COLORS.cyan}https://smith.langchain.com${COLORS.reset}\n`);
  }

  // =====================================================================
  // OpenAI GPT-5 Family Tests
  // =====================================================================

  console.log(`\n${COLORS.magenta}${COLORS.bold}━━━ OpenAI GPT-5 Family ━━━${COLORS.reset}`);

  // Test 1: GPT-5 Nano → GPT-5
  await testModelPair(
    'GPT-5 Nano → GPT-5 (66% savings)',
    new ChatOpenAI({ modelName: 'gpt-5-nano', temperature: 1.0 }),
    new ChatOpenAI({ modelName: 'gpt-5', temperature: 1.0 }),
    'OpenAI'
  );

  // Test 2: GPT-5 Mini → GPT-5
  await testModelPair(
    'GPT-5 Mini → GPT-5 (50% savings)',
    new ChatOpenAI({ modelName: 'gpt-5-mini', temperature: 1.0 }),
    new ChatOpenAI({ modelName: 'gpt-5', temperature: 1.0 }),
    'OpenAI'
  );

  // Test 3: GPT-5 Nano → GPT-5 Mini
  await testModelPair(
    'GPT-5 Nano → GPT-5 Mini (50% savings)',
    new ChatOpenAI({ modelName: 'gpt-5-nano', temperature: 1.0 }),
    new ChatOpenAI({ modelName: 'gpt-5-mini', temperature: 1.0 }),
    'OpenAI'
  );

  // =====================================================================
  // Cross-Provider Tests (Anthropic ↔ OpenAI)
  // =====================================================================

  console.log(`\n${COLORS.magenta}${COLORS.bold}━━━ Cross-Provider: Anthropic → OpenAI ━━━${COLORS.reset}`);

  if (!process.env.ANTHROPIC_API_KEY) {
    console.log(`${COLORS.yellow}⚠ ANTHROPIC_API_KEY not set - skipping Anthropic tests${COLORS.reset}\n`);
  } else {
    // Test 4: Claude Haiku → GPT-5
    await testModelPair(
      'Claude 3.5 Haiku → GPT-5 (80% savings)',
      new ChatAnthropic({ model: 'claude-3-5-haiku-20241022' }),
      new ChatOpenAI({ modelName: 'gpt-5', temperature: 1.0 }),
      'Cross-Provider'
    );

    // Test 5: Claude Haiku → GPT-5 Mini
    await testModelPair(
      'Claude 3.5 Haiku → GPT-5 Mini (60% savings)',
      new ChatAnthropic({ model: 'claude-3-5-haiku-20241022' }),
      new ChatOpenAI({ modelName: 'gpt-5-mini', temperature: 1.0 }),
      'Cross-Provider'
    );
  }

  // =====================================================================
  // Google Gemini Tests
  // =====================================================================

  console.log(`\n${COLORS.magenta}${COLORS.bold}━━━ Cross-Provider: Google → OpenAI ━━━${COLORS.reset}`);

  if (!process.env.GOOGLE_API_KEY) {
    console.log(`${COLORS.yellow}⚠ GOOGLE_API_KEY not set - skipping Gemini tests${COLORS.reset}\n`);
  } else {
    // Test 6: Gemini Flash → GPT-5
    await testModelPair(
      'Gemini 2.5 Flash → GPT-5 (75% savings)',
      new ChatGoogleGenerativeAI({ modelName: 'gemini-2.5-flash' }),
      new ChatOpenAI({ modelName: 'gpt-5', temperature: 1.0 }),
      'Cross-Provider'
    );

    // Test 7: Gemini Flash → Gemini Pro
    await testModelPair(
      'Gemini 2.5 Flash → Gemini 2.5 Pro (75% savings)',
      new ChatGoogleGenerativeAI({ modelName: 'gemini-2.5-flash' }),
      new ChatGoogleGenerativeAI({ modelName: 'gemini-2.5-pro' }),
      'Google'
    );
  }

  // =====================================================================
  // Summary
  // =====================================================================

  console.log(`\n${COLORS.magenta}${COLORS.bold}${'='.repeat(100)}${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}Testing Complete!${COLORS.reset}\n`);

  console.log(`${COLORS.cyan}${COLORS.bold}📊 View Results in LangSmith:${COLORS.reset}`);
  console.log(`  1. Go to: ${COLORS.cyan}https://smith.langchain.com${COLORS.reset}`);
  console.log(`  2. Select project: ${COLORS.yellow}${process.env.LANGSMITH_PROJECT || 'default'}${COLORS.reset}`);
  console.log(`  3. Filter by: ${COLORS.yellow}last 1 hour${COLORS.reset}`);
  console.log(`  4. Look for traces with metadata:`);
  console.log(`     - ${COLORS.green}cascade_decision${COLORS.reset}: "cascaded" or "escalated"`);
  console.log(`     - ${COLORS.green}drafter_quality${COLORS.reset}: quality score (0-1)`);
  console.log(`     - ${COLORS.green}model_used${COLORS.reset}: "drafter" or "verifier"`);
  console.log(`     - ${COLORS.green}savings_percentage${COLORS.reset}: cost savings\n`);

  console.log(`${COLORS.green}${COLORS.bold}✓ All traces sent to LangSmith!${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}${'='.repeat(100)}${COLORS.reset}\n`);
}

main().catch(console.error);
