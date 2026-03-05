type Action = 'allow' | 'switch_model' | 'deny_tool' | 'stop';

type CreateFunction = (this: any, ...args: any[]) => any;

type OpenAIModuleLike = {
  Completions?: {
    prototype?: {
      create?: CreateFunction;
    };
  };
};

type AnthropicModuleLike = {
  Messages?: {
    prototype?: {
      create?: CreateFunction;
    };
  };
};

type Pricing = { input: number; output: number };

type PreCallDecision = {
  action: Action;
  reason: string;
  targetModel: string;
};

type HarnessRuntime = {
  getCurrentRun: () => HarnessRunContextLike | null;
  getHarnessMode: () => HarnessModeLike;
  createBudgetExceededError: (message: string, remaining?: number) => Error;
  createHarnessStopError: (message: string, reason?: string) => Error;
};

type HarnessModeLike = 'off' | 'observe' | 'enforce';

type HarnessRunContextLike = {
  mode: HarnessModeLike;
  cost: number;
  stepCount: number;
  toolCalls: number;
  latencyUsedMs: number;
  energyUsed: number;
  budgetMax?: number;
  budgetRemaining?: number;
  toolCallsMax?: number;
  latencyMaxMs?: number;
  energyMax?: number;
  compliance?: string;
  kpiWeights?: Record<string, number>;
  record: (
    action: string,
    reason: string,
    model?: string,
    options?: {
      applied?: boolean;
      decisionMode?: HarnessModeLike;
    },
  ) => void;
};

const MODEL_PRICING_PER_MILLION: Record<string, Pricing> = {
  // OpenAI
  'gpt-5': { input: 1.25, output: 10.0 },
  'gpt-5-mini': { input: 0.25, output: 2.0 },
  'gpt-5-nano': { input: 0.05, output: 0.4 },
  'gpt-4o': { input: 2.5, output: 10.0 },
  'gpt-4o-mini': { input: 0.15, output: 0.6 },
  'o1': { input: 15.0, output: 60.0 },
  'o1-mini': { input: 3.0, output: 12.0 },
  'o3-mini': { input: 1.0, output: 5.0 },

  // Anthropic
  'claude-opus-4-5-20251101': { input: 15.0, output: 75.0 },
  'claude-opus-4-20250514': { input: 15.0, output: 75.0 },
  'claude-sonnet-4-5-20250929': { input: 3.0, output: 15.0 },
  'claude-sonnet-4-20250514': { input: 3.0, output: 15.0 },
  'claude-haiku-4-5-20251001': { input: 1.0, output: 5.0 },
  'claude-3-5-haiku-20241022': { input: 1.0, output: 5.0 },
};

const ENERGY_COEFFICIENTS: Record<string, number> = {
  'gpt-5': 1.15,
  'gpt-5-mini': 0.72,
  'gpt-5-nano': 0.45,
  'gpt-4o': 1.0,
  'gpt-4o-mini': 0.55,
  'o1': 1.25,
  'o1-mini': 0.85,
  'o3-mini': 0.75,
  'claude-opus-4-5-20251101': 1.2,
  'claude-opus-4-20250514': 1.15,
  'claude-sonnet-4-5-20250929': 0.95,
  'claude-sonnet-4-20250514': 0.92,
  'claude-haiku-4-5-20251001': 0.7,
  'claude-3-5-haiku-20241022': 0.68,
};

const LATENCY_PRIORS: Record<string, number> = {
  'gpt-5': 0.45,
  'gpt-5-mini': 0.72,
  'gpt-5-nano': 0.9,
  'gpt-4o': 0.58,
  'gpt-4o-mini': 0.82,
  'o1': 0.35,
  'o1-mini': 0.62,
  'o3-mini': 0.7,
  'claude-opus-4-5-20251101': 0.4,
  'claude-opus-4-20250514': 0.44,
  'claude-sonnet-4-5-20250929': 0.6,
  'claude-sonnet-4-20250514': 0.63,
  'claude-haiku-4-5-20251001': 0.85,
  'claude-3-5-haiku-20241022': 0.86,
};

