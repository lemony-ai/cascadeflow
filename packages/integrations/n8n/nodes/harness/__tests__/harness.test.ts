import { describe, expect, it } from 'vitest';

import {
  PRICING_USD_PER_M,
  DEFAULT_PRICING_USD_PER_M,
  ENERGY_COEFFICIENTS,
  DEFAULT_ENERGY_COEFFICIENT,
  ENERGY_OUTPUT_WEIGHT,
  resolvePricingKey,
  estimateCost,
  estimateEnergy,
  modelTotalPrice,
} from '../pricing';

import {
  HarnessRunContext,
  COMPLIANCE_MODEL_ALLOWLISTS,
  QUALITY_PRIORS,
  LATENCY_PRIORS,
  normalizeWeights,
  type HarnessConfig,
} from '../harness';

// ---------------------------------------------------------------------------
// Pricing data fidelity
// ---------------------------------------------------------------------------

describe('pricing data', () => {
  it('has 18 models in PRICING_USD_PER_M', () => {
    expect(Object.keys(PRICING_USD_PER_M)).toHaveLength(18);
  });

  it('matches Python values for gpt-4o', () => {
    expect(PRICING_USD_PER_M['gpt-4o']).toEqual([2.50, 10.00]);
  });

  it('matches Python values for gpt-4o-mini', () => {
    expect(PRICING_USD_PER_M['gpt-4o-mini']).toEqual([0.15, 0.60]);
  });

  it('matches Python values for claude-sonnet-4', () => {
    expect(PRICING_USD_PER_M['claude-sonnet-4']).toEqual([3.00, 15.00]);
  });

  it('matches Python values for gemini-2.5-flash', () => {
    expect(PRICING_USD_PER_M['gemini-2.5-flash']).toEqual([0.15, 0.60]);
  });

  it('has correct default pricing', () => {
    expect(DEFAULT_PRICING_USD_PER_M).toEqual([2.50, 10.00]);
  });

  it('has 18 models in ENERGY_COEFFICIENTS', () => {
    expect(Object.keys(ENERGY_COEFFICIENTS)).toHaveLength(18);
  });

  it('has correct energy defaults', () => {
    expect(DEFAULT_ENERGY_COEFFICIENT).toBe(1.0);
    expect(ENERGY_OUTPUT_WEIGHT).toBe(1.5);
  });
});

// ---------------------------------------------------------------------------
// estimateCost / estimateEnergy
// ---------------------------------------------------------------------------

describe('estimateCost', () => {
  it('calculates gpt-4o cost correctly (1000 in, 500 out = $0.0075)', () => {
    const cost = estimateCost('gpt-4o', 1000, 500);
    expect(cost).toBeCloseTo(0.0075, 6);
  });

  it('calculates gpt-4o-mini cost correctly', () => {
    const cost = estimateCost('gpt-4o-mini', 1_000_000, 1_000_000);
    expect(cost).toBeCloseTo(0.15 + 0.60, 6);
  });

  it('uses default pricing for unknown models', () => {
    const cost = estimateCost('unknown-model', 1_000_000, 1_000_000);
    expect(cost).toBeCloseTo(2.50 + 10.00, 6);
  });
});

describe('estimateEnergy', () => {
  it('calculates gpt-4o energy correctly (100 in, 50 out)', () => {
    // coeff=1.0, energy = 1.0 * (100 + 50 * 1.5) = 175.0
    const energy = estimateEnergy('gpt-4o', 100, 50);
    expect(energy).toBeCloseTo(175.0, 4);
  });

  it('uses default coefficient for unknown models', () => {
    // coeff=1.0, energy = 1.0 * (100 + 50 * 1.5) = 175.0
    const energy = estimateEnergy('unknown-model', 100, 50);
    expect(energy).toBeCloseTo(175.0, 4);
  });

  it('uses correct coefficient for gpt-4o-mini', () => {
    // coeff=0.3, energy = 0.3 * (100 + 50 * 1.5) = 52.5
    const energy = estimateEnergy('gpt-4o-mini', 100, 50);
    expect(energy).toBeCloseTo(52.5, 4);
  });
});

describe('modelTotalPrice', () => {
  it('returns input + output for gpt-4o', () => {
    expect(modelTotalPrice('gpt-4o')).toBeCloseTo(12.50, 6);
  });

  it('returns default for unknown model', () => {
    expect(modelTotalPrice('unknown')).toBeCloseTo(12.50, 6);
  });
});

// ---------------------------------------------------------------------------
// Fuzzy model resolution
// ---------------------------------------------------------------------------

