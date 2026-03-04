import {
  __resetInstrumentationStateForTest,
  detectAnthropicInstrumentationTarget,
  detectOpenAIInstrumentationTarget,
  patchAnthropic,
  patchOpenAI,
  setHarnessRuntimeBindingsForInstrumentation,
  unpatchAnthropic,
  unpatchOpenAI,
} from './harness-instrument';

export type HarnessMode = 'off' | 'observe' | 'enforce';

export type HarnessConfig = {
  mode: HarnessMode;
  verbose: boolean;
  budget?: number;
  maxToolCalls?: number;
  maxLatencyMs?: number;
  maxEnergy?: number;
  kpiTargets?: Record<string, number>;
  kpiWeights?: Record<string, number>;
  compliance?: string;
};

export type HarnessInitOptions = Partial<HarnessConfig>;

export type HarnessRunOptions = {
  budget?: number;
  maxToolCalls?: number;
  maxLatencyMs?: number;
  maxEnergy?: number;
  kpiTargets?: Record<string, number>;
  kpiWeights?: Record<string, number>;
  compliance?: string;
};

export type HarnessInitReport = {
  mode: HarnessMode;
  instrumented: string[];
  detectedButNotInstrumented: string[];
  configSources: Record<string, 'code' | 'env' | 'file' | 'default'>;
};

export type HarnessRecordOptions = {
  applied?: boolean;
  decisionMode?: HarnessMode;
};

export type HarnessTraceEntry = {
  action: string;
  reason: string;
  model?: string;
  runId: string;
  mode: HarnessMode;
  step: number;
  timestampMs: number;
  toolCallsTotal: number;
  costTotal: number;
  latencyUsedMs: number;
  energyUsed: number;
  budgetState: {
    max?: number;
    remaining?: number;
  };
  applied?: boolean;
  decisionMode?: HarnessMode;
};

export type HarnessRunSummary = {
  runId: string;
  mode: HarnessMode;
  stepCount: number;
  toolCalls: number;
  cost: number;
  savings: number;
  latencyUsedMs: number;
  energyUsed: number;
  budgetMax?: number;
  budgetRemaining?: number;
  lastAction: string;
  modelUsed?: string;
  durationMs?: number;
};

export class HarnessStopError extends Error {
  reason: string;

  constructor(message: string, reason = 'stop') {
    super(message);
    this.name = 'HarnessStopError';
    this.reason = reason;
  }
}

export class BudgetExceededError extends HarnessStopError {
  remaining: number;

  constructor(message: string, remaining = 0) {
    super(message, 'budget_exceeded');
    this.name = 'BudgetExceededError';
    this.remaining = remaining;
  }
}

