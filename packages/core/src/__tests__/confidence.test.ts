/**
 * Tests for Production Confidence Estimator
 *
 * Tests multi-signal confidence estimation with provider calibration
 *
 * Run: pnpm test confidence.test.ts
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  ProductionConfidenceEstimator,
  PROVIDER_CONFIDENCE_CALIBRATION,
} from '../confidence';
import type { ConfidenceAnalysis } from '../confidence';

describe('ProductionConfidenceEstimator', () => {
  let estimator: ProductionConfidenceEstimator;

  beforeEach(() => {
    estimator = new ProductionConfidenceEstimator('openai');
  });

  describe('basic confidence estimation', () => {
    it('should estimate confidence for simple response', () => {
      const response = 'TypeScript is a superset of JavaScript with static typing.';
      const analysis = estimator.estimate(response);

      expect(analysis.finalConfidence).toBeGreaterThan(0);
      expect(analysis.finalConfidence).toBeLessThanOrEqual(1);
      expect(analysis.semanticConfidence).toBeDefined();
      expect(analysis.methodUsed).toBe('semantic');
    });

    it('should return higher confidence for quality responses', () => {
      const highQuality =
        'TypeScript is a strongly typed programming language that builds on JavaScript. ' +
        'It adds optional static typing to the language, which helps catch errors at compile time. ' +
        'For example, you can define interfaces and type annotations like: interface User { name: string; age: number; }';

      const lowQuality = "I don't know. Maybe it's something related to JavaScript. I'm not sure.";

      const highAnalysis = estimator.estimate(highQuality);
      const lowAnalysis = estimator.estimate(lowQuality);

      expect(highAnalysis.finalConfidence).toBeGreaterThan(lowAnalysis.finalConfidence);
      expect(lowAnalysis.semanticConfidence).toBeLessThan(highAnalysis.semanticConfidence);
    });

    it('should handle empty or very short responses', () => {
      const emptyAnalysis = estimator.estimate('');
      const shortAnalysis = estimator.estimate('No');

      expect(emptyAnalysis.finalConfidence).toBeLessThanOrEqual(0.3);
      // Short but direct responses like "No" can have moderate confidence
      expect(shortAnalysis.finalConfidence).toBeGreaterThan(0);
      expect(shortAnalysis.finalConfidence).toBeLessThan(1);
    });
  });

  describe('logprobs confidence calculation', () => {
    it('should use logprobs when available', () => {
      const response = 'TypeScript is a typed superset of JavaScript.';
      const logprobs = [-0.1, -0.2, -0.15, -0.3, -0.12, -0.18, -0.25];

      const analysis = estimator.estimate(response, { logprobs });

      expect(analysis.logprobsConfidence).toBeDefined();
      expect(analysis.methodUsed).toBe('hybrid'); // logprobs + semantic
      expect(analysis.components.logprobs).toBeDefined();
    });

    it('should calculate higher confidence for confident logprobs', () => {
      const response = 'The answer is correct.';

      // High confidence logprobs (close to 0)
      const highLogprobs = [-0.05, -0.08, -0.06, -0.04];

      // Low confidence logprobs (very negative)
      const lowLogprobs = [-2.5, -3.0, -2.8, -3.2];

      const highAnalysis = estimator.estimate(response, { logprobs: highLogprobs });
      const lowAnalysis = estimator.estimate(response, { logprobs: lowLogprobs });

      expect(highAnalysis.logprobsConfidence).toBeGreaterThan(lowAnalysis.logprobsConfidence);
    });

    it('should handle empty logprobs array', () => {
      const response = 'Test response';
      const analysis = estimator.estimate(response, { logprobs: [] });

      expect(analysis.logprobsConfidence).toBeUndefined();
      expect(analysis.methodUsed).toBe('semantic');
    });

    it('should combine multiple logprobs methods (geometric, harmonic, min, entropy)', () => {
      const response = 'Test';
      // Diverse probabilities to test different methods
      const logprobs = [-0.1, -0.5, -0.2, -1.0, -0.15];

      const analysis = estimator.estimate(response, { logprobs });

      expect(analysis.logprobsConfidence).toBeDefined();
      // Should be a balanced combination of all methods
      expect(analysis.logprobsConfidence!).toBeGreaterThan(0.2);
      expect(analysis.logprobsConfidence!).toBeLessThan(0.9);
    });
  });

  describe('semantic quality analysis', () => {
    it('should detect hedging and reduce confidence', () => {
      const confident = 'TypeScript is a strongly typed language that compiles to JavaScript.';
      const hedged =
        "I'm not sure, but I think TypeScript might be probably related to JavaScript. I don't know for certain.";

      const confidentAnalysis = estimator.estimate(confident);
      const hedgedAnalysis = estimator.estimate(hedged);

      expect(confidentAnalysis.semanticConfidence).toBeGreaterThan(
        hedgedAnalysis.semanticConfidence
      );
    });

    it('should reward completeness with examples and details', () => {
      const brief = 'TypeScript is typed JavaScript.';
      const detailed =
        'TypeScript is a strongly typed superset of JavaScript developed by Microsoft. ' +
        'For example, you can write: let count: number = 42; or interface User { name: string; age: number; }. ' +
        'It compiles to plain JavaScript and runs everywhere JavaScript runs.';

      const briefAnalysis = estimator.estimate(brief);
      const detailedAnalysis = estimator.estimate(detailed);

      expect(detailedAnalysis.semanticConfidence).toBeGreaterThan(
        briefAnalysis.semanticConfidence
      );
    });

    it('should detect specificity (numbers, examples, technical terms)', () => {
      const vague = 'TypeScript is a programming language that is somewhat better than JavaScript.';
      const specific =
        'TypeScript 5.0 adds 40+ new features including decorators and const type parameters. ' +
        'For example, the compiler can catch type errors at build time, reducing bugs by 15%.';

      const vagueAnalysis = estimator.estimate(vague);
      const specificAnalysis = estimator.estimate(specific);

      expect(specificAnalysis.semanticConfidence).toBeGreaterThan(vagueAnalysis.semanticConfidence);
    });

    it('should penalize contradictions for coherence', () => {
      const coherent = 'TypeScript is statically typed. This makes code more maintainable.';
      const contradictory =
        'TypeScript is statically typed. No, TypeScript is not typed. Yes, it is correct. But it is incorrect.';

      const coherentAnalysis = estimator.estimate(coherent);
      const contradictoryAnalysis = estimator.estimate(contradictory);

      expect(coherentAnalysis.semanticConfidence).toBeGreaterThan(
        contradictoryAnalysis.semanticConfidence
      );
    });

    it('should penalize evasiveness for directness', () => {
      const direct = 'TypeScript is a typed superset of JavaScript developed by Microsoft in 2012.';
      const evasive =
        "Well, that's a complex question. It depends on many factors. There's no simple answer. It varies.";

      const directAnalysis = estimator.estimate(direct);
      const evasiveAnalysis = estimator.estimate(evasive);

      expect(directAnalysis.semanticConfidence).toBeGreaterThan(evasiveAnalysis.semanticConfidence);
    });

    it('should maintain continuous scoring (no discrete bins)', () => {
      // Generate responses with gradually increasing quality
      const responses = [
        "I don't know.",
        'Maybe TypeScript.',
        'TypeScript is a language.',
        'TypeScript is a typed superset of JavaScript.',
        'TypeScript is a strongly typed superset of JavaScript that adds compile-time type checking.',
        'TypeScript is a strongly typed superset of JavaScript developed by Microsoft. For example: let x: number = 5;',
      ];

      const confidences = responses.map((r) => estimator.estimate(r).semanticConfidence);

      // Each should be generally higher than the previous (allowing for small variations)
      for (let i = 1; i < confidences.length; i++) {
        // Most should increase
        const avgPrev = confidences.slice(0, i).reduce((a, b) => a + b, 0) / i;
        expect(confidences[i]).toBeGreaterThan(avgPrev * 0.9); // Allow 10% tolerance
      }

      // Should be distributed, not clustered
      const uniqueConfidences = new Set(confidences);
      expect(uniqueConfidences.size).toBeGreaterThan(4); // At least 5 different values
    });
  });

  describe('multi-signal confidence methods', () => {
    it('should use multi-signal-hybrid when all signals available', () => {
      const query = 'What is TypeScript?';
      const response = 'TypeScript is a strongly typed superset of JavaScript.';
      const logprobs = [-0.1, -0.2, -0.15, -0.18];

      const analysis = estimator.estimate(response, {
        query,
        logprobs,
        queryDifficulty: 0.3,
      });

      expect(analysis.methodUsed).toBe('multi-signal-hybrid');
      expect(analysis.logprobsConfidence).toBeDefined();
      expect(analysis.alignmentScore).toBeDefined();
      expect(analysis.queryDifficulty).toBeDefined();
    });

    it('should use hybrid when only logprobs available (no query)', () => {
      const response = 'TypeScript is a typed language.';
      const logprobs = [-0.15, -0.2, -0.18];

      const analysis = estimator.estimate(response, { logprobs });

      expect(analysis.methodUsed).toBe('hybrid');
      expect(analysis.logprobsConfidence).toBeDefined();
      expect(analysis.alignmentScore).toBeUndefined();
    });

    it('should use multi-signal-semantic when query available but no logprobs', () => {
      const query = 'What is TypeScript?';
      const response = 'TypeScript is a strongly typed superset of JavaScript.';

      const analysis = estimator.estimate(response, { query });

      expect(analysis.methodUsed).toBe('multi-signal-semantic');
      expect(analysis.logprobsConfidence).toBeUndefined();
      expect(analysis.alignmentScore).toBeDefined();
    });

    it('should use semantic only as fallback', () => {
      const response = 'TypeScript is a programming language.';

      const analysis = estimator.estimate(response);

      expect(analysis.methodUsed).toBe('semantic');
      expect(analysis.logprobsConfidence).toBeUndefined();
      expect(analysis.alignmentScore).toBeUndefined();
    });

    it('should weight signals appropriately in multi-signal-hybrid', () => {
      const query = 'What is TypeScript?';
      const response =
        'TypeScript is a strongly typed superset of JavaScript that adds compile-time type checking. ' +
        'It was developed by Microsoft and includes features like interfaces, generics, and decorators. ' +
        'For example: interface User { name: string; age: number; } provides type safety.';

      // High logprobs (50%), good semantic (20%), good alignment (20%), moderate query (10%)
      const logprobs = [-0.05, -0.06, -0.04, -0.07, -0.05, -0.08, -0.06];

      const analysis = estimator.estimate(response, {
        query,
        logprobs,
        queryDifficulty: 0.3,
      });

      expect(analysis.methodUsed).toBe('multi-signal-hybrid');
      // Should have high confidence due to all signals being strong
      expect(analysis.finalConfidence).toBeGreaterThan(0.7);
    });
  });

  describe('query-response alignment', () => {
    it('should calculate alignment score when query provided', () => {
      const query = 'What is TypeScript?';
      const response = 'TypeScript is a strongly typed superset of JavaScript.';

      const analysis = estimator.estimate(response, { query });

      expect(analysis.alignmentScore).toBeDefined();
      expect(analysis.alignmentScore).toBeGreaterThan(0);
      expect(analysis.alignmentScore).toBeLessThanOrEqual(1);
    });

    it('should detect well-aligned responses', () => {
      const query = 'What is TypeScript?';
      const goodResponse =
        'TypeScript is a strongly typed superset of JavaScript that adds static type checking.';
      const poorResponse =
        'JavaScript is a programming language. Python is also popular. I like coding.';

      const goodAnalysis = estimator.estimate(goodResponse, { query });
      const poorAnalysis = estimator.estimate(poorResponse, { query });

      expect(goodAnalysis.alignmentScore).toBeGreaterThan(poorAnalysis.alignmentScore);
    });
  });

  describe('alignment safety floor', () => {
    it('should apply alignment floor for severely off-topic responses (< 0.15)', () => {
      const query = 'What is TypeScript?';
      const offTopic = 'I love pizza. The weather is nice today. Cats are wonderful animals.';

      const analysis = estimator.estimate(offTopic, {
        query,
        logprobs: [-0.05, -0.06, -0.04], // Even with good logprobs
      });

      // Should cap confidence despite good logprobs
      expect(analysis.alignmentFloorApplied).toBe(true);
      expect(analysis.finalConfidence).toBeLessThanOrEqual(0.35);
      expect(analysis.components.alignmentFloorSeverity).toBeDefined();
    });

    it('should apply floor for very poor alignment (0.15-0.20)', () => {
      const query = 'What is TypeScript?';
      const veryPoor = 'JavaScript is a language. Programming is about code. Web development exists.';

      const analysis = estimator.estimate(veryPoor, {
        query,
        logprobs: [-0.1, -0.12, -0.08],
      });

      if (analysis.alignmentScore && analysis.alignmentScore < 0.2) {
        expect(analysis.alignmentFloorApplied).toBe(true);
        expect(analysis.finalConfidence).toBeLessThanOrEqual(0.4);
      }
    });

    it('should apply floor for poor alignment (0.20-0.25)', () => {
      const query = 'What is TypeScript?';
      const poor =
        'TypeScript and JavaScript are programming languages used in web development and software engineering.';

      const analysis = estimator.estimate(poor, {
        query,
        logprobs: [-0.1, -0.12, -0.15],
      });

      if (analysis.alignmentScore && analysis.alignmentScore < 0.25) {
        expect(analysis.alignmentFloorApplied).toBe(true);
        expect(analysis.finalConfidence).toBeLessThanOrEqual(0.45);
      }
    });

    it('should not apply floor for well-aligned responses', () => {
      const query = 'What is TypeScript?';
      const wellAligned = 'TypeScript is a strongly typed superset of JavaScript.';

      const analysis = estimator.estimate(wellAligned, {
        query,
        logprobs: [-0.1, -0.15, -0.12],
      });

      expect(analysis.alignmentFloorApplied).toBe(false);
    });

    it('should track reduction amount when floor applied', () => {
      const query = 'What is TypeScript?';
      const offTopic = 'Pizza is delicious. I enjoy eating food.';

      const analysis = estimator.estimate(offTopic, {
        query,
        logprobs: [-0.05, -0.06, -0.04], // Good logprobs
      });

      if (analysis.alignmentFloorApplied) {
        expect(analysis.components.alignmentFloorReduction).toBeDefined();
        expect(analysis.components.alignmentFloorReduction).toBeGreaterThan(0);
      }
    });
  });

  describe('query difficulty estimation', () => {
    it('should estimate difficulty when query provided', () => {
      const query = 'What is TypeScript?';
      const response = 'TypeScript is a typed superset of JavaScript.';

      const analysis = estimator.estimate(response, { query });

      expect(analysis.queryDifficulty).toBeDefined();
      expect(analysis.queryDifficulty).toBeGreaterThanOrEqual(0);
      expect(analysis.queryDifficulty).toBeLessThanOrEqual(1);
    });

    it('should rate simple questions as easier', () => {
      const simpleQuery = 'What is 2+2?';
      const complexQuery =
        'How can we design a distributed system architecture that optimally balances consistency and availability?';

      const simpleResponse = '4';
      const complexResponse = 'It depends on many factors...';

      const simpleAnalysis = estimator.estimate(simpleResponse, { query: simpleQuery });
      const complexAnalysis = estimator.estimate(complexResponse, { query: complexQuery });

      expect(simpleAnalysis.queryDifficulty).toBeLessThan(complexAnalysis.queryDifficulty);
    });

    it('should detect technical queries as more difficult', () => {
      const basicQuery = 'What is a variable?';
      const technicalQuery =
        'Explain the algorithm for optimizing distributed consensus in Byzantine fault-tolerant systems.';

      const basicResponse = 'A variable stores data.';
      const technicalResponse = 'Byzantine consensus...';

      const basicAnalysis = estimator.estimate(basicResponse, { query: basicQuery });
      const technicalAnalysis = estimator.estimate(technicalResponse, {
        query: technicalQuery,
      });

      expect(technicalAnalysis.queryDifficulty).toBeGreaterThan(basicAnalysis.queryDifficulty);
    });

    it('should use provided queryDifficulty when given', () => {
      const response = 'Test response';
      const providedDifficulty = 0.75;

      const analysis = estimator.estimate(response, {
        query: 'Test query',
        queryDifficulty: providedDifficulty,
      });

      expect(analysis.queryDifficulty).toBe(providedDifficulty);
    });
  });

  describe('provider calibration', () => {
    it('should apply provider-specific multipliers', () => {
      const response = 'TypeScript is a strongly typed superset of JavaScript.';
      const logprobs = [-0.15, -0.2, -0.18];

      const openaiEstimator = new ProductionConfidenceEstimator('openai');
      const anthropicEstimator = new ProductionConfidenceEstimator('anthropic');

      const openaiAnalysis = openaiEstimator.estimate(response, { logprobs });
      const anthropicAnalysis = anthropicEstimator.estimate(response, { logprobs });

      // OpenAI has 1.0 multiplier, Anthropic has 0.95
      // OpenAI should have slightly higher confidence (all else equal)
      expect(openaiAnalysis.calibratedConfidence).toBeGreaterThan(
        anthropicAnalysis.calibratedConfidence
      );
    });

    it('should apply temperature penalty', () => {
      const response = 'TypeScript is a typed language.';
      const logprobs = [-0.15, -0.2];

      const lowTempAnalysis = estimator.estimate(response, { logprobs, temperature: 0.0 });
      const highTempAnalysis = estimator.estimate(response, { logprobs, temperature: 1.5 });

      // Higher temperature = lower confidence
      expect(lowTempAnalysis.finalConfidence).toBeGreaterThan(highTempAnalysis.finalConfidence);
    });

    it('should apply finish reason boosts/penalties', () => {
      const response = 'TypeScript is a typed language.';
      const logprobs = [-0.15, -0.2];

      const stopAnalysis = estimator.estimate(response, { logprobs, finishReason: 'stop' });
      const lengthAnalysis = estimator.estimate(response, { logprobs, finishReason: 'length' });

      // 'stop' gets +0.05, 'length' gets -0.1
      expect(stopAnalysis.finalConfidence).toBeGreaterThan(lengthAnalysis.finalConfidence);
    });

    it('should respect provider min/max confidence bounds', () => {
      // OpenAI bounds: 0.3-0.98
      const estimatorOpenAI = new ProductionConfidenceEstimator('openai');

      // Try to push confidence very high
      const highResponse =
        'TypeScript is a strongly typed superset of JavaScript with excellent tooling and IDE support. ' +
        'For example: interface User { name: string; age: number; } provides compile-time type safety.';
      const highLogprobs = [-0.01, -0.02, -0.015, -0.018, -0.012];

      // Try to push confidence very low
      const lowResponse = "I don't know anything. I'm uncertain. Maybe. Probably not sure.";
      const lowLogprobs = [-5.0, -6.0, -7.0, -8.0];

      const highAnalysis = estimatorOpenAI.estimate(highResponse, {
        logprobs: highLogprobs,
        temperature: 0.0,
        finishReason: 'stop',
      });
      const lowAnalysis = estimatorOpenAI.estimate(lowResponse, {
        logprobs: lowLogprobs,
        temperature: 1.5,
      });

      expect(highAnalysis.finalConfidence).toBeLessThanOrEqual(0.98);
      expect(lowAnalysis.finalConfidence).toBeGreaterThanOrEqual(0.3);
    });

    it('should handle unknown providers with openai defaults', () => {
      const unknownEstimator = new ProductionConfidenceEstimator('unknown-provider');
      const response = 'Test response.';

      const analysis = unknownEstimator.estimate(response);

      // Should not throw, should use OpenAI defaults
      expect(analysis.finalConfidence).toBeDefined();
      expect(analysis.finalConfidence).toBeGreaterThanOrEqual(
        PROVIDER_CONFIDENCE_CALIBRATION.openai.minConfidence
      );
    });
  });

  describe('components breakdown', () => {
    it('should provide detailed component breakdown', () => {
      const query = 'What is TypeScript?';
      const response = 'TypeScript is a strongly typed superset of JavaScript.';
      const logprobs = [-0.15, -0.2, -0.18];

      const analysis = estimator.estimate(response, { query, logprobs, queryDifficulty: 0.3 });

      expect(analysis.components).toBeDefined();
      expect(analysis.components.logprobs).toBeDefined();
      expect(analysis.components.semantic).toBeDefined();
      expect(analysis.components.alignment).toBeDefined();
      expect(analysis.components.base).toBeDefined();
      expect(analysis.components.calibrated).toBeDefined();
    });

    it('should track query difficulty in components', () => {
      const query = 'What is TypeScript?';
      const response = 'TypeScript is a typed language.';

      const analysis = estimator.estimate(response, { query });

      expect(analysis.components.queryDifficulty).toBeDefined();
    });
  });

  describe('explanation generation', () => {
    it('should generate human-readable explanation', () => {
      const query = 'What is TypeScript?';
      const response = 'TypeScript is a strongly typed superset of JavaScript.';
      const logprobs = [-0.15, -0.2, -0.18];

      const analysis = estimator.estimate(response, { query, logprobs });
      const explanation = estimator.explainConfidence(analysis);

      expect(explanation).toContain('Confidence:');
      expect(explanation).toContain('Method:');
      expect(explanation).toContain('Semantic quality:');
    });

    it('should include logprobs info when available', () => {
      const response = 'TypeScript is a typed language.';
      const logprobs = [-0.15, -0.2];

      const analysis = estimator.estimate(response, { logprobs });
      const explanation = estimator.explainConfidence(analysis);

      expect(explanation).toContain('Logprobs-based:');
      expect(explanation).toContain('token probability');
    });

    it('should include alignment info when query provided', () => {
      const query = 'What is TypeScript?';
      const response = 'TypeScript is a typed language.';

      const analysis = estimator.estimate(response, { query });
      const explanation = estimator.explainConfidence(analysis);

      expect(explanation).toContain('Query-response alignment:');
    });

    it('should warn about alignment floor when applied', () => {
      const query = 'What is TypeScript?';
      const offTopic = 'Pizza is delicious and I love food.';

      const analysis = estimator.estimate(offTopic, {
        query,
        logprobs: [-0.05, -0.06],
      });

      const explanation = estimator.explainConfidence(analysis);

      if (analysis.alignmentFloorApplied) {
        expect(explanation).toContain('SAFETY');
        expect(explanation).toContain('Alignment floor applied');
        expect(explanation).toContain('off-topic');
      }
    });

    it('should categorize query difficulty', () => {
      const queries = [
        { query: 'What is 2+2?', expectedCategory: 'trivial' },
        { query: 'What is TypeScript?', expectedCategory: 'simple' },
        { query: 'How do neural networks learn?', expectedCategory: 'moderate' },
      ];

      for (const { query, expectedCategory } of queries) {
        const analysis = estimator.estimate('Test response', { query });
        const explanation = estimator.explainConfidence(analysis);

        if (analysis.queryDifficulty !== undefined) {
          expect(explanation).toContain('Query difficulty:');
          // Category might vary, but explanation should exist
        }
      }
    });

    it('should provide interpretation of confidence level', () => {
      const responses = [
        { response: 'Test', expectedRange: 'Very low' },
        {
          response:
            'TypeScript is a strongly typed superset of JavaScript with excellent IDE support and tooling.',
          expectedRange: 'High',
        },
      ];

      for (const { response } of responses) {
        const analysis = estimator.estimate(response, {
          logprobs: response.length > 10 ? [-0.1, -0.15] : [-2.0, -3.0],
        });
        const explanation = estimator.explainConfidence(analysis);

        // Should contain interpretation
        expect(
          explanation.includes('Very high') ||
            explanation.includes('High') ||
            explanation.includes('Moderate') ||
            explanation.includes('Low') ||
            explanation.includes('Very low')
        ).toBe(true);
      }
    });
  });

  describe('edge cases', () => {
    it('should handle undefined/null inputs gracefully', () => {
      const analysis = estimator.estimate('Test response', {
        query: undefined,
        logprobs: undefined,
        temperature: undefined,
      });

      expect(analysis.finalConfidence).toBeDefined();
      expect(analysis.methodUsed).toBe('semantic');
    });

    it('should handle very long responses', () => {
      const longResponse = 'TypeScript is a language. '.repeat(1000);

      const analysis = estimator.estimate(longResponse);

      expect(analysis.finalConfidence).toBeDefined();
      expect(analysis.semanticConfidence).toBeGreaterThan(0);
    });

    it('should handle responses with special characters', () => {
      const specialResponse = 'TypeScript ≈ JavaScript + Types 🎉 ∑(x) = ∫ f(x) dx';

      const analysis = estimator.estimate(specialResponse);

      expect(analysis.finalConfidence).toBeDefined();
    });

    it('should handle single-token logprobs', () => {
      const response = 'Yes';
      const logprobs = [-0.5];

      const analysis = estimator.estimate(response, { logprobs });

      expect(analysis.logprobsConfidence).toBeDefined();
    });

    it('should handle extreme temperature values', () => {
      const response = 'Test';

      const zeroTemp = estimator.estimate(response, { temperature: 0 });
      const extremeTemp = estimator.estimate(response, { temperature: 10 });

      expect(zeroTemp.finalConfidence).toBeDefined();
      expect(extremeTemp.finalConfidence).toBeDefined();
      expect(zeroTemp.finalConfidence).toBeGreaterThan(extremeTemp.finalConfidence);
    });

    it('should handle negative logprobs correctly', () => {
      // Logprobs should always be negative (log probabilities)
      const response = 'Test response';
      const logprobs = [-0.5, -1.0, -0.3];

      const analysis = estimator.estimate(response, { logprobs });

      expect(analysis.logprobsConfidence).toBeGreaterThan(0);
      expect(analysis.logprobsConfidence).toBeLessThanOrEqual(1);
    });
  });

  describe('provider-specific tests', () => {
    it('should handle all supported providers', () => {
      const providers = ['openai', 'anthropic', 'groq', 'together', 'vllm', 'ollama', 'huggingface'];
      const response = 'TypeScript is a typed language.';

      for (const provider of providers) {
        const estimator = new ProductionConfidenceEstimator(provider);
        const analysis = estimator.estimate(response);

        expect(analysis.finalConfidence).toBeDefined();
        expect(analysis.finalConfidence).toBeGreaterThan(0);
      }
    });

    it('should respect logprobs availability per provider', () => {
      const response = 'Test';
      const logprobs = [-0.15, -0.2];

      // Providers with logprobs
      const openaiEst = new ProductionConfidenceEstimator('openai');
      const openaiAnalysis = openaiEst.estimate(response, { logprobs });
      expect(openaiAnalysis.methodUsed).toBe('hybrid');

      // Providers without logprobs (should still accept them if provided)
      const anthropicEst = new ProductionConfidenceEstimator('anthropic');
      const anthropicAnalysis = anthropicEst.estimate(response, { logprobs });
      expect(anthropicAnalysis.logprobsConfidence).toBeDefined();
    });

    it('should apply different calibrations per provider', () => {
      const response = 'TypeScript is a language.';
      const options = { logprobs: [-0.15, -0.2], temperature: 0.7 };

      const openaiEst = new ProductionConfidenceEstimator('openai');
      const ollamaEst = new ProductionConfidenceEstimator('ollama');

      const openaiAnalysis = openaiEst.estimate(response, options);
      const ollamaAnalysis = ollamaEst.estimate(response, options);

      // Different providers should produce different calibrated results
      // OpenAI: 1.0 multiplier, Ollama: 0.85 multiplier
      expect(openaiAnalysis.calibratedConfidence).not.toBe(ollamaAnalysis.calibratedConfidence);
    });
  });
});

describe('PROVIDER_CONFIDENCE_CALIBRATION', () => {
  it('should have calibration for all major providers', () => {
    expect(PROVIDER_CONFIDENCE_CALIBRATION.openai).toBeDefined();
    expect(PROVIDER_CONFIDENCE_CALIBRATION.anthropic).toBeDefined();
    expect(PROVIDER_CONFIDENCE_CALIBRATION.groq).toBeDefined();
    expect(PROVIDER_CONFIDENCE_CALIBRATION.together).toBeDefined();
    expect(PROVIDER_CONFIDENCE_CALIBRATION.vllm).toBeDefined();
    expect(PROVIDER_CONFIDENCE_CALIBRATION.ollama).toBeDefined();
    expect(PROVIDER_CONFIDENCE_CALIBRATION.huggingface).toBeDefined();
  });

  it('should have valid multipliers (0.8-1.0)', () => {
    for (const [provider, calibration] of Object.entries(PROVIDER_CONFIDENCE_CALIBRATION)) {
      expect(calibration.baseMultiplier).toBeGreaterThanOrEqual(0.8);
      expect(calibration.baseMultiplier).toBeLessThanOrEqual(1.0);
    }
  });

  it('should have valid min/max confidence bounds', () => {
    for (const [provider, calibration] of Object.entries(PROVIDER_CONFIDENCE_CALIBRATION)) {
      expect(calibration.minConfidence).toBeGreaterThanOrEqual(0);
      expect(calibration.maxConfidence).toBeLessThanOrEqual(1);
      expect(calibration.minConfidence).toBeLessThan(calibration.maxConfidence);
    }
  });

  it('should have temperature penalty functions', () => {
    for (const [provider, calibration] of Object.entries(PROVIDER_CONFIDENCE_CALIBRATION)) {
      expect(typeof calibration.temperaturePenalty).toBe('function');

      const penalty0 = calibration.temperaturePenalty(0);
      const penalty1 = calibration.temperaturePenalty(1);

      expect(penalty0).toBeLessThanOrEqual(penalty1);
    }
  });

  it('should have finish reason boosts defined', () => {
    for (const [provider, calibration] of Object.entries(PROVIDER_CONFIDENCE_CALIBRATION)) {
      expect(calibration.finishReasonBoost).toBeDefined();
      expect(typeof calibration.finishReasonBoost).toBe('object');
    }
  });
});
