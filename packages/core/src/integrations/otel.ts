/**
 * OpenTelemetry integration for CascadeFlow metrics export.
 *
 * This module provides OpenTelemetry-based metric export for production observability.
 * Exports cost, token, and latency metrics to any OpenTelemetry-compatible backend
 * (Grafana, Datadog, CloudWatch, Prometheus, etc.).
 *
 * Key Features:
 * - Cost tracking per user/model/provider
 * - Token usage tracking (input + output)
 * - Latency histograms for performance monitoring
 * - Automatic dimension tagging (user, model, provider, tier)
 * - Compatible with all OpenTelemetry backends
 *
 * @example
 * ```typescript
 * import { OpenTelemetryExporter, CascadeflowMetrics, MetricDimensions } from '@cascadeflow/core';
 *
 * // Initialize exporter
 * const exporter = new OpenTelemetryExporter({
 *   endpoint: 'http://localhost:4318',  // OTLP HTTP endpoint
 *   serviceName: 'cascadeflow-prod'
 * });
 *
 * // Record metrics
 * exporter.record({
 *   cost: 0.001,
 *   tokensInput: 100,
 *   tokensOutput: 200,
 *   latencyMs: 1500,
 *   dimensions: {
 *     userId: 'user123',
 *     model: 'gpt-4o-mini',
 *     provider: 'openai'
 *   }
 * });
 * ```
 *
 * @see https://opentelemetry.io/docs/
 */

/**
 * Dimensions for metric tagging.
 *
 * These dimensions allow filtering and grouping metrics by:
 * - User (track costs per user)
 * - Model (compare model performance)
 * - Provider (compare provider performance)
 * - Tier (compare free vs pro users)
 * - Domain (compare domain-specific performance)
 */
export interface MetricDimensions {
  /** User identifier for per-user cost tracking */
  userId?: string;
  /** User tier (e.g., 'free', 'pro', 'enterprise') */
  userTier?: string;
  /** Model name used for generation */
  model?: string;
  /** Provider name (e.g., 'openai', 'anthropic') */
  provider?: string;
  /** Query domain (e.g., 'code', 'medical', 'general') */
  domain?: string;
}

/**
 * Metric values for a single CascadeFlow execution.
 *
 * Contains all the metrics we want to export:
 * - Cost (in USD)
 * - Tokens (input + output)
 * - Latency (in milliseconds)
 * - Dimensions (user, model, provider, etc.)
 */
export interface CascadeflowMetrics {
  /** Cost in USD */
  cost: number;
  /** Number of input/prompt tokens */
  tokensInput: number;
  /** Number of output/completion tokens */
  tokensOutput: number;
  /** Request latency in milliseconds */
  latencyMs: number;
  /** Optional dimensions for metric tagging */
  dimensions?: MetricDimensions;
}

/**
 * Configuration options for OpenTelemetry exporter.
 */
export interface OpenTelemetryExporterConfig {
  /**
   * OTLP HTTP endpoint (e.g., 'http://localhost:4318')
   * If not provided, reads from OTEL_EXPORTER_OTLP_ENDPOINT env var
   */
  endpoint?: string;
  /** Service name for metrics (default: 'cascadeflow') */
  serviceName?: string;
  /** Environment name (e.g., 'prod', 'staging') */
  environment?: string;
  /** Enable/disable metric export (default: true) */
  enabled?: boolean;
  /** Export interval in milliseconds (default: 60000 = 60 seconds) */
  exportIntervalMs?: number;
}

/**
 * Convert dimensions to OpenTelemetry attributes format.
 */
function dimensionsToAttributes(dimensions: MetricDimensions): Record<string, string> {
  const attrs: Record<string, string> = {};

  if (dimensions.userId) {
    attrs['user.id'] = dimensions.userId;
  }
  if (dimensions.userTier) {
    attrs['user.tier'] = dimensions.userTier;
  }
  if (dimensions.model) {
    attrs['model.name'] = dimensions.model;
  }
  if (dimensions.provider) {
    attrs['provider.name'] = dimensions.provider;
  }
  if (dimensions.domain) {
    attrs['query.domain'] = dimensions.domain;
  }

  return attrs;
}

/**
 * OpenTelemetry-based metrics exporter.
 *
 * Exports CascadeFlow metrics to any OpenTelemetry-compatible backend:
 * - Grafana Cloud
 * - Datadog
 * - AWS CloudWatch
 * - Prometheus
 * - Honeycomb
 * - New Relic
 * - And more...
 *
 * Metrics Exported:
 * 1. cascadeflow.cost.total - Total cost in USD (Counter)
 * 2. cascadeflow.tokens.input - Input tokens (Counter)
 * 3. cascadeflow.tokens.output - Output tokens (Counter)
 * 4. cascadeflow.latency - Request latency in ms (Histogram)
 *
 * All metrics include dimensions:
 * - user.id (if provided)
 * - user.tier (if provided)
 * - model.name
 * - provider.name
 * - query.domain (if provided)
 *
 * @example
 * ```typescript
 * const exporter = new OpenTelemetryExporter({
 *   endpoint: 'http://localhost:4318',
 *   serviceName: 'my-app'
 * });
 *
 * // Record a metric
 * exporter.record({
 *   cost: 0.001,
 *   tokensInput: 100,
 *   tokensOutput: 200,
 *   latencyMs: 1500,
 *   dimensions: {
 *     userId: 'user123',
 *     userTier: 'pro',
 *     model: 'gpt-4o-mini',
 *     provider: 'openai'
 *   }
 * });
 * ```
 */
