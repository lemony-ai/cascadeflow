/**
 * Callback system for monitoring and hooks
 *
 * Provides hooks for:
 * - Before/after cascade decisions
 * - Model selection events
 * - Completion events
 * - Error handling
 *
 * Enhanced with: verbose mode, print_stats, reset_stats, callback_errors tracking
 */

/**
 * Types of callback events
 */
export enum CallbackEvent {
  QUERY_START = 'query_start',
  COMPLEXITY_DETECTED = 'complexity_detected',
  MODELS_SCORED = 'models_scored',
  STRATEGY_SELECTED = 'strategy_selected',
  MODEL_CALL_START = 'model_call_start',
  MODEL_CALL_COMPLETE = 'model_call_complete',
  MODEL_CALL_ERROR = 'model_call_error',
  CASCADE_DECISION = 'cascade_decision',
  CACHE_HIT = 'cache_hit',
  CACHE_MISS = 'cache_miss',
  QUERY_COMPLETE = 'query_complete',
  QUERY_ERROR = 'query_error',
}

/**
 * Data passed to callbacks
 */
export interface CallbackData {
  /** Event type */
  event: CallbackEvent;

  /** User query */
  query: string;

  /** User tier name (optional) */
  userTier?: string;

  /** Workflow name (optional) */
  workflow?: string;

  /** Event-specific data */
  data: Record<string, any>;

  /** Timestamp when event occurred */
  timestamp: number;
}

/**
 * Callback function type
 */
export type CallbackFunction = (data: CallbackData) => void | Promise<void>;

/**
 * Callback statistics
 */
export interface CallbackStats {
  /** Total number of triggered events */
  totalTriggers: number;

  /** Triggers by event type */
  byEvent: Record<CallbackEvent, number>;

  /** Number of callback errors */
  callbackErrors: number;

  /** List of events with registered callbacks */
  registeredEvents: string[];
}

/**
 * Manages callbacks for monitoring and hooks
 *
 * @example
 * ```typescript
 * import { CallbackManager, CallbackEvent } from '@cascadeflow/core';
 *
 * const manager = new CallbackManager();
 *
 * // Register callback
 * manager.register(CallbackEvent.CASCADE_DECISION, (data) => {
 *   console.log(`Cascade: ${data.data.from} -> ${data.data.to}`);
 * });
 *
 * // Trigger event
 * manager.trigger(
 *   CallbackEvent.CASCADE_DECISION,
 *   'test query',
 *   { from: 'llama3', to: 'gpt-4', reason: 'Low confidence' }
 * );
 * ```
 */
export class CallbackManager {
  private callbacks: Map<CallbackEvent, CallbackFunction[]> = new Map();
  private stats: {
    totalTriggers: number;
    byEvent: Map<CallbackEvent, number>;
    callbackErrors: number;
  };
  private verbose: boolean;

  /**
   * Initialize callback manager
   *
   * @param verbose - Enable verbose logging
   */
  constructor(verbose: boolean = false) {
    this.verbose = verbose;

    // Initialize stats
    this.stats = {
      totalTriggers: 0,
      byEvent: new Map(),
      callbackErrors: 0,
    };

    // Initialize event counters
    for (const event of Object.values(CallbackEvent)) {
      this.stats.byEvent.set(event, 0);
    }

    if (this.verbose) {
      console.log('[CallbackManager] Initialized');
    }
  }

  /**
   * Register a callback for an event
   *
   * @param event - Event type to listen for
   * @param callback - Function to call when event occurs
   */
  register(event: CallbackEvent, callback: CallbackFunction): void {
    if (!this.callbacks.has(event)) {
      this.callbacks.set(event, []);
    }

    this.callbacks.get(event)!.push(callback);

    if (this.verbose) {
      console.log(`[CallbackManager] Registered callback for ${event}`);
    }
  }

  /**
   * Unregister a callback
   *
   * @param event - Event type
   * @param callback - Callback function to remove
   */
  unregister(event: CallbackEvent, callback: CallbackFunction): void {
    const callbacks = this.callbacks.get(event);

    if (!callbacks) {
      if (this.verbose) {
        console.warn(`[CallbackManager] No callbacks registered for ${event}`);
      }
      return;
    }

    const index = callbacks.indexOf(callback);

    if (index === -1) {
      if (this.verbose) {
        console.warn(`[CallbackManager] Callback not found for ${event}`);
      }
      return;
    }

    callbacks.splice(index, 1);

    if (this.verbose) {
      console.log(`[CallbackManager] Unregistered callback for ${event}`);
    }
  }

