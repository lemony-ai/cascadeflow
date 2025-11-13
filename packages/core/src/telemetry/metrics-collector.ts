/**
 * Metrics Collector - Extract stats logic from agent
 *
 * This module handles all statistics and metrics collection for cascadeflow,
 * tracking query-level metrics, routing decisions, quality system performance,
 * component timing, tool calling, and more.
 *
 * Features:
 * - Query-level metrics (cost, latency, complexity)
 * - Routing metrics (cascade vs direct)
 * - Quality system metrics (scores, acceptance rates)
 * - Component-level timing breakdown
 * - Tool calling metrics
 * - Aggregated statistics and percentiles
 * - Anomaly detection
 * - Time-windowed metrics
 * - Export capabilities (dict, JSON)
 */

import type { CascadeResult } from '../result';

/**
 * Point-in-time snapshot of metrics
 *
 * Used for monitoring, dashboards, and reporting
 */
export interface MetricsSnapshot {
  /** Total number of queries */
  totalQueries: number;

  /** Total cost across all queries */
  totalCost: number;

  /** Average latency in milliseconds */
  avgLatencyMs: number;

  /** Query counts by complexity level */
  byComplexity: Record<string, number>;

  /** Query counts by routing strategy */
  byStrategy: Record<string, number>;

  /** Draft acceptance rate (0-100) */
  acceptanceRate: number;

  /** Average speedup from cascading */
  avgSpeedup: number;

  /** Quality statistics */
  qualityMean?: number;
  qualityMedian?: number;
  qualityMin?: number;
  qualityMax?: number;

  /** Timing statistics */
  avgDraftMs?: number;
  avgVerificationMs?: number;
  p95DraftMs?: number;
  p95VerificationMs?: number;

  /** Tool metrics */
  toolQueries: number;
  totalToolCalls: number;
  avgToolsPerQuery: number;

  /** Timestamp of snapshot */
  timestamp: string;
}

/**
 * Individual result record for rolling metrics
 */
interface ResultRecord {
  cost: number;
  latencyMs: number;
  complexity: string;
  cascaded: boolean;
  accepted?: boolean;
  speedup: number;
  streaming: boolean;
  hasTools: boolean;
  toolCallsCount: number;
  timestamp: string;
  query: string;
  modelUsed: string;
}

/**
 * Component timing data
 */
interface TimingData {
  complexityDetection: number[];
  draftGeneration: number[];
  qualityVerification: number[];
  verifierGeneration: number[];
  cascadeOverhead: number[];
}

/**
 * Metrics Collector
 *
 * Collects and aggregates metrics for cascadeflow agent
 *
 * @example
 * ```typescript
 * import { MetricsCollector } from '@cascadeflow/core';
 *
 * const collector = new MetricsCollector({ maxRecentResults: 100 });
 *
 * // Record a query result
 * collector.record(result, 'cascade', 'moderate', { draftGeneration: 120 });
 *
 * // Get summary
 * const summary = collector.getSummary();
 * console.log(`Total queries: ${summary.totalQueries}`);
 * console.log(`Avg cost: $${summary.avgCost}`);
 *
 * // Print formatted summary
 * collector.printSummary();
 * ```
 */
export class MetricsCollector {
  private maxRecentResults: number;
  private verbose: boolean;
  private startTime: number;

  private stats: {
    totalQueries: number;
    totalCost: number;
    totalLatencyMs: number;
    byComplexity: Map<string, number>;
    directRouted: number;
    cascadeUsed: number;
    draftAccepted: number;
    draftRejected: number;
    streamingUsed: number;
    toolQueries: number;
    totalToolCalls: number;
  };

  private qualityScores: number[];
  private acceptanceByComplexity: Map<string, { accepted: number; rejected: number }>;
  private timingByComponent: TimingData;
  private recentResults: ResultRecord[];