const QUALITY_PRIORS: Record<string, number> = {
  'gpt-5': 0.95,
  'gpt-5-mini': 0.86,
  'gpt-5-nano': 0.74,
  'gpt-4o': 0.9,
  'gpt-4o-mini': 0.82,
  'o1': 0.93,
  'o1-mini': 0.84,
  'o3-mini': 0.86,
  'claude-opus-4-5-20251101': 0.94,
  'claude-opus-4-20250514': 0.92,
  'claude-sonnet-4-5-20250929': 0.9,
  'claude-sonnet-4-20250514': 0.88,
  'claude-haiku-4-5-20251001': 0.82,
  'claude-3-5-haiku-20241022': 0.8,
};

const COMPLIANCE_ALLOWLISTS: Record<string, Set<string>> = {
  strict: new Set(['gpt-4o', 'gpt-4o-mini', 'claude-sonnet-4-5-20250929', 'claude-haiku-4-5-20251001']),
  regulated: new Set(['gpt-4o', 'claude-sonnet-4-5-20250929']),
};

const DEFAULT_ENERGY_COEFFICIENT = 0.9;
const DEFAULT_OUTPUT_WEIGHT = 1.5;

const PRICING_MODELS = Object.keys(MODEL_PRICING_PER_MILLION);

let openAIPatched = false;
let anthropicPatched = false;

let originalOpenAICreate: CreateFunction | null = null;
let originalAnthropicCreate: CreateFunction | null = null;
let patchedOpenAIClass: { prototype?: { create?: CreateFunction } } | null = null;
let patchedAnthropicClass: { prototype?: { create?: CreateFunction } } | null = null;

const defaultOpenAILoader = (): OpenAIModuleLike | null => {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    return require('openai/resources/chat/completions') as OpenAIModuleLike;
  } catch {
    return null;
  }
};

const defaultAnthropicLoader = (): AnthropicModuleLike | null => {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    return require('@anthropic-ai/sdk/resources/messages') as AnthropicModuleLike;
  } catch {
    return null;
  }
};

let loadOpenAIModule = defaultOpenAILoader;
let loadAnthropicModule = defaultAnthropicLoader;
let harnessRuntimeBindings: HarnessRuntime | null = null;

function getHarnessRuntime(): HarnessRuntime {
  if (!harnessRuntimeBindings) {
    throw new Error('Harness runtime bindings not configured');
  }
  return harnessRuntimeBindings;
}

export function setHarnessRuntimeBindingsForInstrumentation(bindings: HarnessRuntime): void {
  harnessRuntimeBindings = bindings;
}

function nowMonotonicMs(): number {
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  if (typeof globalThis !== 'undefined' && (globalThis as any).performance?.now) {
    return (globalThis as any).performance.now() as number;
  }

  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  if (typeof process !== 'undefined' && process.hrtime?.bigint) {
    return Number(process.hrtime.bigint()) / 1_000_000;
  }

  return Date.now();
}

function normalizeModelName(model: string): string {
  return model.trim().toLowerCase();
}

function estimateCost(model: string, promptTokens: number, completionTokens: number): number {
  const price = MODEL_PRICING_PER_MILLION[normalizeModelName(model)];
  if (!price) {
    return 0;
  }

  return (promptTokens / 1_000_000) * price.input + (completionTokens / 1_000_000) * price.output;
}

function estimateEnergy(model: string, promptTokens: number, completionTokens: number): number {
  const coefficient = ENERGY_COEFFICIENTS[normalizeModelName(model)] ?? DEFAULT_ENERGY_COEFFICIENT;
  return coefficient * (promptTokens + completionTokens * DEFAULT_OUTPUT_WEIGHT) / 1000;
}

function modelTotalCost(model: string): number {
  const price = MODEL_PRICING_PER_MILLION[normalizeModelName(model)];
  if (!price) {
    return Number.POSITIVE_INFINITY;
  }
  return price.input + price.output;
}

