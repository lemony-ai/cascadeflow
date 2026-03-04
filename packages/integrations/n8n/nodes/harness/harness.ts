/**
 * HarnessRunContext — multi-dimensional decision engine for n8n (TypeScript port).
 *
 * Ported from cascadeflow/harness/api.py (HarnessRunContext) and
 * cascadeflow/harness/instrument.py (pre-call decision logic, compliance,
 * quality/latency priors, KPI scoring).
 *
 * Key n8n constraint: models are graph connections (sub-nodes), not string
 * parameters. The harness cannot switch models at runtime. Only `stop` and
 * `deny_tool` actions have enforcement effects. `switch_model` decisions are
 * recorded in the trace as observations.
 */

import {
  ENERGY_COEFFICIENTS,
  DEFAULT_ENERGY_COEFFICIENT,
  estimateCost,
  estimateEnergy,
  modelTotalPrice,
  PRICING_USD_PER_M,
} from './pricing';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type HarnessMode = 'off' | 'observe' | 'enforce';

export interface KpiWeights {
  quality?: number;
  cost?: number;
  latency?: number;
  energy?: number;
}

export interface HarnessConfig {
  mode: HarnessMode;
  budgetMax: number | null;
  toolCallsMax: number | null;
  latencyMaxMs: number | null;
  energyMax: number | null;
  compliance: string | null;
  kpiWeights: KpiWeights;
}

export interface PreCallDecision {
  action: 'allow' | 'stop' | 'switch_model' | 'deny_tool';
  reason: string;
  targetModel: string;
}

export interface HarnessTraceEntry {
  action: string;
  reason: string;
  model: string | null;
  step: number;
  timestampMs: number;
  costTotal: number;
  budgetState: { max: number | null; remaining: number | null };
  applied: boolean;
  decisionMode: string;
}

export interface HarnessSummary {
  runId: string;
  mode: HarnessMode;
  stepCount: number;
  toolCalls: number;
  cost: number;
  latencyUsedMs: number;
  energyUsed: number;
  budgetMax: number | null;
  budgetRemaining: number | null;
  lastAction: string;
  durationMs: number;
  trace: HarnessTraceEntry[];
}

export interface RecordCallParams {
  model: string;
  inputTokens: number;
  outputTokens: number;
  toolCallCount: number;
  elapsedMs: number;
  decision?: PreCallDecision;
}

// ---------------------------------------------------------------------------
// Compliance allowlists (from instrument.py lines 107-112)
// ---------------------------------------------------------------------------

const COMPLIANCE_MODEL_ALLOWLISTS: Record<string, Set<string>> = {
  gdpr: new Set(['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo']),
  hipaa: new Set(['gpt-4o', 'gpt-4o-mini']),
  pci: new Set(['gpt-4o-mini', 'gpt-3.5-turbo']),
  strict: new Set(['gpt-4o']),
};

// ---------------------------------------------------------------------------
// Quality & latency priors for KPI scoring (from instrument.py lines 74-95)
// ---------------------------------------------------------------------------

const QUALITY_PRIORS: Record<string, number> = {
  'gpt-4o': 0.90,
  'gpt-4o-mini': 0.75,
  'gpt-5-mini': 0.86,
  'gpt-4-turbo': 0.88,
  'gpt-4': 0.87,
  'gpt-3.5-turbo': 0.65,
  'o1': 0.95,
  'o1-mini': 0.82,
  'o3-mini': 0.80,
};

const LATENCY_PRIORS: Record<string, number> = {
  'gpt-4o': 0.72,
  'gpt-4o-mini': 0.93,
  'gpt-5-mini': 0.84,
  'gpt-4-turbo': 0.66,
  'gpt-4': 0.52,
  'gpt-3.5-turbo': 1.00,
  'o1': 0.40,
  'o1-mini': 0.60,
  'o3-mini': 0.78,
};

// Pre-computed model cost/energy bounds for utility functions.
const MODEL_POOL = Object.keys(PRICING_USD_PER_M);
const MODEL_TOTAL_COSTS = new Map(MODEL_POOL.map(m => [m, modelTotalPrice(m)]));
const MIN_TOTAL_COST = Math.min(...MODEL_TOTAL_COSTS.values());
const MAX_TOTAL_COST = Math.max(...MODEL_TOTAL_COSTS.values());

const MODEL_ENERGY_COEFFS = new Map(
  MODEL_POOL.map(m => [m, ENERGY_COEFFICIENTS[m] ?? DEFAULT_ENERGY_COEFFICIENT]),
);
const MIN_ENERGY_COEFF = Math.min(...MODEL_ENERGY_COEFFS.values());
const MAX_ENERGY_COEFF = Math.max(...MODEL_ENERGY_COEFFS.values());

// ---------------------------------------------------------------------------
// KPI scoring helpers (from instrument.py lines 234-267)
// ---------------------------------------------------------------------------

