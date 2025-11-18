/**
 * cascadeflow - Custom Validation Example (TypeScript)
 *
 * Build custom quality validators beyond cascadeflow's built-in validation.
 *
 * This example demonstrates:
 * - Custom validation rules for specific domains
 * - Keyword-based validation (must contain/avoid certain terms)
 * - Length-based validation (min/max words)
 * - Format validation (JSON, XML, markdown)
 * - Domain-specific quality checks (medical, legal, code)
 * - Combining multiple validators
 * - Integration with cascadeflow quality system
 *
 * Requirements:
 *   - Node.js 18+
 *   - @cascadeflow/core
 *   - OpenAI API key
 *
 * Setup:
 *   npm install @cascadeflow/core
 *   export OPENAI_API_KEY="your-key-here"
 *   npx tsx custom-validation.ts
 *
 * Use Cases:
 *   1. Medical/Legal: Verify disclaimers present
 *   2. Code: Validate syntax, ensure runnable
 *   3. JSON: Validate format, required fields
 *   4. Content moderation: Block unwanted content
 *   5. Brand compliance: Enforce tone/terminology
 *
 * Documentation:
 *   📖 Validation Guide: docs/guides/custom_validation.md
 *   📖 Quality System: docs/guides/quality.md
 *   📚 Examples README: examples/README.md
 */

import { CascadeAgent } from '@cascadeflow/core';

// ═══════════════════════════════════════════════════════════════════════════
// CUSTOM VALIDATOR BASE CLASS
// ═══════════════════════════════════════════════════════════════════════════

interface CustomValidationResult {
  passed: boolean;
  score: number; // 0.0 to 1.0
  reason: string;
  checks: Record<string, boolean>;
  violations: string[];
}

abstract class CustomValidator {
  /**
   * Validate response. Override in subclasses.
   */
  abstract validate(response: string, query?: string): CustomValidationResult;
}

// ═══════════════════════════════════════════════════════════════════════════
// VALIDATOR 1: Keyword-Based Validation
// ═══════════════════════════════════════════════════════════════════════════

class KeywordValidator extends CustomValidator {
  private required: string[];
  private forbidden: string[];
  private caseSensitive: boolean;

  constructor(options: {
    requiredKeywords?: string[];
    forbiddenKeywords?: string[];
    caseSensitive?: boolean;
  }) {
    super();
    this.required = options.requiredKeywords || [];
    this.forbidden = options.forbiddenKeywords || [];
    this.caseSensitive = options.caseSensitive || false;
  }

