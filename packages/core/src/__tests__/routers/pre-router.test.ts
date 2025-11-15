/**
 * PreRouter Tests
 *
 * Comprehensive test suite for PreRouter class.
 * Tests complexity-based routing, statistics tracking, and configuration.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  PreRouter,
  createPreRouter,
  type PreRouterConfig,
} from '../../routers/pre-router';
import { RoutingStrategy } from '../../routers/base';
import { ComplexityDetector } from '../../complexity';
import type { QueryComplexity } from '../../types';

describe('PreRouter', () => {
  let router: PreRouter;

  beforeEach(() => {
    router = new PreRouter();
  });

  describe('constructor and configuration', () => {
    it('should initialize with default configuration', () => {
      const config = {
        enableCascade: true,
        verbose: false,
      };

      const router = new PreRouter(config);
      expect(router).toBeInstanceOf(PreRouter);
    });

    it('should accept custom complexity detector', () => {
      const customDetector = new ComplexityDetector();
      const router = new PreRouter({
        complexityDetector: customDetector,
      });

      expect(router).toBeInstanceOf(PreRouter);
    });

    it('should accept custom cascade complexities', () => {
      const router = new PreRouter({
        cascadeComplexities: ['trivial', 'simple'],
      });

      expect(router).toBeInstanceOf(PreRouter);
    });

    it('should disable cascade when configured', () => {
      const router = new PreRouter({
        enableCascade: false,
      });

      expect(router).toBeInstanceOf(PreRouter);
    });
  });

  describe('routing decisions', () => {
    it('should route trivial query to cascade', async () => {
      const decision = await router.route('What is 2+2?');

      expect(decision.strategy).toBe(RoutingStrategy.CASCADE);
      expect(decision.metadata.complexity).toBe('trivial');
      expect(decision.metadata.router).toBe('pre');
      expect(decision.confidence).toBeGreaterThan(0);
    });

    it('should route simple query to cascade', async () => {
      const decision = await router.route('Who is the current US president?');

      expect(decision.strategy).toBe(RoutingStrategy.CASCADE);
      expect(['trivial', 'simple', 'moderate']).toContain(decision.metadata.complexity);
    });

    it('should route moderate query to cascade', async () => {
      const decision = await router.route('Explain the water cycle in 3 sentences.');

      expect(decision.strategy).toBe(RoutingStrategy.CASCADE);
      expect(['trivial', 'simple', 'moderate']).toContain(decision.metadata.complexity);
    });

    it('should route hard query to direct best', async () => {
      const decision = await router.route(
        'Analyze the economic implications of quantum computing on global financial markets.'
      );

      expect(decision.strategy).toBe(RoutingStrategy.DIRECT_BEST);
      expect(['hard', 'expert']).toContain(decision.metadata.complexity);
    });

    it('should route expert query to direct best', async () => {
      const decision = await router.route(
        'Derive the Schrödinger equation from first principles and explain its implications for quantum field theory.'
      );

      expect(decision.strategy).toBe(RoutingStrategy.DIRECT_BEST);
      expect(decision.metadata.complexity).toBe('expert');
    });

    it('should include reasoning in decision', async () => {
      const decision = await router.route('What is 2+2?');

      expect(decision.reason).toBeTruthy();
      expect(typeof decision.reason).toBe('string');
      expect(decision.reason.length).toBeGreaterThan(0);
    });

    it('should include confidence in decision', async () => {
      const decision = await router.route('What is TypeScript?');

      expect(decision.confidence).toBeGreaterThanOrEqual(0);
      expect(decision.confidence).toBeLessThanOrEqual(1);
    });
  });

  describe('context overrides', () => {
    it('should accept pre-detected complexity', async () => {
      const decision = await router.route('Any query', {
        complexity: 'expert' as QueryComplexity,
      });

      expect(decision.metadata.complexity).toBe('expert');
      expect(decision.strategy).toBe(RoutingStrategy.DIRECT_BEST);
    });

    it('should accept complexity hint', async () => {
      const decision = await router.route('Any query', {
        complexityHint: 'trivial',
      });

      expect(decision.metadata.complexity).toBe('trivial');
      expect(decision.strategy).toBe(RoutingStrategy.CASCADE);
    });

    it('should fallback to auto-detect on invalid hint', async () => {
      const decision = await router.route('What is 2+2?', {
        complexityHint: 'invalid_complexity',
      });

      // Should auto-detect as trivial
      expect(['trivial', 'simple', 'moderate', 'hard', 'expert']).toContain(
        decision.metadata.complexity
      );
    });

    it('should force direct routing when requested', async () => {
      const decision = await router.route('What is 2+2?', {
        forceDirect: true,
      });

      expect(decision.strategy).toBe(RoutingStrategy.DIRECT_BEST);
      expect(decision.metadata.forceDirect).toBe(true);
      expect(decision.confidence).toBe(1.0);
    });

    it('should accept complexityConfidence override', async () => {
      const decision = await router.route('Any query', {
        complexity: 'simple' as QueryComplexity,
        complexityConfidence: 0.95,
      });

      expect(decision.confidence).toBe(0.95);
    });
  });

  describe('cascade enabled/disabled', () => {
    it('should route to direct when cascade disabled', async () => {
      const router = new PreRouter({ enableCascade: false });

      const decision = await router.route('What is 2+2?');

      expect(decision.strategy).toBe(RoutingStrategy.DIRECT_BEST);
      expect(decision.reason).toContain('disabled');
    });

    it('should still route to direct for complex queries when cascade enabled', async () => {
      const router = new PreRouter({ enableCascade: true });

      const decision = await router.route('Explain quantum mechanics', {
        complexity: 'expert' as QueryComplexity,
      });

      expect(decision.strategy).toBe(RoutingStrategy.DIRECT_BEST);
    });
  });

  describe('custom cascade complexities', () => {
    it('should route only specified complexities to cascade', async () => {
      const router = new PreRouter({
        cascadeComplexities: ['trivial', 'simple'], // Exclude 'moderate'
      });

      const decision1 = await router.route('What is 2+2?', {
        complexity: 'trivial' as QueryComplexity,
      });
      expect(decision1.strategy).toBe(RoutingStrategy.CASCADE);

      const decision2 = await router.route('What is TypeScript?', {
        complexity: 'simple' as QueryComplexity,
      });
      expect(decision2.strategy).toBe(RoutingStrategy.CASCADE);

      const decision3 = await router.route('Explain TypeScript', {
        complexity: 'moderate' as QueryComplexity,
      });
      expect(decision3.strategy).toBe(RoutingStrategy.DIRECT_BEST);
    });

    it('should route all to direct if cascade complexities is empty', async () => {
      const router = new PreRouter({
        cascadeComplexities: [],
      });

      const decision = await router.route('What is 2+2?', {
        complexity: 'trivial' as QueryComplexity,
      });

      expect(decision.strategy).toBe(RoutingStrategy.DIRECT_BEST);
    });
  });

  describe('statistics tracking', () => {
    it('should track total queries', async () => {
      await router.route('Query 1');
      await router.route('Query 2');
      await router.route('Query 3');

      const stats = router.getStats();
      expect(stats.totalQueries).toBe(3);
    });

    it('should track queries by complexity', async () => {
      await router.route('What is 2+2?', {
        complexity: 'trivial' as QueryComplexity,
      });
      await router.route('What is TypeScript?', {
        complexity: 'simple' as QueryComplexity,
      });
      await router.route('What is 2+2 again?', {
        complexity: 'trivial' as QueryComplexity,
      });

      const stats = router.getStats();
      expect(stats.byComplexity['trivial']).toBe(2);
      expect(stats.byComplexity['simple']).toBe(1);
    });

    it('should track queries by strategy', async () => {
      await router.route('Simple query', {
        complexity: 'simple' as QueryComplexity,
      });
      await router.route('Expert query', {
        complexity: 'expert' as QueryComplexity,
      });
      await router.route('Another simple query', {
        complexity: 'simple' as QueryComplexity,
      });

      const stats = router.getStats();
      expect(stats.byStrategy[RoutingStrategy.CASCADE]).toBe(2);
      expect(stats.byStrategy[RoutingStrategy.DIRECT_BEST]).toBe(1);
    });

    it('should calculate cascade rate', async () => {
      await router.route('Query 1', { complexity: 'simple' as QueryComplexity });
      await router.route('Query 2', { complexity: 'simple' as QueryComplexity });
      await router.route('Query 3', { complexity: 'expert' as QueryComplexity });
      await router.route('Query 4', { complexity: 'expert' as QueryComplexity });

      const stats = router.getStats();
      expect(stats.cascadeRate).toBe('50.0%');
      expect(stats.directRate).toBe('50.0%');
    });

    it('should track forced direct count', async () => {
      await router.route('Query 1', { forceDirect: true });
      await router.route('Query 2', { forceDirect: true });
      await router.route('Query 3');

      const stats = router.getStats();
      expect(stats.forcedDirect).toBe(2);
    });

    it('should track cascade disabled count', async () => {
      const router = new PreRouter({ enableCascade: false });

      await router.route('Query 1');
      await router.route('Query 2');

      const stats = router.getStats();
      expect(stats.cascadeDisabledCount).toBe(2);
    });

    it('should return zero stats when no queries', () => {
      const stats = router.getStats();

      expect(stats.totalQueries).toBe(0);
      expect(stats.cascadeRate).toBe('0.0%');
      expect(stats.directRate).toBe('0.0%');
      expect(stats.forcedDirect).toBe(0);
      expect(stats.cascadeDisabledCount).toBe(0);
    });

    it('should reset statistics', async () => {
      await router.route('Query 1');
      await router.route('Query 2');

      router.resetStats();

      const stats = router.getStats();
      expect(stats.totalQueries).toBe(0);
      expect(Object.keys(stats.byComplexity).length).toBe(0);
      expect(Object.keys(stats.byStrategy).length).toBe(0);
    });
  });

  describe('createPreRouter factory', () => {
    it('should create router with factory', () => {
      const router = createPreRouter({ enableCascade: true });

      expect(router).toBeInstanceOf(PreRouter);
    });

    it('should create router with default config', () => {
      const router = createPreRouter();

      expect(router).toBeInstanceOf(PreRouter);
    });
  });

  describe('edge cases', () => {
    it('should handle empty query', async () => {
      const decision = await router.route('');

      expect(decision.strategy).toBeDefined();
      expect(decision.confidence).toBeGreaterThanOrEqual(0);
    });

    it('should handle very long query', async () => {
      const longQuery = 'word '.repeat(1000);
      const decision = await router.route(longQuery);

      expect(decision.strategy).toBeDefined();
    });

    it('should handle query with special characters', async () => {
      const decision = await router.route('What is 2+2? 🤔 (seriously)');

      expect(decision.strategy).toBeDefined();
    });

    it('should handle multiple routing decisions in sequence', async () => {
      const decision1 = await router.route('Query 1');
      const decision2 = await router.route('Query 2');
      const decision3 = await router.route('Query 3');

      expect(decision1).toBeDefined();
      expect(decision2).toBeDefined();
      expect(decision3).toBeDefined();
      expect(router.getStats().totalQueries).toBe(3);
    });
  });

  describe('metadata completeness', () => {
    it('should include all required metadata fields', async () => {
      const decision = await router.route('Test query');

      expect(decision.metadata).toBeDefined();
      expect(decision.metadata.complexity).toBeDefined();
      expect(decision.metadata.complexityConfidence).toBeDefined();
      expect(decision.metadata.router).toBe('pre');
      expect(decision.metadata.routerType).toBe('complexity_based');
      expect(decision.metadata.forceDirect).toBeDefined();
      expect(decision.metadata.cascadeEnabled).toBeDefined();
    });

    it('should preserve cascadeEnabled in metadata', async () => {
      const router1 = new PreRouter({ enableCascade: true });
      const decision1 = await router1.route('Query');
      expect(decision1.metadata.cascadeEnabled).toBe(true);

      const router2 = new PreRouter({ enableCascade: false });
      const decision2 = await router2.route('Query');
      expect(decision2.metadata.cascadeEnabled).toBe(false);
    });
  });
});
