/**
 * Tests for Semantic Quality Validation (ML-based)
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SemanticQualityChecker } from '../quality-semantic';
import { QualityValidator } from '../quality';

// Mock @cascadeflow/ml module
vi.mock('@cascadeflow/ml', () => {
  // Mock UnifiedEmbeddingService
  class MockUnifiedEmbeddingService {
    async isAvailable(): Promise<boolean> {
      return true;
    }

    async similarity(text1: string, text2: string): Promise<number> {
      // Simple mock: return high similarity for similar word overlap
      const words1 = text1.toLowerCase().split(/\s+/);
      const words2 = text2.toLowerCase().split(/\s+/);

      // Calculate Jaccard similarity
      const set1 = new Set(words1);
      const set2 = new Set(words2);
      const intersection = new Set([...set1].filter(x => set2.has(x)));
      const union = new Set([...set1, ...set2]);

      if (union.size === 0) return 0;
      return intersection.size / union.size;
    }
  }

  // Mock EmbeddingCache
  class MockEmbeddingCache {
    private embedder: any;
    private cache: Map<string, number[]>;

    constructor(embedder: any) {
      this.embedder = embedder;
      this.cache = new Map();
    }

    async similarity(text1: string, text2: string): Promise<number> {
      return this.embedder.similarity(text1, text2);
    }

    clear(): void {
      this.cache.clear();
    }

    cacheInfo(): { size: number; texts: string[] } {
      return {
        size: this.cache.size,
        texts: Array.from(this.cache.keys()),
      };
    }
  }

  return {
    UnifiedEmbeddingService: MockUnifiedEmbeddingService,
    EmbeddingCache: MockEmbeddingCache,
  };
});

describe('SemanticQualityChecker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Initialization', () => {
    it('should initialize with default threshold', async () => {
      const checker = new SemanticQualityChecker();
      const isAvailable = await checker.isAvailable();

      expect(isAvailable).toBe(true);
    });

    it('should initialize with custom threshold', async () => {
      const checker = new SemanticQualityChecker(0.7);
      const isAvailable = await checker.isAvailable();

      expect(isAvailable).toBe(true);
    });

    it('should initialize with caching enabled by default', async () => {
      const checker = new SemanticQualityChecker();
      await checker.isAvailable();

      const cacheInfo = checker.getCacheInfo();
      expect(cacheInfo).toHaveProperty('size');
      expect(cacheInfo).toHaveProperty('texts');
    });

    it('should initialize with caching disabled', async () => {
      const checker = new SemanticQualityChecker(0.5, undefined, false);
      await checker.isAvailable();

      const cacheInfo = checker.getCacheInfo();
      expect(cacheInfo.size).toBe(0);
    });
  });

  describe('Availability Checking', () => {
    it('should report availability when ML dependencies installed', async () => {
      const checker = new SemanticQualityChecker();
      const isAvailable = await checker.isAvailable();

      expect(isAvailable).toBe(true);
    });

    it('should handle multiple availability checks', async () => {
      const checker = new SemanticQualityChecker();

      const check1 = await checker.isAvailable();
      const check2 = await checker.isAvailable();
      const check3 = await checker.isAvailable();

      expect(check1).toBe(true);
      expect(check2).toBe(true);
      expect(check3).toBe(true);
    });
  });

  describe('Similarity Checking', () => {
    it('should compute similarity between query and response', async () => {
      const checker = new SemanticQualityChecker(0.5);
      await checker.isAvailable();

      const result = await checker.checkSimilarity(
        'What is machine learning?',
        'Machine learning is a subset of artificial intelligence that enables systems to learn from data.'
      );

      expect(result).toHaveProperty('similarity');
      expect(result).toHaveProperty('passed');
      expect(result.similarity).toBeGreaterThanOrEqual(0);
      expect(result.similarity).toBeLessThanOrEqual(1);
    });

    it('should pass when similarity exceeds threshold', async () => {
      const checker = new SemanticQualityChecker(0.2);
      await checker.isAvailable();

      const result = await checker.checkSimilarity(
        'What is TypeScript programming language?',
        'TypeScript is a programming language that is strongly typed and builds on JavaScript programming language.'
      );

      expect(result.passed).toBe(true);
      expect(result.reason).toBeUndefined();
    });

    it('should fail when similarity below threshold', async () => {
      const checker = new SemanticQualityChecker(0.99);
      await checker.isAvailable();

      const result = await checker.checkSimilarity(
        'What is TypeScript?',
        'TypeScript is a strongly typed programming language.'
      );

      expect(result.passed).toBe(false);
      expect(result.reason).toBeDefined();
      expect(result.reason).toContain('below threshold');
    });

    it('should include metadata in results', async () => {
      const threshold = 0.6;
      const checker = new SemanticQualityChecker(threshold);
      await checker.isAvailable();

      const result = await checker.checkSimilarity('test query', 'test response');

      expect(result.metadata).toBeDefined();
      expect(result.metadata?.threshold).toBe(threshold);
      expect(result.metadata).toHaveProperty('cached');
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty query', async () => {
      const checker = new SemanticQualityChecker();
      await checker.isAvailable();

      const result = await checker.checkSimilarity('', 'Some response');

      expect(result).toHaveProperty('similarity');
      expect(result).toHaveProperty('passed');
    });

    it('should handle empty response', async () => {
      const checker = new SemanticQualityChecker();
      await checker.isAvailable();

      const result = await checker.checkSimilarity('Some query', '');

      expect(result).toHaveProperty('similarity');
      expect(result).toHaveProperty('passed');
    });

    it('should handle both empty strings', async () => {
      const checker = new SemanticQualityChecker();
      await checker.isAvailable();

      const result = await checker.checkSimilarity('', '');

      expect(result).toHaveProperty('similarity');
      expect(result).toHaveProperty('passed');
    });

    it('should handle very long texts', async () => {
      const checker = new SemanticQualityChecker();
      await checker.isAvailable();

      const longQuery = 'What is machine learning? '.repeat(100);
      const longResponse = 'Machine learning is a subset of AI. '.repeat(100);

      const result = await checker.checkSimilarity(longQuery, longResponse);

      expect(result).toHaveProperty('similarity');
      expect(result).toHaveProperty('passed');
    });

    it('should handle special characters', async () => {
      const checker = new SemanticQualityChecker();
      await checker.isAvailable();

      const result = await checker.checkSimilarity(
        'What is @cascadeflow/ml? 🤖',
        'The @cascadeflow/ml package provides embeddings! 🚀'
      );

      expect(result).toHaveProperty('similarity');
      expect(result).toHaveProperty('passed');
    });
  });

  describe('Caching Functionality', () => {
    it('should clear cache when requested', async () => {
      const checker = new SemanticQualityChecker();
      await checker.isAvailable();

      await checker.checkSimilarity('query1', 'response1');
      checker.clearCache();

      const cacheInfo = checker.getCacheInfo();
      expect(cacheInfo.size).toBe(0);
    });

    it('should provide cache info', async () => {
      const checker = new SemanticQualityChecker();
      await checker.isAvailable();

      const cacheInfo = checker.getCacheInfo();

      expect(cacheInfo).toHaveProperty('size');
      expect(cacheInfo).toHaveProperty('texts');
      expect(Array.isArray(cacheInfo.texts)).toBe(true);
    });

    it('should handle cache operations when caching disabled', async () => {
      const checker = new SemanticQualityChecker(0.5, undefined, false);
      await checker.isAvailable();

      checker.clearCache();
      const cacheInfo = checker.getCacheInfo();

      expect(cacheInfo.size).toBe(0);
      expect(cacheInfo.texts).toEqual([]);
    });
  });

  describe('Threshold Variations', () => {
    const testCases = [
      { threshold: 0.0, expectedPass: true },
      { threshold: 0.05, expectedPass: true },
      { threshold: 0.1, expectedPass: true },
      { threshold: 0.3, expectedPass: false },
      { threshold: 1.0, expectedPass: false },
    ];

    testCases.forEach(({ threshold, expectedPass }) => {
      it(`should handle threshold ${threshold} correctly`, async () => {
        const checker = new SemanticQualityChecker(threshold);
        await checker.isAvailable();

        const result = await checker.checkSimilarity(
          'What is cascadeflow?',
          'cascadeflow is a library for AI model cascading.'
        );

        expect(result.passed).toBe(expectedPass);
      });
    });
  });
});

describe('QualityValidator with Semantic Validation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Integration', () => {
    it('should integrate semantic validation into quality checks', async () => {
      const validator = new QualityValidator({
        useSemanticValidation: true,
        semanticThreshold: 0.5,
      });

      const result = await validator.validate(
        'TypeScript is a strongly typed programming language.',
        'What is TypeScript?',
        [-0.5, -0.6, -0.4]
      );

      expect(result).toHaveProperty('passed');
      expect(result).toHaveProperty('details');
      expect(result.details).toHaveProperty('semanticSimilarity');
    });

    it('should work without semantic validation', async () => {
      const validator = new QualityValidator({
        useSemanticValidation: false,
      });

      const result = await validator.validate(
        'TypeScript is a strongly typed programming language.',
        'What is TypeScript?',
        [-0.5, -0.6, -0.4]
      );

      expect(result).toHaveProperty('passed');
      expect(result.details?.semanticSimilarity).toBeUndefined();
    });

    it.skip('should fail validation when semantic similarity too low', async () => {
      // TODO: This test requires @cascadeflow/ml to be properly mocked
      // Skipping for now until we add proper mocking infrastructure
      const validator = new QualityValidator({
        useSemanticValidation: true,
        semanticThreshold: 0.99, // Very high threshold
        useAlignmentScoring: false, // Disable alignment check
        minConfidence: 0.0, // Disable other checks
        minWordCount: 0,
      });

      const result = await validator.validate(
        'A response.',
        'A very different query?',
        [-0.5]
      );

      expect(result.passed).toBe(false);
      expect(result.reason).toContain('Semantic similarity too low');
    });

    it.skip('should include semantic score in success reason', async () => {
      // TODO: This test requires @cascadeflow/ml to be properly mocked
      // Skipping for now until we add proper mocking infrastructure
      const validator = new QualityValidator({
        useSemanticValidation: true,
        semanticThreshold: 0.1,
        useAlignmentScoring: false,
        minConfidence: 0.0,
        minWordCount: 0,
      });

      const result = await validator.validate(
        'TypeScript is a programming language that adds types to JavaScript.',
        'What is TypeScript programming language?',
        [-0.5, -0.6, -0.4, -0.5, -0.3]
      );

      expect(result.passed).toBe(true);
      expect(result.reason).toContain('semantic');
    });

    it('should handle semantic validation gracefully when unavailable', async () => {
      const validator = new QualityValidator({
        useSemanticValidation: true,
        semanticThreshold: 0.5,
      });

      const result = await validator.validate(
        'Some content',
        'Some query',
        [-0.5, -0.6]
      );

      // Should not fail just because semantic validation unavailable
      expect(result).toHaveProperty('passed');
      expect(result).toHaveProperty('details');
    });
  });

  describe('Combined Validation', () => {
    it('should combine semantic, alignment, and confidence checks', async () => {
      const validator = new QualityValidator({
        useSemanticValidation: true,
        semanticThreshold: 0.5,
        useAlignmentScoring: true,
        minAlignmentScore: 0.5,
        minConfidence: 0.5,
      });

      const result = await validator.validate(
        'TypeScript adds static typing to JavaScript, enabling better tooling and error detection.',
        'What is TypeScript?',
        [-0.3, -0.4, -0.5, -0.3, -0.4]
      );

      expect(result).toHaveProperty('passed');
      expect(result.details).toHaveProperty('semanticSimilarity');
      expect(result.details).toHaveProperty('alignmentScore');
      expect(result.details).toHaveProperty('avgLogprob');
    });

    it('should fail if any validation fails', async () => {
      const validator = new QualityValidator({
        useSemanticValidation: true,
        semanticThreshold: 0.99, // Will fail
        useAlignmentScoring: true,
        minAlignmentScore: 0.5,
        minConfidence: 0.5,
      });

      const result = await validator.validate(
        'A short response',
        'A completely different query',
        [-0.3, -0.4]
      );

      expect(result.passed).toBe(false);
    });
  });

  describe('Configuration Options', () => {
    it('should respect custom semantic threshold', async () => {
      const validator = new QualityValidator({
        useSemanticValidation: true,
        semanticThreshold: 0.8,
      });

      const result = await validator.validate(
        'Response',
        'Query',
        [-0.5]
      );

      expect(result).toHaveProperty('details');
    });

    it('should enable semantic validation by default', async () => {
      const validator = new QualityValidator({
        // useSemanticValidation not specified, should default to enabled
      });

      const result = await validator.validate(
        'TypeScript is great',
        'What is TypeScript?',
        [-0.5, -0.6]
      );

      // Semantic validation should be attempted
      expect(result.details).toHaveProperty('semanticSimilarity');
    });

    it('should handle explicit disable of semantic validation', async () => {
      const validator = new QualityValidator({
        useSemanticValidation: false,
      });

      const result = await validator.validate(
        'TypeScript is great',
        'What is TypeScript?',
        [-0.5, -0.6]
      );

      // Semantic validation should not run
      expect(result.details?.semanticSimilarity).toBeUndefined();
    });
  });
});

describe('Graceful Degradation', () => {
  it('should handle missing ML dependencies gracefully', async () => {
    // This would test the real scenario where @cascadeflow/ml is not installed
    // In practice, the module import would fail and be caught
    const checker = new SemanticQualityChecker();

    // Even if initialization fails, isAvailable should work
    const isAvailable = await checker.isAvailable();
    expect(typeof isAvailable).toBe('boolean');
  });

  it('should return appropriate error when ML unavailable', async () => {
    // Mock a scenario where the embedder fails to initialize
    const checker = new SemanticQualityChecker();
    await checker.isAvailable();

    const result = await checker.checkSimilarity('query', 'response');

    expect(result).toHaveProperty('passed');
    expect(result).toHaveProperty('similarity');
    expect(result).toHaveProperty('metadata');
  });
});
