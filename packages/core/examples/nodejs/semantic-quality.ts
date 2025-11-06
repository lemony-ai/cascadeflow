/**
 * cascadeflow - Semantic Quality Validation Example (TypeScript)
 *
 * This example demonstrates ML-based semantic quality validation using embeddings.
 * Semantic validation measures how well a model's response answers the user's query
 * by computing cosine similarity between embeddings.
 *
 * Features demonstrated:
 * - Semantic similarity scoring using embeddings (BGE-small-en-v1.5)
 * - Integration with cascadeflow's quality validation system
 * - Comparison with traditional confidence-based validation
 * - Request-scoped caching for 50% latency reduction
 * - Graceful degradation when ML dependencies not installed
 *
 * Requirements:
 *     - @cascadeflow/core
 *     - @cascadeflow/ml (for embeddings)
 *     - @xenova/transformers (ONNX runtime for embeddings)
 *     - OpenAI API key
 *
 * Setup:
 *     npm install @cascadeflow/core @cascadeflow/ml @xenova/transformers
 *     export OPENAI_API_KEY="your-key-here"
 *     npx tsx semantic-quality.ts
 *
 * What You'll Learn:
 *     1. How to enable semantic quality validation
 *     2. How semantic similarity complements confidence scoring
 *     3. When semantic validation catches low-quality responses
 *     4. How to configure semantic thresholds
 *     5. Performance impact and caching benefits
 *
 * Expected Output:
 *     - Demonstration of semantic similarity scores
 *     - Comparison with/without semantic validation
 *     - Examples of caught off-topic responses
 *     - Performance metrics with caching
 *
 * Model Details:
 *     - Embedding Model: BGE-small-en-v1.5 (~40MB, ONNX)
 *     - Runs entirely locally (no API calls for embeddings)
 *     - Auto-downloads on first use
 *     - Fast inference (~50-100ms per embedding pair with caching)
 *
 * Documentation:
 *     For more details, see:
 *     docs/guides/custom_validation.md
 */

import { CascadeAgent, SemanticQualityChecker, type ModelConfig } from '@cascadeflow/core';

interface TestCase {
  query: string;
  expectedBehavior: string;
  description: string;
}