function randomRunId(): string {
  return Math.random().toString(36).slice(2, 14);
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

const MAX_ACTION_LEN = 64;
const MAX_REASON_LEN = 160;
const MAX_MODEL_LEN = 128;

function sanitizeTraceValue(value: unknown, maxLength: number): string | undefined {
  if (value == null) {
    return undefined;
  }

  const text = String(value).replace(/\r?\n/g, ' ').trim();
  if (!text) {
    return undefined;
  }

  if (text.length <= maxLength) {
    return text;
  }

  return `${text.slice(0, Math.max(0, maxLength - 3))}...`;
}

export class HarnessRunContext {
  runId: string;
  startedAtMs: number;
  endedAtMs?: number;
  durationMs?: number;

  mode: HarnessMode;
  budgetMax?: number;
  toolCallsMax?: number;
  latencyMaxMs?: number;
  energyMax?: number;
  kpiTargets?: Record<string, number>;
  kpiWeights?: Record<string, number>;
  compliance?: string;

  cost = 0;
  savings = 0;
  toolCalls = 0;
  stepCount = 0;
  latencyUsedMs = 0;
  energyUsed = 0;
  verbose = false;
  budgetRemaining?: number;
  modelUsed?: string;
  lastAction = 'allow';
  draftAccepted?: boolean;

  private readonly _startedMonotonic: number;
  private readonly _trace: HarnessTraceEntry[] = [];
  private _finalized = false;

  constructor(config: {
    mode: HarnessMode;
    budgetMax?: number;
    toolCallsMax?: number;
    latencyMaxMs?: number;
    energyMax?: number;
    kpiTargets?: Record<string, number>;
    kpiWeights?: Record<string, number>;
    compliance?: string;
    verbose?: boolean;
  }) {
    this.runId = randomRunId();
    this.startedAtMs = Date.now();
    this._startedMonotonic = nowMonotonicMs();

    this.mode = config.mode;
    this.budgetMax = config.budgetMax;
    this.toolCallsMax = config.toolCallsMax;
    this.latencyMaxMs = config.latencyMaxMs;
    this.energyMax = config.energyMax;
    this.kpiTargets = config.kpiTargets;
    this.kpiWeights = config.kpiWeights;
    this.compliance = config.compliance;
    this.verbose = Boolean(config.verbose);

    if (config.budgetMax != null) {
      this.budgetRemaining = config.budgetMax;
    }
  }

  finish(): void {
    if (this._finalized) {
      return;
    }

    this._finalized = true;
    this.endedAtMs = Date.now();
    this.durationMs = Math.max(0, nowMonotonicMs() - this._startedMonotonic);

    if (this.verbose && this.mode !== 'off' && this.stepCount > 0) {
      // Keep logging cheap and controlled.
      // eslint-disable-next-line no-console
      console.info(
        '[cascadeflow.harness] run summary',
        {
          runId: this.runId,
          mode: this.mode,
          steps: this.stepCount,
          toolCalls: this.toolCalls,
          cost: this.cost,
          latencyMs: this.latencyUsedMs,
          energy: this.energyUsed,
          lastAction: this.lastAction,
          model: this.modelUsed,
          budgetRemaining: this.budgetRemaining,
          durationMs: this.durationMs,
        },
      );
    }
  }

  record(action: string, reason: string, model?: string, options: HarnessRecordOptions = {}): void {
    let safeAction = sanitizeTraceValue(action, MAX_ACTION_LEN);
    if (!safeAction) {
      safeAction = 'allow';
    }

    const safeReason = sanitizeTraceValue(reason, MAX_REASON_LEN) ?? 'unspecified';
    const safeModel = sanitizeTraceValue(model, MAX_MODEL_LEN);

    this.lastAction = safeAction;
    this.modelUsed = safeModel;

    const entry: HarnessTraceEntry = {
      action: safeAction,
      reason: safeReason,
      model: safeModel,
      runId: this.runId,
      mode: this.mode,
      step: this.stepCount,
      timestampMs: Date.now(),
      toolCallsTotal: this.toolCalls,
      costTotal: this.cost,
      latencyUsedMs: this.latencyUsedMs,
      energyUsed: this.energyUsed,
      budgetState: {
        max: this.budgetMax,
        remaining: this.budgetRemaining,
      },
    };

    if (options.applied != null) {
      entry.applied = options.applied;
    }

    if (options.decisionMode != null) {
      entry.decisionMode = options.decisionMode;
    }

    this._trace.push(entry);
  }

  trace(): HarnessTraceEntry[] {
    return [...this._trace];
  }

  summary(): HarnessRunSummary {
    return {
      runId: this.runId,
      mode: this.mode,
      stepCount: this.stepCount,
      toolCalls: this.toolCalls,
      cost: this.cost,
      savings: this.savings,
      latencyUsedMs: this.latencyUsedMs,
      energyUsed: this.energyUsed,
      budgetMax: this.budgetMax,
      budgetRemaining: this.budgetRemaining,
      lastAction: this.lastAction,
      modelUsed: this.modelUsed,
      durationMs: this.durationMs,
    };
  }
}

type ConfigSource = 'code' | 'env' | 'file' | 'default';

type ConfigWithSources = {
  config: HarnessConfig;
  sources: Record<string, ConfigSource>;
};

let _harnessConfig: HarnessConfig = {
  mode: 'off',
  verbose: false,
};

let _isInstrumented = false;
let fallbackCurrentRun: HarnessRunContext | null = null;

let asyncLocalStorageInstance: { run: (store: HarnessRunContext, callback: () => Promise<unknown>) => Promise<unknown>; getStore: () => HarnessRunContext | undefined } | null = null;

function getAsyncLocalStorage(): typeof asyncLocalStorageInstance {
  if (asyncLocalStorageInstance) {
    return asyncLocalStorageInstance;
  }

  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require('node:async_hooks') as {
      AsyncLocalStorage: new <T>() => { run: (store: T, callback: () => Promise<unknown>) => Promise<unknown>; getStore: () => T | undefined };
    };

    asyncLocalStorageInstance = new mod.AsyncLocalStorage<HarnessRunContext>();
  } catch {
    asyncLocalStorageInstance = null;
  }

  return asyncLocalStorageInstance;
}

