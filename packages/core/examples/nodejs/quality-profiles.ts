/**
 * Example: Quality Profiles
 *
 * Demonstrates the different quality validation profiles:
 * - strict(): Highest quality thresholds with semantic validation
 * - forProduction(): Production-ready with multi-signal confidence
 * - forDevelopment(): Lenient thresholds for development
 * - forCascade(): Optimized for 50-60% acceptance rate
 * - permissive(): Most lenient for maximum throughput
 *
 * Run: npx tsx examples/nodejs/quality-profiles.ts
 */

import { CascadeAgent, QualityValidator } from '@cascadeflow/core';

async function main() {
  console.log('🎯 Quality Profiles Example\n');

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

  // ============================================================================
  // 1. Strict Mode - Maximum Quality
  // ============================================================================
  console.log('📊 1. Strict Mode (Maximum Quality)');
  console.log('   - Highest thresholds');
  console.log('   - Semantic validation enabled');
  console.log('   - Production confidence estimator\n');

  const strictAgent = new CascadeAgent({
    models,
    quality: {
      useProductionConfidence: true,
      strictMode: true,
      useSemanticValidation: true,
      minConfidence: 0.85,
      provider: 'openai',
    },
  });

  try {
    const strictResult = await strictAgent.run(
      'What is TypeScript and why should I use it?'
    );
    console.log(`   ✅ Response accepted (${strictResult.modelUsed})`);
    console.log(`   💰 Cost: $${strictResult.totalCost.toFixed(6)}`);
    console.log(`   📈 Quality: ${strictResult.qualityCheckPassed !== undefined ? (strictResult.qualityCheckPassed ? 'PASSED' : 'REJECTED') : 'N/A'}${strictResult.qualityScore !== undefined ? ` (score: ${strictResult.qualityScore.toFixed(2)})` : ''}`);
  } catch (error) {
    console.log(`   ❌ Error: ${error instanceof Error ? error.message : error}`);
  }

  console.log();

  // ============================================================================
  // 2. Production Mode - Balanced Quality
  // ============================================================================
  console.log('🏭 2. Production Mode (Balanced Quality)');
  console.log('   - Moderate to high thresholds');
  console.log('   - Multi-signal confidence estimation');
  console.log('   - Alignment scoring enabled\n');

  const prodAgent = new CascadeAgent({
    models,
    quality: {
      useProductionConfidence: true,
      minConfidence: 0.73,
      provider: 'openai',
    },
  });

  try {
    const prodResult = await prodAgent.run(
      'Explain the benefits of static typing.'
    );
    console.log(`   ✅ Response accepted (${prodResult.modelUsed})`);
    console.log(`   💰 Cost: $${prodResult.totalCost.toFixed(6)}`);
    console.log(`   📈 Quality: ${prodResult.qualityCheckPassed !== undefined ? (prodResult.qualityCheckPassed ? 'PASSED' : 'REJECTED') : 'N/A'}${prodResult.qualityScore !== undefined ? ` (score: ${prodResult.qualityScore.toFixed(2)})` : ''}`);
  } catch (error) {
    console.log(`   ❌ Error: ${error instanceof Error ? error.message : error}`);
  }

  console.log();

  // ============================================================================
  // 3. Development Mode - Lenient Quality
  // ============================================================================
  console.log('🔧 3. Development Mode (Lenient Quality)');
  console.log('   - Lower thresholds for faster iteration');
  console.log('   - Good for testing and development\n');

  const devAgent = new CascadeAgent({
    models,
    quality: {
      minConfidence: 0.60,
      requireMinimumTokens: 5,
    },
  });

  try {
    const devResult = await devAgent.run('What is a compiler?');
    console.log(`   ✅ Response accepted (${devResult.modelUsed})`);
    console.log(`   💰 Cost: $${devResult.totalCost.toFixed(6)}`);
    console.log(`   📈 Quality: ${devResult.qualityCheckPassed !== undefined ? (devResult.qualityCheckPassed ? 'PASSED' : 'REJECTED') : 'N/A'}${devResult.qualityScore !== undefined ? ` (score: ${devResult.qualityScore.toFixed(2)})` : ''}`);
  } catch (error) {
    console.log(`   ❌ Error: ${error instanceof Error ? error.message : error}`);
  }

  console.log();

  // ============================================================================
  // 4. Cascade Mode - Optimized Acceptance Rate
  // ============================================================================
  console.log('⚡ 4. Cascade Mode (50-60% Acceptance)');
  console.log('   - Optimized for cascade performance');
  console.log('   - Semantic validation disabled for speed');
  console.log('   - Relaxed thresholds\n');

  const cascadeAgent = new CascadeAgent({
    models,
    quality: {
      minConfidence: 0.55,
      requireMinimumTokens: 5,
      useSemanticValidation: false,
    },
  });

  try {
    const cascadeResult = await cascadeAgent.run(
      'What are the key features of modern programming languages?'
    );
    console.log(`   ✅ Response accepted (${cascadeResult.modelUsed})`);
    console.log(`   💰 Cost: $${cascadeResult.totalCost.toFixed(6)}`);
    console.log(`   📈 Quality: ${cascadeResult.qualityCheckPassed !== undefined ? (cascadeResult.qualityCheckPassed ? 'PASSED' : 'REJECTED') : 'N/A'}${cascadeResult.qualityScore !== undefined ? ` (score: ${cascadeResult.qualityScore.toFixed(2)})` : ''}`);
    console.log(`   🎯 Draft accepted: ${cascadeResult.draftAccepted}`);
  } catch (error) {
    console.log(`   ❌ Error: ${error instanceof Error ? error.message : error}`);
  }

  console.log();

  // ============================================================================
  // 5. Permissive Mode - Maximum Throughput
  // ============================================================================
  console.log('🚀 5. Permissive Mode (Maximum Throughput)');
  console.log('   - Lowest thresholds');
  console.log('   - Accept almost all responses');
  console.log('   - Best for high-volume scenarios\n');

  const permissiveAgent = new CascadeAgent({
    models,
    quality: {
      minConfidence: 0.40,
      requireMinimumTokens: 3,
      useSemanticValidation: false,
    },
  });

  try {
    const permissiveResult = await permissiveAgent.run('Define API.');
    console.log(`   ✅ Response accepted (${permissiveResult.modelUsed})`);
    console.log(`   💰 Cost: $${permissiveResult.totalCost.toFixed(6)}`);
    console.log(`   📈 Quality: ${permissiveResult.qualityCheckPassed !== undefined ? (permissiveResult.qualityCheckPassed ? 'PASSED' : 'REJECTED') : 'N/A'}${permissiveResult.qualityScore !== undefined ? ` (score: ${permissiveResult.qualityScore.toFixed(2)})` : ''}`);
    console.log(`   🎯 Draft accepted: ${permissiveResult.draftAccepted}`);
  } catch (error) {
    console.log(`   ❌ Error: ${error instanceof Error ? error.message : error}`);
  }

  console.log();

  // ============================================================================
  // 6. Using Factory Methods
  // ============================================================================
  console.log('🏗️  6. Using QualityValidator Factory Methods\n');

  const strictValidator = QualityValidator.strict();
  const prodValidator = QualityValidator.forProduction();
  const devValidator = QualityValidator.forDevelopment();
  const cascadeValidator = QualityValidator.forCascade();
  const permissiveValidator = QualityValidator.permissive();

  console.log('   Validator Configs:');
  console.log(`   - Strict:      minConfidence=${strictValidator.getConfig().minConfidence}`);
  console.log(`   - Production:  minConfidence=${prodValidator.getConfig().minConfidence}`);
  console.log(`   - Development: minConfidence=${devValidator.getConfig().minConfidence}`);
  console.log(`   - Cascade:     minConfidence=${cascadeValidator.getConfig().minConfidence}`);
  console.log(`   - Permissive:  minConfidence=${permissiveValidator.getConfig().minConfidence}`);

  console.log('\n✅ Example complete!');
}

main().catch(console.error);