  /**
   * Initialize metrics collector
   *
   * @param options - Configuration options
   * @param options.maxRecentResults - Max results to keep for rolling stats (default: 100)
   * @param options.verbose - Enable verbose logging (default: false)
   */
  constructor(options: { maxRecentResults?: number; verbose?: boolean } = {}) {
    this.maxRecentResults = options.maxRecentResults ?? 100;
    this.verbose = options.verbose ?? false;
    this.startTime = Date.now();

    // Initialize stats
    this.stats = {
      totalQueries: 0,
      totalCost: 0,
      totalLatencyMs: 0,
      byComplexity: new Map(),
      directRouted: 0,
      cascadeUsed: 0,
      draftAccepted: 0,
      draftRejected: 0,
      streamingUsed: 0,
      toolQueries: 0,
      totalToolCalls: 0,
    };

    this.qualityScores = [];
    this.acceptanceByComplexity = new Map();

    this.timingByComponent = {
      complexityDetection: [],
      draftGeneration: [],
      qualityVerification: [],
      verifierGeneration: [],
      cascadeOverhead: [],
    };

    this.recentResults = [];

    if (this.verbose) {
      console.log(
        `[MetricsCollector] Initialized: max_recent=${this.maxRecentResults}, verbose=${this.verbose}`
      );
    }
  }

  /**
   * Get current uptime in seconds
   */
  get uptimeSeconds(): number {
    return (Date.now() - this.startTime) / 1000;
  }

  /**
   * Record metrics from a query result
   *
   * @param result - CascadeResult or similar result object
   * @param routingStrategy - 'cascade' or 'direct'
   * @param complexity - Complexity level string
   * @param timingBreakdown - Dict of component timings (ms)
   * @param streaming - Whether streaming was used
   * @param hasTools - Whether tools were used
   */
  record(
    result: CascadeResult | null,
    routingStrategy: 'cascade' | 'direct',
    complexity: string,
    timingBreakdown?: Record<string, number>,
    streaming: boolean = false,
    hasTools: boolean = false
  ): void {
    // Update core stats
    this.stats.totalQueries++;

    if (streaming) {
      this.stats.streamingUsed++;
    }

    // Initialize complexity counter if needed
    if (!this.stats.byComplexity.has(complexity)) {
      this.stats.byComplexity.set(complexity, 0);
    }
    this.stats.byComplexity.set(complexity, this.stats.byComplexity.get(complexity)! + 1);

    // Track cost and latency
    if (result) {
      this.stats.totalCost += result.totalCost;
      this.stats.totalLatencyMs += result.latencyMs;
    }

    // Track routing strategy
    const useCascade = routingStrategy === 'cascade';

    if (useCascade) {
      this.stats.cascadeUsed++;

      // Track acceptance
      if (result && result.draftAccepted) {
        this.stats.draftAccepted++;

        // Initialize acceptance tracker if needed
        if (!this.acceptanceByComplexity.has(complexity)) {
          this.acceptanceByComplexity.set(complexity, { accepted: 0, rejected: 0 });
        }
        this.acceptanceByComplexity.get(complexity)!.accepted++;
      } else {
        this.stats.draftRejected++;

        // Initialize acceptance tracker if needed
        if (!this.acceptanceByComplexity.has(complexity)) {
          this.acceptanceByComplexity.set(complexity, { accepted: 0, rejected: 0 });
        }
        this.acceptanceByComplexity.get(complexity)!.rejected++;
      }

      // Track quality score
      if (result && result.metadata && result.metadata.qualityScore !== undefined) {
        this.qualityScores.push(result.metadata.qualityScore);
      }
    } else {
      this.stats.directRouted++;
    }

    // Track tool usage
    let toolCallsCount = 0;
    if (hasTools) {
      this.stats.toolQueries++;

      // Count actual tool calls if available
      if (result) {
        const toolCalls = result.toolCalls || result.metadata?.toolCalls;

        if (toolCalls && Array.isArray(toolCalls)) {
          toolCallsCount = toolCalls.length;
          this.stats.totalToolCalls += toolCallsCount;
        }
      }
    }

    // Track component timing
    if (timingBreakdown) {
      for (const [component, timingMs] of Object.entries(timingBreakdown)) {
        if (component in this.timingByComponent && timingMs > 0) {
          const key = component as keyof TimingData;
          this.timingByComponent[key].push(timingMs);
        }
      }
    }

    // Keep recent results for rolling metrics
    if (result) {
      try {
        const record: ResultRecord = {
          cost: result.totalCost,
          latencyMs: result.latencyMs,
          complexity,
          cascaded: useCascade,
          accepted: useCascade ? result.draftAccepted : undefined,
          speedup: result.speedup || 1.0,
          streaming,
          hasTools,
          toolCallsCount,
          timestamp: new Date().toISOString(),
          query: result.content.substring(0, 100), // Truncate for memory
          modelUsed: result.modelUsed,
        };

        this.recentResults.push(record);

        // Maintain max size
        if (this.recentResults.length > this.maxRecentResults) {
          this.recentResults.shift();
        }
      } catch (error) {
        console.warn('[MetricsCollector] Failed to append to recent_results:', error);
      }
    }

    if (this.verbose) {
      const status = streaming ? '✓ STREAMED' : '✓ COMPLETE';
      const toolInfo = hasTools && toolCallsCount > 0 ? `, ${toolCallsCount} tools` : '';
      const cost = result ? result.totalCost : 0;
      const latency = result ? result.latencyMs : 0;

      console.log(
        `${status}: complexity=${complexity}, strategy=${routingStrategy}, ` +
          `cost=$${cost.toFixed(6)}, latency=${latency.toFixed(0)}ms${toolInfo}`
      );
    }
  }