function parseBoolean(raw: string): boolean {
  const normalized = raw.trim().toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on';
}

function parseNumber(raw: string): number {
  const value = Number(raw);
  if (!Number.isFinite(value)) {
    throw new Error(`Invalid numeric value: ${raw}`);
  }
  return value;
}

function parseJSONMap(raw: string): Record<string, number> {
  const parsed = JSON.parse(raw);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Expected object');
  }

  const result: Record<string, number> = {};
  for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
    result[String(key)] = Number(value);
  }
  return result;
}

function normalizeMode(mode: unknown): HarnessMode {
  if (mode === 'off' || mode === 'observe' || mode === 'enforce') {
    return mode;
  }

  throw new Error('mode must be one of: off, observe, enforce');
}

function normalizeConfigRecord(raw: Record<string, unknown>): HarnessInitOptions {
  const out: HarnessInitOptions = {};

  const mode = raw.mode ?? raw.harness_mode;
  if (typeof mode === 'string') {
    out.mode = normalizeMode(mode);
  }

  const verbose = raw.verbose ?? raw.harness_verbose;
  if (typeof verbose === 'boolean') {
    out.verbose = verbose;
  }

  const budget = raw.budget ?? raw.max_budget;
  if (typeof budget === 'number') {
    out.budget = budget;
  }

  const maxToolCalls = raw.maxToolCalls ?? raw.max_tool_calls;
  if (typeof maxToolCalls === 'number') {
    out.maxToolCalls = maxToolCalls;
  }

  const maxLatencyMs = raw.maxLatencyMs ?? raw.max_latency_ms;
  if (typeof maxLatencyMs === 'number') {
    out.maxLatencyMs = maxLatencyMs;
  }

  const maxEnergy = raw.maxEnergy ?? raw.max_energy;
  if (typeof maxEnergy === 'number') {
    out.maxEnergy = maxEnergy;
  }

  const kpiTargets = raw.kpiTargets ?? raw.kpi_targets;
  if (kpiTargets && typeof kpiTargets === 'object' && !Array.isArray(kpiTargets)) {
    out.kpiTargets = kpiTargets as Record<string, number>;
  }

  const kpiWeights = raw.kpiWeights ?? raw.kpi_weights;
  if (kpiWeights && typeof kpiWeights === 'object' && !Array.isArray(kpiWeights)) {
    out.kpiWeights = kpiWeights as Record<string, number>;
  }

  const compliance = raw.compliance;
  if (typeof compliance === 'string') {
    out.compliance = compliance;
  }

  return out;
}

function readEnvConfig(): HarnessInitOptions {
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  if (typeof process === 'undefined' || !process.env) {
    return {};
  }

  const env = process.env;
  const config: HarnessInitOptions = {};

  const mode = env.CASCADEFLOW_HARNESS_MODE ?? env.CASCADEFLOW_MODE;
  if (mode) {
    config.mode = normalizeMode(mode);
  }

  if (env.CASCADEFLOW_HARNESS_VERBOSE != null) {
    config.verbose = parseBoolean(env.CASCADEFLOW_HARNESS_VERBOSE);
  }

  const budget = env.CASCADEFLOW_HARNESS_BUDGET ?? env.CASCADEFLOW_BUDGET;
  if (budget != null) {
    config.budget = parseNumber(budget);
  }

  if (env.CASCADEFLOW_HARNESS_MAX_TOOL_CALLS != null) {
    config.maxToolCalls = parseNumber(env.CASCADEFLOW_HARNESS_MAX_TOOL_CALLS);
  }

  if (env.CASCADEFLOW_HARNESS_MAX_LATENCY_MS != null) {
    config.maxLatencyMs = parseNumber(env.CASCADEFLOW_HARNESS_MAX_LATENCY_MS);
  }

  if (env.CASCADEFLOW_HARNESS_MAX_ENERGY != null) {
    config.maxEnergy = parseNumber(env.CASCADEFLOW_HARNESS_MAX_ENERGY);
  }

  if (env.CASCADEFLOW_HARNESS_KPI_TARGETS != null) {
    config.kpiTargets = parseJSONMap(env.CASCADEFLOW_HARNESS_KPI_TARGETS);
  }

  if (env.CASCADEFLOW_HARNESS_KPI_WEIGHTS != null) {
    config.kpiWeights = parseJSONMap(env.CASCADEFLOW_HARNESS_KPI_WEIGHTS);
  }

  if (env.CASCADEFLOW_HARNESS_COMPLIANCE != null) {
    config.compliance = env.CASCADEFLOW_HARNESS_COMPLIANCE;
  }

  return config;
}

