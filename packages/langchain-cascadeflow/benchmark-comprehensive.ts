/**
 * Comprehensive Benchmark Suite for LangChain Cascade Integration
 *
 * Tests:
 * - All available model combinations
 * - With/without semantic quality validation
 * - Streaming (normal + tool streaming)
 * - Tool calling
 * - Batch processing
 * - Structured output
 * - LCEL chains
 * - Cost tracking
 */

import { ChatOpenAI } from '@langchain/openai';
import { CascadeWrapper, discoverCascadePairs, analyzeModel } from './src/index.js';
import { StringOutputParser } from '@langchain/core/output_parsers';
import { PromptTemplate } from '@langchain/core/prompts';
import type { BaseChatModel } from '@langchain/core/language_models/chat_models';

// ============================================================================
// Configuration
// ============================================================================

const COLORS = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  red: '\x1b[31m',
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

// ============================================================================
// Model Discovery
// ============================================================================

async function discoverAvailableModels(): Promise<BaseChatModel[]> {
  section('MODEL DISCOVERY');

  const models: BaseChatModel[] = [];

  // Try to create various OpenAI models
  const openAIModels = [
    'gpt-4o',
    'gpt-4o-mini',
    'gpt-4-turbo',
    'gpt-3.5-turbo',
    'gpt-4',
  ];

  for (const modelName of openAIModels) {
    try {
      const model = new ChatOpenAI({
        modelName,
        temperature: 0.7,
      });

      // Test if model is accessible
      await model.invoke('ping');
      models.push(model);
      log(COLORS.green, `✓ ${modelName} - Available`);
    } catch (error: any) {
      if (error.message?.includes('API key')) {
        log(COLORS.red, `✗ ${modelName} - No API key`);
        break; // No point trying other models if no API key
      } else if (error.message?.includes('model') || error.status === 404) {
        log(COLORS.yellow, `⚠ ${modelName} - Not available in account`);
      } else {
        log(COLORS.yellow, `⚠ ${modelName} - Error: ${error.message}`);
      }
    }
  }

  // Try Anthropic if available
  try {
    const { ChatAnthropic } = await import('@langchain/anthropic');
    const anthropicModels = [
      'claude-3-5-sonnet-20241022',
      'claude-3-5-haiku-20241022',
      'claude-3-haiku-20240307',
    ];

    for (const modelName of anthropicModels) {
      try {
        const model = new ChatAnthropic({ model: modelName });
        await model.invoke('ping');
        models.push(model);
        log(COLORS.green, `✓ ${modelName} - Available`);
      } catch (error: any) {
        if (error.message?.includes('API key')) {
          break;
        }
        log(COLORS.yellow, `⚠ ${modelName} - Not available`);
      }
    }
  } catch {
    log(COLORS.yellow, '⚠ @langchain/anthropic not installed');
  }

  console.log(`\nTotal models available: ${models.length}`);

  if (models.length === 0) {
    throw new Error('No models available for testing');
  }

  // Analyze each model
  console.log('\nModel Analysis:');
  for (const model of models) {
    const analysis = analyzeModel(model);
    console.log(`  ${analysis.modelName}: ${analysis.tier} tier, ${analysis.recommendation}`);
  }

  return models;
}

// ============================================================================
// Benchmark Results Storage
// ============================================================================

interface BenchmarkResult {
  testName: string;
  configuration: string;
  drafterModel: string;
  verifierModel: string;
  qualityThreshold?: number;
  withQualityValidation: boolean;

  // Timing
  latencyMs: number;

  // Cost
  totalCost: number;
  drafterCost: number;
  verifierCost: number;
  savingsPercentage: number;

  // Quality
  drafterQuality?: number;
  accepted?: boolean;
  modelUsed?: 'drafter' | 'verifier';

  // Success
  success: boolean;
  error?: string;

  // Response
  responseLength?: number;
  responsePreview?: string;
}

const results: BenchmarkResult[] = [];

// ============================================================================
// Test Prompts
// ============================================================================

const TEST_PROMPTS = {
  simple: 'What is TypeScript in one sentence?',
  complex: 'Explain the differences between async/await and Promises in JavaScript, including when to use each.',
  reasoning: 'If a train leaves Station A at 60 mph and another train leaves Station B (100 miles away) at 40 mph, when will they meet?',
  code: 'Write a Python function to find the longest palindromic substring in a given string.',
};