  /**
   * Get comprehensive summary of all metrics
   *
   * @returns Dictionary with aggregated metrics
   */
  getSummary(): Record<string, any> {
    if (this.stats.totalQueries === 0) {
      return {
        // Basic stats
        totalQueries: 0,
        totalCost: 0.0,
        avgCost: 0.0,
        avgLatencyMs: 0.0,
        uptimeSeconds: Math.round(this.uptimeSeconds * 10) / 10,
        // Routing stats
        cascadeRate: 0.0,
        acceptanceRate: 0.0,
        streamingRate: 0.0,
        cascadeUsed: 0,
        directRouted: 0,
        draftAccepted: 0,
        draftRejected: 0,
        streamingUsed: 0,
        // Tool stats
        toolQueries: 0,
        toolRate: 0.0,
        totalToolCalls: 0,
        avgToolsPerQuery: 0.0,
        // Distribution
        byComplexity: {},
        acceptanceByComplexity: {},
        // Quality and timing
        qualityStats: {},
        timingStats: {},
        // Message
        message: 'No queries executed yet',
      };
    }

    const total = this.stats.totalQueries;
    const cascadeTotal = this.stats.cascadeUsed;

    // Calculate rates
    const cascadeRate = (cascadeTotal / total) * 100;
    const acceptanceRate = cascadeTotal > 0 ? (this.stats.draftAccepted / cascadeTotal) * 100 : 0;
    const streamingRate = (this.stats.streamingUsed / total) * 100;

    // Calculate tool rates
    const toolQueries = this.stats.toolQueries;
    const toolRate = total > 0 ? (toolQueries / total) * 100 : 0;
    const avgToolsPerQuery = toolQueries > 0 ? this.stats.totalToolCalls / toolQueries : 0;

    // Calculate averages
    const avgCost = this.stats.totalCost / total;
    const avgLatency = this.stats.totalLatencyMs / total;

    // Quality statistics
    const qualityStats: Record<string, number> = {};
    if (this.qualityScores.length > 0) {
      qualityStats.mean = this.mean(this.qualityScores);
      qualityStats.median = this.median(this.qualityScores);
      qualityStats.min = Math.min(...this.qualityScores);
      qualityStats.max = Math.max(...this.qualityScores);
      if (this.qualityScores.length > 1) {
        qualityStats.stdev = this.stdev(this.qualityScores);
      }
    }

    // Timing statistics
    const timingStats: Record<string, number> = {};
    for (const [component, timings] of Object.entries(this.timingByComponent)) {
      if (timings.length > 0) {
        const componentKey = component
          .replace(/([A-Z])/g, '_$1')
          .toLowerCase()
          .replace(/^_/, '');
        timingStats[`avg_${componentKey}_ms`] = this.mean(timings);
        timingStats[`p50_${componentKey}_ms`] = this.median(timings);
        timingStats[`p95_${componentKey}_ms`] = this.percentile(timings, 0.95);
        timingStats[`p99_${componentKey}_ms`] = this.percentile(timings, 0.99);
      }
    }

    // Convert maps to objects
    const byComplexity: Record<string, number> = {};
    for (const [key, value] of this.stats.byComplexity.entries()) {
      byComplexity[key] = value;
    }

    const acceptanceByComplexity: Record<string, { accepted: number; rejected: number }> = {};
    for (const [key, value] of this.acceptanceByComplexity.entries()) {
      acceptanceByComplexity[key] = value;
    }

    return {
      // Basic stats
      totalQueries: total,
      totalCost: Math.round(this.stats.totalCost * 1000000) / 1000000,
      avgCost: Math.round(avgCost * 1000000) / 1000000,
      avgLatencyMs: Math.round(avgLatency * 100) / 100,
      uptimeSeconds: Math.round(this.uptimeSeconds * 10) / 10,
      // Routing stats
      cascadeRate: Math.round(cascadeRate * 10) / 10,
      acceptanceRate: Math.round(acceptanceRate * 10) / 10,
      streamingRate: Math.round(streamingRate * 10) / 10,
      cascadeUsed: this.stats.cascadeUsed,
      directRouted: this.stats.directRouted,
      draftAccepted: this.stats.draftAccepted,
      draftRejected: this.stats.draftRejected,
      streamingUsed: this.stats.streamingUsed,
      // Tool stats
      toolQueries,
      toolRate: Math.round(toolRate * 10) / 10,
      totalToolCalls: this.stats.totalToolCalls,
      avgToolsPerQuery: Math.round(avgToolsPerQuery * 100) / 100,
      // Distribution
      byComplexity,
      acceptanceByComplexity,
      // Quality and timing
      qualityStats,
      timingStats,
    };
  }