function readFileConfig(): HarnessInitOptions {
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  if (typeof process === 'undefined' || !process.cwd) {
    return {};
  }

  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const fs = require('node:fs') as typeof import('node:fs');
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const path = require('node:path') as typeof import('node:path');

    const configuredPath = process.env.CASCADEFLOW_CONFIG;
    const candidates = configuredPath
      ? [configuredPath]
      : ['cascadeflow.json', 'cascadeflow.config.json'];

    for (const candidate of candidates) {
      const full = path.isAbsolute(candidate) ? candidate : path.join(process.cwd(), candidate);
      if (!fs.existsSync(full)) {
        continue;
      }

      const content = fs.readFileSync(full, 'utf8');
      const parsed = JSON.parse(content) as Record<string, unknown>;
      const harnessBlock = (
        parsed.harness && typeof parsed.harness === 'object' && !Array.isArray(parsed.harness)
      )
        ? (parsed.harness as Record<string, unknown>)
        : parsed;

      return normalizeConfigRecord(harnessBlock);
    }
  } catch {
    return {};
  }

  return {};
}

function resolveConfig(options: HarnessInitOptions): ConfigWithSources {
  const env = readEnvConfig();
  const file = readFileConfig();
  const sources: Record<string, ConfigSource> = {};

  const resolve = <T>(
    key: keyof HarnessConfig,
    explicit: T | undefined,
    envValue: T | undefined,
    fileValue: T | undefined,
    defaultValue: T,
  ): T => {
    if (explicit !== undefined) {
      sources[key] = 'code';
      return explicit;
    }
    if (envValue !== undefined) {
      sources[key] = 'env';
      return envValue;
    }
    if (fileValue !== undefined) {
      sources[key] = 'file';
      return fileValue;
    }
    sources[key] = 'default';
    return defaultValue;
  };

  const mode = resolve('mode', options.mode, env.mode, file.mode, 'off');
  const verbose = resolve('verbose', options.verbose, env.verbose, file.verbose, false);
  const budget = resolve('budget', options.budget, env.budget, file.budget, undefined);
  const maxToolCalls = resolve(
    'maxToolCalls',
    options.maxToolCalls,
    env.maxToolCalls,
    file.maxToolCalls,
    undefined,
  );
  const maxLatencyMs = resolve(
    'maxLatencyMs',
    options.maxLatencyMs,
    env.maxLatencyMs,
    file.maxLatencyMs,
    undefined,
  );
  const maxEnergy = resolve('maxEnergy', options.maxEnergy, env.maxEnergy, file.maxEnergy, undefined);
  const kpiTargets = resolve(
    'kpiTargets',
    options.kpiTargets,
    env.kpiTargets,
    file.kpiTargets,
    undefined,
  );
  const kpiWeights = resolve(
    'kpiWeights',
    options.kpiWeights,
    env.kpiWeights,
    file.kpiWeights,
    undefined,
  );
  const compliance = resolve(
    'compliance',
    options.compliance,
    env.compliance,
    file.compliance,
    undefined,
  );

  return {
    config: {
      mode,
      verbose,
      budget,
      maxToolCalls,
      maxLatencyMs,
      maxEnergy,
      kpiTargets,
      kpiWeights,
      compliance,
    },
    sources,
  };
}

export function getHarnessConfig(): HarnessConfig {
  return { ..._harnessConfig };
}

export function getCurrentRun(): HarnessRunContext | null {
  const als = getAsyncLocalStorage();
  if (als) {
    return als.getStore() ?? null;
  }

  return fallbackCurrentRun;
}

export function reset(): void {
  unpatchOpenAI();
  unpatchAnthropic();
  __resetInstrumentationStateForTest();

  _harnessConfig = { mode: 'off', verbose: false };
  _isInstrumented = false;
  fallbackCurrentRun = null;
}

