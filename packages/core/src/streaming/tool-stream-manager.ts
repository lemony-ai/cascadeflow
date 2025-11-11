/**
 * ToolStreamManager - Streaming for Tool-Calling Cascades
 *
 * Real-time streaming for tool-calling cascades with progressive JSON parsing,
 * validation, and optional execution.
 *
 * Port from Python cascadeflow/streaming/tools.py
 *
 * @example
 * ```typescript
 * import { ToolStreamManager, ToolStreamEventType } from '@cascadeflow/core/streaming';
 *
 * const manager = new ToolStreamManager(cascade);
 *
 * for await (const event of manager.stream(query, { tools })) {
 *   switch (event.type) {
 *     case ToolStreamEventType.TOOL_CALL_START:
 *       console.log(`[${event.toolCall.name}]`);
 *       break;
 *     case ToolStreamEventType.TOOL_CALL_DELTA:
 *       process.stdout.write(event.delta);
 *       break;
 *     case ToolStreamEventType.TOOL_RESULT:
 *       console.log(`→ ${event.toolResult}`);
 *       break;
 *   }
 * }
 * ```
 */

import type { Tool } from '../types';
import {
  ProgressiveJSONParser,
  ToolCallValidator,
  estimateTokens,
} from './utils';

/**
 * Tool-specific streaming event types
 */
export enum ToolStreamEventType {
  ROUTING = 'routing',
  TOOL_CALL_START = 'tool_call_start', // Tool call detected
  TOOL_CALL_DELTA = 'tool_call_delta', // Arguments streaming
  TOOL_CALL_COMPLETE = 'tool_call_complete', // Tool call formed
  TOOL_EXECUTING = 'tool_executing', // Executing tool
  TOOL_RESULT = 'tool_result', // Execution result
  TOOL_ERROR = 'tool_error', // Tool error
  TEXT_CHUNK = 'text_chunk', // Text response
  DRAFT_DECISION = 'draft_decision', // Quality decision
  SWITCH = 'switch', // Cascading
  COMPLETE = 'complete', // All done
  ERROR = 'error', // System error
}

/**
 * Tool streaming event with structured data
 */
export interface ToolStreamEvent {
  /** Event type */
  type: ToolStreamEventType;

  /** Content (for text chunks) */
  content?: string;

  /** Tool call (full or partial) */
  toolCall?: Record<string, any>;

  /** Progressive argument delta */
  delta?: string;

  /** Tool execution result */
  toolResult?: any;

  /** Error message */
  error?: string;

  /** Standard metadata */
  data?: Record<string, any>;
}

/**
 * Configuration for ToolStreamManager
 */
export interface ToolStreamManagerConfig {
  /** Tool executor function */
  toolExecutor?: (toolCall: Record<string, any>, tools: Tool[]) => Promise<any>;

  /** Enable verbose logging */
  verbose?: boolean;

  /** Cost calculator instance */
  costCalculator?: any;
}

/**
 * Options for stream() method
 */
export interface ToolStreamOptions {
  /** Tool definitions (required) */
  tools: Tool[];

  /** Maximum tokens to generate */
  maxTokens?: number;

  /** Temperature (0-2) */
  temperature?: number;

  /** Tool selection strategy */
  toolChoice?: any;

  /** Execute tools automatically */
  executeTools?: boolean;

  /** Maximum conversation turns */
  maxTurns?: number;

  /** Query complexity */
  complexity?: string;

  /** Routing strategy */
  routingStrategy?: string;

  /** Additional provider parameters */
  [key: string]: any;
}

/**
 * ToolStreamManager - Manages streaming for tool-calling cascades
 *
 * Key Features:
 * 1. Progressive JSON parsing - show tool calls as they arrive
 * 2. Tool validation - check correctness before execution
 * 3. Optional auto-execution - execute and continue
 * 4. Multi-turn support - handle conversation history
 * 5. Quality validation - use ToolQualityValidator
 * 6. Input token counting - accurate cost tracking
 */
export class ToolStreamManager {
  private cascade: any;
  private _toolExecutor?: (toolCall: Record<string, any>, tools: Tool[]) => Promise<any>;
  private verbose: boolean;
  private jsonParser: ProgressiveJSONParser;
  private _validator: ToolCallValidator;
  private costCalculator: any;
  private hasCostCalculator: boolean;

