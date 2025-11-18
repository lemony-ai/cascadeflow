/**
 * cascadeflow - Rate Limiting Example (TypeScript)
 *
 * Demonstrates per-user and per-tier rate limiting with the sliding window algorithm.
 *
 * This example shows:
 * - Rate limiting by user tier (FREE, STARTER, PRO, etc.)
 * - Hourly and daily request limits
 * - Budget-based rate limiting
 * - Sliding window algorithm
 * - Custom limits per user
 * - Rate limit statistics
 *
 * Requirements:
 *   - Node.js 18+
 *   - @cascadeflow/core
 *   - OpenAI API key
 *
 * Setup:
 *   npm install @cascadeflow/core
 *   export OPENAI_API_KEY="your-key-here"
 *   npx tsx rate-limiting-usage.ts
 */

import {
  CascadeAgent,
  RateLimiter,
  createUserProfile,
  type UserProfile,
  type TierLevel,
} from '@cascadeflow/core';

async function main() {
  console.log('='.repeat(60));
  console.log('cascadeflow - Rate Limiting');
  console.log('='.repeat(60));

  // ========================================================================
  // Example 1: Basic rate limiting with FREE tier
  // ========================================================================
  console.log('\n1. FREE tier rate limiting (10 req/hour, 100 req/day)');
  console.log('-'.repeat(60));

  // Create FREE tier profile
  const freeProfile = createUserProfile('FREE' as TierLevel, 'free_user');

  console.log(`Tier: ${freeProfile.tier.name}`);
  console.log(`Hourly limit: ${freeProfile.tier.requestsPerHour}`);
  console.log(`Daily limit: ${freeProfile.tier.requestsPerDay}`);
  console.log(`Daily budget: $${freeProfile.tier.dailyBudget}`);

  // Initialize rate limiter
  const limiter = new RateLimiter();

  // Create agent
  const agent = new CascadeAgent({
    models: [
      {
        name: 'gpt-4o-mini',
        provider: 'openai',
        cost: 0.00015,
      },
      {
        name: 'gpt-4o',
        provider: 'openai',
        cost: 0.00625,
      },
    ],
  });

  // Make some requests
  console.log('\nMaking 5 requests...');
  for (let i = 0; i < 5; i++) {
    try {
      // Check rate limit before making request
      await limiter.checkRateLimit(freeProfile);

      // Make request
      const result = await agent.run(`What is ${i + 1} + ${i + 1}?`);

      // Record the request
      await limiter.recordRequest(freeProfile.userId, result.totalCost);

      console.log(`  Request ${i + 1}: OK - Cost: $${result.totalCost.toFixed(6)}`);
    } catch (err: any) {
      console.log(`  Request ${i + 1}: BLOCKED - ${err.message}`);
      if (err.retryAfterSeconds) {
        console.log(`    Retry after: ${err.retryAfterSeconds}s`);
      }
    }
  }

  // Check usage stats
  const stats = limiter.getUsageStats(freeProfile.userId, freeProfile);
  console.log('\nUsage stats:');
  console.log(`  Hourly: ${stats.hourly.used}/${freeProfile.tier.requestsPerHour}`);
  console.log(`  Daily: ${stats.daily.used}/${freeProfile.tier.requestsPerDay}`);
  console.log(`  Cost: $${stats.cost.used.toFixed(6)}/$${freeProfile.tier.dailyBudget}`);

  // ========================================================================
  // Example 2: Rate limit enforcement
  // ========================================================================
  console.log('\n2. Rate limit enforcement demo');
  console.log('-'.repeat(60));

  // Create profile with very low limits
  const testProfile = createUserProfile('FREE' as TierLevel, 'test_user', {
    customRequestsPerHour: 3, // Only 3 requests per hour
    customDailyBudget: 0.01, // Very low budget
  });

  console.log(
    `Custom limits: ${testProfile.customRequestsPerHour} req/hour, $${testProfile.customDailyBudget} budget`
  );

  // Try to exceed hourly limit
  console.log('\nAttempting 5 requests (limit is 3)...');
  let requestCount = 0;
  let blockedCount = 0;

  for (let i = 0; i < 5; i++) {
    try {
      await limiter.checkRateLimit(testProfile);

      const result = await agent.run(`Simple test ${i + 1}`);
      await limiter.recordRequest(testProfile.userId, result.totalCost);

      requestCount++;
      console.log(`  Request ${i + 1}: OK`);
    } catch (err: any) {
      blockedCount++;
      console.log(`  Request ${i + 1}: BLOCKED - ${err.message}`);
    }
  }

  console.log(`\nSummary: ${requestCount} allowed, ${blockedCount} blocked`);

  // ========================================================================
  // Example 3: Different tier levels
  // ========================================================================
  console.log('\n3. Comparing tier levels');
  console.log('-'.repeat(60));

  const tiers: TierLevel[] = ['FREE', 'STARTER', 'PRO', 'BUSINESS', 'ENTERPRISE'];

  console.log('\nTier comparison:');
  console.log('Tier'.padEnd(15), 'Hourly'.padEnd(10), 'Daily'.padEnd(10), 'Budget');
  console.log('-'.repeat(60));

  for (const tier of tiers) {
    const profile = createUserProfile(tier, `${tier.toLowerCase()}_user`);

    console.log(
      tier.padEnd(15),
      profile.tier.requestsPerHour?.toString().padEnd(10) || 'unlimited',
      profile.tier.requestsPerDay?.toString().padEnd(10) || 'unlimited',
      profile.tier.dailyBudget !== undefined ? `$${profile.tier.dailyBudget}` : 'unlimited'
    );
  }

  // ========================================================================
  // Example 4: Budget-based rate limiting
  // ========================================================================
  console.log('\n4. Budget-based rate limiting');
  console.log('-'.repeat(60));

  const budgetProfile = createUserProfile('STARTER' as TierLevel, 'budget_user', {
    customDailyBudget: 0.005, // Very small budget for demonstration
  });

  console.log(`Daily budget: $${budgetProfile.customDailyBudget}`);
  console.log('\nMaking requests until budget exhausted...');

  let totalSpent = 0;
  let successfulRequests = 0;

  for (let i = 0; i < 10; i++) {
    try {
      // Estimate cost before request
      const estimatedCost = 0.002; // Rough estimate
      await limiter.checkRateLimit(budgetProfile, estimatedCost);

      const result = await agent.run(`Test query ${i + 1}`);
      await limiter.recordRequest(budgetProfile.userId, result.totalCost);

      totalSpent += result.totalCost;
      successfulRequests++;

      console.log(
        `  Request ${i + 1}: OK - Cost: $${result.totalCost.toFixed(6)} (Total: $${totalSpent.toFixed(6)})`
      );
    } catch (err: any) {
      console.log(`  Request ${i + 1}: BLOCKED - ${err.message}`);
      console.log(`  Budget exhausted after ${successfulRequests} requests`);
      break;
    }
  }

  const budgetStats = limiter.getUsageStats(budgetProfile.userId, budgetProfile);
  console.log(`\nFinal stats: $${budgetStats.cost.used.toFixed(6)}/$${budgetProfile.customDailyBudget}`);

  // ========================================================================
  // Example 5: Reset and cleanup
  // ========================================================================
  console.log('\n5. Reset and cleanup');
  console.log('-'.repeat(60));

  // Get stats before reset
  const beforeReset = limiter.getUsageStats(freeProfile.userId, freeProfile);
  console.log(`Before reset: ${beforeReset.hourly.used} hourly requests`);

  // Reset user's limits
  limiter.resetUser(freeProfile.userId);

  // Check stats after reset
  const afterReset = limiter.getUsageStats(freeProfile.userId, freeProfile);
  console.log(`After reset:  ${afterReset.hourly.used} hourly requests`);

  // Cleanup
  limiter.destroy();
  console.log('\nRate limiter cleaned up ✅');

  // ========================================================================
  // Summary
  // ========================================================================
  console.log('\n' + '='.repeat(60));
  console.log('🎯 KEY TAKEAWAYS');
  console.log('='.repeat(60));
  console.log();
  console.log('✅ What You Learned:');
  console.log('   1. How to configure rate limits by user tier');
  console.log('   2. Hourly and daily request limits with sliding windows');
  console.log('   3. Budget-based rate limiting for cost control');
  console.log('   4. Custom limits per user override tier defaults');
  console.log('   5. Rate limit error handling with retry-after');
  console.log('   6. Usage statistics and monitoring');
  console.log();
  console.log('🚀 Production Use Cases:');
  console.log('   • Multi-tenant SaaS with tiered pricing');
  console.log('   • API rate limiting and quota management');
  console.log('   • Cost control for AI applications');
  console.log('   • Fair usage policies');
  console.log('   • DDoS protection');
  console.log();
}

main().catch(console.error);
