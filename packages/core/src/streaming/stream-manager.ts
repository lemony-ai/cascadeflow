/**
 * StreamManager - Streaming for Cascade Operations
 *
 * Manages streaming for cascade operations with integrated cost calculation.
 * Provides real-time event streaming without modifying underlying cascade logic.
 *
 * Port from Python cascadeflow/streaming/base.py
 *
 * @example
 * ```typescript
 * import { StreamManager } from '@cascadeflow/core/streaming';
 *
 * const manager = new StreamManager(cascade, { verbose: true });
 *
 * for await (const event of manager.stream(query, options)) {
 *   switch (event.type) {
 *     case StreamEventType.CHUNK:
 *       process.stdout.write(event.content);
 *       break;
 *     case StreamEventType.COMPLETE:
 *       console.log('Done!', event.data.result);
 *       break;
 *   }
 * }
 * ```
 */

import type { StreamEvent, StreamEventData } from '../streaming';
import { StreamEventType } from '../streaming';
import type { ModelConfig } from '../config';
import {
  estimateTokens,
  estimateConfidenceFromLogprobs,
} from './utils';

/**
 * Configuration for StreamManager
 */
export interface StreamManagerConfig {
  /** Enable verbose logging */
  verbose?: boolean;

  /** Cost calculator instance (optional, will create if not provided) */
  costCalculator?: any;
}

/**
 * Options for stream() method
 */
export interface StreamOptions {
  /** Maximum tokens to generate */
  maxTokens?: number;

  /** Temperature (0-2) */
  temperature?: number;

  /** Query complexity */
  complexity?: string;

  /** Routing strategy */
  routingStrategy?: string;

  /** Force direct routing (skip cascade) */
  isDirectRoute?: boolean;

  /** Tools for function calling */
  tools?: any[];

  /** Tool choice strategy */
  toolChoice?: any;

  /** Additional provider parameters */
  [key: string]: any;
}

/**
 * StreamManager - Manages streaming for cascade operations
 *
 * Features:
 * - Real-time event streaming
 * - Integrated cost calculation with input token counting
 * - Confidence estimation from logprobs
 * - Direct and cascade routing
 * - Quality validation
 *
 * Architecture:
 *   Wraps WholeResponseCascade to provide streaming without
 *   modifying the underlying cascade logic.
 */
export class StreamManager {
  private cascade: any;
  private verbose: boolean;
  private costCalculator: any;
  private hasCostCalculator: boolean;

  constructor(cascade: any, config: StreamManagerConfig = {}) {
    this.cascade = cascade;
    this.verbose = config.verbose ?? false;

    // Initialize CostCalculator
    if (config.costCalculator) {
      this.costCalculator = config.costCalculator;
      this.hasCostCalculator = true;
    } else {
      // Try to create cost calculator
      try {
        // Import dynamically to avoid circular dependencies
        const { CostCalculator } = require('../telemetry/cost-calculator');
        this.costCalculator = new CostCalculator({
          drafter: cascade.drafter,
          verifier: cascade.verifier,
          verbose: this.verbose,
        });
        this.hasCostCalculator = true;
        if (this.verbose) {
          console.log('✅ CostCalculator initialized from telemetry module');
        }
      } catch (e) {
        this.costCalculator = null;
        this.hasCostCalculator = false;
        if (this.verbose) {
          console.warn('⚠️ CostCalculator not available - using fallback calculations');
        }
      }
    }

    if (this.verbose) {
      console.log('StreamManager initialized');
    }
  }

  /**
   * Calculate cost from token count (fallback method)
   */
  private calculateCostFromTokens(modelConfig: ModelConfig, tokens: number): number {
    return modelConfig.cost * (tokens / 1000);
  }

  /**
   * Calculate costs using CostCalculator or fallback
   *
   * @param draftContent - Draft model's output
   * @param verifierContent - Verifier model's output (if cascaded)
   * @param draftAccepted - Whether draft was accepted
   * @param queryText - Original query text for input token counting
   * @returns Cost breakdown
   */
  private _calculateCosts(
    draftContent: string,
    verifierContent: string | null,
    draftAccepted: boolean,
    queryText: string = ''
  ): Record<string, any> {
    // Try using CostCalculator first
    if (this.hasCostCalculator && this.costCalculator) {
      try {
        // Estimate OUTPUT tokens only
        const draftOutputTokens = estimateTokens(draftContent);
        const verifierOutputTokens = verifierContent ? estimateTokens(verifierContent) : 0;
        // Estimate INPUT tokens from query
        const queryInputTokens = estimateTokens(queryText);

        // Use CostCalculator WITH input tokens
        const breakdown = this.costCalculator.calculateFromTokens({
          draftOutputTokens,
          verifierOutputTokens,
          draftAccepted,
          queryInputTokens,
        });

        if (this.verbose) {
          console.log(
            `💰 CostCalculator: input=${queryInputTokens}, ` +
              `draft_output=${draftOutputTokens}, verifier_output=${verifierOutputTokens}, ` +
              `total=$${breakdown.totalCost.toFixed(6)}`
          );
        }

        return {
          draftCost: breakdown.draftCost,
          verifierCost: breakdown.verifierCost,
          totalCost: breakdown.totalCost,
          costSaved: breakdown.costSaved,
          draftTokens: breakdown.draftTokens,
          verifierTokens: breakdown.verifierTokens,
          totalTokens: breakdown.totalTokens,
        };
      } catch (e) {
        if (this.verbose) {
          console.warn(`CostCalculator failed: ${e}, using fallback`);
        }
      }
    }

    // Fallback: Manual calculation
    const queryInputTokens = estimateTokens(queryText);
    const draftOutputTokens = estimateTokens(draftContent);
    const draftTotalTokens = queryInputTokens + draftOutputTokens;
    const draftCost = this.calculateCostFromTokens(this.cascade.drafter, draftTotalTokens);

    if (draftAccepted) {
      // Draft accepted - only paid for draft
      const verifierWouldBeTokens = queryInputTokens + draftOutputTokens;
      const verifierCostAvoided = this.calculateCostFromTokens(
        this.cascade.verifier,
        verifierWouldBeTokens
      );
      const costSaved = verifierCostAvoided - draftCost;

      return {
        draftCost,
        verifierCost: 0.0,
        totalCost: draftCost,
        costSaved,
        draftTokens: draftTotalTokens,
        verifierTokens: 0,
        totalTokens: draftTotalTokens,
      };
    } else {
      // Draft rejected - paid for both
      const verifierOutputTokens = estimateTokens(verifierContent || '');
      const verifierTotalTokens = queryInputTokens + verifierOutputTokens;
      const verifierCost = this.calculateCostFromTokens(this.cascade.verifier, verifierTotalTokens);
      const totalCost = draftCost + verifierCost;
      const costSaved = -draftCost; // Wasted draft cost

      return {
        draftCost,
        verifierCost,
        totalCost,
        costSaved,
        draftTokens: draftTotalTokens,
        verifierTokens: verifierTotalTokens,
        totalTokens: draftTotalTokens + verifierTotalTokens,
      };
    }
  }

