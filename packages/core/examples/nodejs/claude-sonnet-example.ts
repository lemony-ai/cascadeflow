/**
 * Claude 4.5 Sonnet Example - Premium Coding via OpenRouter
 *
 * This example demonstrates using Anthropic's Claude 4.5 Sonnet through OpenRouter.
 * Claude 4.5 Sonnet is the #1 ranked model for programming tasks and accounts for
 * 15% of all OpenRouter traffic.
 *
 * Perfect for:
 * - Complex code generation
 * - Code review and refactoring
 * - Architecture design
 * - Production-quality code
 * - Advanced reasoning tasks
 *
 * Requirements:
 *   - Node.js 18+
 *   - @cascadeflow/core
 *   - OpenRouter API key (get from https://openrouter.ai/keys)
 *
 * Setup:
 *   npm install @cascadeflow/core
 *   export OPENROUTER_API_KEY="your-key"
 *   npx tsx claude-sonnet-example.ts
 */

import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

async function main() {
  console.log('='.repeat(80));
  console.log('🧠 CLAUDE 4.5 SONNET - PREMIUM AI CODING ASSISTANT');
  console.log('='.repeat(80));
  console.log();

  // Check for OpenRouter API key
  if (!process.env.OPENROUTER_API_KEY) {
    console.error('❌ OPENROUTER_API_KEY environment variable is required');
    console.error('');
    console.error('Get your API key: https://openrouter.ai/keys');
    console.error('Then run: export OPENROUTER_API_KEY="your-key"');
    process.exit(1);
  }

  console.log('🔑 API Key Status:');
  console.log('   ✅ OpenRouter API key found');
  console.log();

  console.log('🤖 Model: anthropic/claude-4.5-sonnet-20250929');
  console.log('   Provider: Anthropic (via OpenRouter)');
  console.log('   Cost: $3/$15 per 1M tokens');
  console.log('   Usage: 15.0% of all OpenRouter traffic');
  console.log('   Rank: #1 for programming tasks (October 2025)');
  console.log('   Best for: Complex coding, architecture, production code');
  console.log();

  // ========================================================================
  // Example 1: Complex Algorithm Implementation
  // ========================================================================

  console.log('='.repeat(80));
  console.log('📝 EXAMPLE 1: Complex Algorithm Implementation');
  console.log('='.repeat(80));
  console.log();

  const agent = new CascadeAgent({
    models: [
      {
        name: 'anthropic/claude-4.5-sonnet-20250929',
        provider: 'openrouter',
        cost: 0.003,
        apiKey: process.env.OPENROUTER_API_KEY,
      },
    ],
  });

  console.log('Query: "Implement a thread-safe LRU cache with O(1) operations in TypeScript"\n');

  const startTime1 = Date.now();
  const result1 = await agent.run(
    'Implement a thread-safe LRU cache in TypeScript with O(1) get and put operations. ' +
    'Include proper type definitions, error handling, and comprehensive comments.'
  );
  const elapsed1 = Date.now() - startTime1;

  console.log('✅ Implementation:');
  console.log('-'.repeat(80));
  console.log(result1.content);
  console.log('-'.repeat(80));
  console.log();
  console.log('📊 Metrics:');
  console.log(`   Model: ${result1.modelUsed}`);
  console.log(`   Tokens: ${result1.promptTokens} in / ${result1.completionTokens} out`);
  console.log(`   Latency: ${elapsed1}ms`);
  console.log(`   Cost: $${result1.totalCost.toFixed(6)}`);
  console.log();

  // ========================================================================
  // Example 2: Code Review and Refactoring
  // ========================================================================

  console.log('='.repeat(80));
  console.log('📝 EXAMPLE 2: Code Review and Refactoring');
  console.log('='.repeat(80));
  console.log();

  const codeToReview = `
class UserManager {
  constructor() {
    this.users = [];
  }

  addUser(name, email) {
    this.users.push({ name: name, email: email });
  }

  findUser(email) {
    for (let i = 0; i < this.users.length; i++) {
      if (this.users[i].email == email) {
        return this.users[i];
      }
    }
    return null;
  }

  deleteUser(email) {
    for (let i = 0; i < this.users.length; i++) {
      if (this.users[i].email == email) {
        this.users.splice(i, 1);
        break;
      }
    }
  }
}
`;

  console.log('Query: "Review and refactor this code for production quality"');
  console.log('Code to review:');
  console.log(codeToReview);
  console.log();

  const startTime2 = Date.now();
  const result2 = await agent.run(
    `Review this code and provide a production-quality refactored version:\n\n${codeToReview}\n\n` +
    `Include:\n` +
    `1. Type safety improvements\n` +
    `2. Better performance\n` +
    `3. Error handling\n` +
    `4. Modern ES6+ features\n` +
    `5. Best practices`
  );
  const elapsed2 = Date.now() - startTime2;

  console.log('✅ Review & Refactored Code:');
  console.log('-'.repeat(80));
  console.log(result2.content);
  console.log('-'.repeat(80));
  console.log();
  console.log('📊 Metrics:');
  console.log(`   Tokens: ${result2.promptTokens} in / ${result2.completionTokens} out`);
  console.log(`   Latency: ${elapsed2}ms`);
  console.log(`   Cost: $${result2.totalCost.toFixed(6)}`);
  console.log();

  // ========================================================================
  // Example 3: System Architecture Design
  // ========================================================================

  console.log('='.repeat(80));
  console.log('📝 EXAMPLE 3: System Architecture Design');
  console.log('='.repeat(80));
  console.log();

  console.log('Query: "Design a scalable microservices architecture for an e-commerce platform"\n');

  const startTime3 = Date.now();
  const result3 = await agent.run(
    'Design a scalable microservices architecture for an e-commerce platform. Include:\n' +
    '1. Service breakdown and responsibilities\n' +
    '2. Communication patterns\n' +
    '3. Data storage strategies\n' +
    '4. Scaling considerations\n' +
    '5. Key technology choices'
  );
  const elapsed3 = Date.now() - startTime3;

  console.log('✅ Architecture Design:');
  console.log('-'.repeat(80));
  console.log(result3.content);
  console.log('-'.repeat(80));
  console.log();
  console.log('📊 Metrics:');
  console.log(`   Tokens: ${result3.promptTokens} in / ${result3.completionTokens} out`);
  console.log(`   Latency: ${elapsed3}ms`);
  console.log(`   Cost: $${result3.totalCost.toFixed(6)}`);
  console.log();

  // ========================================================================
  // Example 4: Advanced Debugging
  // ========================================================================

  console.log('='.repeat(80));
  console.log('📝 EXAMPLE 4: Advanced Debugging');
  console.log('='.repeat(80));
  console.log();

  const buggyAsyncCode = `
async function processOrders(orders) {
  const results = [];

  for (const order of orders) {
    setTimeout(async () => {
      const processed = await processOrder(order);
      results.push(processed);
    }, 0);
  }

  return results;
}

async function processOrder(order) {
  // Simulated async processing
  return new Promise((resolve) => {
    setTimeout(() => resolve({ ...order, processed: true }), 100);
  });
}
`;

  console.log('Query: "Find and fix all bugs in this async code"');
  console.log('Buggy Code:');
  console.log(buggyAsyncCode);
  console.log();

  const startTime4 = Date.now();
  const result4 = await agent.run(
    `Find and fix all bugs in this async code:\n\n${buggyAsyncCode}\n\n` +
    `Provide:\n` +
    `1. Explanation of each bug\n` +
    `2. Corrected version\n` +
    `3. Best practices for async JavaScript`
  );
  const elapsed4 = Date.now() - startTime4;

  console.log('✅ Debugging Solution:');
  console.log('-'.repeat(80));
  console.log(result4.content);
  console.log('-'.repeat(80));
  console.log();
  console.log('📊 Metrics:');
  console.log(`   Tokens: ${result4.promptTokens} in / ${result4.completionTokens} out`);
  console.log(`   Latency: ${elapsed4}ms`);
  console.log(`   Cost: $${result4.totalCost.toFixed(6)}`);
  console.log();

  // ========================================================================
  // Summary
  // ========================================================================

  const totalCost = result1.totalCost + result2.totalCost + result3.totalCost + result4.totalCost;
  const totalTokens = result1.promptTokens + result1.completionTokens +
                      result2.promptTokens + result2.completionTokens +
                      result3.promptTokens + result3.completionTokens +
                      result4.promptTokens + result4.completionTokens;
  const totalTime = elapsed1 + elapsed2 + elapsed3 + elapsed4;

  console.log('='.repeat(80));
  console.log('📊 SESSION SUMMARY');
  console.log('='.repeat(80));
  console.log();
  console.log('✅ Completed 4 advanced coding tasks');
  console.log(`   Total tokens used: ${totalTokens.toLocaleString()}`);
  console.log(`   Total time: ${totalTime}ms`);
  console.log(`   Total cost: $${totalCost.toFixed(6)}`);
  console.log();
  console.log('💡 Why Claude 4.5 Sonnet?');
  console.log('   • #1 ranked for programming (October 2025)');
  console.log('   • Superior code quality and reasoning');
  console.log('   • Extended thinking for complex problems');
  console.log('   • 200K token context window');
  console.log('   • 15% of OpenRouter traffic (highly trusted)');
  console.log('   • Great balance of cost and quality ($3/$15 per 1M)');
  console.log();
  console.log('💰 Cost Optimization Tip:');
  console.log('   Combine with free models in a cascade:');
  console.log('   1. Try Grok Code Fast (FREE) first');
  console.log('   2. Fall back to Claude Sonnet for complex tasks');
  console.log('   → Save up to 80% while maintaining quality!');
  console.log();
  console.log('🚀 Next Steps:');
  console.log('   • Try cascade with Grok → Claude');
  console.log('   • Explore Claude Opus 4 for even better coding');
  console.log('   • Check OpenRouter rankings: https://openrouter.ai/rankings');
  console.log();
}

main().catch(console.error);
