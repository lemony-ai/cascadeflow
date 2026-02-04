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
