/**
 * GPT-5 Cascade Demo - Real-World Usage
 *
 * Demonstrates cascade routing decisions:
 * - Cascaded (saved money by using drafter)
 * - Direct routed (quality threshold not met, used verifier)
 * - Alignment floor (pre-routing based on complexity)
 */

import { ChatOpenAI } from '@langchain/openai';
import { CascadeFlow } from './src/index.js';

const COLORS = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
  bold: '\x1b[1m',
};

function log(color: string, message: string) {
  console.log(`${color}${message}${COLORS.reset}`);
}

function section(title: string) {
  console.log('\n' + '='.repeat(100));
  log(COLORS.cyan + COLORS.bold, `  ${title}`);
  console.log('='.repeat(100) + '\n');
}

async function main() {
  section('GPT-5 CASCADE ROUTING DEMONSTRATION');

  // Your LangChain models (already configured in your environment)
  const drafter = new ChatOpenAI({ modelName: 'gpt-5-nano', temperature: 1.0 });
  const verifier = new ChatOpenAI({ modelName: 'gpt-5', temperature: 1.0 });

  log(COLORS.blue, 'Models:');
  console.log('  Drafter:  gpt-5-nano (ultra-cheap, fast)');
  console.log('  Verifier: gpt-5 (powerful, expensive)');
  console.log('  Expected savings: 66% when drafter succeeds\n');

  // Create cascade wrapper
  const cascade = new CascadeFlow({
    drafter,
    verifier,
    qualityThreshold: 0.7,
    enableCostTracking: true,
  });

  // Test 1: Simple query (should CASCADE - drafter handles it)
  section('TEST 1: SIMPLE QUERY (EXPECTED: CASCADED)');

  const prompt1 = 'What is machine learning in one sentence?';
  log(COLORS.blue, `Prompt: "${prompt1}"`);

  const result1 = await cascade.invoke(prompt1);
  const stats1 = cascade.getLastCascadeResult();

  console.log('\nResult:');
  console.log(result1.content);

  console.log('\n' + '-'.repeat(100));
  log(COLORS.bold, 'ROUTING DECISION:');
  if (stats1?.modelUsed === 'drafter') {
    log(COLORS.green, '✓ CASCADED - Drafter handled the request');
    console.log(`  Quality score: ${stats1.drafterQuality.toFixed(2)} (threshold: 0.7)`);
    console.log(`  Cost saved: ${stats1.savingsPercentage.toFixed(1)}%`);
    console.log(`  Latency: ${stats1.latencyMs}ms`);
  } else if (stats1?.modelUsed === 'verifier') {
    log(COLORS.yellow, '⚠ DIRECT ROUTED - Verifier used (drafter quality too low)');
    console.log(`  Drafter quality: ${stats1.drafterQuality.toFixed(2)} (below threshold)`);
    console.log(`  Cost: No savings (used expensive model)`);
  }

  // Test 2: Complex reasoning (might need verifier)
  section('TEST 2: COMPLEX REASONING (TESTING QUALITY THRESHOLD)');

  const prompt2 = 'Explain the differences between async/await and Promises in JavaScript, including when to use each, with code examples.';
  log(COLORS.blue, `Prompt: "${prompt2}"`);

  const result2 = await cascade.invoke(prompt2);
  const stats2 = cascade.getLastCascadeResult();

  console.log('\nResult preview:');
  console.log(result2.content.toString().substring(0, 200) + '...\n');

  console.log('-'.repeat(100));
  log(COLORS.bold, 'ROUTING DECISION:');
  if (stats2?.modelUsed === 'drafter') {
    log(COLORS.green, '✓ CASCADED - Drafter quality was sufficient');
    console.log(`  Quality score: ${stats2.drafterQuality.toFixed(2)} (threshold: 0.7)`);
    console.log(`  Cost saved: ${stats2.savingsPercentage.toFixed(1)}%`);
    console.log(`  Latency: ${stats2.latencyMs}ms`);
  } else if (stats2?.modelUsed === 'verifier') {
    log(COLORS.yellow, '⚠ ESCALATED - Drafter quality below threshold');
    console.log(`  Drafter quality: ${stats2.drafterQuality.toFixed(2)} (below 0.7 threshold)`);
    console.log(`  Verifier used for accuracy`);
    console.log(`  Cost: No savings this time`);
    console.log(`  Latency: ${stats2.latencyMs}ms`);
  }

  // Test 3: Very simple query (definitely should cascade)
  section('TEST 3: TRIVIAL QUERY (EXPECTED: CASCADED)');

  const prompt3 = 'What is 2+2?';
  log(COLORS.blue, `Prompt: "${prompt3}"`);

  const result3 = await cascade.invoke(prompt3);
  const stats3 = cascade.getLastCascadeResult();

  console.log('\nResult:');
  console.log(result3.content);

  console.log('\n' + '-'.repeat(100));
  log(COLORS.bold, 'ROUTING DECISION:');
  if (stats3?.modelUsed === 'drafter') {
    log(COLORS.green, '✓ CASCADED - Perfect for cheap model');
    console.log(`  Quality score: ${stats3.drafterQuality.toFixed(2)}`);
    console.log(`  Cost saved: ${stats3.savingsPercentage.toFixed(1)}%`);
  }

  // Summary
  section('ROUTING SUMMARY');

  const totalTests = 3;
  const cascaded = [stats1, stats2, stats3].filter(s => s?.modelUsed === 'drafter').length;
  const escalated = totalTests - cascaded;

  console.log(`Total queries: ${totalTests}`);
  log(COLORS.green, `Cascaded (drafter): ${cascaded} (${((cascaded / totalTests) * 100).toFixed(0)}%)`);
  log(COLORS.yellow, `Escalated (verifier): ${escalated} (${((escalated / totalTests) * 100).toFixed(0)}%)`);

  console.log(`\nAverage savings: ${(
    ([stats1, stats2, stats3]
      .filter(s => s?.savingsPercentage !== undefined)
      .reduce((sum, s) => sum + (s?.savingsPercentage || 0), 0) / totalTests)
  ).toFixed(1)}%`);

  section('KEY INSIGHTS');

  console.log(`${COLORS.bold}Cascade Behavior with GPT-5 Models:${COLORS.reset}`);
  console.log(`  • gpt-5-nano successfully handles simple queries (66% cost savings)`);
  console.log(`  • Quality threshold (0.7) determines routing decisions`);
  console.log(`  • Complex queries may escalate to gpt-5 if needed`);
  console.log(`  • No "alignment floor" needed - quality scoring handles routing`);

  console.log(`\n${COLORS.bold}Production Recommendations:${COLORS.reset}`);
  console.log(`  • Use gpt-5-nano → gpt-5 for general-purpose tasks`);
  console.log(`  • Quality threshold 0.7 provides good accuracy/cost balance`);
  console.log(`  • Monitor drafter acceptance rate over time`);
  console.log(`  • Adjust threshold based on your quality requirements\n`);
}

main().catch(console.error);
