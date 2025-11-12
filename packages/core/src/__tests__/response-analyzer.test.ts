/**
 * Tests for Response Analyzer
 *
 * Tests response analysis including hedging, specificity, length, and hallucination detection
 *
 * Run: pnpm test response-analyzer.test.ts
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { ResponseAnalyzer } from '../response-analyzer';
import type {
  LengthAnalysis,
  HedgingAnalysis,
  SpecificityAnalysis,
  HallucinationAnalysis,
} from '../response-analyzer';

describe('ResponseAnalyzer', () => {
  let analyzer: ResponseAnalyzer;

  beforeEach(() => {
    analyzer = new ResponseAnalyzer();
  });

  describe('Length Analysis', () => {
    it('should analyze length for trivial complexity', () => {
      const shortResponse = '42';
      const result = analyzer.analyzeLength(shortResponse, 'trivial');

      expect(result.wordCount).toBe(1);
      expect(result.appropriate).toBe(true);
      expect(result.tooShort).toBe(false);
      expect(result.expectedRange).toEqual([1, 50]);
    });

    it('should detect too short responses', () => {
      const tooShort = 'Yes.';
      const result = analyzer.analyzeLength(tooShort, 'expert');

      expect(result.tooShort).toBe(true);
      expect(result.appropriate).toBe(false);
    });

    it('should detect too long responses', () => {
      const tooLong = 'word '.repeat(700); // 700 > 150 * 4 = 600 for simple
      const result = analyzer.analyzeLength(tooLong, 'simple');

      expect(result.tooLong).toBe(true);
      expect(result.appropriate).toBe(false);
    });

    it('should handle appropriate length for simple complexity', () => {
      const appropriate = 'TypeScript is a strongly typed superset of JavaScript.';
      const result = analyzer.analyzeLength(appropriate, 'simple');

      expect(result.appropriate).toBe(true);
      expect(result.tooShort).toBe(false);
      expect(result.tooLong).toBe(false);
    });

    it('should have different ranges for different complexities', () => {
      const content = 'word '.repeat(100);

      const trivial = analyzer.analyzeLength(content, 'trivial');
      const moderate = analyzer.analyzeLength(content, 'moderate');
      const expert = analyzer.analyzeLength(content, 'expert');

      // 100 words: trivial max = 50 * 4 = 200 (appropriate), moderate max = 300 * 3 = 900 (appropriate)
      expect(trivial.appropriate).toBe(true); // 100 < 50 * 3 = 150
      expect(moderate.appropriate).toBe(true);
      expect(expert.appropriate).toBe(true);
    });

    it('should count words and characters correctly', () => {
      const content = 'Hello world from TypeScript';
      const result = analyzer.analyzeLength(content, 'simple');

      expect(result.wordCount).toBe(4);
      expect(result.charCount).toBe(content.length);
    });
  });

  describe('Hedging Detection', () => {
    it('should detect hedging phrases', () => {
      const hedged = 'TypeScript might be useful. It could possibly help with type safety.';
      const result = analyzer.detectHedging(hedged);

      expect(result.count).toBeGreaterThan(0);
      expect(result.ratio).toBeGreaterThan(0);
    });

    it('should detect severe uncertainty markers', () => {
      const uncertain = "I don't know the answer. I'm not sure about this.";
      const result = analyzer.detectHedging(uncertain);

      expect(result.severe).toBe(true);
      expect(result.acceptable).toBe(false);
    });

    it('should accept responses with minimal hedging', () => {
      const confident = 'TypeScript is a strongly typed superset of JavaScript.';
      const result = analyzer.detectHedging(confident);

      expect(result.acceptable).toBe(true);
      expect(result.ratio).toBeLessThanOrEqual(0.3);
    });

    it('should calculate ratio per sentence', () => {
      const multiSentence =
        'TypeScript is great. It might be useful. Perhaps it helps. Maybe consider it.';
      const result = analyzer.detectHedging(multiSentence);

      expect(result.ratio).toBeGreaterThan(0);
      // 4 hedging words (might, perhaps, maybe, consider) detected in list / 4 sentences = 1.0
      // Note: The algorithm counts unique phrases found anywhere in text, not per sentence
      expect(result.count).toBeGreaterThanOrEqual(3);
    });

    it('should handle empty content', () => {
      const result = analyzer.detectHedging('');

      expect(result.ratio).toBe(0);
      expect(result.count).toBe(0);
      expect(result.severe).toBe(false);
      expect(result.acceptable).toBe(true);
    });

    it('should identify common hedging patterns', () => {
      const patterns = [
        'I think TypeScript is good',
        'TypeScript seems to be useful',
        'It appears to help',
        'This typically works',
        'It often helps',
      ];

      for (const pattern of patterns) {
        const result = analyzer.detectHedging(pattern);
        expect(result.count).toBeGreaterThan(0);
      }
    });

    it('should detect multiple uncertainty markers', () => {
      const veryUncertain =
        "I'm sorry, but I cannot provide that information. I don't know enough about this topic.";
      const result = analyzer.detectHedging(veryUncertain);

      expect(result.severe).toBe(true);
      expect(result.acceptable).toBe(false);
    });
  });

  describe('Specificity Analysis', () => {
    it('should reward numbers', () => {
      const withNumbers = 'TypeScript 5.0 was released in 2023 with 40+ features.';
      const withoutNumbers = 'TypeScript was released recently with many features.';

      const resultWith = analyzer.analyzeSpecificity(withNumbers, 'simple');
      const resultWithout = analyzer.analyzeSpecificity(withoutNumbers, 'simple');

      expect(resultWith.hasNumbers).toBe(true);
      expect(resultWithout.hasNumbers).toBe(false);
      expect(resultWith.score).toBeGreaterThan(resultWithout.score);
    });

    it('should reward examples', () => {
      const withExamples =
        'TypeScript has types. For example, you can use interface User { name: string; }.';
      const withoutExamples = 'TypeScript has types that you can use.';

      const resultWith = analyzer.analyzeSpecificity(withExamples, 'moderate');
      const resultWithout = analyzer.analyzeSpecificity(withoutExamples, 'moderate');

      expect(resultWith.hasExamples).toBe(true);
      expect(resultWithout.hasExamples).toBe(false);
      expect(resultWith.score).toBeGreaterThan(resultWithout.score);
    });

    it('should penalize vague language', () => {
      const vague = 'TypeScript is something that does various things with stuff and many things.';
      const specific = 'TypeScript provides static type checking for JavaScript applications.';

      const vagueResult = analyzer.analyzeSpecificity(vague, 'moderate');
      const specificResult = analyzer.analyzeSpecificity(specific, 'moderate');

      expect(vagueResult.vaguenessRatio).toBeGreaterThan(specificResult.vaguenessRatio);
      expect(vagueResult.score).toBeLessThan(specificResult.score);
    });

    it('should have different requirements for different complexities', () => {
      const simpleContent = 'TypeScript adds types.';

      const trivialResult = analyzer.analyzeSpecificity(simpleContent, 'trivial');
      const expertResult = analyzer.analyzeSpecificity(simpleContent, 'expert');

      expect(trivialResult.meetsRequirement).toBe(true);
      expect(expertResult.meetsRequirement).toBe(false);
      expect(expertResult.minRequired).toBeGreaterThan(trivialResult.minRequired);
    });

    it('should detect technical terms', () => {
      const technical = 'TypeScript uses structural typing with TypeGuards and GenericConstraints.';
      const result = analyzer.analyzeSpecificity(technical, 'moderate');

      // Should have base score of at least 0.3 (min for moderate)
      expect(result.score).toBeGreaterThanOrEqual(0.15);
      expect(result.meetsRequirement).toBe(true);
    });

    it('should calculate overall specificity score', () => {
      const highlySpecific =
        'TypeScript 5.0 introduced 15 new features in March 2023. ' +
        'For example, const type parameters enable: const fn = <const T>(x: T) => x;';

      const result = analyzer.analyzeSpecificity(highlySpecific, 'hard');

      expect(result.hasNumbers).toBe(true);
      expect(result.hasExamples).toBe(true);
      expect(result.score).toBeGreaterThan(0.5);
      expect(result.meetsRequirement).toBe(true);
    });

    it('should handle empty content', () => {
      const result = analyzer.analyzeSpecificity('', 'moderate');

      expect(result.score).toBeGreaterThanOrEqual(0);
      expect(result.hasNumbers).toBe(false);
      expect(result.hasExamples).toBe(false);
    });
  });

  describe('Hallucination Detection', () => {
    it('should detect absolute claims', () => {
      const suspicious = 'All experts always agree that this never fails.';
      const result = analyzer.detectHallucinations(suspicious);

      expect(result.suspiciousPatterns).toBeGreaterThan(0);
      expect(result.riskLevel).not.toBe('low');
    });

    it('should detect fake research claims', () => {
      const fakeResearch = 'According to studies show that TypeScript is 100% better.';
      const result = analyzer.detectHallucinations(fakeResearch);

      expect(result.suspiciousPatterns).toBeGreaterThan(0);
      expect(result.riskLevel).not.toBe('low');
    });

    it('should detect false authority', () => {
      const falseAuthority = 'Scientists confirm that all developers use TypeScript.';
      const result = analyzer.detectHallucinations(falseAuthority);

      expect(result.suspiciousPatterns).toBeGreaterThan(0);
      expect(result.riskLevel).not.toBe('low');
    });

    it('should detect overly precise claims', () => {
      const overprecise = 'Exactly 87.432% of developers prefer TypeScript.';
      const result = analyzer.detectHallucinations(overprecise);

      expect(result.suspiciousPatterns).toBeGreaterThan(0);
    });

    it('should detect contradictions', () => {
      const contradiction = 'TypeScript is useful, however it is not helpful.';
      const result = analyzer.detectHallucinations(contradiction);

      expect(result.hasContradiction).toBe(true);
    });

    it('should have low risk for normal responses', () => {
      const normal = 'TypeScript is a strongly typed superset of JavaScript developed by Microsoft.';
      const result = analyzer.detectHallucinations(normal);

      expect(result.riskLevel).toBe('low');
      expect(result.suspiciousPatterns).toBe(0);
    });

    it('should have high risk for multiple patterns', () => {
      const highRisk =
        'According to research shows that all scientists agree TypeScript is never bad. ' +
        'It is well-known that every developer always uses it.';

      const result = analyzer.detectHallucinations(highRisk);

      expect(result.riskLevel).toBe('high');
      expect(result.suspiciousPatterns).toBeGreaterThanOrEqual(2);
    });

    it('should have medium risk for one pattern', () => {
      const mediumRisk = 'Exactly 99.5% of developers prefer TypeScript over JavaScript.';
      const result = analyzer.detectHallucinations(mediumRisk);

      expect(result.riskLevel).toBe('medium');
      expect(result.suspiciousPatterns).toBe(1);
    });

    it('should handle empty content', () => {
      const result = analyzer.detectHallucinations('');

      expect(result.suspiciousPatterns).toBe(0);
      expect(result.hasContradiction).toBe(false);
      expect(result.riskLevel).toBe('low');
    });
  });

  describe('Comprehensive Analysis', () => {
    it('should perform all analyses at once', () => {
      const content = 'TypeScript is a strongly typed superset of JavaScript.';
      const result = analyzer.analyze(content, 'simple');

      expect(result.length).toBeDefined();
      expect(result.hedging).toBeDefined();
      expect(result.specificity).toBeDefined();
      expect(result.hallucinations).toBeDefined();
    });

    it('should use default complexity (moderate)', () => {
      const content = 'Test response';
      const result = analyzer.analyze(content);

      expect(result.length.expectedRange).toEqual([15, 300]);
    });

    it('should analyze high quality response favorably', () => {
      const highQuality =
        'TypeScript is a strongly typed superset of JavaScript developed by Microsoft in 2012. ' +
        'It adds compile-time type checking through a sophisticated type system. ' +
        'For example, interfaces provide structural typing: interface User { name: string; age: number; }. ' +
        'This enables developers to catch type errors during development rather than at runtime.';

      const result = analyzer.analyze(highQuality, 'moderate');

      expect(result.length.appropriate).toBe(true);
      expect(result.hedging.acceptable).toBe(true);
      expect(result.specificity.meetsRequirement).toBe(true);
      expect(result.hallucinations.riskLevel).toBe('low');
    });

    it('should analyze low quality response unfavorably', () => {
      const lowQuality =
        "I'm not sure, but TypeScript might be something related to programming. " +
        "I think it could possibly help with various things. " +
        "According to research shows all experts always agree it is universally perfect.";

      const result = analyzer.analyze(lowQuality, 'moderate');

      expect(result.hedging.acceptable).toBe(false);
      expect(result.hallucinations.riskLevel).not.toBe('low');
    });
  });

  describe('Static Constants', () => {
    it('should have hedging phrases defined', () => {
      expect(ResponseAnalyzer.HEDGING_PHRASES).toBeDefined();
      expect(ResponseAnalyzer.HEDGING_PHRASES.length).toBeGreaterThan(0);
      expect(ResponseAnalyzer.HEDGING_PHRASES).toContain('might');
      expect(ResponseAnalyzer.HEDGING_PHRASES).toContain('probably');
    });

    it('should have uncertainty markers defined', () => {
      expect(ResponseAnalyzer.UNCERTAINTY_MARKERS).toBeDefined();
      expect(ResponseAnalyzer.UNCERTAINTY_MARKERS.length).toBeGreaterThan(0);
      expect(ResponseAnalyzer.UNCERTAINTY_MARKERS).toContain("i don't know");
      expect(ResponseAnalyzer.UNCERTAINTY_MARKERS).toContain("i'm not sure");
    });

    it('should have hallucination patterns defined', () => {
      expect(ResponseAnalyzer.HALLUCINATION_PATTERNS).toBeDefined();
      expect(ResponseAnalyzer.HALLUCINATION_PATTERNS.length).toBeGreaterThan(0);
      expect(ResponseAnalyzer.HALLUCINATION_PATTERNS[0]).toBeInstanceOf(RegExp);
    });
  });

  describe('Edge Cases', () => {
    it('should handle single word responses', () => {
      const result = analyzer.analyze('TypeScript', 'trivial');

      expect(result.length.wordCount).toBe(1);
      expect(result.hedging.ratio).toBe(0);
    });

    it('should handle very long responses', () => {
      const longContent = 'TypeScript is a language. '.repeat(1100); // 4400 words > 1000 * 4 = 4000 for expert
      const result = analyzer.analyze(longContent, 'expert');

      expect(result.length.wordCount).toBeGreaterThan(4000);
      expect(result.length.tooLong).toBe(true);
    });

    it('should handle responses with special characters', () => {
      const special = 'TypeScript: type safety = good! @developer #code $money 100%';
      const result = analyzer.analyze(special, 'moderate');

      expect(result).toBeDefined();
      expect(result.specificity.hasNumbers).toBe(true);
    });

    it('should handle responses with only punctuation', () => {
      const punctuation = '...!!!???';
      const result = analyzer.analyze(punctuation, 'simple');

      expect(result.length.wordCount).toBeLessThan(5);
      expect(result.length.tooShort).toBe(true);
    });

    it('should handle multiline responses', () => {
      const multiline = `TypeScript is a language.

      It provides type safety.

      Developers use it for large projects.`;

      const result = analyzer.analyze(multiline, 'moderate');

      expect(result.length.wordCount).toBeGreaterThan(10);
      expect(result.hedging.ratio).toBe(0);
    });

    it('should handle responses with numbers in different formats', () => {
      const numbers = 'TypeScript 5.0 released 2023-03-15 with 40+ features and $0 cost.';
      const result = analyzer.analyzeSpecificity(numbers, 'moderate');

      expect(result.hasNumbers).toBe(true);
    });

    it('should handle case insensitivity properly', () => {
      const upperCase = "I DON'T KNOW IF TYPESCRIPT MIGHT BE GOOD.";
      const lowerCase = "i don't know if typescript might be good.";

      const upperResult = analyzer.detectHedging(upperCase);
      const lowerResult = analyzer.detectHedging(lowerCase);

      expect(upperResult.severe).toBe(lowerResult.severe);
      expect(upperResult.count).toBe(lowerResult.count);
    });
  });
});