export class OpenTelemetryExporter {
  private enabled: boolean;
  private serviceName: string;
  private environment: string;
  private endpoint?: string;
  private exportIntervalMs: number;

  // OpenTelemetry SDK instances (lazy initialized)
  private meter: any = null;
  private metrics: Record<string, any> = {};
  private initialized: boolean = false;

  constructor(config: OpenTelemetryExporterConfig = {}) {
    this.serviceName = config.serviceName ?? 'cascadeflow';
    this.environment = config.environment ?? process.env.ENVIRONMENT ?? 'development';
    this.exportIntervalMs = config.exportIntervalMs ?? 60000;

    // Get endpoint from config or environment
    this.endpoint = config.endpoint ?? process.env.OTEL_EXPORTER_OTLP_ENDPOINT;

    // Default to enabled, but disable if no endpoint
    this.enabled = config.enabled ?? true;

    if (!this.endpoint && this.enabled) {
      console.warn(
        'OpenTelemetry endpoint not configured. ' +
          'Set OTEL_EXPORTER_OTLP_ENDPOINT or pass endpoint parameter. ' +
          'Metrics will not be exported.'
      );
      this.enabled = false;
    }

    // Initialize OpenTelemetry if enabled
    if (this.enabled) {
      this.initializeOtel();
    }
  }

  /**
   * Dynamic import helper that avoids TypeScript type checking for optional dependencies.
   * This allows the OTEL integration to be optional - if packages aren't installed,
   * metrics are silently disabled rather than causing runtime errors.
   */
  private async dynamicImport(moduleName: string): Promise<any> {
    // Use Function constructor to create dynamic import that TypeScript won't type-check
    // This is necessary because @opentelemetry packages are optional peer dependencies
    const importFn = new Function('moduleName', 'return import(moduleName)');
    return importFn(moduleName);
  }

  /**
   * Initialize OpenTelemetry SDK (lazy).
   *
   * This method tries to import and initialize OpenTelemetry.
   * If @opentelemetry packages are not installed, metrics export is disabled.
   */
  private async initializeOtel(): Promise<void> {
    if (this.initialized) return;

    try {
      // Dynamic imports for optional OpenTelemetry dependencies
      // Using require() with dynamic string to avoid TypeScript type checking
      // These packages are optional - if not installed, metrics are disabled
      const otelApi = await this.dynamicImport('@opentelemetry/api');
      const otelSdkMetrics = await this.dynamicImport('@opentelemetry/sdk-metrics');
      const otelExporter = await this.dynamicImport('@opentelemetry/exporter-metrics-otlp-http');
      const otelResources = await this.dynamicImport('@opentelemetry/resources');
      const otelSemconv = await this.dynamicImport('@opentelemetry/semantic-conventions');

      const { metrics } = otelApi;
      const { MeterProvider, PeriodicExportingMetricReader } = otelSdkMetrics;
      const { OTLPMetricExporter } = otelExporter;
      const { Resource } = otelResources;
      const { ATTR_SERVICE_NAME, ATTR_DEPLOYMENT_ENVIRONMENT } = otelSemconv;

      // Create resource with service name and environment
      const resource = new Resource({
        [ATTR_SERVICE_NAME]: this.serviceName,
        [ATTR_DEPLOYMENT_ENVIRONMENT]: this.environment,
      });

      // Create OTLP exporter
      const otlpExporter = new OTLPMetricExporter({
        url: `${this.endpoint}/v1/metrics`,
        timeoutMillis: 10000,
      });

      // Create metric reader (exports periodically)
      const reader = new PeriodicExportingMetricReader({
        exporter: otlpExporter,
        exportIntervalMillis: this.exportIntervalMs,
      });

      // Create meter provider
      const provider = new MeterProvider({
        resource,
        readers: [reader],
      });

      // Set global meter provider
      metrics.setGlobalMeterProvider(provider);

      // Get meter for this library
      this.meter = metrics.getMeter('cascadeflow', '1.0.0');

      // Create metrics
      this.metrics = {
        cost: this.meter.createCounter('cascadeflow.cost.total', {
          description: 'Total cost in USD',
          unit: 'USD',
        }),
        tokensInput: this.meter.createCounter('cascadeflow.tokens.input', {
          description: 'Input tokens consumed',
          unit: 'tokens',
        }),
        tokensOutput: this.meter.createCounter('cascadeflow.tokens.output', {
          description: 'Output tokens generated',
          unit: 'tokens',
        }),
        latency: this.meter.createHistogram('cascadeflow.latency', {
          description: 'Request latency in milliseconds',
          unit: 'ms',
        }),
      };

      this.initialized = true;
      console.info(
        `OpenTelemetry exporter initialized: ${this.endpoint} ` +
          `(service=${this.serviceName}, env=${this.environment})`
      );
    } catch (error: any) {
      if (error.code === 'MODULE_NOT_FOUND' || error.code === 'ERR_MODULE_NOT_FOUND') {
        console.warn(
          'OpenTelemetry packages not installed. ' +
            'Metrics will not be exported. ' +
            'Install with: npm install @opentelemetry/api @opentelemetry/sdk-metrics ' +
            '@opentelemetry/exporter-metrics-otlp-http @opentelemetry/resources ' +
            '@opentelemetry/semantic-conventions'
        );
      } else {
        console.error('Failed to initialize OpenTelemetry:', error);
      }
      this.enabled = false;
    }
  }

