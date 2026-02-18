export const DEFAULT_PAYGENTIC_LIVE_URL = 'https://api.paygentic.io';
export const DEFAULT_PAYGENTIC_SANDBOX_URL = 'https://api.sandbox.paygentic.io';

const TRANSIENT_STATUS_CODES = new Set([429, 500, 502, 503, 504]);

export type PaygenticQuantityMode = 'tokens' | 'cost_usd' | 'requests';

export interface PaygenticConfig {
  apiKey: string;
  merchantId: string;
  billableMetricId: string;
  baseUrl?: string;
  sandbox?: boolean;
  timeoutMs?: number;
  maxRetries?: number;
  retryBackoffMs?: number;
}

export interface PaygenticCustomerInput {
  email: string;
  name: string;
  address: Record<string, any>;
  phone?: string;
  taxRates?: Record<string, any>;
  idempotencyKey?: string;
}

export interface PaygenticSubscriptionInput {
  planId: string;
  name: string;
  startedAt?: string;
  customerId?: string;
  customer?: Record<string, any>;
  autoCharge?: boolean;
  taxExempt?: boolean;
  endingAt?: string;
  minimumAccountBalance?: string;
  redirectUrls?: Record<string, any>;
  testClockId?: string;
  idempotencyKey?: string;
}

export interface PaygenticUsageEventInput {
  customerId: string;
  quantity: number;
  timestamp?: string;
  idempotencyKey?: string;
  billableMetricId?: string;
  metadata?: Record<string, any>;
  entitlementId?: string;
  description?: string;
  price?: string;
}

export interface ProxyUsageLike {
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
}

export interface ProxyResultLike {
  provider?: string;
  model?: string;
  latency_ms?: number;
  latencyMs?: number;
  cost?: number;
  usage?: ProxyUsageLike | null;
}

export interface ReportProxyUsageInput {
  result: ProxyResultLike;
  customerId: string;
  requestId?: string;
  timestamp?: string;
  metadata?: Record<string, any>;
}

export interface PaygenticReporterConfig {
  quantityMode?: PaygenticQuantityMode;
  costScale?: number;
  failOpen?: boolean;
}

export class PaygenticAPIError extends Error {
  public readonly statusCode?: number;
  public readonly payload?: any;

  constructor(message: string, statusCode?: number, payload?: any) {
    super(message);
    this.name = 'PaygenticAPIError';
    this.statusCode = statusCode;
    this.payload = payload;
  }
}

function normalizePart(value: unknown): string {
  if (value === null || value === undefined) {
    return String(value);
  }

  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return '[unserializable]';
    }
  }

  return String(value);
}

function isoTimestamp(timestamp?: string): string {
  return timestamp ?? new Date().toISOString();
}

function validateCustomerAddress(address: Record<string, any>): void {
  const required = ['line1', 'city', 'country', 'postalCode'];
  const missing = required.filter((key) => !address?.[key]);
  if (missing.length > 0) {
    throw new Error(
      `Customer address missing required fields: ${missing.join(', ')}. Expected keys: ${required.join(', ')}`
    );
  }
}

async function parseResponseBody(response: Response): Promise<any> {
  const text = await response.text();
  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

export function createIdempotencyKey(scope: string, ...parts: unknown[]): string {
  const input = parts.map(normalizePart).join('|');

  let hash = 0;
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash << 5) - hash + input.charCodeAt(i);
    hash |= 0;
  }

  const stable = Math.abs(hash).toString(16).padStart(8, '0');
  return `${scope}_${stable}`;
}

export class PaygenticClient {
  private readonly config: Required<Pick<PaygenticConfig, 'timeoutMs' | 'maxRetries' | 'retryBackoffMs'>> &
    PaygenticConfig;

  private readonly fetchImpl: typeof fetch;

  constructor(config: PaygenticConfig, fetchImpl: typeof fetch = globalThis.fetch) {
    if (!config.apiKey) {
      throw new Error('Paygentic apiKey is required');
    }
    if (!config.merchantId) {
      throw new Error('Paygentic merchantId is required');
    }
    if (!config.billableMetricId) {
      throw new Error('Paygentic billableMetricId is required');
    }
    if (typeof fetchImpl !== 'function') {
      throw new Error('A fetch implementation is required');
    }

    this.config = {
      timeoutMs: 10_000,
      maxRetries: 2,
      retryBackoffMs: 250,
      ...config,
    };
    this.fetchImpl = fetchImpl;
  }