function selectCheaperModel(currentModel: string): string {
  const currentCost = modelTotalCost(currentModel);
  let bestModel = currentModel;
  let bestCost = currentCost;

  for (const candidate of PRICING_MODELS) {
    const candidateCost = modelTotalCost(candidate);
    if (candidateCost < bestCost) {
      bestModel = candidate;
      bestCost = candidateCost;
    }
  }

  return bestModel;
}

function selectLowerEnergyModel(currentModel: string): string {
  const currentCoeff = ENERGY_COEFFICIENTS[normalizeModelName(currentModel)] ?? DEFAULT_ENERGY_COEFFICIENT;
  let bestModel = currentModel;
  let bestCoeff = currentCoeff;

  for (const candidate of PRICING_MODELS) {
    const coeff = ENERGY_COEFFICIENTS[candidate] ?? DEFAULT_ENERGY_COEFFICIENT;
    if (coeff < bestCoeff) {
      bestModel = candidate;
      bestCoeff = coeff;
    }
  }

  return bestModel;
}

function selectFasterModel(currentModel: string): string {
  const currentLatency = LATENCY_PRIORS[normalizeModelName(currentModel)] ?? 0.7;
  let bestModel = currentModel;
  let bestLatency = currentLatency;

  for (const candidate of PRICING_MODELS) {
    const score = LATENCY_PRIORS[candidate] ?? 0.7;
    if (score > bestLatency) {
      bestModel = candidate;
      bestLatency = score;
    }
  }

  return bestModel;
}

function normalizeWeights(weights: Record<string, number>): Record<string, number> {
  const normalized: Record<string, number> = {};
  let total = 0;

  for (const [key, value] of Object.entries(weights)) {
    if (!Number.isFinite(value) || value <= 0) {
      continue;
    }
    normalized[key] = value;
    total += value;
  }

  if (total <= 0) {
    return {};
  }

  for (const key of Object.keys(normalized)) {
    normalized[key] /= total;
  }

  return normalized;
}

function costUtility(model: string): number {
  const costs = PRICING_MODELS.map(modelTotalCost).filter(Number.isFinite);
  const min = Math.min(...costs);
  const max = Math.max(...costs);
  const current = modelTotalCost(model);

  if (!Number.isFinite(current) || max === min) {
    return 0.5;
  }

  return (max - current) / (max - min);
}

function energyUtility(model: string): number {
  const coeffs = PRICING_MODELS.map((name) => ENERGY_COEFFICIENTS[name] ?? DEFAULT_ENERGY_COEFFICIENT);
  const min = Math.min(...coeffs);
  const max = Math.max(...coeffs);
  const current = ENERGY_COEFFICIENTS[normalizeModelName(model)] ?? DEFAULT_ENERGY_COEFFICIENT;

  if (max === min) {
    return 0.5;
  }

  return (max - current) / (max - min);
}

function kpiScore(model: string, weights: Record<string, number>): number {
  const normalized = normalizeWeights(weights);
  if (Object.keys(normalized).length === 0) {
    return 0;
  }

  const key = normalizeModelName(model);
  const quality = QUALITY_PRIORS[key] ?? 0.7;
  const latency = LATENCY_PRIORS[key] ?? 0.7;
  const cost = costUtility(key);
  const energy = energyUtility(key);

  return (
    (normalized.quality ?? 0) * quality
    + (normalized.latency ?? 0) * latency
    + (normalized.cost ?? 0) * cost
    + (normalized.energy ?? 0) * energy
  );
}

function selectKPIWeightedModel(currentModel: string, weights: Record<string, number>): string {
  const normalized = normalizeWeights(weights);
  if (Object.keys(normalized).length === 0) {
    return currentModel;
  }

  let bestModel = currentModel;
  let bestScore = kpiScore(currentModel, normalized);

  for (const candidate of PRICING_MODELS) {
    const score = kpiScore(candidate, normalized);
    if (score > bestScore) {
      bestModel = candidate;
      bestScore = score;
    }
  }

  return bestModel;
}