function normalizeWeights(weights: KpiWeights): Record<string, number> {
  const raw: Record<string, number> = {};
  for (const [key, val] of Object.entries(weights)) {
    if (['cost', 'quality', 'latency', 'energy'].includes(key) && typeof val === 'number' && val > 0) {
      raw[key] = val;
    }
  }
  const total = Object.values(raw).reduce((a, b) => a + b, 0);
  if (total <= 0) return {};
  const normalized: Record<string, number> = {};
  for (const [key, val] of Object.entries(raw)) {
    normalized[key] = val / total;
  }
  return normalized;
}

function costUtility(model: string): number {
  const modelCost = MODEL_TOTAL_COSTS.get(model) ?? modelTotalPrice(model);
  if (MAX_TOTAL_COST === MIN_TOTAL_COST) return 1.0;
  return (MAX_TOTAL_COST - modelCost) / (MAX_TOTAL_COST - MIN_TOTAL_COST);
}

function energyUtility(model: string): number {
  const coeff = ENERGY_COEFFICIENTS[model] ?? DEFAULT_ENERGY_COEFFICIENT;
  if (MAX_ENERGY_COEFF === MIN_ENERGY_COEFF) return 1.0;
  return (MAX_ENERGY_COEFF - coeff) / (MAX_ENERGY_COEFF - MIN_ENERGY_COEFF);
}

function kpiScoreWithNormalized(model: string, normalized: Record<string, number>): number {
  if (Object.keys(normalized).length === 0) return 0.0;
  const quality = QUALITY_PRIORS[model] ?? 0.7;
  const latency = LATENCY_PRIORS[model] ?? 0.7;
  const cost = costUtility(model);
  const energy = energyUtility(model);
  return (
    (normalized.quality ?? 0) * quality +
    (normalized.latency ?? 0) * latency +
    (normalized.cost ?? 0) * cost +
    (normalized.energy ?? 0) * energy
  );
}

function selectKpiWeightedModel(currentModel: string, weights: KpiWeights): string {
  const normalized = normalizeWeights(weights);
  if (Object.keys(normalized).length === 0) return currentModel;
  let bestModel = currentModel;
  let bestScore = kpiScoreWithNormalized(currentModel, normalized);
  for (const candidate of MODEL_POOL) {
    const score = kpiScoreWithNormalized(candidate, normalized);
    if (score > bestScore) {
      bestModel = candidate;
      bestScore = score;
    }
  }
  return bestModel;
}

// Cheapest/fastest/lowest-energy helpers
function selectCheaperModel(currentModel: string): string {
  let cheapest = currentModel;
  let cheapestCost = MODEL_TOTAL_COSTS.get(currentModel) ?? modelTotalPrice(currentModel);
  for (const [m, c] of MODEL_TOTAL_COSTS) {
    if (c < cheapestCost) {
      cheapest = m;
      cheapestCost = c;
    }
  }
  return cheapest;
}

function selectFasterModel(currentModel: string): string {
  const currentLatency = LATENCY_PRIORS[currentModel] ?? 0.7;
  let best = currentModel;
  let bestLatency = currentLatency;
  for (const [m, lat] of Object.entries(LATENCY_PRIORS)) {
    if (lat > bestLatency) {
      best = m;
      bestLatency = lat;
    }
  }
  return best;
}

function selectLowerEnergyModel(currentModel: string): string {
  const currentCoeff = ENERGY_COEFFICIENTS[currentModel] ?? DEFAULT_ENERGY_COEFFICIENT;
  let best = currentModel;
  let bestCoeff = currentCoeff;
  for (const [m, c] of MODEL_ENERGY_COEFFS) {
    if (c < bestCoeff) {
      best = m;
      bestCoeff = c;
    }
  }
  return best;
}

// ---------------------------------------------------------------------------
// HarnessRunContext
// ---------------------------------------------------------------------------

let runIdCounter = 0;

function generateRunId(): string {
  runIdCounter += 1;
  const ts = Date.now().toString(36);
  const counter = runIdCounter.toString(36);
  return `${ts}${counter}`.slice(-8);
}

export class HarnessRunContext {
  readonly runId: string;
  readonly config: HarnessConfig;

  stepCount = 0;
  toolCalls = 0;
  cost = 0;
  latencyUsedMs = 0;
  energyUsed = 0;
  budgetRemaining: number | null;
  lastAction = 'allow';

  private startedAt: number;
  private trace: HarnessTraceEntry[] = [];

  constructor(config: HarnessConfig) {
    this.runId = generateRunId();
    this.config = config;
    this.budgetRemaining = config.budgetMax;
    this.startedAt = Date.now();
  }

  // -----------------------------------------------------------------------
  // Pre-call decision cascade (ported from instrument.py _evaluate_pre_call_decision)
  // -----------------------------------------------------------------------

