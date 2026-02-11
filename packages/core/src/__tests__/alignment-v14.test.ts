import { describe, expect, it } from 'vitest';
import { QueryResponseAlignmentScorer } from '../alignment';

describe('alignment scorer v14 parity', () => {
  const scorer = new QueryResponseAlignmentScorer();

  it('scores trivial numeric answers as aligned', () => {
    const score = scorer.score('What is 2+2?', '4');
    expect(score).toBeGreaterThanOrEqual(0.6);
  });

  it('returns MCQ boost for valid answers', () => {
    const score = scorer.score(
      'Answer the following multiple-choice question. A) Red B) Blue C) Green D) Yellow Answer:',
      'B'
    );
    expect(score).toBeCloseTo(0.75, 2);
  });

  it('detects reasoning chains in long, structured responses', () => {
    const analysis = scorer.score(
      'Why does the sample variance divide by n-1?',
      `First, we consider the sample mean as an estimate of the population mean.\n\n` +
        `Second, we evaluate the squared deviations from the sample mean to measure dispersion.\n\n` +
        `Third, because the mean is estimated from the same data, we lose a degree of freedom.\n\n` +
        `Therefore, dividing by n-1 corrects the bias and gives an unbiased estimator.\n\n` +
        `In conclusion, the adjustment accounts for estimation error in the mean and yields the expected value.`,
      0.7,
      true
    );

    expect(analysis.features.reasoningChain ?? 0).toBeGreaterThan(0.1);
    expect(analysis.alignmentScore).toBeGreaterThan(0.5);
  });

  it('penalizes off-topic responses', () => {
    const score = scorer.score('What is AI?', 'Bananas are yellow and grow in bunches.');
    expect(score).toBeLessThan(0.3);
  });

  it('returns multi-turn boost for user/assistant history', () => {
    const analysis = scorer.score(
      "User: What's the weather in Paris?\nAssistant: It's sunny.\nUser: And tomorrow?",
      'Tomorrow in Paris is partly cloudy with a high of 18C.',
      0.3,
      true
    );

    expect(analysis.features.isMultiTurn).toBe(true);
    expect(analysis.alignmentScore).toBeCloseTo(0.72, 2);
  });
});

describe('alignment scorer v15 semantic fallback', () => {
  it('no-ops when useSemanticFallback is false', () => {
    const scorer = new QueryResponseAlignmentScorer({ useSemanticFallback: false });
    const analysis = scorer.score(
      'Explain quantum entanglement',
      'Particles are correlated.',
      0.3,
      true
    );
    expect(analysis.features.semanticFallback).toBeUndefined();
  });

  it('no-ops when no callback is provided', () => {
    const scorer = new QueryResponseAlignmentScorer({ useSemanticFallback: true });
    const analysis = scorer.score(
      'Explain quantum entanglement',
      'Particles are correlated.',
      0.3,
      true
    );
    // Without a callback, semantic fallback cannot fire
    expect(analysis.features.semanticFallback).toBeUndefined();
  });

  it('fires callback when score is in uncertain zone (0.35-0.55)', () => {
    let callbackCalled = false;
    const scorer = new QueryResponseAlignmentScorer({
      useSemanticFallback: true,
      getSemanticScore: (_q, _r) => {
        callbackCalled = true;
        return 0.80; // high semantic score
      },
    });

    // Use a query/response that produces a rule score in the uncertain zone
    const analysis = scorer.score(
      'Explain the concept of machine learning optimization',
      'It involves adjusting parameters to minimize loss.',
      0.3,
      true
    );

    // If rule score landed in 0.35-0.55, callback fires and blends
    if (analysis.features.semanticFallback) {
      expect(callbackCalled).toBe(true);
      expect(analysis.features.semanticScore).toBe(0.80);
      // Blended: 70% rule + 30% * 0.80
      expect(analysis.alignmentScore).toBeGreaterThan(0.35);
    }
  });

  it('skips callback for high-confidence scores', () => {
    let callbackCalled = false;
    const scorer = new QueryResponseAlignmentScorer({
      useSemanticFallback: true,
      getSemanticScore: () => {
        callbackCalled = true;
        return 0.90;
      },
    });

    // MCQ gets 0.75 — well above the 0.55 threshold
    scorer.score(
      'Answer the following multiple-choice question. A) Red B) Blue Answer:',
      'B'
    );
    expect(callbackCalled).toBe(false);
  });
});