export function init(options: HarnessInitOptions = {}): HarnessInitReport {
  const { config, sources } = resolveConfig(options);
  config.mode = normalizeMode(config.mode);

  _harnessConfig = config;

  const instrumented: string[] = [];
  const detectedButNotInstrumented: string[] = [];

  const openaiDetected = detectOpenAIInstrumentationTarget();
  const anthropicDetected = detectAnthropicInstrumentationTarget();

  if (config.mode !== 'off' && openaiDetected) {
    if (patchOpenAI()) {
      instrumented.push('openai');
    } else {
      detectedButNotInstrumented.push('openai');
    }
  }

  if (config.mode !== 'off' && anthropicDetected) {
    if (patchAnthropic()) {
      instrumented.push('anthropic');
    } else {
      detectedButNotInstrumented.push('anthropic');
    }
  }

  if (config.mode === 'off') {
    unpatchOpenAI();
    unpatchAnthropic();
  }

  _isInstrumented = true;

  if (config.verbose) {
    // eslint-disable-next-line no-console
    console.info('[cascadeflow.harness] init', {
      mode: config.mode,
      instrumented,
      detectedButNotInstrumented,
    });
  }

  return {
    mode: config.mode,
    instrumented,
    detectedButNotInstrumented,
    configSources: sources,
  };
}

type RunCallback<T> = (run: HarnessRunContext) => Promise<T> | T;

async function executeScopedRun<T>(runContext: HarnessRunContext, fn: RunCallback<T>): Promise<T> {
  try {
    return await fn(runContext);
  } finally {
    runContext.finish();
  }
}

export async function run<T>(callback: RunCallback<T>): Promise<T>;
export async function run<T>(options: HarnessRunOptions, callback: RunCallback<T>): Promise<T>;
export async function run<T>(
  optionsOrCallback: HarnessRunOptions | RunCallback<T>,
  callback?: RunCallback<T>,
): Promise<T> {
  const options = typeof optionsOrCallback === 'function' ? {} : optionsOrCallback;
  const cb = (typeof optionsOrCallback === 'function' ? optionsOrCallback : callback) as RunCallback<T> | undefined;

  if (!cb) {
    throw new Error('run() requires a callback: run(options?, async (run) => { ... })');
  }

  const cfg = getHarnessConfig();
  const runContext = new HarnessRunContext({
    mode: cfg.mode,
    budgetMax: options.budget ?? cfg.budget,
    toolCallsMax: options.maxToolCalls ?? cfg.maxToolCalls,
    latencyMaxMs: options.maxLatencyMs ?? cfg.maxLatencyMs,
    energyMax: options.maxEnergy ?? cfg.maxEnergy,
    kpiTargets: options.kpiTargets ?? cfg.kpiTargets,
    kpiWeights: options.kpiWeights ?? cfg.kpiWeights,
    compliance: options.compliance ?? cfg.compliance,
    verbose: cfg.verbose,
  });

  const als = getAsyncLocalStorage();
  if (als) {
    return als.run(runContext, async () => executeScopedRun(runContext, cb)) as Promise<T>;
  }

  const previous = fallbackCurrentRun;
  fallbackCurrentRun = runContext;
  try {
    return await executeScopedRun(runContext, cb);
  } finally {
    fallbackCurrentRun = previous;
  }
}

export function agent(policy: HarnessRunOptions): <T extends (...args: any[]) => any>(fn: T) => T {
  return <T extends (...args: any[]) => any>(fn: T): T => {
    const wrapped = ((...args: any[]) => fn(...args)) as T;
    (wrapped as any).__cascadeflow_agent_policy__ = {
      budget: policy.budget,
      kpiTargets: policy.kpiTargets,
      kpiWeights: policy.kpiWeights,
      compliance: policy.compliance,
    };
    return wrapped;
  };
}

setHarnessRuntimeBindingsForInstrumentation({
  getCurrentRun,
  getHarnessMode: () => getHarnessConfig().mode,
  createBudgetExceededError: (message: string, remaining?: number) =>
    new BudgetExceededError(message, remaining),
  createHarnessStopError: (message: string, reason?: string) =>
    new HarnessStopError(message, reason),
});

export const cascadeflow = {
  init,
  run,
  agent,
  reset,
  getHarnessConfig,
  getCurrentRun,
};

export function isHarnessInstrumented(): boolean {
  return _isInstrumented;
}
