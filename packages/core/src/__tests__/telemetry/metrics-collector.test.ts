/**
 * Tests for MetricsCollector
 *
 * Tests metrics collection and aggregation
 *
 * Run: pnpm test metrics-collector.test.ts
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { MetricsCollector } from '../../telemetry/metrics-collector';
import type { CascadeResult } from '../../result';

// Helper to create mock result
function createMockResult(overrides: Partial<CascadeResult> = {}): CascadeResult {
  return {
    content: overrides.content || 'Test response',
    modelUsed: overrides.modelUsed || 'gpt-4o-mini',
    totalCost: overrides.totalCost ?? 0.001,
    latencyMs: overrides.latencyMs ?? 100,
    draftAccepted: overrides.draftAccepted ?? false,
    speedup: overrides.speedup ?? 1.0,
    providerResponses: [],
    metadata: overrides.metadata || {},
    toolCalls: overrides.toolCalls,
    ...overrides,
  } as CascadeResult;
}

describe('MetricsCollector', () => {
  let collector: MetricsCollector;

  beforeEach(() => {
    collector = new MetricsCollector();
  });

  describe('constructor', () => {
    it('should initialize with default settings', () => {
      const coll = new MetricsCollector();
      const summary = coll.getSummary();

      expect(summary.totalQueries).toBe(0);
      expect(summary.totalCost).toBe(0);
      expect(summary.message).toBe('No queries executed yet');
    });

    it('should initialize with custom max recent results', () => {
      const coll = new MetricsCollector({ maxRecentResults: 50 });
      const summary = coll.getSummary();

      expect(summary.totalQueries).toBe(0);
    });

    it('should initialize with verbose mode', () => {
      const coll = new MetricsCollector({ verbose: true });
      const summary = coll.getSummary();

      expect(summary.totalQueries).toBe(0);
    });
  });

  describe('record', () => {
    it('should record a cascade query', () => {
      const result = createMockResult({
        totalCost: 0.002,
        latencyMs: 150,
        draftAccepted: true,
      });

      collector.record(result, 'cascade', 'moderate');

      const summary = collector.getSummary();

      expect(summary.totalQueries).toBe(1);
      expect(summary.totalCost).toBe(0.002);
      expect(summary.cascadeUsed).toBe(1);
      expect(summary.draftAccepted).toBe(1);
    });

    it('should record a direct query', () => {
      const result = createMockResult({
        totalCost: 0.005,
        latencyMs: 200,
      });

      collector.record(result, 'direct', 'hard');

      const summary = collector.getSummary();

      expect(summary.totalQueries).toBe(1);
      expect(summary.directRouted).toBe(1);
      expect(summary.cascadeUsed).toBe(0);
    });

    it('should track streaming usage', () => {
      const result = createMockResult();

      collector.record(result, 'direct', 'simple', undefined, true);

      const summary = collector.getSummary();

      expect(summary.streamingUsed).toBe(1);
      expect(summary.streamingRate).toBeGreaterThan(0);
    });

    it('should track tool usage', () => {
      const result = createMockResult({
        toolCalls: [{
          id: '1',
          type: 'function',
          function: { name: 'test', arguments: '{}' }
        }],
      });

      collector.record(result, 'direct', 'simple', undefined, false, true);

      const summary = collector.getSummary();

      expect(summary.toolQueries).toBe(1);
      expect(summary.totalToolCalls).toBe(1);
    });

    it('should track quality scores', () => {
      const result = createMockResult({
        metadata: { qualityScore: 0.85 },
        draftAccepted: true,
      });

      collector.record(result, 'cascade', 'moderate');

      const summary = collector.getSummary();

      expect(summary.qualityStats.mean).toBe(0.85);
    });

    it('should track component timing', () => {
      const result = createMockResult();
      const timing = {
        draftGeneration: 120,
        qualityVerification: 30,
      };

      collector.record(result, 'cascade', 'moderate', timing);

      const summary = collector.getSummary();

      expect(summary.timingStats.avg_draft_generation_ms).toBe(120);
      expect(summary.timingStats.avg_quality_verification_ms).toBe(30);
    });

    it('should handle null result gracefully', () => {
      collector.record(null, 'direct', 'simple');

      const summary = collector.getSummary();

      expect(summary.totalQueries).toBe(1);
      expect(summary.totalCost).toBe(0);
    });

    it('should track complexity distribution', () => {
      collector.record(createMockResult(), 'direct', 'simple');
      collector.record(createMockResult(), 'direct', 'simple');
      collector.record(createMockResult(), 'direct', 'moderate');

      const summary = collector.getSummary();

      expect(summary.byComplexity.simple).toBe(2);
      expect(summary.byComplexity.moderate).toBe(1);
    });

    it('should track acceptance by complexity', () => {
      const accepted = createMockResult({ draftAccepted: true });
      const rejected = createMockResult({ draftAccepted: false });

      collector.record(accepted, 'cascade', 'simple');
      collector.record(rejected, 'cascade', 'simple');

      const summary = collector.getSummary();

      expect(summary.acceptanceByComplexity.simple.accepted).toBe(1);
      expect(summary.acceptanceByComplexity.simple.rejected).toBe(1);
    });
  });

  describe('getSummary', () => {
    it('should return empty summary when no queries', () => {
      const summary = collector.getSummary();

      expect(summary.totalQueries).toBe(0);
      expect(summary.cascadeRate).toBe(0);
      expect(summary.acceptanceRate).toBe(0);
      expect(summary.message).toBe('No queries executed yet');
    });

    it('should calculate cascade rate correctly', () => {
      collector.record(createMockResult(), 'cascade', 'simple');
      collector.record(createMockResult(), 'cascade', 'simple');
      collector.record(createMockResult(), 'direct', 'simple');

      const summary = collector.getSummary();

      expect(summary.cascadeRate).toBeCloseTo(66.7, 1);
    });

    it('should calculate acceptance rate correctly', () => {
      collector.record(createMockResult({ draftAccepted: true }), 'cascade', 'simple');
      collector.record(createMockResult({ draftAccepted: true }), 'cascade', 'simple');
      collector.record(createMockResult({ draftAccepted: false }), 'cascade', 'simple');

      const summary = collector.getSummary();

      expect(summary.acceptanceRate).toBeCloseTo(66.7, 1);
    });

    it('should calculate average cost', () => {
      collector.record(createMockResult({ totalCost: 0.001 }), 'direct', 'simple');
      collector.record(createMockResult({ totalCost: 0.003 }), 'direct', 'simple');

      const summary = collector.getSummary();

      expect(summary.avgCost).toBe(0.002);
    });

    it('should calculate average latency', () => {
      collector.record(createMockResult({ latencyMs: 100 }), 'direct', 'simple');
      collector.record(createMockResult({ latencyMs: 200 }), 'direct', 'simple');

      const summary = collector.getSummary();

      expect(summary.avgLatencyMs).toBe(150);
    });

    it('should calculate tool metrics', () => {
      const withTools1 = createMockResult({
        toolCalls: [{
          id: '1',
          type: 'function',
          function: { name: 'test1', arguments: '{}' }
        }],
      });
      const withTools2 = createMockResult({
        toolCalls: [
          { id: '2', type: 'function', function: { name: 'test2', arguments: '{}' } },
          { id: '3', type: 'function', function: { name: 'test3', arguments: '{}' } },
        ],
      });

      collector.record(withTools1, 'direct', 'simple', undefined, false, true);
      collector.record(withTools2, 'direct', 'simple', undefined, false, true);

      const summary = collector.getSummary();

      expect(summary.toolQueries).toBe(2);
      expect(summary.totalToolCalls).toBe(3);
      expect(summary.avgToolsPerQuery).toBe(1.5);
    });

    it('should include uptime', () => {
      const summary = collector.getSummary();

      expect(summary.uptimeSeconds).toBeGreaterThanOrEqual(0);
    });

    it('should calculate quality statistics', () => {
      const results = [
        createMockResult({ metadata: { qualityScore: 0.7 }, draftAccepted: true }),
        createMockResult({ metadata: { qualityScore: 0.8 }, draftAccepted: true }),
        createMockResult({ metadata: { qualityScore: 0.9 }, draftAccepted: true }),
      ];

      for (const result of results) {
        collector.record(result, 'cascade', 'simple');
      }

      const summary = collector.getSummary();

      expect(summary.qualityStats.mean).toBeCloseTo(0.8, 2);
      expect(summary.qualityStats.median).toBe(0.8);
      expect(summary.qualityStats.min).toBe(0.7);
      expect(summary.qualityStats.max).toBe(0.9);
    });

    it('should calculate timing percentiles', () => {
      const timings = [
        { draftGeneration: 100 },
        { draftGeneration: 150 },
        { draftGeneration: 200 },
        { draftGeneration: 250 },
        { draftGeneration: 300 },
      ];

      for (const timing of timings) {
        collector.record(createMockResult(), 'cascade', 'simple', timing);
      }

      const summary = collector.getSummary();

      expect(summary.timingStats.avg_draft_generation_ms).toBe(200);
      expect(summary.timingStats.p50_draft_generation_ms).toBe(200);
      expect(summary.timingStats.p95_draft_generation_ms).toBeGreaterThan(250);
    });
  });

  describe('getSnapshot', () => {
    it('should return empty snapshot when no queries', () => {
      const snapshot = collector.getSnapshot();

      expect(snapshot.totalQueries).toBe(0);
      expect(snapshot.acceptanceRate).toBe(0);
      expect(snapshot.avgSpeedup).toBe(1.0);
    });

    it('should include timestamp', () => {
      const snapshot = collector.getSnapshot();

      expect(snapshot.timestamp).toBeDefined();
      expect(new Date(snapshot.timestamp).getTime()).toBeGreaterThan(0);
    });

    it('should include strategy breakdown', () => {
      collector.record(createMockResult(), 'cascade', 'simple');
      collector.record(createMockResult(), 'direct', 'simple');

      const snapshot = collector.getSnapshot();

      expect(snapshot.byStrategy.cascade).toBe(1);
      expect(snapshot.byStrategy.direct).toBe(1);
    });

    it('should include quality metrics', () => {
      collector.record(
        createMockResult({ metadata: { qualityScore: 0.85 }, draftAccepted: true }),
        'cascade',
        'simple'
      );

      const snapshot = collector.getSnapshot();

      expect(snapshot.qualityMean).toBe(0.85);
      expect(snapshot.qualityMedian).toBe(0.85);
    });

    it('should include timing metrics', () => {
      collector.record(createMockResult(), 'cascade', 'simple', {
        draftGeneration: 120,
        qualityVerification: 30,
      });

      const snapshot = collector.getSnapshot();

      expect(snapshot.avgDraftMs).toBe(120);
      expect(snapshot.avgVerificationMs).toBe(30);
    });

    it('should include tool metrics', () => {
      collector.record(
        createMockResult({
          toolCalls: [{
            id: '1',
            type: 'function',
            function: { name: 'test', arguments: '{}' }
          }]
        }),
        'direct',
        'simple',
        undefined,
        false,
        true
      );

      const snapshot = collector.getSnapshot();

      expect(snapshot.toolQueries).toBe(1);
      expect(snapshot.totalToolCalls).toBe(1);
    });
  });

  describe('reset', () => {
    it('should reset all metrics', () => {
      collector.record(createMockResult(), 'cascade', 'simple');
      collector.record(createMockResult(), 'direct', 'moderate');

      collector.reset();

      const summary = collector.getSummary();

      expect(summary.totalQueries).toBe(0);
      expect(summary.totalCost).toBe(0);
      expect(summary.cascadeUsed).toBe(0);
      expect(summary.directRouted).toBe(0);
    });

    it('should reset quality scores', () => {
      collector.record(
        createMockResult({ metadata: { qualityScore: 0.8 }, draftAccepted: true }),
        'cascade',
        'simple'
      );

      collector.reset();

      const summary = collector.getSummary();

      expect(Object.keys(summary.qualityStats)).toHaveLength(0);
    });

    it('should reset timing data', () => {
      collector.record(createMockResult(), 'cascade', 'simple', {
        draftGeneration: 120,
      });

      collector.reset();

      const summary = collector.getSummary();

      expect(Object.keys(summary.timingStats)).toHaveLength(0);
    });

    it('should reset complexity distribution', () => {
      collector.record(createMockResult(), 'direct', 'simple');
      collector.record(createMockResult(), 'direct', 'moderate');

      collector.reset();

      const summary = collector.getSummary();

      expect(Object.keys(summary.byComplexity)).toHaveLength(0);
    });
  });

  describe('printSummary', () => {
    it('should print summary without throwing', () => {
      expect(() => {
        collector.printSummary();
      }).not.toThrow();
    });

    it('should print summary with data without throwing', () => {
      collector.record(createMockResult(), 'cascade', 'simple');

      expect(() => {
        collector.printSummary();
      }).not.toThrow();
    });
  });

  describe('uptimeSeconds', () => {
    it('should return uptime in seconds', () => {
      const uptime = collector.uptimeSeconds;

      expect(uptime).toBeGreaterThanOrEqual(0);
      expect(uptime).toBeLessThan(2); // Should be very small initially
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero cost queries', () => {
      collector.record(createMockResult({ totalCost: 0 }), 'direct', 'simple');

      const summary = collector.getSummary();

      expect(summary.totalCost).toBe(0);
      expect(summary.avgCost).toBe(0);
    });

    it('should handle very large latencies', () => {
      collector.record(createMockResult({ latencyMs: 10000 }), 'direct', 'simple');

      const summary = collector.getSummary();

      expect(summary.avgLatencyMs).toBe(10000);
    });

    it('should handle missing metadata', () => {
      collector.record(createMockResult({ metadata: {} }), 'cascade', 'simple');

      const summary = collector.getSummary();

      expect(Object.keys(summary.qualityStats)).toHaveLength(0);
    });

    it('should handle tool calls in metadata', () => {
      const result = createMockResult({
        metadata: {
          toolCalls: [
            { id: '1', name: 'test1', args: {} },
            { id: '2', name: 'test2', args: {} },
          ],
        },
      });

      collector.record(result, 'direct', 'simple', undefined, false, true);

      const summary = collector.getSummary();

      expect(summary.totalToolCalls).toBe(2);
    });

    it('should handle empty tool calls array', () => {
      collector.record(createMockResult({ toolCalls: [] }), 'direct', 'simple', undefined, false, true);

      const summary = collector.getSummary();

      expect(summary.toolQueries).toBe(1);
      expect(summary.totalToolCalls).toBe(0);
    });
  });

  describe('Integration Tests', () => {
    it('should track mixed query types', () => {
      // Cascade accepted
      collector.record(
        createMockResult({ totalCost: 0.001, draftAccepted: true, speedup: 1.5 }),
        'cascade',
        'simple'
      );

      // Cascade rejected
      collector.record(
        createMockResult({ totalCost: 0.005, draftAccepted: false }),
        'cascade',
        'moderate'
      );

      // Direct
      collector.record(createMockResult({ totalCost: 0.003 }), 'direct', 'hard');

      const summary = collector.getSummary();

      expect(summary.totalQueries).toBe(3);
      expect(summary.cascadeUsed).toBe(2);
      expect(summary.directRouted).toBe(1);
      expect(summary.draftAccepted).toBe(1);
      expect(summary.draftRejected).toBe(1);
      expect(summary.acceptanceRate).toBe(50);
    });

    it('should track comprehensive metrics over multiple queries', () => {
      for (let i = 0; i < 10; i++) {
        const isEven = i % 2 === 0;
        const result = createMockResult({
          totalCost: 0.001 * (i + 1),
          latencyMs: 100 + i * 10,
          draftAccepted: isEven,
          metadata: { qualityScore: 0.7 + i * 0.02 },
        });

        collector.record(result, isEven ? 'cascade' : 'direct', 'simple', {
          draftGeneration: 100 + i * 5,
        });
      }

      const summary = collector.getSummary();

      expect(summary.totalQueries).toBe(10);
      expect(summary.cascadeUsed).toBe(5);
      expect(summary.directRouted).toBe(5);
      expect(summary.avgCost).toBeGreaterThan(0);
      expect(summary.avgLatencyMs).toBeGreaterThan(0);
      expect(summary.qualityStats.mean).toBeDefined();
      expect(summary.timingStats.avg_draft_generation_ms).toBeDefined();
    });
  });
});
