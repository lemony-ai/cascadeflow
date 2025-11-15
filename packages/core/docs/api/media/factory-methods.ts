/**
 * Example: Factory Methods
 *
 * Demonstrates convenient factory methods for creating agents:
 * - fromEnv(): Auto-detect providers and configure from environment
 * - fromProfile(): Create agent from user profile
 * - Quick setup with minimal configuration
 *
 * Run: npx tsx examples/nodejs/factory-methods.ts
 */

import { CascadeAgent, createUserProfile, TIER_PRESETS } from '@cascadeflow/core';

async function main() {
  console.log('🏭 Factory Methods Example\n');

  // ============================================================================
  // 1. fromEnv() - Auto-Configuration
  // ============================================================================
  console.log('1️⃣  fromEnv() - Auto-Configuration from Environment\n');

  console.log('Creating agent from environment variables...');
  console.log('Checking for: OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, etc.');

  try {
    const envAgent = CascadeAgent.fromEnv();

    console.log('✅ Agent created successfully!');
    console.log('   Models auto-configured from available API keys');

    const result = await envAgent.run('What is TypeScript?');
    console.log(`\n   Query result:`);
    console.log(`   Model: ${result.modelUsed}`);
    console.log(`   Cost: $${result.totalCost.toFixed(6)}`);
  } catch (error) {
    console.log(`❌ Error: ${error instanceof Error ? error.message : error}`);
    console.log('   Make sure at least one provider API key is set');
  }

  // ============================================================================
  // 2. fromProfile() - Profile-Based Configuration
  // ============================================================================
  console.log('\n2️⃣  fromProfile() - Profile-Based Configuration\n');

  const profile = createUserProfile('PRO', 'user-123', {
    preferredModels: [
      'gpt-4o-mini',
      'gpt-4o',
      'claude-3-5-haiku-20241022',
      'claude-3-5-sonnet-20241022',
    ],
  });

  console.log('Creating agent from user profile...');

  try {
    const profileAgent = CascadeAgent.fromProfile(profile);

    console.log('✅ Agent created with profile settings!');

    const result = await profileAgent.run('Explain async programming.');
    console.log(`\n   Query result:`);
    console.log(`   Model: ${result.modelUsed}`);
    console.log(`   Cost: $${result.totalCost.toFixed(6)}`);
  } catch (error) {
    console.log(`❌ Error: ${error instanceof Error ? error.message : error}`);
  }

  // ============================================================================
  // 3. Manual Configuration (Traditional)
  // ============================================================================
  console.log('\n3️⃣  Manual Configuration (Traditional Approach)\n');

  const manualAgent = new CascadeAgent({
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
    quality: {
      minConfidence: 0.70,
    },
  });

  console.log('Agent created with manual configuration');
  console.log('   Explicit model list');
  console.log('   Custom cascade settings');

  const result = await manualAgent.run('What is REST API?');
  console.log(`\n   Query result:`);
  console.log(`   Model: ${result.modelUsed}`);
  console.log(`   Cost: $${result.totalCost.toFixed(6)}`);

  // ============================================================================
  // 4. Quality Profile Factory Methods
  // ============================================================================
  console.log('\n4️⃣  Quality Profile Factory Methods\n');

  console.log('fromEnv() with different quality thresholds:');

  const qualityThresholds = [
    { name: 'strict', minConfidence: 0.85 },
    { name: 'balanced', minConfidence: 0.70 },
    { name: 'lenient', minConfidence: 0.50 }
  ];

  for (const config of qualityThresholds) {
    console.log(`\n   ${config.name} mode:`);
    try {
      const agent = CascadeAgent.fromEnv({
        quality: { minConfidence: config.minConfidence },
      });

      const testResult = await agent.run('Hello!');
      console.log(`   ✅ Model: ${testResult.modelUsed}, Cost: $${testResult.totalCost.toFixed(6)}`);
    } catch (error) {
      console.log(`   ❌ Error: ${error instanceof Error ? error.message : error}`);
    }
  }

  // ============================================================================
  // 5. Comparison: Factory vs Manual
  // ============================================================================
  console.log('\n5️⃣  Comparison: Factory vs Manual\n');

  console.log('Factory Method Benefits:');
  console.log('   ✅ Auto-detects available providers');
  console.log('   ✅ Sensible defaults for common use cases');
  console.log('   ✅ Less boilerplate code');
  console.log('   ✅ Profile-based configuration');

  console.log('\nManual Configuration Benefits:');
  console.log('   ✅ Full control over all settings');
  console.log('   ✅ Explicit model selection');
  console.log('   ✅ Custom provider configurations');
  console.log('   ✅ Fine-tuned quality settings');

  console.log('\n💡 Recommendation:');
  console.log('   - Use fromEnv() for quick prototyping');
  console.log('   - Use fromProfile() for multi-tenant applications');
  console.log('   - Use manual config for production with specific requirements');

  console.log('\n✅ Example complete!');
}

main().catch(console.error);