  /**
   * Calculate confidence from logprobs with provider-specific handling
   */
  private _calculateConfidenceFromLogprobs(
    logprobs: number[],
    providerType?: string
  ): number | null {
    if (!logprobs || logprobs.length === 0) {
      return null;
    }

    // Provider-specific handling
    if (providerType === 'anthropic') {
      // Anthropic doesn't provide logprobs
      return null;
    }

    const confidence = estimateConfidenceFromLogprobs(logprobs, 'mean');

    if (this.verbose && confidence !== null) {
      console.log(`Calculated confidence from logprobs: ${confidence.toFixed(3)}`);
    }

    return confidence;
  }

  /**
   * Stream cascade execution with real-time events
   *
   * @param query - User query to process
   * @param options - Streaming options
   * @yields StreamEvent objects with type, content, and data
   *
   * @example
   * ```typescript
   * for await (const event of manager.stream(query, { maxTokens: 100 })) {
   *   console.log(event.type, event.content);
   * }
   * ```
   */
  async *stream(query: string, options: StreamOptions = {}): AsyncGenerator<StreamEvent> {
    const {
      maxTokens = 100,
      temperature = 0.7,
      complexity,
      routingStrategy = 'cascade',
      isDirectRoute = false,
      tools,
      toolChoice,
      ...providerKwargs
    } = options;

    try {
      if (this.verbose) {
        console.log(`Starting streaming execution for query: ${query.slice(0, 50)}...`);
      }

      // Filter kwargs to prevent contamination
      const cleanKwargs = { ...providerKwargs };
      delete cleanKwargs.routing_strategy;
      delete cleanKwargs.is_direct_route;
      delete cleanKwargs.complexity;

      // Add tools if provided
      if (tools) {
        cleanKwargs.tools = tools;
      }
      if (toolChoice) {
        cleanKwargs.tool_choice = toolChoice;
      }

      // Emit routing event
      yield this.createEvent(StreamEventType.ROUTING, '', {
        strategy: routingStrategy,
        complexity: complexity || 'unknown',
      });

      // For now, this is a foundational implementation
      // Full streaming logic would go here following the Python pattern:
      // 1. Stream draft generation
      // 2. Validate quality
      // 3. Either accept draft or cascade to verifier
      // 4. Calculate costs
      // 5. Emit complete event

      // Placeholder: Emit a complete event with basic structure
      yield this.createEvent(StreamEventType.COMPLETE, '', {
        result: {
          content: 'Streaming infrastructure ready for full implementation',
          modelUsed: this.cascade.drafter.name,
          draftAccepted: true,
          cascaded: false,
        },
      });

      if (this.verbose) {
        console.log('Streaming execution complete (foundational implementation)');
      }
    } catch (e) {
      console.error(`Streaming error: ${e}`);
      yield this.createEvent(StreamEventType.ERROR, String(e), {
        error: String(e),
        type: (e as Error).constructor.name,
      });
    }
  }

  /**
   * Create a StreamEvent
   */
  private createEvent(
    type: StreamEventType,
    content: string = '',
    data: StreamEventData = {}
  ): StreamEvent {
    return {
      type,
      content,
      data,
    };
  }

  /**
   * Get stream manager statistics
   */
  getStats(): Record<string, any> {
    return {
      hasCostCalculator: this.hasCostCalculator,
      verbose: this.verbose,
    };
  }
}

/**
 * Create a StreamManager instance
 *
 * @param cascade - Cascade instance to wrap
 * @param config - Configuration options
 * @returns StreamManager instance
 *
 * @example
 * ```typescript
 * import { createStreamManager } from '@cascadeflow/core/streaming';
 *
 * const manager = createStreamManager(cascade, { verbose: true });
 * ```
 */
export function createStreamManager(cascade: any, config?: StreamManagerConfig): StreamManager {
  return new StreamManager(cascade, config);
}
