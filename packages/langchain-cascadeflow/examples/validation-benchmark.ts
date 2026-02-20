/**
 * Comprehensive Validation Benchmark
 *
 * Tests:
 * - Streaming vs non-streaming behavior
 * - Cascading effectiveness (not 100% drafter acceptance)
 * - PreRouter performance
 * - Agent role metadata
 * - Various query complexity levels (trivial/expert, short/long)
 */

import { ChatOpenAI } from '@langchain/openai';
import { ChatAnthropic } from '@langchain/anthropic';
import { withCascade, createPreRouter } from '../src/index.js';

// Test queries categorized by complexity and length
const TEST_QUERIES = {
  trivialShort: [
    'What is 2+2?',
    'What color is the sky?',
    'How many days in a week?',
    'What is the capital of France?',
    'Spell "hello"',
  ],
  trivialLong: [
    'Can you please explain to me in a detailed way what the result of adding two plus two together would be, including any mathematical principles involved?',
    'I would like a comprehensive explanation of what color the sky typically appears to be during a clear day, including the scientific reasons behind this phenomenon.',
    'Could you provide me with a thorough explanation of how many days are contained within a standard calendar week, along with the historical context?',
  ],
  moderateShort: [
    'Explain photosynthesis',
    'What is machine learning?',
    'How does DNA work?',
    'What is blockchain?',
    'Explain quantum physics',
  ],
  moderateLong: [
    'Can you provide a comprehensive explanation of how photosynthesis works in plants, including the light-dependent and light-independent reactions, the role of chlorophyll, and how this process contributes to the global carbon cycle?',
    'Please explain in detail what machine learning is, how it differs from traditional programming, what the main types of machine learning are, and provide examples of real-world applications.',
    'I need a detailed explanation of how DNA functions as the genetic blueprint for living organisms, including its structure, replication process, and how it codes for proteins.',
  ],
  expertShort: [
    'Explain the P vs NP problem',
    'What is the Riemann Hypothesis?',
    'Explain quantum entanglement implications',
    'What are Gödel\'s incompleteness theorems?',
    'Explain the halting problem',
  ],
  expertLong: [
    'Can you provide a comprehensive analysis of the P versus NP problem in computational complexity theory, including its mathematical formulation, its implications for computer science and cryptography, known results about complexity classes, and why it remains one of the most important open problems in mathematics?',
    'Please give me a detailed explanation of quantum entanglement, including the EPR paradox, Bell\'s theorem, the implications for quantum computing and quantum cryptography, and how it challenges our classical understanding of locality and realism.',
    'Explain Gödel\'s incompleteness theorems in detail, including the historical context, the mathematical proof technique, what they mean for the foundations of mathematics, and their philosophical implications for the nature of truth and provability.',
  ],
};

interface BenchmarkResult {
  query: string;
  category: string;
  streaming: boolean;
  modelUsed: 'drafter' | 'verifier';
  accepted: boolean;
  drafterQuality: number;
  latencyMs: number;
  response: string;
  agentRole?: string;
  preRouterDecision?: string;
}

async function runNonStreamingTest(
  cascade: any,
  query: string,
  category: string
): Promise<BenchmarkResult> {
  const start = Date.now();
  const result = await cascade.invoke(query);
  const latencyMs = Date.now() - start;

  const stats = cascade.getLastCascadeResult();

  // Check for agent role in response metadata
  const agentRole = result.response_metadata?.agent_role;

  return {
    query,
    category,
    streaming: false,
    modelUsed: stats?.modelUsed || 'unknown',
    accepted: stats?.accepted || false,
    drafterQuality: stats?.drafterQuality || 0,
    latencyMs,
    response: result.content.substring(0, 100) + '...',
    agentRole,
  };
}

async function runStreamingTest(
  cascade: any,
  query: string,
  category: string
): Promise<BenchmarkResult> {
  const start = Date.now();
  let response = '';
  let chunkCount = 0;

  const stream = await cascade.stream(query);

  for await (const chunk of stream) {
    const content = typeof chunk.content === 'string' ? chunk.content : '';
    response += content;
    chunkCount++;
  }

  const latencyMs = Date.now() - start;
  const stats = cascade.getLastCascadeResult();

  return {
    query,
    category,
    streaming: true,
    modelUsed: stats?.modelUsed || 'unknown',
    accepted: stats?.accepted || false,
    drafterQuality: stats?.drafterQuality || 0,
    latencyMs,
    response: response.substring(0, 100) + '...',
  };
}