async function main() {
  console.log('='.repeat(80));
  console.log('🧠 CASCADEFLOW - SEMANTIC QUALITY VALIDATION');
  console.log('='.repeat(80));
  console.log();
  console.log('This example demonstrates ML-based semantic quality validation.');
  console.log('Semantic validation uses embeddings to measure how well responses');
  console.log('answer the original query, catching off-topic or irrelevant answers.');
  console.log();

  // ========================================================================
  // STEP 1: Check ML Availability
  // ========================================================================

  console.log('📋 Step 1: Checking ML dependencies...');
  console.log();

  const semanticChecker = new SemanticQualityChecker();
  const mlAvailable = await semanticChecker.isAvailable();

  if (!mlAvailable) {
    console.log('❌ ML dependencies not available!');
    console.log();
    console.log('To use semantic validation, install:');
    console.log('   npm install @cascadeflow/ml @xenova/transformers');
    console.log();
    console.log('The BGE-small-en-v1.5 model (~40MB) will auto-download on first use.');
    console.log();
    return;
  }

  console.log('✅ ML dependencies available!');
  console.log('   Embedding Model: BGE-small-en-v1.5 (ONNX)');
  console.log('   Model Size: ~40MB');
  console.log('   Inference: CPU-based, fully local');
  console.log();

  // ========================================================================
  // STEP 2: Test Semantic Similarity Directly
  // ========================================================================

  console.log('📝 Step 2: Testing semantic similarity directly...\n');

  const testPairs = [
    {
      query: 'What is machine learning?',
      response: 'Machine learning is a subset of AI that enables systems to learn from data.',
      expected: 'HIGH',
    },
    {
      query: 'What is machine learning?',
      response: 'Python is a programming language.',
      expected: 'LOW',
    },
    {
      query: 'How do I reverse a string in Python?',
      response: 'You can use [::-1] slice notation to reverse a string in Python.',
      expected: 'HIGH',
    },
    {
      query: 'How do I reverse a string in Python?',
      response: 'JavaScript is used for web development.',
      expected: 'LOW',
    },
  ];

  console.log('Testing similarity on example query-response pairs:');
  console.log();

  for (const pair of testPairs) {
    const result = await semanticChecker.checkSimilarity(pair.query, pair.response);

    const icon = result.passed ? '✅' : '❌';
    const status = result.passed ? 'PASSED' : 'FAILED';

    console.log('─'.repeat(80));
    console.log(`${icon} Semantic Check ${status}`);
    console.log('─'.repeat(80));
    console.log(`Query:    "${pair.query}"`);
    console.log(`Response: "${pair.response}"`);
    console.log(`Similarity: ${(result.similarity * 100).toFixed(1)}%`);
    console.log(`Expected:   ${pair.expected} similarity`);
    console.log();
  }

  // ========================================================================
  // STEP 3: Configure Cascade with Semantic Validation
  // ========================================================================

  console.log('📋 Step 3: Configuring cascade with semantic validation...');
  console.log();

  const models: ModelConfig[] = [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.000375,
    },
    {
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.00625,
    },
  ];

  // Create two agents for comparison
  const agentWithoutSemantic = new CascadeAgent({
    models,
    quality: {
      threshold: 0.40,
      requireMinimumTokens: 5,
      useSemanticValidation: false, // Traditional validation only
    },
  });

  const agentWithSemantic = new CascadeAgent({
    models,
    quality: {
      threshold: 0.40,
      requireMinimumTokens: 5,
      useSemanticValidation: true, // Enable ML semantic validation
      semanticThreshold: 0.5, // 50% minimum similarity
    },
  });

  console.log('   ✅ Agent 1: Traditional validation (confidence + heuristics)');
  console.log('   ✅ Agent 2: Enhanced validation (+ semantic similarity)');
  console.log();

  // ========================================================================
  // STEP 4: Test with Various Queries
  // ========================================================================

  console.log('📝 Step 4: Testing queries with both validation modes...\n');

  const testCases: TestCase[] = [
    {
      query: 'Explain what TypeScript is',
      expectedBehavior: 'Both should pass (on-topic response)',
      description: 'Standard factual question',
    },
    {
      query: 'What are the key differences between React and Vue?',
      expectedBehavior: 'Both should pass (on-topic response)',
      description: 'Comparison question',
    },
    {
      query: 'How does async/await work in JavaScript?',
      expectedBehavior: 'Both should pass (technical explanation)',
      description: 'Technical concept explanation',
    },
  ];

  for (let i = 0; i < testCases.length; i++) {
    const testCase = testCases[i];

    console.log('='.repeat(80));
    console.log(`Test Case ${i + 1}/${testCases.length}`);
    console.log('='.repeat(80));
    console.log(`Query: "${testCase.query}"`);
    console.log(`Expected: ${testCase.expectedBehavior}`);
    console.log(`Type: ${testCase.description}`);
    console.log();

    // Test without semantic validation
    console.log('🔵 Testing WITHOUT semantic validation:');
    const result1 = await agentWithoutSemantic.run(testCase.query, { maxTokens: 150 });

    console.log(`   Model: ${result1.modelUsed}`);
    console.log(`   Cost: $${result1.totalCost.toFixed(6)}`);
    console.log(`   Latency: ${result1.latencyMs}ms`);
    console.log(`   Response: ${result1.content.substring(0, 100)}...`);
    console.log();

    // Test with semantic validation
    console.log('🟢 Testing WITH semantic validation:');
    const startTime = Date.now();
    const result2 = await agentWithSemantic.run(testCase.query, { maxTokens: 150 });
    const totalTime = Date.now() - startTime;

    console.log(`   Model: ${result2.modelUsed}`);
    console.log(`   Cost: $${result2.totalCost.toFixed(6)}`);
    console.log(`   Latency: ${result2.latencyMs}ms`);

    // Show semantic validation details if available
    if (result2.draftMetadata?.quality?.details?.semanticSimilarity !== undefined) {
      const semScore = result2.draftMetadata.quality.details.semanticSimilarity;
      console.log(`   Semantic Similarity: ${(semScore * 100).toFixed(1)}%`);
    }

    console.log(`   Response: ${result2.content.substring(0, 100)}...`);
    console.log();

    // Compare
    const behaviorMatch =
      result1.modelUsed === result2.modelUsed ? 'SAME' : 'DIFFERENT';
    console.log(`📊 Comparison: Models used are ${behaviorMatch}`);
    console.log();
  }

  // ========================================================================
  // STEP 5: Performance Analysis
  // ========================================================================

  console.log('='.repeat(80));
  console.log('⚡ PERFORMANCE ANALYSIS');
  console.log('='.repeat(80));
  console.log();

  console.log('💡 Semantic Validation Performance:');
  console.log('   • Embedding inference: ~50-100ms per query-response pair');
  console.log('   • Request-scoped caching: 50% latency reduction on cache hits');
  console.log('   • Fully local: No external API calls required');
  console.log('   • Model size: ~40MB (auto-downloads once)');
  console.log('   • CPU-based: Works without GPU');
  console.log();

  console.log('📊 When to Use Semantic Validation:');
  console.log('   ✅ You want to catch off-topic responses');
  console.log('   ✅ Quality is more important than speed');
  console.log('   ✅ You have queries where relevance matters');
  console.log('   ✅ You want to reduce hallucinations');
  console.log();

  console.log('⚠️  When to Skip Semantic Validation:');
  console.log('   • Ultra-low latency requirements (<100ms)');
  console.log('   • Simple queries where confidence scores suffice');
  console.log('   • Resource-constrained environments');
  console.log('   • You want minimal dependencies');
  console.log();

  // ========================================================================
  // STEP 6: Configuration Examples
  // ========================================================================

  console.log('='.repeat(80));
  console.log('⚙️  CONFIGURATION EXAMPLES');
  console.log('='.repeat(80));
  console.log();

  console.log('📝 Basic Setup (default):');
  console.log(`
  const agent = new CascadeAgent({
    models: [...],
    quality: {
      useSemanticValidation: true,  // Enable ML validation
      semanticThreshold: 0.5,        // 50% minimum similarity
    },
  });
  `);

  console.log('📝 Strict Quality (higher threshold):');
  console.log(`
  const agent = new CascadeAgent({
    models: [...],
    quality: {
      useSemanticValidation: true,
      semanticThreshold: 0.7,  // 70% minimum (stricter)
      threshold: 0.7,          // Also increase confidence threshold
    },
  });
  `);

  console.log('📝 Performance-Optimized (lower threshold):');
  console.log(`
  const agent = new CascadeAgent({
    models: [...],
    quality: {
      useSemanticValidation: true,
      semanticThreshold: 0.3,  // 30% minimum (more lenient)
    },
  });
  `);

  console.log('📝 Using SemanticQualityChecker directly:');
  console.log(`
  import { SemanticQualityChecker } from '@cascadeflow/core';

  const checker = new SemanticQualityChecker(0.5); // threshold

  if (await checker.isAvailable()) {
    const result = await checker.checkSimilarity(
      'What is TypeScript?',
      'TypeScript is a typed superset of JavaScript.'
    );

    console.log(\`Similarity: \${result.similarity}\`);
    console.log(\`Passed: \${result.passed}\`);
  }
  `);

  // ========================================================================
  // STEP 7: Key Takeaways
  // ========================================================================

  console.log('='.repeat(80));
  console.log('🎯 KEY TAKEAWAYS');
  console.log('='.repeat(80));
  console.log();

  console.log('✅ What You Learned:');
  console.log('   1. Semantic validation uses embeddings to measure response relevance');
  console.log('   2. It complements traditional confidence-based validation');
  console.log('   3. Helps catch off-topic or hallucinated responses');
  console.log('   4. Fully local inference (no external API calls)');
  console.log('   5. Gracefully degrades when ML dependencies not installed');
  console.log('   6. Request-scoped caching provides 50% latency improvement');
  console.log();

  console.log('🚀 Next Steps:');
  console.log('   • Experiment with different semantic thresholds');
  console.log('   • Combine with alignment scoring for best results');
  console.log('   • Test on your own domain-specific queries');
  console.log('   • Monitor semantic scores in production');
  console.log('   • Consider disabling for latency-critical paths');
  console.log();

  console.log('📚 Resources:');
  console.log('   • Custom Validation Guide: docs/guides/custom_validation.md');
  console.log('   • ML Package: packages/ml/README.md');
  console.log('   • API Reference: docs/api/');
  console.log('   • GitHub: https://github.com/lemony-ai/cascadeflow');
  console.log();

  console.log('='.repeat(80));
}

main().catch(console.error);