function extractOpenAIUsage(response: any): [number, number] {
  const usage = response?.usage;
  if (!usage || typeof usage !== 'object') {
    return [0, 0];
  }
  const promptTokens = Number(usage.prompt_tokens ?? usage.input_tokens ?? 0);
  const completionTokens = Number(usage.completion_tokens ?? usage.output_tokens ?? 0);
  return [
    Number.isFinite(promptTokens) ? promptTokens : 0,
    Number.isFinite(completionTokens) ? completionTokens : 0,
  ];
}

function extractAnthropicUsage(response: any): [number, number] {
  const usage = response?.usage;
  if (!usage || typeof usage !== 'object') {
    return [0, 0];
  }

  const inputTokens = Number(usage.input_tokens ?? usage.prompt_tokens ?? 0);
  const outputTokens = Number(usage.output_tokens ?? usage.completion_tokens ?? 0);
  return [
    Number.isFinite(inputTokens) ? inputTokens : 0,
    Number.isFinite(outputTokens) ? outputTokens : 0,
  ];
}

function countOpenAIToolCalls(response: any): number {
  const toolCalls = response?.choices?.[0]?.message?.tool_calls;
  if (!Array.isArray(toolCalls)) {
    return 0;
  }
  return toolCalls.length;
}

function countAnthropicToolCalls(response: any): number {
  const content = response?.content;
  if (!Array.isArray(content)) {
    return 0;
  }
  return content.filter((item: any) => item?.type === 'tool_use').length;
}

function evaluatePreCallDecision(ctx: HarnessRunContextLike, model: string, hasTools: boolean): PreCallDecision {
  if (ctx.budgetMax != null && ctx.cost >= ctx.budgetMax) {
    return { action: 'stop', reason: 'budget_exceeded', targetModel: model };
  }

  if (hasTools && ctx.toolCallsMax != null && ctx.toolCalls >= ctx.toolCallsMax) {
    return { action: 'deny_tool', reason: 'max_tool_calls_reached', targetModel: model };
  }

  if (ctx.compliance) {
    const profile = COMPLIANCE_ALLOWLISTS[ctx.compliance.trim().toLowerCase()];
    if (profile) {
      const normalized = normalizeModelName(model);
      if (!profile.has(normalized)) {
        const next = PRICING_MODELS.find((candidate) => profile.has(candidate));
        if (next) {
          return { action: 'switch_model', reason: 'compliance_model_policy', targetModel: next };
        }
        return {
          action: hasTools ? 'deny_tool' : 'stop',
          reason: hasTools ? 'compliance_no_approved_tool_path' : 'compliance_no_approved_model',
          targetModel: model,
        };
      }
      if (ctx.compliance.trim().toLowerCase() === 'strict' && hasTools) {
        return { action: 'deny_tool', reason: 'compliance_tool_restriction', targetModel: model };
      }
    }
  }

  if (ctx.latencyMaxMs != null && ctx.latencyUsedMs >= ctx.latencyMaxMs) {
    const faster = selectFasterModel(model);
    if (normalizeModelName(faster) !== normalizeModelName(model)) {
      return { action: 'switch_model', reason: 'latency_limit_exceeded', targetModel: faster };
    }
    return { action: 'stop', reason: 'latency_limit_exceeded', targetModel: model };
  }

  if (ctx.energyMax != null && ctx.energyUsed >= ctx.energyMax) {
    const lower = selectLowerEnergyModel(model);
    if (normalizeModelName(lower) !== normalizeModelName(model)) {
      return { action: 'switch_model', reason: 'energy_limit_exceeded', targetModel: lower };
    }
    return { action: 'stop', reason: 'energy_limit_exceeded', targetModel: model };
  }

  if (
    ctx.budgetMax != null
    && ctx.budgetMax > 0
    && ctx.budgetRemaining != null
    && (ctx.budgetRemaining / ctx.budgetMax) < 0.2
  ) {
    const cheaper = selectCheaperModel(model);
    if (normalizeModelName(cheaper) !== normalizeModelName(model)) {
      return { action: 'switch_model', reason: 'budget_pressure', targetModel: cheaper };
    }
  }

  if (ctx.kpiWeights && Object.keys(ctx.kpiWeights).length > 0) {
    const candidate = selectKPIWeightedModel(model, ctx.kpiWeights);
    if (normalizeModelName(candidate) !== normalizeModelName(model)) {
      return { action: 'switch_model', reason: 'kpi_weight_optimization', targetModel: candidate };
    }
  }

  return { action: 'allow', reason: ctx.mode, targetModel: model };
}