  /**
   * Trigger callbacks for an event
   *
   * @param event - Event type
   * @param query - User query
   * @param data - Event-specific data
   * @param userTier - User tier name (optional)
   * @param workflow - Workflow name (optional)
   */
  async trigger(
    event: CallbackEvent,
    query: string,
    data: Record<string, any>,
    userTier?: string,
    workflow?: string
  ): Promise<void> {
    // Always count triggers, even if no callbacks registered
    this.stats.totalTriggers++;
    this.stats.byEvent.set(event, (this.stats.byEvent.get(event) || 0) + 1);

    const callbacks = this.callbacks.get(event);

    if (!callbacks || callbacks.length === 0) {
      return;
    }

    const callbackData: CallbackData = {
      event,
      query,
      userTier,
      workflow,
      data,
      timestamp: Date.now(),
    };

    // Execute all callbacks, catching errors
    for (const callback of callbacks) {
      try {
        await callback(callbackData);
      } catch (error) {
        this.stats.callbackErrors++;
        console.error(`[CallbackManager] Callback error for ${event}:`, error);
      }
    }
  }

  /**
   * Clear callbacks for event or all events
   *
   * @param event - Specific event to clear, or undefined for all
   */
  clear(event?: CallbackEvent): void {
    if (event) {
      this.callbacks.set(event, []);

      if (this.verbose) {
        console.log(`[CallbackManager] Cleared callbacks for ${event}`);
      }
    } else {
      this.callbacks.clear();

      if (this.verbose) {
        console.log('[CallbackManager] Cleared all callbacks');
      }
    }
  }

  /**
   * Get callback statistics
   *
   * @returns Callback statistics
   */
  getStats(): CallbackStats {
    const byEvent: Record<CallbackEvent, number> = {} as Record<CallbackEvent, number>;

    for (const [event, count] of this.stats.byEvent.entries()) {
      byEvent[event] = count;
    }

    const registeredEvents: string[] = [];

    for (const [event, callbacks] of this.callbacks.entries()) {
      if (callbacks.length > 0) {
        registeredEvents.push(event);
      }
    }

    return {
      totalTriggers: this.stats.totalTriggers,
      byEvent,
      callbackErrors: this.stats.callbackErrors,
      registeredEvents,
    };
  }

  /**
   * Reset callback statistics
   */
  resetStats(): void {
    this.stats.totalTriggers = 0;
    this.stats.callbackErrors = 0;

    // Reset all event counters
    for (const event of Object.values(CallbackEvent)) {
      this.stats.byEvent.set(event, 0);
    }

    if (this.verbose) {
      console.log('[CallbackManager] Stats reset');
    }
  }

  /**
   * Print formatted callback statistics
   */
  printStats(): void {
    const stats = this.getStats();

    console.log('\n' + '='.repeat(60));
    console.log('CALLBACK MANAGER STATISTICS');
    console.log('='.repeat(60));
    console.log(`Total Triggers:    ${stats.totalTriggers}`);
    console.log(`Callback Errors:   ${stats.callbackErrors}`);
    console.log();

    // Filter events with triggers > 0
    const activeEvents = Object.entries(stats.byEvent)
      .filter(([, count]) => count > 0)
      .sort(([, a], [, b]) => b - a);

    if (activeEvents.length > 0) {
      console.log('TRIGGERS BY EVENT:');

      for (const [event, count] of activeEvents) {
        console.log(`  ${event.padEnd(30)}: ${String(count).padStart(6)}`);
      }

      console.log();
    }

    if (stats.registeredEvents.length > 0) {
      console.log('REGISTERED CALLBACKS:');

      for (const event of stats.registeredEvents.sort()) {
        const callbackCount = this.callbacks.get(event as CallbackEvent)?.length || 0;
        console.log(`  ${event.padEnd(30)}: ${String(callbackCount).padStart(3)} callback(s)`);
      }
    }

    console.log('='.repeat(60) + '\n');
  }
}