const TOOL_DEFINITION = {
  type: 'function' as const,
  function: {
    name: 'calculator',
    description: 'Performs arithmetic operations',
    parameters: {
      type: 'object',
      properties: {
        operation: {
          type: 'string',
          enum: ['add', 'subtract', 'multiply', 'divide'],
        },
        a: { type: 'number' },
        b: { type: 'number' },
      },
      required: ['operation', 'a', 'b'],
    },
  },
};

// ============================================================================
// Benchmark Tests
// ============================================================================

async function benchmarkBasicCascade(
  drafter: BaseChatModel,
  verifier: BaseChatModel,
  withQuality: boolean
): Promise<BenchmarkResult> {
  const drafterName = analyzeModel(drafter).modelName;
  const verifierName = analyzeModel(verifier).modelName;

  try {
    const cascade = new CascadeWrapper({
      drafter,
      verifier,
      qualityThreshold: withQuality ? 0.7 : 0.0,
      enableCostTracking: true,
    });

    const startTime = Date.now();
    const result = await cascade.invoke(TEST_PROMPTS.complex);
    const latencyMs = Date.now() - startTime;

    const stats = cascade.getLastCascadeResult();

    return {
      testName: 'Basic Cascade',
      configuration: withQuality ? 'With Quality Validation' : 'Without Quality Validation',
      drafterModel: drafterName,
      verifierModel: verifierName,
      qualityThreshold: withQuality ? 0.7 : 0.0,
      withQualityValidation: withQuality,
      latencyMs,
      totalCost: stats?.totalCost || 0,
      drafterCost: stats?.drafterCost || 0,
      verifierCost: stats?.verifierCost || 0,
      savingsPercentage: stats?.savingsPercentage || 0,
      drafterQuality: stats?.drafterQuality,
      accepted: stats?.accepted,
      modelUsed: stats?.modelUsed,
      success: true,
      responseLength: result.content.toString().length,
      responsePreview: result.content.toString().substring(0, 100),
    };
  } catch (error: any) {
    return {
      testName: 'Basic Cascade',
      configuration: withQuality ? 'With Quality Validation' : 'Without Quality Validation',
      drafterModel: drafterName,
      verifierModel: verifierName,
      qualityThreshold: withQuality ? 0.7 : 0.0,
      withQualityValidation: withQuality,
      latencyMs: 0,
      totalCost: 0,
      drafterCost: 0,
      verifierCost: 0,
      savingsPercentage: 0,
      success: false,
      error: error.message,
    };
  }
}

async function benchmarkStreaming(
  drafter: BaseChatModel,
  verifier: BaseChatModel
): Promise<BenchmarkResult> {
  const drafterName = analyzeModel(drafter).modelName;
  const verifierName = analyzeModel(verifier).modelName;

  try {
    const cascade = new CascadeWrapper({
      drafter,
      verifier,
      qualityThreshold: 0.7,
      enableCostTracking: true,
    });

    const startTime = Date.now();
    const stream = await cascade.stream(TEST_PROMPTS.simple);

    let chunks = 0;
    let fullContent = '';
    for await (const chunk of stream) {
      fullContent += chunk.content;
      chunks++;
    }
    const latencyMs = Date.now() - startTime;

    const stats = cascade.getLastCascadeResult();

    return {
      testName: 'Streaming',
      configuration: `${chunks} chunks`,
      drafterModel: drafterName,
      verifierModel: verifierName,
      withQualityValidation: true,
      qualityThreshold: 0.7,
      latencyMs,
      totalCost: stats?.totalCost || 0,
      drafterCost: stats?.drafterCost || 0,
      verifierCost: stats?.verifierCost || 0,
      savingsPercentage: stats?.savingsPercentage || 0,
      drafterQuality: stats?.drafterQuality,
      accepted: stats?.accepted,
      modelUsed: stats?.modelUsed,
      success: true,
      responseLength: fullContent.length,
      responsePreview: fullContent.substring(0, 100),
    };
  } catch (error: any) {
    return {
      testName: 'Streaming',
      configuration: 'Failed',
      drafterModel: drafterName,
      verifierModel: verifierName,
      withQualityValidation: true,
      latencyMs: 0,
      totalCost: 0,
      drafterCost: 0,
      verifierCost: 0,
      savingsPercentage: 0,
      success: false,
      error: error.message,
    };
  }
}