async function main() {
  console.log('🔬 CascadeFlow Validation Benchmark\n');
  console.log('Configuration:');
  console.log('  Drafter: gpt-5-mini (OpenAI)');
  console.log('  Verifier: claude-opus-4-6 (Anthropic)');
  console.log('  Quality Threshold: 0.7');
  console.log('  PreRouter: Enabled\n');

  // Initialize models
  const drafter = new ChatOpenAI({
    model: 'gpt-5-mini',
    // gpt-5-mini only supports temperature=1 (default)
  });

  const verifier = new ChatAnthropic({
    model: 'claude-opus-4-6',
    temperature: 0.7,
  });

  // Create PreRouter
  const preRouter = createPreRouter({
    enableCascade: true,
    cascadeComplexities: ['trivial', 'simple', 'moderate'],
    verbose: false,
  });

  // Create cascade model with PreRouter
  const cascade = withCascade({
    drafter,
    verifier,
    qualityThreshold: 0.7,
    enablePreRouter: true,
    preRouter,
  });

  const results: BenchmarkResult[] = [];

  // Test each category
  const categories = Object.entries(TEST_QUERIES);

  for (const [categoryName, queries] of categories) {
    console.log(`\n📊 Testing Category: ${categoryName}`);
    console.log('─'.repeat(60));

    for (let i = 0; i < Math.min(queries.length, 2); i++) {
      const query = queries[i];

      console.log(`\n  Query ${i + 1}/${Math.min(queries.length, 2)}: "${query.substring(0, 50)}..."`);

      // Test non-streaming
      console.log('    → Testing non-streaming...');
      const nonStreamingResult = await runNonStreamingTest(
        cascade,
        query,
        `${categoryName}-non-streaming`
      );
      results.push(nonStreamingResult);
      console.log(`       Model: ${nonStreamingResult.modelUsed}, Quality: ${nonStreamingResult.drafterQuality.toFixed(2)}, Latency: ${nonStreamingResult.latencyMs}ms`);

      // Test streaming
      console.log('    → Testing streaming...');
      const streamingResult = await runStreamingTest(
        cascade,
        query,
        `${categoryName}-streaming`
      );
      results.push(streamingResult);
      console.log(`       Model: ${streamingResult.modelUsed}, Quality: ${streamingResult.drafterQuality.toFixed(2)}, Latency: ${streamingResult.latencyMs}ms`);

      // Small delay between queries
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  }

  // Analysis
  console.log('\n\n' + '='.repeat(60));
  console.log('📈 ANALYSIS RESULTS');
  console.log('='.repeat(60));

  // 1. Cascading Effectiveness
  const drafterAccepted = results.filter(r => r.accepted).length;
  const totalQueries = results.length;
  const cascadeRate = ((totalQueries - drafterAccepted) / totalQueries * 100).toFixed(1);

  console.log('\n1️⃣  Cascading Effectiveness:');
  console.log(`   ✓ Drafter Accepted: ${drafterAccepted}/${totalQueries} (${(drafterAccepted/totalQueries*100).toFixed(1)}%)`);
  console.log(`   ✓ Cascaded to Verifier: ${totalQueries - drafterAccepted}/${totalQueries} (${cascadeRate}%)`);

  if (cascadeRate === '0.0') {
    console.log('   ⚠️  WARNING: 100% drafter acceptance - cascading not working!');
  } else if (parseFloat(cascadeRate) < 10) {
    console.log('   ⚠️  Low cascade rate - quality threshold may be too low');
  } else {
    console.log('   ✓ Cascading working correctly!');
  }

  // 2. Streaming vs Non-Streaming
  const streamingResults = results.filter(r => r.streaming);
  const nonStreamingResults = results.filter(r => !r.streaming);

  const streamingAccepted = streamingResults.filter(r => r.accepted).length;
  const nonStreamingAccepted = nonStreamingResults.filter(r => r.accepted).length;

  console.log('\n2️⃣  Streaming vs Non-Streaming:');
  console.log(`   Streaming - Accepted: ${streamingAccepted}/${streamingResults.length} (${(streamingAccepted/streamingResults.length*100).toFixed(1)}%)`);
  console.log(`   Non-Streaming - Accepted: ${nonStreamingAccepted}/${nonStreamingResults.length} (${(nonStreamingAccepted/nonStreamingResults.length*100).toFixed(1)}%)`);

  const streamingAvgLatency = streamingResults.reduce((sum, r) => sum + r.latencyMs, 0) / streamingResults.length;
  const nonStreamingAvgLatency = nonStreamingResults.reduce((sum, r) => sum + r.latencyMs, 0) / nonStreamingResults.length;

  console.log(`   Streaming Avg Latency: ${streamingAvgLatency.toFixed(0)}ms`);
  console.log(`   Non-Streaming Avg Latency: ${nonStreamingAvgLatency.toFixed(0)}ms`);

  // 3. Quality by Category
  console.log('\n3️⃣  Quality by Category:');
  const categoryStats: Record<string, { avgQuality: number; cascadeRate: number; count: number }> = {};

  for (const result of results) {
    const baseCat = result.category.split('-')[0];
    if (!categoryStats[baseCat]) {
      categoryStats[baseCat] = { avgQuality: 0, cascadeRate: 0, count: 0 };
    }
    categoryStats[baseCat].avgQuality += result.drafterQuality;
    categoryStats[baseCat].cascadeRate += result.accepted ? 0 : 1;
    categoryStats[baseCat].count++;
  }

  for (const [cat, stats] of Object.entries(categoryStats)) {
    const avgQuality = stats.avgQuality / stats.count;
    const cascadeRate = (stats.cascadeRate / stats.count * 100).toFixed(1);
    console.log(`   ${cat.padEnd(20)} - Avg Quality: ${avgQuality.toFixed(2)}, Cascade Rate: ${cascadeRate}%`);
  }

  // 4. Agent Role Check
  console.log('\n4️⃣  Agent Role Metadata:');
  const withAgentRole = results.filter(r => r.agentRole).length;
  console.log(`   Results with agent_role: ${withAgentRole}/${results.length}`);

  if (withAgentRole > 0) {
    console.log('   ✓ Agent role metadata is being sent correctly!');
    const sampleRole = results.find(r => r.agentRole)?.agentRole;
    console.log(`   Sample agent_role: "${sampleRole}"`);
  } else {
    console.log('   ⚠️  No agent_role metadata found in responses');
  }

  // 5. Model Usage Distribution
  console.log('\n5️⃣  Model Usage Distribution:');
  const drafterUsed = results.filter(r => r.modelUsed === 'drafter').length;
  const verifierUsed = results.filter(r => r.modelUsed === 'verifier').length;

  console.log(`   Drafter: ${drafterUsed}/${totalQueries} (${(drafterUsed/totalQueries*100).toFixed(1)}%)`);
  console.log(`   Verifier: ${verifierUsed}/${totalQueries} (${(verifierUsed/totalQueries*100).toFixed(1)}%)`);

  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('✅ VALIDATION SUMMARY');
  console.log('='.repeat(60));

  const validations = [
    { name: 'Cascading works (not 100% acceptance)', passed: parseFloat(cascadeRate) > 0 },
    { name: 'Streaming implemented', passed: streamingResults.length > 0 },
    { name: 'Quality scores reasonable (0-1)', passed: results.every(r => r.drafterQuality >= 0 && r.drafterQuality <= 1) },
    { name: 'Both models used', passed: drafterUsed > 0 && verifierUsed > 0 },
    { name: 'Agent role metadata present', passed: withAgentRole > 0 },
  ];

  for (const validation of validations) {
    console.log(`${validation.passed ? '✓' : '✗'} ${validation.name}`);
  }

  const allPassed = validations.every(v => v.passed);
  console.log(`\n${allPassed ? '🎉 All validations passed!' : '⚠️  Some validations failed'}`);

  // 6. PreRouter Statistics
  console.log('\n6️⃣  PreRouter Statistics:');
  preRouter.printStats();

  // Save detailed results
  const fs = await import('fs');
  fs.writeFileSync(
    'validation-results.json',
    JSON.stringify(results, null, 2)
  );
  console.log('\n💾 Detailed results saved to validation-results.json');
}

main().catch(console.error);