  /**
   * Record metrics to OpenTelemetry.
   *
   * This method exports metrics to the configured OTLP endpoint.
   * Metrics are batched and exported according to exportIntervalMs.
   *
   * @param metrics - CascadeflowMetrics to export
   */
  record(metrics: CascadeflowMetrics): void {
    if (!this.enabled || !this.meter) {
      return;
    }

    try {
      // Get attributes from dimensions
      const attributes = metrics.dimensions
        ? dimensionsToAttributes(metrics.dimensions)
        : {};

      // Record metrics
      this.metrics.cost?.add(metrics.cost, attributes);
      this.metrics.tokensInput?.add(metrics.tokensInput, attributes);
      this.metrics.tokensOutput?.add(metrics.tokensOutput, attributes);
      this.metrics.latency?.record(metrics.latencyMs, attributes);
    } catch (error) {
      console.error('Failed to record metrics:', error);
    }
  }

  /**
   * Force flush metrics to backend.
   *
   * Normally metrics are exported according to exportIntervalMs.
   * Call this method to force immediate export (useful for testing).
   */
  async flush(): Promise<void> {
    if (!this.enabled || !this.meter) {
      return;
    }

    try {
      const otelApi = await this.dynamicImport('@opentelemetry/api');
      const provider = otelApi.metrics.getMeterProvider();
      if (provider && typeof (provider as any).forceFlush === 'function') {
        await (provider as any).forceFlush();
      }
    } catch (error) {
      console.error('Failed to flush metrics:', error);
    }
  }

  /**
   * Shutdown OpenTelemetry exporter.
   *
   * Call this when your application is shutting down to ensure
   * all metrics are exported before exit.
   */
  async shutdown(): Promise<void> {
    if (!this.enabled || !this.meter) {
      return;
    }

    try {
      const otelApi = await this.dynamicImport('@opentelemetry/api');
      const provider = otelApi.metrics.getMeterProvider();
      if (provider && typeof (provider as any).shutdown === 'function') {
        await (provider as any).shutdown();
        console.info('OpenTelemetry exporter shutdown complete');
      }
    } catch (error) {
      console.error('Failed to shutdown OpenTelemetry:', error);
    }
  }

  /**
   * Check if the exporter is enabled and initialized.
   */
  isEnabled(): boolean {
    return this.enabled && this.initialized;
  }

  /**
   * Get the configured endpoint.
   */
  getEndpoint(): string | undefined {
    return this.endpoint;
  }

  /**
   * Get the service name.
   */
  getServiceName(): string {
    return this.serviceName;
  }
}

/**
 * Create OpenTelemetry exporter from environment variables.
 *
 * Reads configuration from:
 * - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP HTTP endpoint (required)
 * - OTEL_SERVICE_NAME: Service name (default: 'cascadeflow')
 * - ENVIRONMENT: Environment name (default: 'development')
 * - OTEL_ENABLED: Enable/disable export (default: 'true')
 *
 * @returns OpenTelemetryExporter if configured, null otherwise
 *
 * @example
 * ```typescript
 * // Set environment variables
 * process.env.OTEL_EXPORTER_OTLP_ENDPOINT = 'http://localhost:4318';
 * process.env.OTEL_SERVICE_NAME = 'my-app';
 *
 * // Create exporter
 * const exporter = createExporterFromEnv();
 * ```
 */
export function createExporterFromEnv(): OpenTelemetryExporter | null {
  const endpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT;

  if (!endpoint) {
    return null;
  }

  const serviceName = process.env.OTEL_SERVICE_NAME ?? 'cascadeflow';
  const environment = process.env.ENVIRONMENT ?? 'development';
  const enabled = ['true', '1', 'yes'].includes(
    (process.env.OTEL_ENABLED ?? 'true').toLowerCase()
  );

  return new OpenTelemetryExporter({
    endpoint,
    serviceName,
    environment,
    enabled,
  });
}