async function benchmarkToolCalling(
  drafter: BaseChatModel,
  verifier: BaseChatModel
): Promise<BenchmarkResult> {
  const drafterName = analyzeModel(drafter).modelName;
  const verifierName = analyzeModel(verifier).modelName;

  try {
    const cascade = new CascadeWrapper({
      drafter,
      verifier,
      qualityThreshold: 0.7,
      enableCostTracking: true,
    });

    const boundCascade = cascade.bindTools([TOOL_DEFINITION]);

    const startTime = Date.now();
    const result = await boundCascade.invoke('What is 15 multiplied by 27?');
    const latencyMs = Date.now() - startTime;

    const stats = cascade.getLastCascadeResult();
    const toolCalls = (result as any).tool_calls || (result as any).additional_kwargs?.tool_calls;

    return {
      testName: 'Tool Calling',
      configuration: toolCalls ? `${toolCalls.length} tool calls` : 'No tool calls',
      drafterModel: drafterName,
      verifierModel: verifierName,
      withQualityValidation: true,
      qualityThreshold: 0.7,
      latencyMs,
      totalCost: stats?.totalCost || 0,
      drafterCost: stats?.drafterCost || 0,
      verifierCost: stats?.verifierCost || 0,
      savingsPercentage: stats?.savingsPercentage || 0,
      drafterQuality: stats?.drafterQuality,
      accepted: stats?.accepted,
      modelUsed: stats?.modelUsed,
      success: !!toolCalls,
      responsePreview: toolCalls ? JSON.stringify(toolCalls[0], null, 2).substring(0, 100) : undefined,
    };
  } catch (error: any) {
    return {
      testName: 'Tool Calling',
      configuration: 'Failed',
      drafterModel: drafterName,
      verifierModel: verifierName,
      withQualityValidation: true,
      latencyMs: 0,
      totalCost: 0,
      drafterCost: 0,
      verifierCost: 0,
      savingsPercentage: 0,
      success: false,
      error: error.message,
    };
  }
}

async function benchmarkStructuredOutput(
  drafter: BaseChatModel,
  verifier: BaseChatModel
): Promise<BenchmarkResult> {
  const drafterName = analyzeModel(drafter).modelName;
  const verifierName = analyzeModel(verifier).modelName;

  try {
    const schema = {
      type: 'object',
      properties: {
        name: { type: 'string' },
        age: { type: 'number' },
        occupation: { type: 'string' },
      },
      required: ['name', 'age'],
    };

    const cascade = new CascadeWrapper({
      drafter,
      verifier,
      qualityThreshold: 0.7,
      enableCostTracking: true,
    });

    const structuredCascade = cascade.withStructuredOutput(schema);

    const startTime = Date.now();
    const result = await structuredCascade.invoke('Extract: Sarah is 32 years old and works as an engineer.');
    const latencyMs = Date.now() - startTime;

    const stats = cascade.getLastCascadeResult();

    return {
      testName: 'Structured Output',
      configuration: 'JSON extraction',
      drafterModel: drafterName,
      verifierModel: verifierName,
      withQualityValidation: true,
      qualityThreshold: 0.7,
      latencyMs,
      totalCost: stats?.totalCost || 0,
      drafterCost: stats?.drafterCost || 0,
      verifierCost: stats?.verifierCost || 0,
      savingsPercentage: stats?.savingsPercentage || 0,
      drafterQuality: stats?.drafterQuality,
      accepted: stats?.accepted,
      modelUsed: stats?.modelUsed,
      success: typeof result === 'object' && (result as any).name && (result as any).age,
      responsePreview: JSON.stringify(result, null, 2).substring(0, 100),
    };
  } catch (error: any) {
    return {
      testName: 'Structured Output',
      configuration: 'Failed',
      drafterModel: drafterName,
      verifierModel: verifierName,
      withQualityValidation: true,
      latencyMs: 0,
      totalCost: 0,
      drafterCost: 0,
      verifierCost: 0,
      savingsPercentage: 0,
      success: false,
      error: error.message,
    };
  }
}