  /**
   * Get point-in-time metrics snapshot
   *
   * @returns MetricsSnapshot with current metrics
   */
  getSnapshot(): MetricsSnapshot {
    const total = this.stats.totalQueries;
    const cascadeTotal = this.stats.cascadeUsed;

    if (total === 0) {
      return {
        totalQueries: 0,
        totalCost: 0.0,
        avgLatencyMs: 0.0,
        byComplexity: {},
        byStrategy: {},
        acceptanceRate: 0.0,
        avgSpeedup: 1.0,
        toolQueries: 0,
        totalToolCalls: 0,
        avgToolsPerQuery: 0.0,
        timestamp: new Date().toISOString(),
      };
    }

    // Calculate acceptance rate
    const acceptanceRate = cascadeTotal > 0 ? (this.stats.draftAccepted / cascadeTotal) * 100 : 0;

    // Calculate average speedup
    const avgSpeedup = this.calculateAvgSpeedup();

    // Tool metrics
    const toolQueries = this.stats.toolQueries;
    const totalToolCalls = this.stats.totalToolCalls;
    const avgToolsPerQuery = toolQueries > 0 ? totalToolCalls / toolQueries : 0.0;

    // Quality stats
    const qualityStats: {
      qualityMean?: number;
      qualityMedian?: number;
      qualityMin?: number;
      qualityMax?: number;
    } = {};

    if (this.qualityScores.length > 0) {
      qualityStats.qualityMean = Math.round(this.mean(this.qualityScores) * 1000) / 1000;
      qualityStats.qualityMedian = Math.round(this.median(this.qualityScores) * 1000) / 1000;
      qualityStats.qualityMin = Math.round(Math.min(...this.qualityScores) * 1000) / 1000;
      qualityStats.qualityMax = Math.round(Math.max(...this.qualityScores) * 1000) / 1000;
    }

    // Timing stats
    const timingStats: {
      avgDraftMs?: number;
      avgVerificationMs?: number;
      p95DraftMs?: number;
      p95VerificationMs?: number;
    } = {};

    if (this.timingByComponent.draftGeneration.length > 0) {
      timingStats.avgDraftMs =
        Math.round(this.mean(this.timingByComponent.draftGeneration) * 10) / 10;
      timingStats.p95DraftMs =
        Math.round(this.percentile(this.timingByComponent.draftGeneration, 0.95) * 10) / 10;
    }

    if (this.timingByComponent.qualityVerification.length > 0) {
      timingStats.avgVerificationMs =
        Math.round(this.mean(this.timingByComponent.qualityVerification) * 10) / 10;
      timingStats.p95VerificationMs =
        Math.round(this.percentile(this.timingByComponent.qualityVerification, 0.95) * 10) / 10;
    }

    // Convert maps to objects
    const byComplexity: Record<string, number> = {};
    for (const [key, value] of this.stats.byComplexity.entries()) {
      byComplexity[key] = value;
    }

    return {
      totalQueries: total,
      totalCost: Math.round(this.stats.totalCost * 1000000) / 1000000,
      avgLatencyMs: Math.round((this.stats.totalLatencyMs / total) * 100) / 100,
      byComplexity,
      byStrategy: {
        direct: this.stats.directRouted,
        cascade: this.stats.cascadeUsed,
      },
      acceptanceRate: Math.round(acceptanceRate * 10) / 10,
      avgSpeedup: Math.round(avgSpeedup * 100) / 100,
      toolQueries,
      totalToolCalls,
      avgToolsPerQuery: Math.round(avgToolsPerQuery * 100) / 100,
      timestamp: new Date().toISOString(),
      ...qualityStats,
      ...timingStats,
    };
  }

