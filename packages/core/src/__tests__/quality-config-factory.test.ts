/**
 * Tests for QualityConfigFactory
 *
 * Tests quality configuration factory methods for different use cases
 *
 * Run: pnpm test quality-config-factory.test.ts
 */

import { describe, it, expect } from 'vitest';
import { QualityConfigFactory } from '../quality';
import type { QualityConfig } from '../quality';

describe('QualityConfigFactory', () => {
  describe('forProduction', () => {
    it('should create production quality config', () => {
      const config = QualityConfigFactory.forProduction();

      expect(config).toBeDefined();
      expect(config.minConfidence).toBe(0.55);
      expect(config.confidenceThresholds).toBeDefined();
      expect(config.useLogprobs).toBe(true);
      expect(config.strictMode).toBe(false);
    });

    it('should have cascade-optimized thresholds by complexity', () => {
      const config = QualityConfigFactory.forProduction();

      // Synced with Python cascadeflow/quality/quality.py defaults
      // Cascade-optimized: inverted thresholds (harder → lower → escalate to verifier)
      expect(config.confidenceThresholds?.trivial).toBe(0.55);
      expect(config.confidenceThresholds?.simple).toBe(0.50);
      expect(config.confidenceThresholds?.moderate).toBe(0.45);
      expect(config.confidenceThresholds?.hard).toBe(0.42);
      expect(config.confidenceThresholds?.expert).toBe(0.40);
    });

    it('should have cascade-appropriate acceptance rate', () => {
      const config = QualityConfigFactory.forProduction();

      // Production is cascade-optimized, more lenient than strict
      expect(config.minConfidence).toBeGreaterThanOrEqual(0.50);
      expect(config.minConfidence).toBeLessThan(0.85); // Strict fallback
    });

    it('should use alignment scoring', () => {
      const config = QualityConfigFactory.forProduction();

      expect(config.useAlignmentScoring).toBe(true);
      expect(config.minAlignmentScore).toBe(0.15);
    });
  });

  describe('forDevelopment', () => {
    it('should create development quality config', () => {
      const config = QualityConfigFactory.forDevelopment();

      expect(config).toBeDefined();
      expect(config.minConfidence).toBe(0.70);
      expect(config.minWordCount).toBe(8);
      expect(config.strictMode).toBe(false);
    });

    it('should have higher thresholds than cascade-optimized production', () => {
      const prodConfig = QualityConfigFactory.forProduction();
      const devConfig = QualityConfigFactory.forDevelopment();

      // Production uses cascade-optimized inverted thresholds (Python-synced),
      // so dev thresholds are actually higher (stricter) than prod
      expect(devConfig.minConfidence).toBeGreaterThanOrEqual(prodConfig.minConfidence);
      expect(devConfig.confidenceThresholds?.trivial).toBeLessThanOrEqual(
        prodConfig.confidenceThresholds?.trivial!
      );
      expect(devConfig.confidenceThresholds?.expert).toBeGreaterThan(
        prodConfig.confidenceThresholds?.expert!
      );
    });

    it('should have lower thresholds for all complexities', () => {
      const config = QualityConfigFactory.forDevelopment();

      expect(config.confidenceThresholds?.trivial).toBe(0.50);
      expect(config.confidenceThresholds?.simple).toBe(0.60);
      expect(config.confidenceThresholds?.moderate).toBe(0.70);
      expect(config.confidenceThresholds?.hard).toBe(0.75);
      expect(config.confidenceThresholds?.expert).toBe(0.80);
    });
  });

  describe('strict', () => {
    it('should create strict quality config', () => {
      const config = QualityConfigFactory.strict();

      expect(config).toBeDefined();
      expect(config.minConfidence).toBe(0.85);
      expect(config.strictMode).toBe(true);
      expect(config.useSemanticValidation).toBe(true);
    });

    it('should be stricter than production', () => {
      const prodConfig = QualityConfigFactory.forProduction();
      const strictConfig = QualityConfigFactory.strict();

      expect(strictConfig.minConfidence).toBeGreaterThan(prodConfig.minConfidence);
      expect(strictConfig.confidenceThresholds?.trivial).toBeGreaterThan(
        prodConfig.confidenceThresholds?.trivial!
      );
      expect(strictConfig.confidenceThresholds?.expert).toBeGreaterThan(
        prodConfig.confidenceThresholds?.expert!
      );
    });

    it('should have high thresholds for all complexities', () => {
      const config = QualityConfigFactory.strict();

      expect(config.confidenceThresholds?.trivial).toBe(0.70);
      expect(config.confidenceThresholds?.simple).toBe(0.80);
      expect(config.confidenceThresholds?.moderate).toBe(0.85);
      expect(config.confidenceThresholds?.hard).toBe(0.90);
      expect(config.confidenceThresholds?.expert).toBe(0.95);
    });

    it('should have higher alignment floor', () => {
      const config = QualityConfigFactory.strict();

      expect(config.minAlignmentScore).toBe(0.20);
      expect(config.minAlignmentScore).toBeGreaterThan(
        QualityConfigFactory.forProduction().minAlignmentScore!
      );
    });

    it('should enable semantic validation', () => {
      const config = QualityConfigFactory.strict();

      expect(config.useSemanticValidation).toBe(true);
      expect(config.semanticThreshold).toBe(0.6);
    });

    it('should have longer minimum word count', () => {
      const config = QualityConfigFactory.strict();

      expect(config.minWordCount).toBe(15);
      expect(config.minWordCount).toBeGreaterThan(
        QualityConfigFactory.forProduction().minWordCount
      );
    });
  });

  describe('forCascade', () => {
    it('should create cascade-optimized quality config', () => {
      const config = QualityConfigFactory.forCascade();

      expect(config).toBeDefined();
      expect(config.minConfidence).toBe(0.55);
      expect(config.minWordCount).toBe(5);
      expect(config.strictMode).toBe(false);
    });

    it('should be more lenient than production for word count', () => {
      const prodConfig = QualityConfigFactory.forProduction();
      const cascadeConfig = QualityConfigFactory.forCascade();

      // Both share cascade-optimized minConfidence (0.55), but cascade has lower word count
      expect(cascadeConfig.minConfidence).toBeLessThanOrEqual(prodConfig.minConfidence);
      expect(cascadeConfig.minWordCount).toBeLessThan(prodConfig.minWordCount);
      // Cascade has traditional increasing thresholds while production has inverted
      // so cascade.moderate (0.55) > prod.moderate (0.45)
      expect(cascadeConfig.confidenceThresholds?.trivial).toBeLessThan(
        prodConfig.confidenceThresholds?.trivial!
      );
    });

    it('should have relaxed thresholds for optimal cascade performance', () => {
      const config = QualityConfigFactory.forCascade();

      expect(config.confidenceThresholds?.trivial).toBe(0.25);
      expect(config.confidenceThresholds?.simple).toBe(0.40);
      expect(config.confidenceThresholds?.moderate).toBe(0.55);
      expect(config.confidenceThresholds?.hard).toBe(0.70);
      expect(config.confidenceThresholds?.expert).toBe(0.80);
    });

    it('should target 50-60% acceptance rate', () => {
      const config = QualityConfigFactory.forCascade();

      // Lower thresholds = higher acceptance
      expect(config.confidenceThresholds?.moderate).toBeLessThan(0.60);
      expect(config.minWordCount).toBeLessThanOrEqual(5);
    });

    it('should disable semantic validation for speed', () => {
      const config = QualityConfigFactory.forCascade();

      expect(config.useSemanticValidation).toBe(false);
    });
  });

  describe('permissive', () => {
    it('should create permissive quality config', () => {
      const config = QualityConfigFactory.permissive();

      expect(config).toBeDefined();
      expect(config.minConfidence).toBe(0.50);
      expect(config.minWordCount).toBe(3);
      expect(config.strictMode).toBe(false);
    });

    it('should be the most lenient config', () => {
      const devConfig = QualityConfigFactory.forDevelopment();
      const cascadeConfig = QualityConfigFactory.forCascade();
      const permissiveConfig = QualityConfigFactory.permissive();

      expect(permissiveConfig.minConfidence).toBeLessThanOrEqual(devConfig.minConfidence);
      expect(permissiveConfig.minConfidence).toBeLessThanOrEqual(cascadeConfig.minConfidence);
      expect(permissiveConfig.minWordCount).toBeLessThanOrEqual(devConfig.minWordCount);
      expect(permissiveConfig.minWordCount).toBeLessThanOrEqual(cascadeConfig.minWordCount);
    });

    it('should have very low thresholds', () => {
      const config = QualityConfigFactory.permissive();

      expect(config.confidenceThresholds?.trivial).toBe(0.30);
      expect(config.confidenceThresholds?.simple).toBe(0.40);
      expect(config.confidenceThresholds?.moderate).toBe(0.50);
      expect(config.confidenceThresholds?.hard).toBe(0.60);
      expect(config.confidenceThresholds?.expert).toBe(0.70);
    });

    it('should have low alignment floor', () => {
      const config = QualityConfigFactory.permissive();

      expect(config.minAlignmentScore).toBe(0.10);
      expect(config.minAlignmentScore).toBeLessThan(
        QualityConfigFactory.forProduction().minAlignmentScore!
      );
    });
  });

  describe('comparative analysis', () => {
    it('should have strictness ordering: permissive < cascade < dev < strict (production uses inverted)', () => {
      const permissive = QualityConfigFactory.permissive();
      const cascade = QualityConfigFactory.forCascade();
      const dev = QualityConfigFactory.forDevelopment();
      const prod = QualityConfigFactory.forProduction();
      const strict = QualityConfigFactory.strict();

      // Traditional presets follow increasing moderate thresholds
      expect(permissive.confidenceThresholds?.moderate).toBeLessThan(
        cascade.confidenceThresholds?.moderate!
      );
      expect(cascade.confidenceThresholds?.moderate).toBeLessThanOrEqual(
        dev.confidenceThresholds?.moderate!
      );
      expect(dev.confidenceThresholds?.moderate).toBeLessThan(
        strict.confidenceThresholds?.moderate!
      );

      // Production uses cascade-optimized inverted thresholds (Python-synced)
      // so prod.moderate (0.45) is lower than all traditional presets
      expect(prod.confidenceThresholds?.expert).toBeLessThan(
        strict.confidenceThresholds?.expert!
      );
      expect(prod.minConfidence).toBeLessThan(strict.minConfidence);
    });

    it('should all enable logprobs', () => {
      const configs = [
        QualityConfigFactory.forProduction(),
        QualityConfigFactory.forDevelopment(),
        QualityConfigFactory.strict(),
        QualityConfigFactory.forCascade(),
        QualityConfigFactory.permissive(),
      ];

      for (const config of configs) {
        expect(config.useLogprobs).toBe(true);
      }
    });

    it('should all enable alignment scoring', () => {
      const configs = [
        QualityConfigFactory.forProduction(),
        QualityConfigFactory.forDevelopment(),
        QualityConfigFactory.strict(),
        QualityConfigFactory.forCascade(),
        QualityConfigFactory.permissive(),
      ];

      for (const config of configs) {
        expect(config.useAlignmentScoring).toBe(true);
        expect(config.minAlignmentScore).toBeGreaterThan(0);
      }
    });

    it('should all enable fallback to heuristic', () => {
      const configs = [
        QualityConfigFactory.forProduction(),
        QualityConfigFactory.forDevelopment(),
        QualityConfigFactory.strict(),
        QualityConfigFactory.forCascade(),
        QualityConfigFactory.permissive(),
      ];

      for (const config of configs) {
        expect(config.fallbackToHeuristic).toBe(true);
      }
    });

    it('should only strict enable semantic validation', () => {
      expect(QualityConfigFactory.forProduction().useSemanticValidation).toBe(false);
      expect(QualityConfigFactory.forDevelopment().useSemanticValidation).toBe(false);
      expect(QualityConfigFactory.strict().useSemanticValidation).toBe(true);
      expect(QualityConfigFactory.forCascade().useSemanticValidation).toBe(false);
      expect(QualityConfigFactory.permissive().useSemanticValidation).toBe(false);
    });

    it('should only strict enable strict mode', () => {
      expect(QualityConfigFactory.forProduction().strictMode).toBe(false);
      expect(QualityConfigFactory.forDevelopment().strictMode).toBe(false);
      expect(QualityConfigFactory.strict().strictMode).toBe(true);
      expect(QualityConfigFactory.forCascade().strictMode).toBe(false);
      expect(QualityConfigFactory.permissive().strictMode).toBe(false);
    });
  });

  describe('configuration completeness', () => {
    const requiredFields: (keyof QualityConfig)[] = [
      'minConfidence',
      'minWordCount',
      'useLogprobs',
      'fallbackToHeuristic',
      'strictMode',
      'useAlignmentScoring',
      'minAlignmentScore',
    ];

    it('should have all required fields in forProduction', () => {
      const config = QualityConfigFactory.forProduction();
      for (const field of requiredFields) {
        expect(config[field]).toBeDefined();
      }
    });

    it('should have all required fields in forDevelopment', () => {
      const config = QualityConfigFactory.forDevelopment();
      for (const field of requiredFields) {
        expect(config[field]).toBeDefined();
      }
    });

    it('should have all required fields in strict', () => {
      const config = QualityConfigFactory.strict();
      for (const field of requiredFields) {
        expect(config[field]).toBeDefined();
      }
    });

    it('should have all required fields in forCascade', () => {
      const config = QualityConfigFactory.forCascade();
      for (const field of requiredFields) {
        expect(config[field]).toBeDefined();
      }
    });

    it('should have all required fields in permissive', () => {
      const config = QualityConfigFactory.permissive();
      for (const field of requiredFields) {
        expect(config[field]).toBeDefined();
      }
    });
  });

  describe('threshold ranges', () => {
    it('should have all thresholds between 0 and 1', () => {
      const configs = [
        QualityConfigFactory.forProduction(),
        QualityConfigFactory.forDevelopment(),
        QualityConfigFactory.strict(),
        QualityConfigFactory.forCascade(),
        QualityConfigFactory.permissive(),
      ];

      for (const config of configs) {
        expect(config.minConfidence).toBeGreaterThanOrEqual(0);
        expect(config.minConfidence).toBeLessThanOrEqual(1);

        if (config.confidenceThresholds) {
          for (const threshold of Object.values(config.confidenceThresholds)) {
            expect(threshold).toBeGreaterThanOrEqual(0);
            expect(threshold).toBeLessThanOrEqual(1);
          }
        }

        expect(config.minAlignmentScore).toBeGreaterThanOrEqual(0);
        expect(config.minAlignmentScore).toBeLessThanOrEqual(1);
      }
    });

    it('should have increasing thresholds by complexity for traditional presets', () => {
      // Traditional presets have increasing thresholds (harder → higher threshold)
      const traditionalConfigs = [
        QualityConfigFactory.forDevelopment(),
        QualityConfigFactory.strict(),
        QualityConfigFactory.forCascade(),
        QualityConfigFactory.permissive(),
      ];

      for (const config of traditionalConfigs) {
        const thresholds = config.confidenceThresholds;
        if (thresholds) {
          expect(thresholds.trivial).toBeLessThanOrEqual(thresholds.simple!);
          expect(thresholds.simple).toBeLessThanOrEqual(thresholds.moderate!);
          expect(thresholds.moderate).toBeLessThanOrEqual(thresholds.hard!);
          expect(thresholds.hard).toBeLessThanOrEqual(thresholds.expert!);
        }
      }
    });

    it('should have inverted thresholds for cascade-optimized production', () => {
      // Production uses cascade-optimized inverted thresholds (Python-synced)
      // harder → lower threshold → escalate to verifier more often
      const prod = QualityConfigFactory.forProduction();
      const thresholds = prod.confidenceThresholds!;

      expect(thresholds.trivial).toBeGreaterThanOrEqual(thresholds.simple!);
      expect(thresholds.simple).toBeGreaterThanOrEqual(thresholds.moderate!);
      expect(thresholds.moderate).toBeGreaterThanOrEqual(thresholds.hard!);
      expect(thresholds.hard).toBeGreaterThanOrEqual(thresholds.expert!);
    });
  });
});