  public get resolvedBaseUrl(): string {
    if (this.config.baseUrl) {
      return this.config.baseUrl.replace(/\/$/, '');
    }

    return this.config.sandbox ? DEFAULT_PAYGENTIC_SANDBOX_URL : DEFAULT_PAYGENTIC_LIVE_URL;
  }

  public createIdempotencyKey(scope: string, ...parts: unknown[]): string {
    return createIdempotencyKey(scope, ...parts);
  }

  private buildHeaders(idempotencyKey?: string): Record<string, string> {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.config.apiKey}`,
      'Content-Type': 'application/json',
    };

    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }

    return headers;
  }

  private async request<T = any>(
    method: string,
    path: string,
    payload: Record<string, any>,
    idempotencyKey?: string
  ): Promise<T> {
    const fullPath = path.startsWith('/') ? path : `/${path}`;
    const url = `${this.resolvedBaseUrl}${fullPath}`;

    let lastError: unknown;

    for (let attempt = 0; attempt <= this.config.maxRetries; attempt += 1) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), this.config.timeoutMs);

      try {
        const response = await this.fetchImpl(url, {
          method,
          headers: this.buildHeaders(idempotencyKey),
          body: JSON.stringify(payload),
          signal: controller.signal,
        });

        clearTimeout(timeout);

        if (!response.ok) {
          if (TRANSIENT_STATUS_CODES.has(response.status) && attempt < this.config.maxRetries) {
            await new Promise((resolve) => setTimeout(resolve, this.config.retryBackoffMs * 2 ** attempt));
            continue;
          }

          const errorBody = await parseResponseBody(response);
          throw new PaygenticAPIError(
            `Paygentic API request failed with status ${response.status}`,
            response.status,
            errorBody
          );
        }

        return (await parseResponseBody(response)) as T;
      } catch (error) {
        clearTimeout(timeout);
        lastError = error;

        if (error instanceof PaygenticAPIError) {
          throw error;
        }

        if (attempt >= this.config.maxRetries) {
          break;
        }

        await new Promise((resolve) => setTimeout(resolve, this.config.retryBackoffMs * 2 ** attempt));
      }
    }

    throw new PaygenticAPIError(`Paygentic API transport failed after retries: ${String(lastError)}`);
  }

  public async createCustomer(input: PaygenticCustomerInput): Promise<any> {
    validateCustomerAddress(input.address);

    const consumer: Record<string, any> = {
      email: input.email,
      name: input.name,
      address: input.address,
    };
    if (input.phone) consumer.phone = input.phone;
    if (input.taxRates) consumer.taxRates = input.taxRates;

    return this.request(
      'POST',
      '/v0/customers',
      {
        merchantId: this.config.merchantId,
        consumer,
      },
      input.idempotencyKey
    );
  }

  public async createSubscription(input: PaygenticSubscriptionInput): Promise<any> {
    if (!input.customerId && !input.customer) {
      throw new Error('Either customerId or customer is required');
    }

    const payload: Record<string, any> = {
      name: input.name,
      planId: input.planId,
      startedAt: isoTimestamp(input.startedAt),
      autoCharge: input.autoCharge ?? false,
      taxExempt: input.taxExempt ?? false,
    };

    if (input.customerId) payload.customerId = input.customerId;
    if (input.customer) payload.customer = input.customer;
    if (input.endingAt) payload.endingAt = input.endingAt;
    if (input.minimumAccountBalance) payload.minimumAccountBalance = input.minimumAccountBalance;
    if (input.redirectUrls) payload.redirectUrls = input.redirectUrls;
    if (input.testClockId) payload.testClockId = input.testClockId;

    return this.request('POST', '/v0/subscriptions', payload, input.idempotencyKey);
  }

  public async createUsageEvent(input: PaygenticUsageEventInput): Promise<any> {
    const metricId = input.billableMetricId ?? this.config.billableMetricId;
    const timestamp = isoTimestamp(input.timestamp);
    const idempotencyKey =
      input.idempotencyKey ??
      this.createIdempotencyKey(
        'usage',
        this.config.merchantId,
        input.customerId,
        metricId,
        timestamp,
        input.quantity
      );

    const usageProperty: Record<string, any> = {
      billableMetricId: metricId,
      quantity: input.quantity,
    };
    if (input.price !== undefined) {
      usageProperty.price = input.price;
    }

    const payload: Record<string, any> = {
      idempotencyKey,
      customerId: input.customerId,
      merchantId: this.config.merchantId,
      timestamp,
      properties: [usageProperty],
    };

    if (input.metadata) payload.metadata = input.metadata;
    if (input.entitlementId) payload.entitlementId = input.entitlementId;
    if (input.description) payload.description = input.description;

    return this.request('POST', '/v0/usage', payload, idempotencyKey);
  }
}

export class PaygenticUsageReporter {
  private readonly client: PaygenticClient;
  private readonly quantityMode: PaygenticQuantityMode;
  private readonly costScale: number;
  private readonly failOpen: boolean;

  constructor(client: PaygenticClient, config: PaygenticReporterConfig = {}) {
    this.client = client;
    this.quantityMode = config.quantityMode ?? 'tokens';
    this.costScale = config.costScale ?? 1_000_000;
    if (!Number.isFinite(this.costScale) || this.costScale <= 0) {
      throw new Error('costScale must be a positive number');
    }
    this.failOpen = config.failOpen ?? true;
  }

  private totalTokens(usage?: ProxyUsageLike | null): number {
    if (!usage) return 0;
    return (
      usage.totalTokens ??
      usage.total_tokens ??
      ((usage.inputTokens ?? usage.input_tokens ?? 0) +
        (usage.outputTokens ?? usage.output_tokens ?? 0))
    );
  }

  private extractQuantity(result: ProxyResultLike): number | null {
    if (this.quantityMode === 'requests') {
      return 1;
    }

    if (this.quantityMode === 'tokens') {
      const tokens = this.totalTokens(result.usage);
      const quantity = Math.round(tokens);
      return quantity > 0 ? quantity : null;
    }

    const cost = result.cost ?? 0;
    const scaledCost = Math.round(cost * this.costScale);
    return scaledCost > 0 ? scaledCost : null;
  }

  public buildUsageEvent(input: ReportProxyUsageInput): PaygenticUsageEventInput | null {
    const quantity = this.extractQuantity(input.result);
    if (quantity === null) {
      return null;
    }

    const timestamp = isoTimestamp(input.timestamp);
    const usage = input.result.usage;

    const metadata: Record<string, any> = {
      integration: '@cascadeflow/paygentic',
      provider: input.result.provider ?? 'unknown',
      model: input.result.model ?? 'unknown',
      latency_ms: input.result.latency_ms ?? input.result.latencyMs,
      cost_usd: input.result.cost,
      quantity_mode: this.quantityMode,
      input_tokens: usage?.input_tokens ?? usage?.inputTokens,
      output_tokens: usage?.output_tokens ?? usage?.outputTokens,
      total_tokens: this.totalTokens(usage),
      ...(input.metadata ?? {}),
    };
    if (this.quantityMode === 'cost_usd') {
      metadata.cost_scale = this.costScale;
      metadata.cost_usd_raw = input.result.cost;
    }

    return {
      customerId: input.customerId,
      quantity,
      timestamp,
      idempotencyKey: this.client.createIdempotencyKey(
        'usage',
        input.customerId,
        input.requestId ?? 'no-request-id',
        input.result.provider ?? 'unknown',
        input.result.model ?? 'unknown',
        this.quantityMode,
        quantity,
        timestamp
      ),
      metadata,
    };
  }

  public async reportProxyUsage(input: ReportProxyUsageInput): Promise<any | null> {
    const event = this.buildUsageEvent(input);
    if (!event) {
      return null;
    }

    try {
      return await this.client.createUsageEvent(event);
    } catch (error) {
      if (!this.failOpen) {
        throw error;
      }
      return null;
    }
  }
}