async function benchmarkBatchProcessing(
  drafter: BaseChatModel,
  verifier: BaseChatModel
): Promise<BenchmarkResult> {
  const drafterName = analyzeModel(drafter).modelName;
  const verifierName = analyzeModel(verifier).modelName;

  try {
    const cascade = new CascadeWrapper({
      drafter,
      verifier,
      qualityThreshold: 0.7,
      enableCostTracking: true,
    });

    const prompts = [
      'What is 2+2?',
      'What is the capital of France?',
      'What is H2O?',
    ];

    const startTime = Date.now();
    const batchResults = await cascade.batch(prompts);
    const latencyMs = Date.now() - startTime;

    const stats = cascade.getLastCascadeResult();

    return {
      testName: 'Batch Processing',
      configuration: `${prompts.length} prompts`,
      drafterModel: drafterName,
      verifierModel: verifierName,
      withQualityValidation: true,
      qualityThreshold: 0.7,
      latencyMs,
      totalCost: stats?.totalCost || 0,
      drafterCost: stats?.drafterCost || 0,
      verifierCost: stats?.verifierCost || 0,
      savingsPercentage: stats?.savingsPercentage || 0,
      drafterQuality: stats?.drafterQuality,
      accepted: stats?.accepted,
      modelUsed: stats?.modelUsed,
      success: batchResults.length === prompts.length,
      responsePreview: `${batchResults.length} results`,
    };
  } catch (error: any) {
    return {
      testName: 'Batch Processing',
      configuration: 'Failed',
      drafterModel: drafterName,
      verifierModel: verifierName,
      withQualityValidation: true,
      latencyMs: 0,
      totalCost: 0,
      drafterCost: 0,
      verifierCost: 0,
      savingsPercentage: 0,
      success: false,
      error: error.message,
    };
  }
}

async function benchmarkLCELChain(
  drafter: BaseChatModel,
  verifier: BaseChatModel
): Promise<BenchmarkResult> {
  const drafterName = analyzeModel(drafter).modelName;
  const verifierName = analyzeModel(verifier).modelName;

  try {
    const cascade = new CascadeWrapper({
      drafter,
      verifier,
      qualityThreshold: 0.7,
      enableCostTracking: true,
    });

    const chain = cascade.pipe(new StringOutputParser());

    const startTime = Date.now();
    const result = await chain.invoke('What is Rust in one sentence?');
    const latencyMs = Date.now() - startTime;

    const stats = cascade.getLastCascadeResult();

    return {
      testName: 'LCEL Chain',
      configuration: 'Pipe to StringOutputParser',
      drafterModel: drafterName,
      verifierModel: verifierName,
      withQualityValidation: true,
      qualityThreshold: 0.7,
      latencyMs,
      totalCost: stats?.totalCost || 0,
      drafterCost: stats?.drafterCost || 0,
      verifierCost: stats?.verifierCost || 0,
      savingsPercentage: stats?.savingsPercentage || 0,
      drafterQuality: stats?.drafterQuality,
      accepted: stats?.accepted,
      modelUsed: stats?.modelUsed,
      success: typeof result === 'string',
      responseLength: result.length,
      responsePreview: result.substring(0, 100),
    };
  } catch (error: any) {
    return {
      testName: 'LCEL Chain',
      configuration: 'Failed',
      drafterModel: drafterName,
      verifierModel: verifierName,
      withQualityValidation: true,
      latencyMs: 0,
      totalCost: 0,
      drafterCost: 0,
      verifierCost: 0,
      savingsPercentage: 0,
      success: false,
      error: error.message,
    };
  }
}

// ============================================================================
// Main Benchmark Runner
// ============================================================================