describe('resolvePricingKey', () => {
  it('exact match', () => {
    expect(resolvePricingKey('gpt-4o')).toBe('gpt-4o');
  });

  it('strips version suffix (-20250120)', () => {
    expect(resolvePricingKey('gpt-4o-20250120')).toBe('gpt-4o');
  });

  it('strips -preview suffix', () => {
    expect(resolvePricingKey('gpt-4o-preview')).toBe('gpt-4o');
  });

  it('strips -latest suffix', () => {
    expect(resolvePricingKey('gpt-4o-latest')).toBe('gpt-4o');
  });

  it('longest-prefix match (gemini-2.5-flash-8b → gemini-2.5-flash)', () => {
    expect(resolvePricingKey('gemini-2.5-flash-8b')).toBe('gemini-2.5-flash');
  });

  it('returns null for completely unknown model', () => {
    expect(resolvePricingKey('totally-unknown-model')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// HarnessRunContext — evaluatePreCall
// ---------------------------------------------------------------------------

function makeConfig(overrides: Partial<HarnessConfig> = {}): HarnessConfig {
  return {
    mode: 'enforce',
    budgetMax: null,
    toolCallsMax: null,
    latencyMaxMs: null,
    energyMax: null,
    compliance: null,
    kpiWeights: {},
    ...overrides,
  };
}

describe('evaluatePreCall', () => {
  it('returns allow when no limits set', () => {
    const ctx = new HarnessRunContext(makeConfig());
    const decision = ctx.evaluatePreCall('gpt-4o', false);
    expect(decision.action).toBe('allow');
  });

  it('returns stop when budget exhausted', () => {
    const ctx = new HarnessRunContext(makeConfig({ budgetMax: 0.01 }));
    ctx.cost = 0.01; // exhaust budget
    const decision = ctx.evaluatePreCall('gpt-4o', false);
    expect(decision.action).toBe('stop');
    expect(decision.reason).toBe('budget_exceeded');
  });

  it('returns deny_tool when tool cap reached', () => {
    const ctx = new HarnessRunContext(makeConfig({ toolCallsMax: 3 }));
    ctx.toolCalls = 3;
    const decision = ctx.evaluatePreCall('gpt-4o', true);
    expect(decision.action).toBe('deny_tool');
    expect(decision.reason).toBe('max_tool_calls_reached');
  });

  it('returns stop for compliance violation (non-compliant model)', () => {
    const ctx = new HarnessRunContext(makeConfig({ compliance: 'gdpr' }));
    const decision = ctx.evaluatePreCall('claude-sonnet-4', false);
    expect(decision.action).toBe('stop');
    expect(decision.reason).toBe('compliance_no_approved_model');
  });

  it('allows compliant model under GDPR', () => {
    const ctx = new HarnessRunContext(makeConfig({ compliance: 'gdpr' }));
    const decision = ctx.evaluatePreCall('gpt-4o', false);
    expect(decision.action).toBe('allow');
  });

  it('returns stop when latency cap exceeded', () => {
    const ctx = new HarnessRunContext(makeConfig({ latencyMaxMs: 1000 }));
    ctx.latencyUsedMs = 1000;
    const decision = ctx.evaluatePreCall('gpt-3.5-turbo', false);
    // gpt-3.5-turbo is already the fastest → can't switch → stop
    expect(decision.action).toBe('stop');
    expect(decision.reason).toBe('latency_limit_exceeded');
  });

  it('returns stop when energy cap exceeded', () => {
    const ctx = new HarnessRunContext(makeConfig({ energyMax: 100 }));
    ctx.energyUsed = 100;
    const decision = ctx.evaluatePreCall('gpt-3.5-turbo', false);
    // gpt-3.5-turbo is already lowest energy → can't switch → stop
    expect(decision.action).toBe('stop');
    expect(decision.reason).toBe('energy_limit_exceeded');
  });

  it('returns switch_model observation for budget pressure', () => {
    const ctx = new HarnessRunContext(makeConfig({ budgetMax: 1.0 }));
    ctx.cost = 0.85; // 85% spent, < 20% remaining
    ctx.budgetRemaining = 0.15;
    const decision = ctx.evaluatePreCall('gpt-4o', false);
    // Budget pressure suggests cheaper model
    expect(decision.action).toBe('switch_model');
    expect(decision.reason).toBe('budget_pressure');
  });

  it('returns switch_model observation for KPI optimization', () => {
    const ctx = new HarnessRunContext(makeConfig({
      kpiWeights: { quality: 0, cost: 1, latency: 0, energy: 0 },
    }));
    // gpt-4 is very expensive, KPI weights purely on cost → should suggest cheaper
    const decision = ctx.evaluatePreCall('gpt-4', false);
    expect(decision.action).toBe('switch_model');
    expect(decision.reason).toBe('kpi_weight_optimization');
  });
});

// ---------------------------------------------------------------------------
// Budget tracking across multiple recordCall invocations
// ---------------------------------------------------------------------------

describe('recordCall and budget tracking', () => {
  it('accumulates cost across calls', () => {
    const ctx = new HarnessRunContext(makeConfig({ budgetMax: 0.10 }));
    ctx.recordCall({ model: 'gpt-4o-mini', inputTokens: 100, outputTokens: 50, toolCallCount: 0, elapsedMs: 50 });
    expect(ctx.cost).toBeGreaterThan(0);
    expect(ctx.stepCount).toBe(1);
    expect(ctx.budgetRemaining).toBeLessThan(0.10);

    ctx.recordCall({ model: 'gpt-4o-mini', inputTokens: 200, outputTokens: 100, toolCallCount: 1, elapsedMs: 60 });
    expect(ctx.stepCount).toBe(2);
    expect(ctx.toolCalls).toBe(1);
    expect(ctx.latencyUsedMs).toBe(110);
  });

  it('detects budget exhaustion', () => {
    const ctx = new HarnessRunContext(makeConfig({ budgetMax: 0.0001 }));
    ctx.recordCall({ model: 'gpt-4o', inputTokens: 10000, outputTokens: 5000, toolCallCount: 0, elapsedMs: 100 });
    expect(ctx.isBudgetExhausted()).toBe(true);
  });

  it('detects tool cap reached', () => {
    const ctx = new HarnessRunContext(makeConfig({ toolCallsMax: 2 }));
    ctx.toolCalls = 2;
    expect(ctx.isToolCapReached()).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Observe vs enforce mode behavior
// ---------------------------------------------------------------------------

describe('observe vs enforce mode', () => {
  it('observe mode evaluatePreCall still returns decisions', () => {
    const ctx = new HarnessRunContext(makeConfig({ mode: 'observe', budgetMax: 0.01 }));
    ctx.cost = 0.01;
    const decision = ctx.evaluatePreCall('gpt-4o', false);
    // Decision is evaluated regardless of mode
    expect(decision.action).toBe('stop');
  });

  it('off mode has no context created (by design)', () => {
    // In the actual agent node, harnessCtx is null when mode=off
    // This test validates that a context with mode=off still works
    const ctx = new HarnessRunContext(makeConfig({ mode: 'off' }));
    const decision = ctx.evaluatePreCall('gpt-4o', false);
    expect(decision.action).toBe('allow');
    expect(decision.reason).toBe('off');
  });
});

// ---------------------------------------------------------------------------
// Compliance allowlists
// ---------------------------------------------------------------------------

describe('compliance allowlists', () => {
  it('GDPR allows gpt-4o, gpt-4o-mini, gpt-3.5-turbo', () => {
    const allowlist = COMPLIANCE_MODEL_ALLOWLISTS['gdpr'];
    expect(allowlist.has('gpt-4o')).toBe(true);
    expect(allowlist.has('gpt-4o-mini')).toBe(true);
    expect(allowlist.has('gpt-3.5-turbo')).toBe(true);
    expect(allowlist.has('claude-sonnet-4')).toBe(false);
  });

  it('strict allows only gpt-4o', () => {
    const allowlist = COMPLIANCE_MODEL_ALLOWLISTS['strict'];
    expect(allowlist.size).toBe(1);
    expect(allowlist.has('gpt-4o')).toBe(true);
  });

  it('strict mode denies tools even for compliant model', () => {
    const ctx = new HarnessRunContext(makeConfig({ compliance: 'strict' }));
    const decision = ctx.evaluatePreCall('gpt-4o', true);
    expect(decision.action).toBe('deny_tool');
    expect(decision.reason).toBe('compliance_tool_restriction');
  });
});

// ---------------------------------------------------------------------------
// KPI weight normalization
// ---------------------------------------------------------------------------

describe('normalizeWeights', () => {
  it('normalizes to sum=1', () => {
    const result = normalizeWeights({ quality: 0.4, cost: 0.3, latency: 0.2, energy: 0.1 });
    const sum = Object.values(result).reduce((a, b) => a + b, 0);
    expect(sum).toBeCloseTo(1.0, 6);
  });

  it('filters out zero and negative values', () => {
    const result = normalizeWeights({ quality: 1, cost: 0, latency: -1, energy: 1 });
    expect(result.cost).toBeUndefined();
    expect(result.latency).toBeUndefined();
    expect(result.quality).toBeCloseTo(0.5, 6);
    expect(result.energy).toBeCloseTo(0.5, 6);
  });

  it('returns empty for all-zero weights', () => {
    const result = normalizeWeights({ quality: 0, cost: 0, latency: 0, energy: 0 });
    expect(Object.keys(result)).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// summary() structure
// ---------------------------------------------------------------------------

describe('summary()', () => {
  it('returns correct structure', () => {
    const ctx = new HarnessRunContext(makeConfig({ budgetMax: 1.0 }));
    ctx.recordCall({ model: 'gpt-4o-mini', inputTokens: 100, outputTokens: 50, toolCallCount: 0, elapsedMs: 42 });

    const s = ctx.summary();
    expect(s.runId).toBeTruthy();
    expect(s.mode).toBe('enforce');
    expect(s.stepCount).toBe(1);
    expect(s.toolCalls).toBe(0);
    expect(s.cost).toBeGreaterThan(0);
    expect(s.latencyUsedMs).toBe(42);
    expect(s.energyUsed).toBeGreaterThan(0);
    expect(s.budgetMax).toBe(1.0);
    expect(s.budgetRemaining).toBeLessThan(1.0);
    expect(s.lastAction).toBe('allow');
    expect(s.durationMs).toBeGreaterThanOrEqual(0);
    expect(Array.isArray(s.trace)).toBe(true);
    expect(s.trace).toHaveLength(1);
    expect(s.trace[0].action).toBe('allow');
    expect(s.trace[0].budgetState.max).toBe(1.0);
  });
});