function raiseStopError(ctx: HarnessRunContextLike, reason: string): never {
  const runtime = getHarnessRuntime();
  if (reason === 'budget_exceeded') {
    const remaining = Math.max(0, (ctx.budgetMax ?? 0) - ctx.cost);
    throw runtime.createBudgetExceededError(
      `Budget exhausted: spent $${ctx.cost.toFixed(4)} of $${(ctx.budgetMax ?? 0).toFixed(4)} max`,
      remaining,
    );
  }

  throw runtime.createHarnessStopError(`cascadeflow harness stop: ${reason}`, reason);
}

function updateContext(
  ctx: HarnessRunContextLike,
  mode: HarnessModeLike,
  model: string,
  promptTokens: number,
  completionTokens: number,
  toolCalls: number,
  elapsedMs: number,
  decision: PreCallDecision,
  applied: boolean,
): void {
  const cost = estimateCost(model, promptTokens, completionTokens);
  const energy = estimateEnergy(model, promptTokens, completionTokens);

  ctx.cost += cost;
  ctx.stepCount += 1;
  ctx.toolCalls += toolCalls;
  ctx.latencyUsedMs += elapsedMs;
  ctx.energyUsed += energy;

  if (ctx.budgetMax != null) {
    ctx.budgetRemaining = ctx.budgetMax - ctx.cost;
  }

  ctx.record(decision.action, decision.reason, decision.targetModel, {
    applied,
    decisionMode: mode,
  });
}

function isThenable(value: any): value is Promise<any> {
  return Boolean(value) && typeof value.then === 'function';
}

function makePatchedCreate(provider: 'openai' | 'anthropic', original: CreateFunction): CreateFunction {
  return function patchedCreate(this: any, ...args: any[]): any {
    const runtime = getHarnessRuntime();
    const activeRun = runtime.getCurrentRun();
    const mode = activeRun?.mode ?? runtime.getHarnessMode();

    if (mode === 'off') {
      return original.apply(this, args);
    }

    const firstArg = args[0];
    const request = firstArg && typeof firstArg === 'object' ? { ...firstArg } : {};
    const model = typeof request.model === 'string' ? request.model : 'unknown';
    const hasTools = Array.isArray(request.tools) && request.tools.length > 0;

    const decision = activeRun ? evaluatePreCallDecision(activeRun, model, hasTools) : {
      action: 'allow' as const,
      reason: mode,
      targetModel: model,
    };

    let applied = decision.action === 'allow';
    let effectiveModel = model;

    if (activeRun && mode === 'enforce') {
      if (decision.action === 'stop') {
        activeRun.record('stop', decision.reason, model, {
          applied: true,
          decisionMode: mode,
        });
        raiseStopError(activeRun, decision.reason);
      }

      if (decision.action === 'switch_model') {
        if (normalizeModelName(decision.targetModel) !== normalizeModelName(model)) {
          request.model = decision.targetModel;
          effectiveModel = decision.targetModel;
          applied = true;
        } else {
          applied = false;
        }
      }

      if (decision.action === 'deny_tool') {
        if (Array.isArray(request.tools) && request.tools.length > 0) {
          request.tools = [];
          applied = true;
        } else {
          applied = false;
        }
      }
    } else if (decision.action !== 'allow') {
      applied = false;
    }

    const interceptedArgs = firstArg && typeof firstArg === 'object'
      ? [request, ...args.slice(1)]
      : args;

    const isStream = Boolean(request.stream);
    const startedAt = nowMonotonicMs();
    const result = original.apply(this, interceptedArgs);

    if (!activeRun) {
      return result;
    }

    const finalize = (response: any): any => {
      const elapsedMs = Math.max(0, nowMonotonicMs() - startedAt);

      let promptTokens = 0;
      let completionTokens = 0;
      let toolCallCount = 0;

      if (!isStream) {
        if (provider === 'openai') {
          [promptTokens, completionTokens] = extractOpenAIUsage(response);
          toolCallCount = countOpenAIToolCalls(response);
        } else {
          [promptTokens, completionTokens] = extractAnthropicUsage(response);
          toolCallCount = countAnthropicToolCalls(response);
        }
      }

      updateContext(
        activeRun,
        mode,
        effectiveModel,
        promptTokens,
        completionTokens,
        toolCallCount,
        elapsedMs,
        decision,
        applied,
      );

      return response;
    };

    if (isThenable(result)) {
      result
        .then((response) => {
          finalize(response);
        })
        .catch(() => {
          // fail-open: harness instrumentation errors must not crash user flow.
        });
      return result;
    }

    return finalize(result);
  };
}

