import { describe, expect, it } from 'vitest';

import {
  DEFAULT_COMPLEXITY_THRESHOLDS,
  DOMAIN_DESCRIPTIONS,
  DOMAIN_DISPLAY_NAMES,
  DOMAIN_UI_CONFIGS,
  DOMAINS,
  getEnabledDomains,
} from '../config';
import { buildCascadeMetadata, calculateSavings } from '../cascade-metadata';

describe('LmChatCascadeFlow domain configuration', () => {
  it('exposes all 16 domains with descriptions', () => {
    const domains = Object.values(DOMAINS);
    expect(domains).toHaveLength(16);

    for (const domain of domains) {
      expect(DOMAIN_DISPLAY_NAMES[domain]).toBeTypeOf('string');
      expect(DOMAIN_DESCRIPTIONS[domain]).toBeTypeOf('string');
    }
  });

  it('returns enabled domains in UI order', () => {
    const params = Object.fromEntries(
      DOMAIN_UI_CONFIGS.map(({ toggleName }) => [toggleName, true])
    );
    const enabled = getEnabledDomains(params);

    expect(enabled).toEqual(DOMAIN_UI_CONFIGS.map(({ domain }) => domain));
  });
});

describe('LmChatCascadeFlow thresholds and metadata', () => {
  it('matches cascade default thresholds', () => {
    expect(DEFAULT_COMPLEXITY_THRESHOLDS).toEqual({
      trivial: 0.25,
      simple: 0.4,
      moderate: 0.55,
      hard: 0.7,
      expert: 0.8,
    });
  });

  it('builds structured cascade metadata with savings', () => {
    const savings = calculateSavings(0.2, 0.5);
    expect(savings.usd).toBeCloseTo(0.3, 5);
    expect(savings.percent).toBeCloseTo(60, 5);

    const metadata = buildCascadeMetadata({
      modelUsed: 'drafter',
      domain: 'general',
      confidence: 0.72,
      costs: {
        drafter: 0.2,
        verifier: 0,
        total: 0.2,
      },
      baselineCost: 0.5,
    });

    expect(metadata).toMatchObject({
      model_used: 'drafter',
      domain: 'general',
      confidence: 0.72,
      costs: {
        drafter: 0.2,
        verifier: 0,
        total: 0.2,
      },
    });
    expect(metadata.savings.usd).toBeCloseTo(0.3, 5);
  });
});