  evaluatePreCall(model: string, hasTools: boolean): PreCallDecision {
    const cfg = this.config;

    // 1. Budget exhausted
    if (cfg.budgetMax !== null && this.cost >= cfg.budgetMax) {
      return { action: 'stop', reason: 'budget_exceeded', targetModel: model };
    }

    // 2. Tool call cap
    if (hasTools && cfg.toolCallsMax !== null && this.toolCalls >= cfg.toolCallsMax) {
      return { action: 'deny_tool', reason: 'max_tool_calls_reached', targetModel: model };
    }

    // 3. Compliance
    if (cfg.compliance) {
      const allowlist = COMPLIANCE_MODEL_ALLOWLISTS[cfg.compliance.trim().toLowerCase()];
      if (allowlist) {
        if (!allowlist.has(model)) {
          // Can't switch models in n8n — stop if no compliant model possible
          return { action: 'stop', reason: 'compliance_no_approved_model', targetModel: model };
        }
        if (cfg.compliance.trim().toLowerCase() === 'strict' && hasTools) {
          return { action: 'deny_tool', reason: 'compliance_tool_restriction', targetModel: model };
        }
      }
    }

    // 4. Latency cap
    if (cfg.latencyMaxMs !== null && this.latencyUsedMs >= cfg.latencyMaxMs) {
      const faster = selectFasterModel(model);
      if (faster !== model) {
        return { action: 'switch_model', reason: 'latency_limit_exceeded', targetModel: faster };
      }
      return { action: 'stop', reason: 'latency_limit_exceeded', targetModel: model };
    }

    // 5. Energy cap
    if (cfg.energyMax !== null && this.energyUsed >= cfg.energyMax) {
      const lower = selectLowerEnergyModel(model);
      if (lower !== model) {
        return { action: 'switch_model', reason: 'energy_limit_exceeded', targetModel: lower };
      }
      return { action: 'stop', reason: 'energy_limit_exceeded', targetModel: model };
    }

    // 6. Budget pressure (<20% remaining) — observation only in n8n
    if (
      cfg.budgetMax !== null &&
      cfg.budgetMax > 0 &&
      this.budgetRemaining !== null &&
      this.budgetRemaining / cfg.budgetMax < 0.2
    ) {
      const cheaper = selectCheaperModel(model);
      if (cheaper !== model) {
        return { action: 'switch_model', reason: 'budget_pressure', targetModel: cheaper };
      }
    }

    // 7. KPI-weighted — observation only in n8n
    const kw = cfg.kpiWeights;
    if (kw && Object.values(kw).some(v => typeof v === 'number' && v > 0)) {
      const weighted = selectKpiWeightedModel(model, kw);
      if (weighted !== model) {
        return { action: 'switch_model', reason: 'kpi_weight_optimization', targetModel: weighted };
      }
    }

    // 8. Default: allow
    return { action: 'allow', reason: cfg.mode, targetModel: model };
  }

  // -----------------------------------------------------------------------
  // Record a completed call
  // -----------------------------------------------------------------------

  recordCall(params: RecordCallParams): void {
    const { model, inputTokens, outputTokens, toolCallCount, elapsedMs, decision } = params;

    const callCost = estimateCost(model, inputTokens, outputTokens);
    const energy = estimateEnergy(model, inputTokens, outputTokens);

    this.cost += callCost;
    this.stepCount += 1;
    this.latencyUsedMs += elapsedMs;
    this.energyUsed += energy;
    this.toolCalls += toolCallCount;

    if (this.config.budgetMax !== null) {
      this.budgetRemaining = this.config.budgetMax - this.cost;
    }

    const action = decision?.action ?? 'allow';
    const reason = decision?.reason ?? this.config.mode;
    const applied = action === 'allow' || (this.config.mode === 'enforce' && (action === 'stop' || action === 'deny_tool'));

    this.lastAction = action;

    this.trace.push({
      action,
      reason,
      model,
      step: this.stepCount,
      timestampMs: Date.now(),
      costTotal: this.cost,
      budgetState: {
        max: this.config.budgetMax,
        remaining: this.budgetRemaining,
      },
      applied,
      decisionMode: this.config.mode,
    });
  }

  // -----------------------------------------------------------------------
  // Quick checks for agent loop
  // -----------------------------------------------------------------------

  isBudgetExhausted(): boolean {
    return this.config.budgetMax !== null && this.cost >= this.config.budgetMax;
  }

  isToolCapReached(): boolean {
    return this.config.toolCallsMax !== null && this.toolCalls >= this.config.toolCallsMax;
  }

  // -----------------------------------------------------------------------
  // Summary
  // -----------------------------------------------------------------------

  summary(): HarnessSummary {
    return {
      runId: this.runId,
      mode: this.config.mode,
      stepCount: this.stepCount,
      toolCalls: this.toolCalls,
      cost: this.cost,
      latencyUsedMs: this.latencyUsedMs,
      energyUsed: this.energyUsed,
      budgetMax: this.config.budgetMax,
      budgetRemaining: this.budgetRemaining,
      lastAction: this.lastAction,
      durationMs: Date.now() - this.startedAt,
      trace: [...this.trace],
    };
  }
}

// Re-export for external test access
export { COMPLIANCE_MODEL_ALLOWLISTS, QUALITY_PRIORS, LATENCY_PRIORS, normalizeWeights };