  /**
   * Reset all metrics to initial state
   */
  reset(): void {
    this.stats.totalQueries = 0;
    this.stats.totalCost = 0.0;
    this.stats.totalLatencyMs = 0.0;
    this.stats.byComplexity.clear();
    this.stats.directRouted = 0;
    this.stats.cascadeUsed = 0;
    this.stats.draftAccepted = 0;
    this.stats.draftRejected = 0;
    this.stats.streamingUsed = 0;
    this.stats.toolQueries = 0;
    this.stats.totalToolCalls = 0;

    this.qualityScores = [];
    this.acceptanceByComplexity.clear();

    for (const key of Object.keys(this.timingByComponent) as (keyof TimingData)[]) {
      this.timingByComponent[key] = [];
    }

    this.recentResults = [];
    this.startTime = Date.now();

    if (this.verbose) {
      console.log('[MetricsCollector] All metrics reset');
    }
  }

  /**
   * Print formatted metrics summary to console
   */
  printSummary(): void {
    const summary = this.getSummary();

    if (summary.totalQueries === 0) {
      console.log('\n' + '='.repeat(80));
      console.log('TELEMETRY METRICS SUMMARY');
      console.log('='.repeat(80));
      console.log('No metrics available - No queries executed yet');
      console.log('='.repeat(80) + '\n');
      return;
    }

    console.log('\n' + '='.repeat(80));
    console.log('TELEMETRY METRICS SUMMARY (Tool Support)');
    console.log('='.repeat(80));
    console.log(`Total Queries:        ${summary.totalQueries}`);
    console.log(`Total Cost:           $${summary.totalCost.toFixed(6)}`);
    console.log(`Avg Cost/Query:       $${summary.avgCost.toFixed(6)}`);
    console.log(`Avg Latency:          ${summary.avgLatencyMs.toFixed(1)}ms`);
    console.log(`Uptime:               ${summary.uptimeSeconds.toFixed(1)}s`);
    console.log();
    console.log('ROUTING:');
    console.log(
      `  Cascade Used:       ${summary.cascadeUsed} (${summary.cascadeRate.toFixed(1)}%)`
    );
    console.log(`  Direct Routed:      ${summary.directRouted}`);
    console.log(
      `  Streaming Used:     ${summary.streamingUsed} (${summary.streamingRate.toFixed(1)}%)`
    );
    console.log();
    console.log('CASCADE PERFORMANCE:');
    console.log(`  Draft Accepted:     ${summary.draftAccepted}`);
    console.log(`  Draft Rejected:     ${summary.draftRejected}`);
    console.log(`  Acceptance Rate:    ${summary.acceptanceRate.toFixed(1)}%`);

    // Tool stats
    if (summary.toolQueries > 0) {
      console.log();
      console.log('TOOL CALLING:');
      console.log(
        `  Queries with Tools: ${summary.toolQueries} (${summary.toolRate.toFixed(1)}%)`
      );
      console.log(`  Total Tool Calls:   ${summary.totalToolCalls}`);
      console.log(`  Avg Tools/Query:    ${summary.avgToolsPerQuery.toFixed(2)}`);
    }

    // Quality stats
    if (Object.keys(summary.qualityStats).length > 0) {
      const qs = summary.qualityStats;
      console.log();
      console.log('QUALITY SYSTEM:');
      console.log(`  Mean Score:         ${qs.mean.toFixed(3)}`);
      console.log(`  Median Score:       ${qs.median.toFixed(3)}`);
      console.log(`  Range:              ${qs.min.toFixed(3)} - ${qs.max.toFixed(3)}`);
      if (qs.stdev !== undefined) {
        console.log(`  Std Dev:            ${qs.stdev.toFixed(3)}`);
      }
    }

    // Timing stats
    if (Object.keys(summary.timingStats).length > 0) {
      console.log();
      console.log('TIMING BREAKDOWN (ms):');

      const components = new Set<string>();
      for (const key of Object.keys(summary.timingStats)) {
        if (key.startsWith('avg_')) {
          const component = key.replace('avg_', '').replace('_ms', '');
          components.add(component);
        }
      }

      for (const component of Array.from(components).sort()) {
        const avgKey = `avg_${component}_ms`;
        const p95Key = `p95_${component}_ms`;
        const p99Key = `p99_${component}_ms`;

        const avgVal = summary.timingStats[avgKey] || 0;
        const p95Val = summary.timingStats[p95Key] || 0;
        const p99Val = summary.timingStats[p99Key] || 0;

        console.log(
          `  ${component.padEnd(25)}: avg=${avgVal.toFixed(1).padStart(6)}  ` +
            `p95=${p95Val.toFixed(1).padStart(6)}  p99=${p99Val.toFixed(1).padStart(6)}`
        );
      }
    }

    // By complexity
    console.log();
    console.log('BY COMPLEXITY:');
    for (const [complexity, count] of Object.entries(summary.byComplexity)) {
      const numCount = Number(count);
      if (numCount > 0) {
        const pct = (numCount / summary.totalQueries) * 100;
        console.log(`  ${complexity.padEnd(12)}: ${String(numCount).padStart(4)} (${pct.toFixed(1)}%)`);
      }
    }

    // Acceptance by complexity
    if (Object.keys(summary.acceptanceByComplexity).length > 0) {
      console.log();
      console.log('ACCEPTANCE BY COMPLEXITY:');
      for (const [complexity, stats] of Object.entries(summary.acceptanceByComplexity)) {
        const complexityStats = stats as { accepted: number; rejected: number };
        const total = complexityStats.accepted + complexityStats.rejected;
        if (total > 0) {
          const rate = (complexityStats.accepted / total) * 100;
          console.log(
            `  ${complexity.padEnd(12)}: ${complexityStats.accepted}/${total} (${rate.toFixed(1)}%)`
          );
        }
      }
    }

    console.log('='.repeat(80) + '\n');
  }

  // Helper methods for statistics

  private mean(values: number[]): number {
    if (values.length === 0) return 0;
    return values.reduce((a, b) => a + b, 0) / values.length;
  }

  private median(values: number[]): number {
    if (values.length === 0) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
  }

  private stdev(values: number[]): number {
    if (values.length < 2) return 0;
    const avg = this.mean(values);
    const squareDiffs = values.map((value) => Math.pow(value - avg, 2));
    return Math.sqrt(this.mean(squareDiffs));
  }

  private percentile(values: number[], percentile: number): number {
    if (values.length === 0) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const index = Math.min(Math.floor(sorted.length * percentile), sorted.length - 1);
    return sorted[index];
  }

  private calculateAvgSpeedup(): number {
    if (this.recentResults.length === 0) return 1.0;

    const speedups = this.recentResults
      .filter((r) => r.cascaded && r.accepted && r.speedup !== undefined)
      .map((r) => r.speedup);

    if (speedups.length === 0) return 1.0;

    return this.mean(speedups);
  }
}