  validate(response: string, query: string = ''): CustomValidationResult {
    const text = this.caseSensitive ? response : response.toLowerCase();

    const checks: Record<string, boolean> = {};
    const violations: string[] = [];

    // Check required keywords
    for (const keyword of this.required) {
      const checkKw = this.caseSensitive ? keyword : keyword.toLowerCase();
      const present = text.includes(checkKw);
      checks[`contains_${keyword}`] = present;
      if (!present) {
        violations.push(`Missing required keyword: ${keyword}`);
      }
    }

    // Check forbidden keywords
    for (const keyword of this.forbidden) {
      const checkKw = this.caseSensitive ? keyword : keyword.toLowerCase();
      const present = text.includes(checkKw);
      checks[`avoids_${keyword}`] = !present;
      if (present) {
        violations.push(`Contains forbidden keyword: ${keyword}`);
      }
    }

    const passed = violations.length === 0;
    const checkValues = Object.values(checks);
    const score = checkValues.length > 0 ? checkValues.filter((v) => v).length / checkValues.length : 1.0;
    const reason = passed ? 'All keyword checks passed' : `${violations.length} violations`;

    return { passed, score, reason, checks, violations };
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// VALIDATOR 2: Length-Based Validation
// ═══════════════════════════════════════════════════════════════════════════

class LengthValidator extends CustomValidator {
  private minWords?: number;
  private maxWords?: number;
  private minSentences?: number;
  private maxSentences?: number;

  constructor(options: {
    minWords?: number;
    maxWords?: number;
    minSentences?: number;
    maxSentences?: number;
  }) {
    super();
    this.minWords = options.minWords;
    this.maxWords = options.maxWords;
    this.minSentences = options.minSentences;
    this.maxSentences = options.maxSentences;
  }

  validate(response: string, query: string = ''): CustomValidationResult {
    const wordCount = response.split(/\s+/).length;
    const sentenceCount = response.split('.').filter((s) => s.trim()).length;

    const checks: Record<string, boolean> = {};
    const violations: string[] = [];

    // Word count checks
    if (this.minWords !== undefined) {
      const passed = wordCount >= this.minWords;
      checks['min_words'] = passed;
      if (!passed) {
        violations.push(`Too short: ${wordCount} words (min: ${this.minWords})`);
      }
    }

    if (this.maxWords !== undefined) {
      const passed = wordCount <= this.maxWords;
      checks['max_words'] = passed;
      if (!passed) {
        violations.push(`Too long: ${wordCount} words (max: ${this.maxWords})`);
      }
    }

    // Sentence count checks
    if (this.minSentences !== undefined) {
      const passed = sentenceCount >= this.minSentences;
      checks['min_sentences'] = passed;
      if (!passed) {
        violations.push(`Too few sentences: ${sentenceCount} (min: ${this.minSentences})`);
      }
    }

    if (this.maxSentences !== undefined) {
      const passed = sentenceCount <= this.maxSentences;
      checks['max_sentences'] = passed;
      if (!passed) {
        violations.push(`Too many sentences: ${sentenceCount} (max: ${this.maxSentences})`);
      }
    }

    const passed = violations.length === 0;
    const checkValues = Object.values(checks);
    const score = checkValues.length > 0 ? checkValues.filter((v) => v).length / checkValues.length : 1.0;
    const reason = passed ? 'Length requirements met' : `${violations.length} violations`;

    return { passed, score, reason, checks, violations };
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// VALIDATOR 3: Format Validation (JSON, Code, etc.)
// ═══════════════════════════════════════════════════════════════════════════

class FormatValidator extends CustomValidator {
  private formatType: string;

  constructor(formatType: string = 'json') {
    super();
    this.formatType = formatType.toLowerCase();
  }

  validate(response: string, query: string = ''): CustomValidationResult {
    const checks: Record<string, boolean> = {};
    const violations: string[] = [];

    if (this.formatType === 'json') {
      // Check if response contains valid JSON
      try {
        const jsonMatch = response.match(/\{.*\}|\[.*\]/s);
        if (jsonMatch) {
          JSON.parse(jsonMatch[0]);
          checks['valid_json'] = true;
        } else {
          checks['valid_json'] = false;
          violations.push('No JSON found in response');
        }
      } catch (e) {
        checks['valid_json'] = false;
        violations.push(`Invalid JSON: ${(e as Error).message}`);
      }
    } else if (this.formatType === 'code') {
      // Check if response contains code block
      const hasCodeBlock = response.includes('```');
      checks['has_code_block'] = hasCodeBlock;
      if (!hasCodeBlock) {
        violations.push('No code block found (expected ```)');
      }
    } else if (this.formatType === 'markdown') {
      // Check basic markdown elements
      const hasHeaders = /^#+\s/m.test(response);
      checks['has_headers'] = hasHeaders;
      if (!hasHeaders) {
        violations.push('No markdown headers found');
      }
    }

    const passed = violations.length === 0;
    const checkValues = Object.values(checks);
    const score = checkValues.length > 0 ? checkValues.filter((v) => v).length / checkValues.length : 1.0;
    const reason = passed ? 'Format valid' : `${violations.length} format issues`;

    return { passed, score, reason, checks, violations };
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// VALIDATOR 4: Domain-Specific Validators
// ═══════════════════════════════════════════════════════════════════════════

class MedicalValidator extends CustomValidator {
  private static REQUIRED_DISCLAIMER = 'consult a healthcare professional';
  private static FORBIDDEN_TERMS = ['guaranteed cure', 'miracle treatment', '100% effective'];

  validate(response: string, query: string = ''): CustomValidationResult {
    const responseLower = response.toLowerCase();
    const checks: Record<string, boolean> = {};
    const violations: string[] = [];

    // Must contain disclaimer
    const hasDisclaimer = responseLower.includes(MedicalValidator.REQUIRED_DISCLAIMER.toLowerCase());
    checks['has_disclaimer'] = hasDisclaimer;
    if (!hasDisclaimer) {
      violations.push(`Missing required disclaimer: '${MedicalValidator.REQUIRED_DISCLAIMER}'`);
    }

    // Must not contain forbidden marketing terms
    for (const term of MedicalValidator.FORBIDDEN_TERMS) {
      const containsTerm = responseLower.includes(term.toLowerCase());
      checks[`avoids_${term}`] = !containsTerm;
      if (containsTerm) {
        violations.push(`Contains forbidden term: '${term}'`);
      }
    }

    const passed = violations.length === 0;
    const checkValues = Object.values(checks);
    const score = checkValues.filter((v) => v).length / checkValues.length;
    const reason = passed ? 'Medical compliance passed' : `${violations.length} compliance issues`;

    return { passed, score, reason, checks, violations };
  }
}

class CodeValidator extends CustomValidator {
  validate(response: string, query: string = ''): CustomValidationResult {
    const checks: Record<string, boolean> = {};
    const violations: string[] = [];

    // Check for code block
    const hasCode = response.includes('```');
    checks['has_code_block'] = hasCode;
    if (!hasCode) {
      violations.push('No code block found');
    }

    // Check for common keywords (if code query)
    if (query.toLowerCase().includes('function') || response.includes('function ') || response.includes('def ')) {
      const hasFunction = response.includes('function ') || response.includes('def ');
      checks['has_function'] = hasFunction;

      // Check for basic structure
      const hasDocstring = response.includes('"""') || response.includes("'''") || response.includes('/**');
      checks['has_docstring'] = hasDocstring;
      if (!hasDocstring) {
        violations.push('Missing docstring or documentation');
      }
    }

    // Check for syntax errors (basic check)
    const commonErrors = ['SyntaxError', 'IndentationError', 'NameError', 'TypeError'];
    const hasErrors = commonErrors.some((err) => response.includes(err));
    checks['no_error_messages'] = !hasErrors;
    if (hasErrors) {
      violations.push('Response contains error messages');
    }

    const passed = violations.length === 0;
    const checkValues = Object.values(checks);
    const score = checkValues.length > 0 ? checkValues.filter((v) => v).length / checkValues.length : 1.0;
    const reason = passed ? 'Code validation passed' : `${violations.length} issues`;

    return { passed, score, reason, checks, violations };
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// VALIDATOR 5: Composite Validator (Combine Multiple)
// ═══════════════════════════════════════════════════════════════════════════

class CompositeValidator extends CustomValidator {
  private validators: CustomValidator[];
  private requireAll: boolean;

  constructor(validators: CustomValidator[], requireAll: boolean = true) {
    super();
    this.validators = validators;
    this.requireAll = requireAll;
  }

  validate(response: string, query: string = ''): CustomValidationResult {
    const results = this.validators.map((v) => v.validate(response, query));

    // Combine checks
    const allChecks: Record<string, boolean> = {};
    const allViolations: string[] = [];

    results.forEach((result, i) => {
      Object.entries(result.checks).forEach(([key, value]) => {
        allChecks[`validator_${i}_${key}`] = value;
      });
      allViolations.push(...result.violations);
    });

    // Determine pass/fail
    let passed: boolean;
    let reason: string;

    if (this.requireAll) {
      passed = results.every((r) => r.passed);
      reason = passed ? 'All validators passed' : `${allViolations.length} total violations`;
    } else {
      passed = results.some((r) => r.passed);
      reason = passed ? 'At least one validator passed' : 'All validators failed';
    }

    const avgScore = results.reduce((sum, r) => sum + r.score, 0) / results.length;

    return {
      passed,
      score: avgScore,
      reason,
      checks: allChecks,
      violations: allViolations,
    };
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// EXAMPLE USAGE
// ═══════════════════════════════════════════════════════════════════════════

async function demoKeywordValidator() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 1: Keyword Validator');
  console.log('='.repeat(70));
  console.log('\nValidate response contains required terms and avoids forbidden ones\n');

  // Create validator
  const validator = new KeywordValidator({
    requiredKeywords: ['Python', 'programming'],
    forbiddenKeywords: ['difficult', 'impossible'],
  });

  // Test responses
  const testCases: Array<[string, string]> = [
    ['Python is a great programming language for beginners.', '✅ Should pass'],
    ["JavaScript is difficult to learn.", "❌ Missing Python, has 'difficult'"],
    ['Python is powerful.', "❌ Missing 'programming'"],
  ];

  for (const [response, expected] of testCases) {
    const result = validator.validate(response);
    console.log(`Response: ${response.substring(0, 60)}...`);
    console.log(`Expected: ${expected}`);
    console.log(`Result: ${result.passed ? '✅ PASS' : '❌ FAIL'} (score: ${result.score.toFixed(2)})`);
    if (result.violations.length > 0) {
      console.log(`Violations: ${result.violations.join(', ')}`);
    }
    console.log();
  }
}

async function demoMedicalValidator() {
  console.log('\n' + '='.repeat(70));
  console.log('EXAMPLE 2: Medical Validator');
  console.log('='.repeat(70));
  console.log('\nEnsure medical responses include disclaimers and avoid marketing claims\n');

  const validator = new MedicalValidator();

  // Generate response with AI
  const agent = new CascadeAgent({
    models: [
      {
        name: 'gpt-4o-mini',
        provider: 'openai',
        cost: 0.00015,
      },
    ],
  });

  const query = 'What helps with headaches?';
  console.log(`Query: ${query}\n`);

  const result = await agent.run(query, { maxTokens: 150, temperature: 0.7 });
  console.log(`AI Response:\n${result.content}\n`);

  // Validate
  const validation = validator.validate(result.content, query);
  console.log(`Validation: ${validation.passed ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`Score: ${validation.score.toFixed(2)}`);
  console.log(`Reason: ${validation.reason}`);
  if (validation.violations.length > 0) {
    console.log('\nViolations:');
    for (const v of validation.violations) {
      console.log(`  • ${v}`);
    }
  }
}

async function demoCompositeValidator() {
  console.log('\n\n' + '='.repeat(70));
  console.log('EXAMPLE 3: Composite Validator');
  console.log('='.repeat(70));
  console.log('\nCombine multiple validators for comprehensive quality checks\n');

  // Create composite validator
  const composite = new CompositeValidator(
    [
      new LengthValidator({ minWords: 20, maxWords: 100 }),
      new KeywordValidator({ requiredKeywords: ['function', 'return'] }),
      new CodeValidator(),
    ],
    true // require all to pass
  );

  // Generate code response
  const agent = new CascadeAgent({
    models: [
      {
        name: 'gpt-4o-mini',
        provider: 'openai',
        cost: 0.00015,
      },
    ],
  });

  const query = 'Write a TypeScript function to calculate factorial';
  console.log(`Query: ${query}\n`);

  const result = await agent.run(query, { maxTokens: 200, temperature: 0.7 });
  console.log(`AI Response:\n${result.content}\n`);

  // Validate
  const validation = composite.validate(result.content, query);
  console.log(`Validation: ${validation.passed ? '✅ PASS' : '❌ FAIL'}`);
  console.log(`Score: ${validation.score.toFixed(2)}`);
  console.log(`Total checks: ${Object.keys(validation.checks).length}`);
  const passedChecks = Object.values(validation.checks).filter((v) => v).length;
  console.log(`Passed: ${passedChecks}/${Object.keys(validation.checks).length}`);

  if (validation.violations.length > 0) {
    console.log('\nViolations:');
    for (const v of validation.violations) {
      console.log(`  • ${v}`);
    }
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════════════════

async function main() {
  console.log('🌊 cascadeflow Custom Validation Examples');
  console.log('='.repeat(70));

  if (!process.env.OPENAI_API_KEY) {
    console.log('\n❌ OPENAI_API_KEY required');
    return;
  }

  // Run examples
  await demoKeywordValidator();
  await demoMedicalValidator();
  await demoCompositeValidator();

  // Summary
  console.log('\n\n' + '='.repeat(70));
  console.log('🎓 KEY TAKEAWAYS');
  console.log('='.repeat(70));

  console.log('\n1. Validator Types:');
  console.log('   ├─ Keyword: Required/forbidden terms');
  console.log('   ├─ Length: Min/max words/sentences');
  console.log('   ├─ Format: JSON, code blocks, markdown');
  console.log('   ├─ Domain: Medical, legal, code-specific');
  console.log('   └─ Composite: Combine multiple validators');

  console.log('\n2. Use Cases:');
  console.log('   ├─ Compliance: Ensure disclaimers, avoid claims');
  console.log('   ├─ Quality: Check format, length, structure');
  console.log('   ├─ Safety: Block inappropriate content');
  console.log('   ├─ Branding: Enforce tone, terminology');
  console.log('   └─ Technical: Validate code, JSON, markup');

  console.log('\n3. Integration:');
  console.log('   ├─ Run validators after AI generation');
  console.log('   ├─ Reject/regenerate if validation fails');
  console.log('   ├─ Log violations for analysis');
  console.log('   ├─ Adjust prompts based on failures');
  console.log('   └─ Combine with cascadeflow quality system');

  console.log('\n📚 Learn more:');
  console.log('   • docs/guides/custom_validation.md');
  console.log('   • docs/guides/quality.md');
  console.log('   • examples/production_patterns.ts\n');
}

main().catch(console.error);
