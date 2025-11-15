/**
 * Example: User Profiles and Workflows
 *
 * Demonstrates user profile and workflow management:
 * - Creating user profiles with tier restrictions
 * - Workflow profiles for different use cases
 * - Latency and optimization weight configuration
 * - Using profiles with CascadeAgent
 *
 * Run: npx tsx examples/nodejs/user-profiles-workflows.ts
 */

import {
  CascadeAgent,
  createUserProfile,
  createWorkflowProfile,
  TIER_PRESETS,
  WORKFLOW_PRESETS,
} from '@cascadeflow/core';

async function main() {
  console.log('👤 User Profiles & Workflows Example\n');

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
  // 1. Tier-Based Profiles
  // ============================================================================
  console.log('1️⃣  Tier-Based User Profiles\n');

  // Free tier: Budget-conscious
  const freeProfile = createUserProfile('FREE', 'user-free');

  console.log('Free Tier Profile:');
  console.log(`   Daily budget: $${freeProfile.tier.dailyBudget}`);
  console.log(`   Min quality: ${freeProfile.tier.minQuality}`);

  // PRO tier: High quality
  const proProfile = createUserProfile('PRO', 'user-pro');

  console.log('\nPRO Tier Profile:');
  console.log(`   Daily budget: $${proProfile.tier.dailyBudget}`);
  console.log(`   Min quality: ${proProfile.tier.minQuality}`);

  // ============================================================================
  // 2. Custom Profile with Optimization Weights
  // ============================================================================
  console.log('\n2️⃣  Custom Profile with Optimization Weights\n');

  const customProfile = createUserProfile('PRO', 'user-custom', {
    optimization: {
      cost: 0.5,    // 50% weight on cost
      speed: 0.3,   // 30% weight on speed
      quality: 0.2, // 20% weight on quality
    },
  });

  console.log('Custom Profile:');
  console.log(`   Cost weight: ${customProfile.optimization?.cost}`);
  console.log(`   Speed weight: ${customProfile.optimization?.speed}`);
  console.log(`   Quality weight: ${customProfile.optimization?.quality}`);

  // ============================================================================
  // 3. Workflow Profiles
  // ============================================================================
  console.log('\n3️⃣  Workflow Profiles\n');

  // Production workflow: High quality, reasonable latency
  const productionWorkflow = createWorkflowProfile(WORKFLOW_PRESETS.production);

  console.log('Production Workflow:');
  console.log(`   Name: ${productionWorkflow.name}`);
  console.log(`   Quality threshold: ${productionWorkflow.qualityThresholdOverride}`);
  console.log(`   Description: ${productionWorkflow.description}`);

  // Real-time workflow: Ultra-low latency
  const realtimeWorkflow = createWorkflowProfile(WORKFLOW_PRESETS.realtime);

  console.log('\nReal-time Workflow:');
  console.log(`   Name: ${realtimeWorkflow.name}`);
  console.log(`   Preferred models: ${realtimeWorkflow.preferredModels?.join(', ')}`);
  console.log(`   Max latency: ${realtimeWorkflow.latencyOverride?.maxTotalMs}ms`);

  // ============================================================================
  // 4. Using Profiles with CascadeAgent
  // ============================================================================
  console.log('\n4️⃣  Using Profiles with CascadeAgent\n');

  const profiledAgent = new CascadeAgent({
    models,
  });

  console.log('Running query...');
  const result = await profiledAgent.run('What is TypeScript?');
  console.log(`   Model: ${result.modelUsed}`);
  console.log(`   Cost: $${result.totalCost.toFixed(6)}`);

  // ============================================================================
  // 5. Latency-Aware Profiles
  // ============================================================================
  console.log('\n5️⃣  Latency-Aware Profiles\n');

  const lowLatencyProfile = createUserProfile('PRO', 'user-lowlat', {
    latency: {
      maxTotalMs: 2000,      // 2 second total limit
      maxPerModelMs: 1000,   // 1 second per model
      preferParallel: true,  // Prefer parallel execution
      skipCascadeThreshold: 1500, // Skip cascade if over 1.5s
    },
  });

  console.log('Low-Latency Profile:');
  console.log(`   Max total latency: ${lowLatencyProfile.latency?.maxTotalMs}ms`);
  console.log(`   Max per model: ${lowLatencyProfile.latency?.maxPerModelMs}ms`);
  console.log(`   Prefer parallel: ${lowLatencyProfile.latency?.preferParallel}`);

  // ============================================================================
  // 6. Profile Serialization
  // ============================================================================
  console.log('\n6️⃣  Profile Serialization\n');

  const profileJson = JSON.stringify(proProfile, null, 2);
  console.log('Serialized profile (for storage/transmission):');
  console.log(profileJson.substring(0, 200) + '...');

  console.log('\n✅ Example complete!');
}

main().catch(console.error);