export function detectOpenAIInstrumentationTarget(): boolean {
  const module = loadOpenAIModule();
  return Boolean(module?.Completions?.prototype?.create);
}

export function detectAnthropicInstrumentationTarget(): boolean {
  const module = loadAnthropicModule();
  return Boolean(module?.Messages?.prototype?.create);
}

export function patchOpenAI(): boolean {
  if (openAIPatched) {
    return true;
  }

  const module = loadOpenAIModule();
  const cls = module?.Completions;
  const prototype = cls?.prototype;
  const create = prototype?.create;

  if (!cls || !prototype || typeof create !== 'function') {
    return false;
  }

  originalOpenAICreate = create;
  patchedOpenAIClass = cls;
  prototype.create = makePatchedCreate('openai', create);
  openAIPatched = true;
  return true;
}

export function patchAnthropic(): boolean {
  if (anthropicPatched) {
    return true;
  }

  const module = loadAnthropicModule();
  const cls = module?.Messages;
  const prototype = cls?.prototype;
  const create = prototype?.create;

  if (!cls || !prototype || typeof create !== 'function') {
    return false;
  }

  originalAnthropicCreate = create;
  patchedAnthropicClass = cls;
  prototype.create = makePatchedCreate('anthropic', create);
  anthropicPatched = true;
  return true;
}

export function unpatchOpenAI(): void {
  if (!openAIPatched) {
    return;
  }

  if (patchedOpenAIClass?.prototype && originalOpenAICreate) {
    patchedOpenAIClass.prototype.create = originalOpenAICreate;
  }

  openAIPatched = false;
  originalOpenAICreate = null;
  patchedOpenAIClass = null;
}

export function unpatchAnthropic(): void {
  if (!anthropicPatched) {
    return;
  }

  if (patchedAnthropicClass?.prototype && originalAnthropicCreate) {
    patchedAnthropicClass.prototype.create = originalAnthropicCreate;
  }

  anthropicPatched = false;
  originalAnthropicCreate = null;
  patchedAnthropicClass = null;
}

export function isOpenAIPatched(): boolean {
  return openAIPatched;
}

export function isAnthropicPatched(): boolean {
  return anthropicPatched;
}

export function isPatched(): boolean {
  return openAIPatched || anthropicPatched;
}

export function __setInstrumentationLoadersForTest(loaders: {
  openai?: () => OpenAIModuleLike | null;
  anthropic?: () => AnthropicModuleLike | null;
}): void {
  if (loaders.openai) {
    loadOpenAIModule = loaders.openai;
  }
  if (loaders.anthropic) {
    loadAnthropicModule = loaders.anthropic;
  }
}

export function __resetInstrumentationLoadersForTest(): void {
  loadOpenAIModule = defaultOpenAILoader;
  loadAnthropicModule = defaultAnthropicLoader;
}

export function __resetInstrumentationStateForTest(): void {
  unpatchOpenAI();
  unpatchAnthropic();
}