  constructor(cascade: any, config: ToolStreamManagerConfig = {}) {
    this.cascade = cascade;
    this._toolExecutor = config.toolExecutor;
    this.verbose = config.verbose ?? false;

    this.jsonParser = new ProgressiveJSONParser();
    this._validator = new ToolCallValidator();

    // Initialize CostCalculator
    if (config.costCalculator) {
      this.costCalculator = config.costCalculator;
      this.hasCostCalculator = true;
    } else {
      try {
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
          console.warn('⚠️ CostCalculator not available - using fallback');
        }
      }
    }

    if (this.verbose) {
      console.log('ToolStreamManager initialized');
    }
  }

  /**
   * Calculate costs using CostCalculator with input token counting
   */
  private _calculateCosts(
    draftContent: string,
    verifierContent: string | null,
    draftAccepted: boolean,
    queryText: string = '',
    toolCalls?: Record<string, any>[]
  ): Record<string, any> {
    if (this.hasCostCalculator && this.costCalculator) {
      try {
        // Estimate OUTPUT tokens
        let draftOutputTokens = estimateTokens(draftContent);

        // Add tool call token overhead (JSON structure)
        if (toolCalls) {
          for (const tc of toolCalls) {
            const tcStr = JSON.stringify(tc);
            draftOutputTokens += estimateTokens(tcStr);
          }
        }

        const verifierOutputTokens = verifierContent ? estimateTokens(verifierContent) : 0;
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
            `💰 CostCalculator (tools): input=${queryInputTokens}, ` +
              `draft_output=${draftOutputTokens}, verifier_output=${verifierOutputTokens}, ` +
              `tool_calls=${toolCalls?.length || 0}, ` +
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
    let draftOutputTokens = estimateTokens(draftContent);

    // Add tool call overhead
    if (toolCalls) {
      for (const tc of toolCalls) {
        const tcStr = JSON.stringify(tc);
        draftOutputTokens += estimateTokens(tcStr);
      }
    }

    const draftTotalTokens = queryInputTokens + draftOutputTokens;
    const draftCost = (draftTotalTokens / 1000) * this.cascade.drafter.cost;

    if (draftAccepted) {
      const verifierWouldBeTokens = queryInputTokens + draftOutputTokens;
      const verifierCostAvoided = (verifierWouldBeTokens / 1000) * this.cascade.verifier.cost;
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
      const verifierOutputTokens = estimateTokens(verifierContent || '');
      const verifierTotalTokens = queryInputTokens + verifierOutputTokens;
      const verifierCost = (verifierTotalTokens / 1000) * this.cascade.verifier.cost;
      const totalCost = draftCost + verifierCost;
      const costSaved = -draftCost;

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
   * Stream tool-calling cascade execution with input token counting
   *
   * @param query - User query
   * @param options - Tool streaming options
   * @yields ToolStreamEvent objects with tool-specific data
   *
   * Event Flow:
   *   1. ROUTING - Strategy chosen
   *   2. TOOL_CALL_START - Tool call begins
   *   3. TOOL_CALL_DELTA (multiple) - Arguments stream in
   *   4. TOOL_CALL_COMPLETE - Tool call ready
   *   5. [TOOL_EXECUTING] - If executeTools=true
   *   6. [TOOL_RESULT] - Execution result
   *   7. TEXT_CHUNK (multiple) - Final response
   *   8. COMPLETE - Done
   */
  async *stream(query: string, options: ToolStreamOptions): AsyncGenerator<ToolStreamEvent> {
    const {
      tools,
      maxTokens: _maxTokens = 1000,
      temperature: _temperature = 0.7,
      toolChoice: _toolChoice,
      executeTools = false,
      maxTurns: _maxTurns = 1,
      complexity,
      routingStrategy = 'cascade',
      ..._providerKwargs
    } = options;

    if (!tools || tools.length === 0) {
      throw new Error('tools parameter is required for tool streaming');
    }

    try {
      if (this.verbose) {
        console.log(`Starting tool streaming for query: ${query.slice(0, 50)}...`);
      }

      // Emit routing event
      yield this.createToolEvent(ToolStreamEventType.ROUTING, {
        data: {
          strategy: routingStrategy,
          complexity: complexity || 'unknown',
          toolsAvailable: tools.length,
          executeTools,
        },
      });

      // For now, this is a foundational implementation
      // Full tool streaming logic would go here following the Python pattern:
      // 1. Stream draft with tool calls
      // 2. Progressive JSON parsing
      // 3. Validate tool calls
      // 4. Execute tools if enabled
      // 5. Handle cascading if needed
      // 6. Calculate costs
      // 7. Emit complete event

      // Placeholder: Emit a complete event
      yield this.createToolEvent(ToolStreamEventType.COMPLETE, {
        data: {
          result: {
            content: 'Tool streaming infrastructure ready for full implementation',
            toolCalls: [],
            toolResults: [],
            modelUsed: this.cascade.drafter.name,
            draftAccepted: true,
          },
        },
      });

      if (this.verbose) {
        console.log('Tool streaming complete (foundational implementation)');
      }
    } catch (e) {
      console.error(`Tool streaming error: ${e}`);
      yield this.createToolEvent(ToolStreamEventType.ERROR, {
        error: String(e),
        data: { errorType: (e as Error).constructor.name },
      });
    }
  }

  /**
   * Process a chunk for tool calls with progressive JSON parsing
   *
   * Emits events as tool calls are detected and parsed.
   */
  private async *_processToolChunk(
    chunk: any,
    _tools: Tool[],
    currentToolCall: Record<string, any> | null,
    jsonBuffer: string
  ): AsyncGenerator<ToolStreamEvent> {
    // Provider-specific logic would go here
    // For now, basic implementation
    const chunkStr = String(chunk);

    // Check for tool call markers
    if (chunkStr.includes('"name":') || chunkStr.includes('"function":')) {
      // Potential tool call
      if (currentToolCall === null) {
        // New tool call starting
        yield this.createToolEvent(ToolStreamEventType.TOOL_CALL_START, {
          data: { detected: true },
        });
      }

      // Add to buffer and try to parse
      jsonBuffer += chunkStr;
      const result = this.jsonParser.parse(jsonBuffer);

      if (result.state === 'partial' && result.data) {
        // Emit delta
        yield this.createToolEvent(ToolStreamEventType.TOOL_CALL_DELTA, {
          delta: chunkStr,
          toolCall: result.data,
        });
      } else if (result.state === 'complete') {
        // Complete tool call
        yield this.createToolEvent(ToolStreamEventType.TOOL_CALL_COMPLETE, {
          toolCall: result.data,
        });
      }
    } else {
      // Regular text
      if (chunkStr.trim()) {
        yield this.createToolEvent(ToolStreamEventType.TEXT_CHUNK, {
          content: chunkStr,
        });
      }
    }
  }

  /**
   * Default tool executor (returns mock result)
   */
  private async _defaultToolExecutor(
    toolCall: Record<string, any>,
    _tools: Tool[]
  ): Promise<any> {
    const toolName = toolCall.name || 'unknown';
    const args = toolCall.arguments || {};

    if (this.verbose) {
      console.log(`Mock execution of tool: ${toolName} with args:`, args);
    }

    return {
      status: 'success',
      message: `Mock result for ${toolName}`,
      data: args,
    };
  }

  /**
   * Create a ToolStreamEvent
   */
  private createToolEvent(
    type: ToolStreamEventType,
    props: Partial<ToolStreamEvent> = {}
  ): ToolStreamEvent {
    return {
      type,
      content: props.content || '',
      toolCall: props.toolCall,
      delta: props.delta,
      toolResult: props.toolResult,
      error: props.error,
      data: props.data || {},
    };
  }

  /**
   * Get tool stream manager statistics
   */
  getStats(): Record<string, any> {
    return {
      hasCostCalculator: this.hasCostCalculator,
      verbose: this.verbose,
    };
  }
}

/**
 * Create a ToolStreamManager instance
 *
 * @param cascade - Cascade instance to wrap
 * @param config - Configuration options
 * @returns ToolStreamManager instance
 *
 * @example
 * ```typescript
 * import { createToolStreamManager } from '@cascadeflow/core/streaming';
 *
 * const manager = createToolStreamManager(cascade, {
 *   toolExecutor: async (toolCall, tools) => {
 *     // Custom execution logic
 *     return result;
 *   },
 *   verbose: true,
 * });
 * ```
 */
export function createToolStreamManager(
  cascade: any,
  config?: ToolStreamManagerConfig
): ToolStreamManager {
  return new ToolStreamManager(cascade, config);
}
