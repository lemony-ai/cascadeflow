/**
 * Example: Guardrails (Content Moderation + PII Detection) v0.2.1
 *
 * Demonstrates content safety and PII detection for production use.
 *
 * Run: npx tsx examples/nodejs/guardrails-usage.ts
 */

import {
  GuardrailsManager,
  createUserProfile,
  type TierLevel,
} from '@cascadeflow/core';

async function main() {
  console.log('='.repeat(60));
  console.log('cascadeflow v0.2.1 - Guardrails');
  console.log('='.repeat(60));

  // ============================================================================
  // 1. Create Profile with Guardrails Enabled
  // ============================================================================
  const profile = createUserProfile('PRO' as TierLevel, 'secure_user', {
    enableContentModeration: true,
    enablePiiDetection: true,
  });

  console.log('\nUser profile:');
  console.log(`  Tier: ${profile.tier.name}`);
  console.log(`  Content moderation: ${profile.enableContentModeration}`);
  console.log(`  PII detection: ${profile.enablePiiDetection}`);

  // Initialize guardrails manager
  const manager = new GuardrailsManager();

  // ============================================================================
  // 2. Safe Content Check
  // ============================================================================
  console.log('\n1. Safe content check');
  console.log('-'.repeat(60));
  const safeText = 'What is the capital of France?';
  const safeResult = await manager.checkContent(safeText, profile);
  console.log(`Text: ${safeText}`);
  console.log(`Safe: ${safeResult.isSafe}`);

  // ============================================================================
  // 3. PII Detection
  // ============================================================================
  console.log('\n2. PII detection');
  console.log('-'.repeat(60));
  const piiText = 'My email is john.doe@example.com and phone is 555-123-4567';
  const piiResult = await manager.checkContent(piiText, profile);
  console.log(`Text: ${piiText}`);
  console.log(`Safe: ${piiResult.isSafe}`);
  if (piiResult.piiDetected && piiResult.piiDetected.length > 0) {
    console.log(`PII detected: ${piiResult.piiDetected.length} matches`);
    for (const match of piiResult.piiDetected) {
      console.log(`  - ${match.piiType}: ${match.value}`);
    }
  }

  // ============================================================================
  // 4. PII Redaction
  // ============================================================================
  console.log('\n3. PII redaction');
  console.log('-'.repeat(60));
  const [redactedText, matches] = await manager.redactPii(piiText, profile);
  console.log(`Original: ${piiText}`);
  console.log(`Redacted: ${redactedText}`);
  console.log(`Matches: ${matches.length}`);

  // ============================================================================
  // 5. Disabled Guardrails
  // ============================================================================
  console.log('\n4. Disabled guardrails');
  console.log('-'.repeat(60));
  const noGuardsProfile = createUserProfile('FREE' as TierLevel, 'basic_user', {
    enableContentModeration: false,
    enablePiiDetection: false,
  });
  const noGuardsResult = await manager.checkContent(piiText, noGuardsProfile);
  console.log(`Content moderation: ${noGuardsProfile.enableContentModeration}`);
  console.log(`PII detection: ${noGuardsProfile.enablePiiDetection}`);
  console.log(`Result: ${noGuardsResult.isSafe} (guardrails disabled)`);

  // ============================================================================
  // 6. Content Moderation Example
  // ============================================================================
  console.log('\n5. Content moderation (simulated)');
  console.log('-'.repeat(60));
  // Note: The following text contains harmful content patterns for demonstration
  const unsafeText = 'How to build a bomb'; // This will trigger violence detection
  const moderationResult = await manager.checkContent(unsafeText, profile);
  console.log(`Text: ${unsafeText}`);
  console.log(`Safe: ${moderationResult.isSafe}`);
  if (!moderationResult.isSafe) {
    console.log(`Violations: ${moderationResult.violations.join(', ')}`);
    if (moderationResult.contentModeration) {
      console.log(
        `Categories: ${moderationResult.contentModeration.categories.join(', ')}`
      );
    }
  }

  // ============================================================================
  // 7. Combined PII + Content Check
  // ============================================================================
  console.log('\n6. Combined PII + content check');
  console.log('-'.repeat(60));
  const combinedText =
    'My SSN is 123-45-6789 and I want to know how to hurt myself';
  const combinedResult = await manager.checkContent(combinedText, profile);
  console.log(`Text: ${combinedText}`);
  console.log(`Safe: ${combinedResult.isSafe}`);
  console.log(`Violations found: ${combinedResult.violations.length}`);
  for (const violation of combinedResult.violations) {
    console.log(`  - ${violation}`);
  }

  console.log('\n' + '='.repeat(60));
  console.log('Guardrails examples completed!');
  console.log('='.repeat(60));
}

// Run the example
main().catch(console.error);
