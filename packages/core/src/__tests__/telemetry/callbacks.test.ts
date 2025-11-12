/**
 * Tests for CallbackManager
 *
 * Tests callback system for monitoring and hooks
 *
 * Run: pnpm test callbacks.test.ts
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  CallbackManager,
  CallbackEvent,
  type CallbackData,
} from '../../telemetry/callbacks';

describe('CallbackManager', () => {
  let manager: CallbackManager;

  beforeEach(() => {
    manager = new CallbackManager();
  });

  describe('constructor', () => {
    it('should initialize with default settings', () => {
      const mgr = new CallbackManager();
      const stats = mgr.getStats();

      expect(stats.totalTriggers).toBe(0);
      expect(stats.callbackErrors).toBe(0);
      expect(stats.registeredEvents).toEqual([]);
    });

    it('should initialize with verbose mode', () => {
      const mgr = new CallbackManager(true);
      const stats = mgr.getStats();

      expect(stats.totalTriggers).toBe(0);
    });
  });

  describe('register', () => {
    it('should register callback for an event', async () => {
      const called: CallbackEvent[] = [];

      const callback = (data: CallbackData) => {
        called.push(data.event);
      };

      manager.register(CallbackEvent.QUERY_START, callback);
      await manager.trigger(CallbackEvent.QUERY_START, 'test', {});

      expect(called).toContain(CallbackEvent.QUERY_START);
    });

    it('should register multiple callbacks for same event', async () => {
      const calls: string[] = [];

      const callback1 = () => {
        calls.push('callback1');
      };

      const callback2 = () => {
        calls.push('callback2');
      };

      manager.register(CallbackEvent.QUERY_START, callback1);
      manager.register(CallbackEvent.QUERY_START, callback2);

      await manager.trigger(CallbackEvent.QUERY_START, 'test', {});

      expect(calls).toHaveLength(2);
      expect(calls).toContain('callback1');
      expect(calls).toContain('callback2');
    });

    it('should register callbacks for different events', async () => {
      const called: CallbackEvent[] = [];

      const callback = (data: CallbackData) => {
        called.push(data.event);
      };

      manager.register(CallbackEvent.QUERY_START, callback);
      manager.register(CallbackEvent.QUERY_COMPLETE, callback);

      await manager.trigger(CallbackEvent.QUERY_START, 'test1', {});
      await manager.trigger(CallbackEvent.QUERY_COMPLETE, 'test2', {});

      expect(called).toHaveLength(2);
      expect(called).toContain(CallbackEvent.QUERY_START);
      expect(called).toContain(CallbackEvent.QUERY_COMPLETE);
    });
  });

  describe('unregister', () => {
    it('should unregister callback', async () => {
      const called: boolean[] = [];

      const callback = () => {
        called.push(true);
      };

      manager.register(CallbackEvent.QUERY_START, callback);
      manager.unregister(CallbackEvent.QUERY_START, callback);

      await manager.trigger(CallbackEvent.QUERY_START, 'test', {});

      expect(called).toHaveLength(0);
    });

    it('should only unregister specified callback', async () => {
      const calls: string[] = [];

      const callback1 = () => {
        calls.push('callback1');
      };

      const callback2 = () => {
        calls.push('callback2');
      };

      manager.register(CallbackEvent.QUERY_START, callback1);
      manager.register(CallbackEvent.QUERY_START, callback2);

      manager.unregister(CallbackEvent.QUERY_START, callback1);

      await manager.trigger(CallbackEvent.QUERY_START, 'test', {});

      expect(calls).toHaveLength(1);
      expect(calls).toContain('callback2');
    });

    it('should handle unregistering non-existent callback', () => {
      const callback = () => {};

      // Should not throw
      expect(() => {
        manager.unregister(CallbackEvent.QUERY_START, callback);
      }).not.toThrow();
    });
  });

  describe('trigger', () => {
    it('should pass correct callback data', async () => {
      const capturedData: CallbackData[] = [];

      const callback = (data: CallbackData) => {
        capturedData.push(data);
      };

      manager.register(CallbackEvent.COMPLEXITY_DETECTED, callback);

      await manager.trigger(
        CallbackEvent.COMPLEXITY_DETECTED,
        'test query',
        { complexity: 'moderate' },
        'premium',
        'production'
      );

      expect(capturedData).toHaveLength(1);

      const data = capturedData[0];
      expect(data.event).toBe(CallbackEvent.COMPLEXITY_DETECTED);
      expect(data.query).toBe('test query');
      expect(data.userTier).toBe('premium');
      expect(data.workflow).toBe('production');
      expect(data.data.complexity).toBe('moderate');
      expect(data.timestamp).toBeGreaterThan(0);
    });

    it('should handle callbacks without user tier and workflow', async () => {
      const capturedData: CallbackData[] = [];

      const callback = (data: CallbackData) => {
        capturedData.push(data);
      };

      manager.register(CallbackEvent.QUERY_START, callback);

      await manager.trigger(CallbackEvent.QUERY_START, 'test', {});

      expect(capturedData).toHaveLength(1);

      const data = capturedData[0];
      expect(data.userTier).toBeUndefined();
      expect(data.workflow).toBeUndefined();
    });

    it('should track triggers even when no callbacks registered', async () => {
      await manager.trigger(CallbackEvent.QUERY_START, 'test', {});

      const stats = manager.getStats();
      expect(stats.totalTriggers).toBe(1);
      expect(stats.byEvent[CallbackEvent.QUERY_START]).toBe(1);
    });

    it('should handle async callbacks', async () => {
      const results: string[] = [];

      const asyncCallback = async (data: CallbackData) => {
        await new Promise((resolve) => setTimeout(resolve, 10));
        results.push('async complete');
      };

      manager.register(CallbackEvent.QUERY_START, asyncCallback);

      await manager.trigger(CallbackEvent.QUERY_START, 'test', {});

      expect(results).toContain('async complete');
    });

    it('should catch and track callback errors', async () => {
      const badCallback = () => {
        throw new Error('Test error');
      };

      const goodCallback = () => {
        // Should still execute
      };

      manager.register(CallbackEvent.QUERY_START, badCallback);
      manager.register(CallbackEvent.QUERY_START, goodCallback);

      // Should not throw
      await manager.trigger(CallbackEvent.QUERY_START, 'test', {});

      const stats = manager.getStats();
      expect(stats.callbackErrors).toBe(1);
    });
  });

  describe('clear', () => {
    it('should clear callbacks for specific event', async () => {
      const called: CallbackEvent[] = [];

      const callback = (data: CallbackData) => {
        called.push(data.event);
      };

      manager.register(CallbackEvent.QUERY_START, callback);
      manager.register(CallbackEvent.QUERY_COMPLETE, callback);

      manager.clear(CallbackEvent.QUERY_START);

      await manager.trigger(CallbackEvent.QUERY_START, 'test1', {});
      await manager.trigger(CallbackEvent.QUERY_COMPLETE, 'test2', {});

      expect(called).toHaveLength(1);
      expect(called).toContain(CallbackEvent.QUERY_COMPLETE);
    });

    it('should clear all callbacks when no event specified', async () => {
      const called: CallbackEvent[] = [];

      const callback = (data: CallbackData) => {
        called.push(data.event);
      };

      manager.register(CallbackEvent.QUERY_START, callback);
      manager.register(CallbackEvent.QUERY_COMPLETE, callback);

      manager.clear();

      await manager.trigger(CallbackEvent.QUERY_START, 'test1', {});
      await manager.trigger(CallbackEvent.QUERY_COMPLETE, 'test2', {});

      expect(called).toHaveLength(0);
    });
  });

  describe('getStats', () => {
    it('should return correct statistics', async () => {
      const callback = () => {};

      manager.register(CallbackEvent.QUERY_START, callback);

      await manager.trigger(CallbackEvent.QUERY_START, 'test1', {});
      await manager.trigger(CallbackEvent.QUERY_START, 'test2', {});
      await manager.trigger(CallbackEvent.QUERY_COMPLETE, 'test3', {});

      const stats = manager.getStats();

      expect(stats.totalTriggers).toBe(3);
      expect(stats.byEvent[CallbackEvent.QUERY_START]).toBe(2);
      expect(stats.byEvent[CallbackEvent.QUERY_COMPLETE]).toBe(1);
      expect(stats.registeredEvents).toContain(CallbackEvent.QUERY_START);
    });

    it('should include all event types in byEvent', () => {
      const stats = manager.getStats();

      // Should have entries for all CallbackEvent values
      expect(Object.keys(stats.byEvent)).toContain(CallbackEvent.QUERY_START);
      expect(Object.keys(stats.byEvent)).toContain(CallbackEvent.QUERY_COMPLETE);
      expect(Object.keys(stats.byEvent)).toContain(CallbackEvent.CASCADE_DECISION);
    });

    it('should list only events with registered callbacks', async () => {
      const callback = () => {};

      manager.register(CallbackEvent.QUERY_START, callback);
      manager.register(CallbackEvent.CASCADE_DECISION, callback);

      const stats = manager.getStats();

      expect(stats.registeredEvents).toHaveLength(2);
      expect(stats.registeredEvents).toContain(CallbackEvent.QUERY_START);
      expect(stats.registeredEvents).toContain(CallbackEvent.CASCADE_DECISION);
    });
  });

  describe('resetStats', () => {
    it('should reset all statistics', async () => {
      const callback = () => {};

      manager.register(CallbackEvent.QUERY_START, callback);

      await manager.trigger(CallbackEvent.QUERY_START, 'test', {});

      manager.resetStats();

      const stats = manager.getStats();

      expect(stats.totalTriggers).toBe(0);
      expect(stats.callbackErrors).toBe(0);
      expect(stats.byEvent[CallbackEvent.QUERY_START]).toBe(0);
    });

    it('should not affect registered callbacks', async () => {
      const called: boolean[] = [];
      const callback = () => {
        called.push(true);
      };

      manager.register(CallbackEvent.QUERY_START, callback);

      manager.resetStats();

      await manager.trigger(CallbackEvent.QUERY_START, 'test', {});

      expect(called).toHaveLength(1);
    });
  });

  describe('printStats', () => {
    it('should print stats without throwing', () => {
      const callback = () => {};

      manager.register(CallbackEvent.QUERY_START, callback);

      // Should not throw
      expect(() => {
        manager.printStats();
      }).not.toThrow();
    });
  });

  describe('Integration Tests', () => {
    it('should handle complex callback scenarios', async () => {
      const events: string[] = [];

      const startCallback = (data: CallbackData) => {
        events.push(`start:${data.query}`);
      };

      const completeCallback = (data: CallbackData) => {
        events.push(`complete:${data.query}`);
      };

      manager.register(CallbackEvent.QUERY_START, startCallback);
      manager.register(CallbackEvent.QUERY_COMPLETE, completeCallback);

      await manager.trigger(CallbackEvent.QUERY_START, 'query1', {});
      await manager.trigger(CallbackEvent.QUERY_COMPLETE, 'query1', {});
      await manager.trigger(CallbackEvent.QUERY_START, 'query2', {});

      expect(events).toEqual(['start:query1', 'complete:query1', 'start:query2']);

      const stats = manager.getStats();
      expect(stats.totalTriggers).toBe(3);
    });

    it('should maintain separate callback lists per event', async () => {
      const startCalls: number[] = [];
      const completeCalls: number[] = [];

      manager.register(CallbackEvent.QUERY_START, () => {
        startCalls.push(1);
      });

      manager.register(CallbackEvent.QUERY_COMPLETE, () => {
        completeCalls.push(1);
      });

      await manager.trigger(CallbackEvent.QUERY_START, 'test', {});
      await manager.trigger(CallbackEvent.QUERY_START, 'test', {});
      await manager.trigger(CallbackEvent.QUERY_COMPLETE, 'test', {});

      expect(startCalls).toHaveLength(2);
      expect(completeCalls).toHaveLength(1);
    });
  });
});