async function runComprehensiveBenchmark() {
  section('COMPREHENSIVE LANGCHAIN CASCADE BENCHMARK');

  // Discover available models
  const models = await discoverAvailableModels();

  // Get cascade pairs
  section('CASCADE PAIR DISCOVERY');
  const pairs = discoverCascadePairs(models);
  console.log(`Found ${pairs.length} valid cascade pairs\n`);

  pairs.forEach((pair, i) => {
    console.log(`Pair ${i + 1}:`);
    console.log(`  Drafter:  ${pair.analysis.drafterModel}`);
    console.log(`  Verifier: ${pair.analysis.verifierModel}`);
    console.log(`  Estimated savings: ${pair.analysis.estimatedSavings.toFixed(1)}%`);
    console.log();
  });

  // Run benchmarks for each pair
  for (const pair of pairs) {
    section(`TESTING: ${pair.analysis.drafterModel} → ${pair.analysis.verifierModel}`);

    // Test 1: Basic cascade with quality validation
    log(COLORS.blue, 'Test 1: Basic Cascade (WITH quality validation)...');
    const result1 = await benchmarkBasicCascade(pair.drafter, pair.verifier, true);
    results.push(result1);
    log(result1.success ? COLORS.green : COLORS.red,
      result1.success
        ? `✓ ${result1.latencyMs}ms, $${result1.totalCost.toFixed(6)}, ${result1.savingsPercentage.toFixed(1)}% savings, used ${result1.modelUsed}`
        : `✗ ${result1.error}`
    );

    // Test 2: Basic cascade without quality validation
    log(COLORS.blue, 'Test 2: Basic Cascade (WITHOUT quality validation)...');
    const result2 = await benchmarkBasicCascade(pair.drafter, pair.verifier, false);
    results.push(result2);
    log(result2.success ? COLORS.green : COLORS.red,
      result2.success
        ? `✓ ${result2.latencyMs}ms, $${result2.totalCost.toFixed(6)}, ${result2.savingsPercentage.toFixed(1)}% savings, used ${result2.modelUsed}`
        : `✗ ${result2.error}`
    );

    // Test 3: Streaming
    log(COLORS.blue, 'Test 3: Streaming...');
    const result3 = await benchmarkStreaming(pair.drafter, pair.verifier);
    results.push(result3);
    log(result3.success ? COLORS.green : COLORS.red,
      result3.success
        ? `✓ ${result3.latencyMs}ms, ${result3.configuration}, used ${result3.modelUsed}`
        : `✗ ${result3.error}`
    );

    // Test 4: Tool calling
    log(COLORS.blue, 'Test 4: Tool Calling...');
    const result4 = await benchmarkToolCalling(pair.drafter, pair.verifier);
    results.push(result4);
    log(result4.success ? COLORS.green : COLORS.red,
      result4.success
        ? `✓ ${result4.latencyMs}ms, ${result4.configuration}`
        : `✗ ${result4.error}`
    );

    // Test 5: Structured output
    log(COLORS.blue, 'Test 5: Structured Output...');
    const result5 = await benchmarkStructuredOutput(pair.drafter, pair.verifier);
    results.push(result5);
    log(result5.success ? COLORS.green : COLORS.red,
      result5.success
        ? `✓ ${result5.latencyMs}ms, extraction successful`
        : `✗ ${result5.error}`
    );

    // Test 6: Batch processing
    log(COLORS.blue, 'Test 6: Batch Processing...');
    const result6 = await benchmarkBatchProcessing(pair.drafter, pair.verifier);
    results.push(result6);
    log(result6.success ? COLORS.green : COLORS.red,
      result6.success
        ? `✓ ${result6.latencyMs}ms, ${result6.configuration}`
        : `✗ ${result6.error}`
    );

    // Test 7: LCEL chain
    log(COLORS.blue, 'Test 7: LCEL Chain...');
    const result7 = await benchmarkLCELChain(pair.drafter, pair.verifier);
    results.push(result7);
    log(result7.success ? COLORS.green : COLORS.red,
      result7.success
        ? `✓ ${result7.latencyMs}ms, ${result7.configuration}`
        : `✗ ${result7.error}`
    );
  }

  // ============================================================================
  // Results Analysis
  // ============================================================================

  section('BENCHMARK RESULTS SUMMARY');

  const successfulTests = results.filter(r => r.success);
  const failedTests = results.filter(r => !r.success);

  console.log(`Total tests: ${results.length}`);
  log(COLORS.green, `Successful: ${successfulTests.length}`);
  log(COLORS.red, `Failed: ${failedTests.length}`);
  console.log();

  // Group by test type
  const byTestType = results.reduce((acc, r) => {
    if (!acc[r.testName]) acc[r.testName] = [];
    acc[r.testName].push(r);
    return acc;
  }, {} as Record<string, BenchmarkResult[]>);

  for (const [testName, testResults] of Object.entries(byTestType)) {
    console.log(`\n${testName}:`);
    const successful = testResults.filter(r => r.success);
    const avgLatency = successful.reduce((sum, r) => sum + r.latencyMs, 0) / successful.length;
    const avgCost = successful.reduce((sum, r) => sum + r.totalCost, 0) / successful.length;
    const avgSavings = successful.reduce((sum, r) => sum + r.savingsPercentage, 0) / successful.length;

    console.log(`  Success rate: ${successful.length}/${testResults.length}`);
    if (successful.length > 0) {
      console.log(`  Avg latency: ${avgLatency.toFixed(0)}ms`);
      console.log(`  Avg cost: $${avgCost.toFixed(6)}`);
      console.log(`  Avg savings: ${avgSavings.toFixed(1)}%`);
    }
  }

  // Best performing pairs
  section('TOP PERFORMING CASCADE PAIRS');

  const pairPerformance = pairs.map(pair => {
    const pairResults = results.filter(
      r => r.drafterModel === pair.analysis.drafterModel &&
           r.verifierModel === pair.analysis.verifierModel &&
           r.success
    );

    const avgSavings = pairResults.reduce((sum, r) => sum + r.savingsPercentage, 0) / pairResults.length;
    const avgLatency = pairResults.reduce((sum, r) => sum + r.latencyMs, 0) / pairResults.length;
    const successRate = (pairResults.length / results.filter(
      r => r.drafterModel === pair.analysis.drafterModel &&
           r.verifierModel === pair.analysis.verifierModel
    ).length) * 100;

    return {
      pair: `${pair.analysis.drafterModel} → ${pair.analysis.verifierModel}`,
      avgSavings,
      avgLatency,
      successRate,
      tests: pairResults.length,
    };
  }).sort((a, b) => b.avgSavings - a.avgSavings);

  pairPerformance.forEach((perf, i) => {
    console.log(`${i + 1}. ${perf.pair}`);
    console.log(`   Avg savings: ${perf.avgSavings.toFixed(1)}%`);
    console.log(`   Avg latency: ${perf.avgLatency.toFixed(0)}ms`);
    console.log(`   Success rate: ${perf.successRate.toFixed(1)}%`);
    console.log(`   Tests passed: ${perf.tests}`);
    console.log();
  });

  // Detailed results table
  section('DETAILED RESULTS');

  console.log('Test Name'.padEnd(20) +
              'Config'.padEnd(25) +
              'Pair'.padEnd(35) +
              'Latency'.padEnd(12) +
              'Cost'.padEnd(12) +
              'Savings'.padEnd(10) +
              'Result');
  console.log('-'.repeat(140));

  for (const result of results) {
    const pair = `${result.drafterModel.substring(0, 15)} → ${result.verifierModel.substring(0, 15)}`;
    console.log(
      result.testName.padEnd(20) +
      (result.configuration || '').substring(0, 24).padEnd(25) +
      pair.padEnd(35) +
      `${result.latencyMs}ms`.padEnd(12) +
      `$${result.totalCost.toFixed(6)}`.padEnd(12) +
      `${result.savingsPercentage.toFixed(1)}%`.padEnd(10) +
      (result.success ? '✓' : `✗ ${result.error?.substring(0, 30)}`)
    );
  }

  // Export results to JSON
  const fs = await import('fs');
  const resultsFile = 'benchmark-results.json';
  fs.writeFileSync(resultsFile, JSON.stringify({
    timestamp: new Date().toISOString(),
    modelsAvailable: models.length,
    pairsTested: pairs.length,
    totalTests: results.length,
    successfulTests: successfulTests.length,
    failedTests: failedTests.length,
    results,
    pairPerformance,
  }, null, 2));

  log(COLORS.green, `\n✓ Results saved to ${resultsFile}`);

  section('BENCHMARK COMPLETE');
}

// Run the benchmark
runComprehensiveBenchmark().catch(console.error);
