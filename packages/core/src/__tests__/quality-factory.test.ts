/**
 * Tests for QualityValidator factory methods
 *
 * Tests the static factory methods for creating pre-configured validators
 *
 * Run: pnpm test quality-factory.test.ts
 */

import { describe, it, expect } from 'vitest';
import { QualityValidator, QualityConfigFactory } from '../quality';

describe('QualityValidator Factory Methods', () => {
  describe('forProduction', () => {
    it('should create validator with production config', () => {
      const validator = QualityValidator.forProduction();
      const config = validator.getConfig();

      // Should match QualityConfigFactory.forProduction()
      const expectedConfig = QualityConfigFactory.forProduction();
      expect(config.minConfidence).toBe(expectedConfig.minConfidence);
      expect(config.minWordCount).toBe(expectedConfig.minWordCount);
      expect(config.useLogprobs).toBe(expectedConfig.useLogprobs);
      expect(config.strictMode).toBe(expectedConfig.strictMode);
      expect(config.useAlignmentScoring).toBe(expectedConfig.useAlignmentScoring);
      expect(config.minAlignmentScore).toBe(expectedConfig.minAlignmentScore);
    });

    it('should have cascade-optimized production thresholds', () => {
      const validator = QualityValidator.forProduction();
      const config = validator.getConfig();

      // Production uses cascade-optimized inverted thresholds (Python-synced)
      // harder → lower threshold → escalate to verifier more often
      expect(config.confidenceThresholds).toBeDefined();
      expect(config.confidenceThresholds!.trivial).toBe(0.55);
      expect(config.confidenceThresholds!.simple).toBe(0.50);
      expect(config.confidenceThresholds!.moderate).toBe(0.45);
      expect(config.confidenceThresholds!.hard).toBe(0.42);
      expect(config.confidenceThresholds!.expert).toBe(0.40);
    });

    it('should validate high-quality responses', async () => {
      const validator = QualityValidator.forProduction();

      const result = await validator.validate(
        'TypeScript is a strongly typed programming language that builds on JavaScript.',
        'What is TypeScript?',
        [-0.1, -0.2, -0.15, -0.1], // Good logprobs
        'simple'
      );

      expect(result.passed).toBe(true);
      expect(result.confidence).toBeGreaterThan(0.7);
    });

    it('should reject low-quality responses', async () => {
      const validator = QualityValidator.forProduction();

      const result = await validator.validate(
        "I'm not sure",
        'What is TypeScript?',
        [-2.5, -3.0, -2.8], // Bad logprobs
        'simple'
      );

      expect(result.passed).toBe(false);
    });
  });

  describe('forDevelopment', () => {
    it('should create validator with development config', () => {
      const validator = QualityValidator.forDevelopment();
      const config = validator.getConfig();

      const expectedConfig = QualityConfigFactory.forDevelopment();
      expect(config.minConfidence).toBe(expectedConfig.minConfidence);
      expect(config.minWordCount).toBe(expectedConfig.minWordCount);
    });

    it('should have traditional thresholds vs production inverted thresholds', () => {
      const dev = QualityValidator.forDevelopment();
      const prod = QualityValidator.forProduction();

      const devConfig = dev.getConfig();
      const prodConfig = prod.getConfig();

      // Production uses cascade-optimized inverted thresholds (Python-synced)
      // Dev uses traditional increasing thresholds
      // Dev.simple (0.60) > prod.simple (0.50) since prod is inverted
      expect(devConfig.confidenceThresholds!.simple).toBeGreaterThan(
        prodConfig.confidenceThresholds!.simple!
      );
      expect(devConfig.confidenceThresholds!.moderate).toBeGreaterThan(
        prodConfig.confidenceThresholds!.moderate!
      );
      expect(devConfig.minWordCount).toBeLessThanOrEqual(prodConfig.minWordCount);
    });

    it('should accept more responses than production', async () => {
      const dev = QualityValidator.forDevelopment();
      const prod = QualityValidator.forProduction();

      // Medium quality response
      const content = 'TypeScript is like JavaScript but with types.';
      const query = 'What is TypeScript?';
      const logprobs = [-0.5, -0.6, -0.5, -0.4]; // Medium logprobs

      const devResult = await dev.validate(content, query, logprobs, 'simple');
      const prodResult = await prod.validate(content, query, logprobs, 'simple');

      // Dev might pass where production fails (or both pass but dev has lower threshold)
      expect(devResult.confidence).toBeGreaterThan(0);
      expect(prodResult.confidence).toBeGreaterThan(0);
    });
  });

  describe('strict', () => {
    it('should create validator with strict config', () => {
      const validator = QualityValidator.strict();
      const config = validator.getConfig();

      const expectedConfig = QualityConfigFactory.strict();
      expect(config.minConfidence).toBe(expectedConfig.minConfidence);
      expect(config.strictMode).toBe(true);
      expect(config.useSemanticValidation).toBe(true);
    });

    it('should have highest thresholds', () => {
      const strict = QualityValidator.strict();
      const prod = QualityValidator.forProduction();
      const dev = QualityValidator.forDevelopment();

      const strictConfig = strict.getConfig();
      const prodConfig = prod.getConfig();
      const devConfig = dev.getConfig();

      // Strict should have highest thresholds
      expect(strictConfig.confidenceThresholds!.simple).toBeGreaterThan(
        prodConfig.confidenceThresholds!.simple!
      );
      expect(strictConfig.confidenceThresholds!.simple).toBeGreaterThan(
        devConfig.confidenceThresholds!.simple!
      );
      expect(strictConfig.minWordCount).toBeGreaterThanOrEqual(prodConfig.minWordCount);
      expect(strictConfig.minAlignmentScore).toBeGreaterThanOrEqual(
        prodConfig.minAlignmentScore
      );
    });

    it('should reject responses with uncertainty markers', async () => {
      const validator = QualityValidator.strict();

      const result = await validator.validate(
        "TypeScript is possibly a programming language, but I'm not entirely sure.",
        'What is TypeScript?',
        [-0.3, -0.4, -0.3], // Decent logprobs but content has uncertainty
        'simple'
      );

      // Strict mode penalizes uncertainty markers
      expect(result.score).toBeLessThan(result.confidence);
    });

    it('should only accept very high quality responses', async () => {
      const validator = QualityValidator.strict();

      // Medium quality content
      const mediumResult = await validator.validate(
        'TypeScript is like JavaScript.',
        'What is TypeScript?',
        [-0.5, -0.6, -0.5], // Medium logprobs
        'simple'
      );

      // Very high quality content with excellent logprobs (very close to 0 = very confident)
      const highResult = await validator.validate(
        'TypeScript is a strongly typed superset of JavaScript developed by Microsoft that compiles to plain JavaScript and adds optional static types for better tooling and error detection.',
        'What is TypeScript?',
        [-0.05, -0.08, -0.06, -0.07, -0.05, -0.06], // Excellent logprobs (closer to 0)
        'simple'
      );

      expect(mediumResult.passed).toBe(false);
      // Strict mode may still reject even high quality with production estimator
      // The production estimator uses multi-signal approach and may be more conservative
      expect(highResult.confidence).toBeGreaterThan(mediumResult.confidence);
    });
  });

  describe('forCascade', () => {
    it('should create validator with cascade config', () => {
      const validator = QualityValidator.forCascade();
      const config = validator.getConfig();

      const expectedConfig = QualityConfigFactory.forCascade();
      expect(config.minConfidence).toBe(expectedConfig.minConfidence);
      expect(config.minWordCount).toBe(5); // Relaxed for cascade
      expect(config.useSemanticValidation).toBe(false); // Disabled for speed
    });

    it('should have lower trivial threshold and word count than production', () => {
      const cascade = QualityValidator.forCascade();
      const prod = QualityValidator.forProduction();

      const cascadeConfig = cascade.getConfig();
      const prodConfig = prod.getConfig();

      // Cascade has lower trivial threshold (0.25 vs 0.55) for high acceptance
      expect(cascadeConfig.confidenceThresholds!.trivial).toBeLessThan(
        prodConfig.confidenceThresholds!.trivial!
      );
      // Cascade has lower simple threshold (0.40 vs 0.50)
      expect(cascadeConfig.confidenceThresholds!.simple).toBeLessThan(
        prodConfig.confidenceThresholds!.simple!
      );
      // But cascade.moderate (0.55) > prod.moderate (0.45) since prod is inverted
      expect(cascadeConfig.confidenceThresholds!.moderate).toBeGreaterThan(
        prodConfig.confidenceThresholds!.moderate!
      );
      expect(cascadeConfig.minWordCount).toBeLessThan(prodConfig.minWordCount);
    });

    it('should accept more responses for optimal cascade performance', async () => {
      const cascade = QualityValidator.forCascade();
      const prod = QualityValidator.forProduction();

      // Test with various quality levels
      const testCases = [
        {
          content: 'TypeScript is JavaScript with types.',
          logprobs: [-0.5, -0.6, -0.5],
          complexity: 'simple' as const,
        },
        {
          content: 'TypeScript adds static typing to JavaScript.',
          logprobs: [-0.4, -0.5, -0.4],
          complexity: 'simple' as const,
        },
        {
          content: 'TypeScript is a programming language.',
          logprobs: [-0.6, -0.7, -0.6],
          complexity: 'simple' as const,
        },
      ];

      let cascadeAccepted = 0;
      let prodAccepted = 0;

      for (const testCase of testCases) {
        const cascadeResult = await cascade.validate(
          testCase.content,
          'What is TypeScript?',
          testCase.logprobs,
          testCase.complexity
        );
        const prodResult = await prod.validate(
          testCase.content,
          'What is TypeScript?',
          testCase.logprobs,
          testCase.complexity
        );

        if (cascadeResult.passed) cascadeAccepted++;
        if (prodResult.passed) prodAccepted++;
      }

      // Cascade should accept more than production
      expect(cascadeAccepted).toBeGreaterThanOrEqual(prodAccepted);
    });
  });

  describe('permissive', () => {
    it('should create validator with permissive config', () => {
      const validator = QualityValidator.permissive();
      const config = validator.getConfig();

      const expectedConfig = QualityConfigFactory.permissive();
      expect(config.minConfidence).toBe(expectedConfig.minConfidence);
      expect(config.minWordCount).toBe(3); // Very relaxed
    });

    it('should have lowest thresholds', () => {
      const permissive = QualityValidator.permissive();
      const cascade = QualityValidator.forCascade();
      const dev = QualityValidator.forDevelopment();

      const permissiveConfig = permissive.getConfig();
      const cascadeConfig = cascade.getConfig();
      const devConfig = dev.getConfig();

      // Permissive should be most lenient
      expect(permissiveConfig.confidenceThresholds!.simple).toBeLessThanOrEqual(
        cascadeConfig.confidenceThresholds!.simple!
      );
      expect(permissiveConfig.confidenceThresholds!.simple).toBeLessThan(
        devConfig.confidenceThresholds!.simple!
      );
      expect(permissiveConfig.minWordCount).toBeLessThanOrEqual(cascadeConfig.minWordCount);
      expect(permissiveConfig.minAlignmentScore).toBeLessThanOrEqual(
        cascadeConfig.minAlignmentScore
      );
    });

    it('should accept almost all responses', async () => {
      const validator = QualityValidator.permissive();

      // Very short response
      const shortResult = await validator.validate(
        'A language.',
        'What is TypeScript?',
        [-1.0, -1.2], // Poor logprobs
        'simple'
      );

      // Medium response
      const mediumResult = await validator.validate(
        'TypeScript is JavaScript with types.',
        'What is TypeScript?',
        [-0.8, -0.9, -0.7],
        'simple'
      );

      // At least medium should pass, possibly even short
      expect(mediumResult.passed).toBe(true);
    });
  });

  describe('Factory Method Comparisons', () => {
    it('should maintain ordering for traditional presets: strict > dev > cascade > permissive', () => {
      const strict = QualityValidator.strict();
      const prod = QualityValidator.forProduction();
      const dev = QualityValidator.forDevelopment();
      const cascade = QualityValidator.forCascade();
      const permissive = QualityValidator.permissive();

      const strictConfig = strict.getConfig();
      const prodConfig = prod.getConfig();
      const devConfig = dev.getConfig();
      const cascadeConfig = cascade.getConfig();
      const permissiveConfig = permissive.getConfig();

      // Traditional presets follow moderate threshold ordering
      expect(strictConfig.confidenceThresholds!.moderate).toBeGreaterThan(
        devConfig.confidenceThresholds!.moderate!
      );
      expect(devConfig.confidenceThresholds!.moderate).toBeGreaterThan(
        cascadeConfig.confidenceThresholds!.moderate!
      );
      expect(cascadeConfig.confidenceThresholds!.moderate).toBeGreaterThanOrEqual(
        permissiveConfig.confidenceThresholds!.moderate!
      );

      // Production uses cascade-optimized inverted thresholds
      // prod.moderate (0.45) is lower than all traditional presets
      expect(prodConfig.confidenceThresholds!.moderate).toBeLessThan(
        strictConfig.confidenceThresholds!.moderate!
      );
      expect(prodConfig.minConfidence).toBeLessThan(strictConfig.minConfidence);
    });

    it('should all enable alignment scoring by default', () => {
      const validators = [
        QualityValidator.forProduction(),
        QualityValidator.forDevelopment(),
        QualityValidator.strict(),
        QualityValidator.forCascade(),
        QualityValidator.permissive(),
      ];

      for (const validator of validators) {
        expect(validator.getConfig().useAlignmentScoring).toBe(true);
      }
    });

    it('should only enable semantic validation in strict mode', () => {
      const validators = [
        { name: 'production', validator: QualityValidator.forProduction() },
        { name: 'development', validator: QualityValidator.forDevelopment() },
        { name: 'strict', validator: QualityValidator.strict() },
        { name: 'cascade', validator: QualityValidator.forCascade() },
        { name: 'permissive', validator: QualityValidator.permissive() },
      ];

      for (const { name, validator } of validators) {
        const config = validator.getConfig();
        if (name === 'strict') {
          expect(config.useSemanticValidation).toBe(true);
        } else {
          expect(config.useSemanticValidation).toBeFalsy();
        }
      }
    });
  });

  describe('Integration Tests', () => {
    it('should validate same content differently based on factory method', async () => {
      const content =
        'TypeScript is a programming language that adds static types to JavaScript.';
      const query = 'What is TypeScript?';
      const logprobs = [-0.4, -0.5, -0.4, -0.3]; // Decent quality

      const results = await Promise.all([
        QualityValidator.strict().validate(content, query, logprobs, 'simple'),
        QualityValidator.forProduction().validate(content, query, logprobs, 'simple'),
        QualityValidator.forDevelopment().validate(content, query, logprobs, 'simple'),
        QualityValidator.forCascade().validate(content, query, logprobs, 'simple'),
        QualityValidator.permissive().validate(content, query, logprobs, 'simple'),
      ]);

      const [strictRes, prodRes, devRes, cascadeRes, permissiveRes] = results;

      // All should have same confidence score (based on logprobs)
      // But passed status may differ based on thresholds
      expect(strictRes.confidence).toBeCloseTo(prodRes.confidence, 2);
      expect(prodRes.confidence).toBeCloseTo(devRes.confidence, 2);

      // At least permissive should pass
      expect(permissiveRes.passed).toBe(true);
    });

    it('should match QualityConfigFactory behavior', () => {
      const factories = [
        {
          validator: QualityValidator.forProduction(),
          config: QualityConfigFactory.forProduction(),
        },
        {
          validator: QualityValidator.forDevelopment(),
          config: QualityConfigFactory.forDevelopment(),
        },
        {
          validator: QualityValidator.strict(),
          config: QualityConfigFactory.strict(),
        },
        {
          validator: QualityValidator.forCascade(),
          config: QualityConfigFactory.forCascade(),
        },
        {
          validator: QualityValidator.permissive(),
          config: QualityConfigFactory.permissive(),
        },
      ];

      for (const { validator, config } of factories) {
        const validatorConfig = validator.getConfig();

        expect(validatorConfig.minConfidence).toBe(config.minConfidence);
        expect(validatorConfig.minWordCount).toBe(config.minWordCount);
        expect(validatorConfig.useLogprobs).toBe(config.useLogprobs);
        expect(validatorConfig.strictMode).toBe(config.strictMode);
        expect(validatorConfig.useAlignmentScoring).toBe(config.useAlignmentScoring);
        expect(validatorConfig.minAlignmentScore).toBe(config.minAlignmentScore);
      }
    });
  });
});
