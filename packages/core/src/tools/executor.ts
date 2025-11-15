/**
 * Tool Execution Engine
 *
 * Executes tool calls and manages results with safe error handling.
 * Supports both synchronous and asynchronous tools, with parallel execution.
 *
 * @example
 * ```typescript
 * import { ToolExecutor, ToolConfig } from '@cascadeflow/core';
 *
 * const weatherTool = new ToolConfig({
 *   name: 'get_weather',
 *   description: 'Get weather',
 *   parameters: { type: 'object', properties: {} },
 *   function: async (location: string) => ({ temp: 72 })
 * });
 *
 * const executor = new ToolExecutor([weatherTool]);
 * const result = await executor.execute(toolCall);
 * ```
 */

import { ToolConfig } from './config';
import { ToolCall } from './call';
import { ToolResult } from './result';

/**
 * Tool execution engine
 *
 * This is the engine that actually runs your tools with safe error handling.
 *
 * @example Basic usage
 * ```typescript
 * const executor = new ToolExecutor([tool1, tool2, tool3]);
 *
 * // Execute single tool
 * const result = await executor.execute(toolCall);
 * console.log(result.success); // true
 *
 * // Execute multiple tools in parallel
 * const results = await executor.executeParallel([call1, call2, call3]);
 * ```
 */
export class ToolExecutor {
  /** Available tools by name */
  private readonly tools: Map<string, ToolConfig>;

  /**
   * Initialize executor with available tools
   *
   * @param tools - List of tool configurations
   *
   * @example
   * ```typescript
   * const executor = new ToolExecutor([
   *   weatherTool,
   *   calculatorTool,
   *   searchTool
   * ]);
   * ```
   */
  constructor(tools: ToolConfig[]) {
    this.tools = new Map(tools.map((tool) => [tool.name, tool]));
    console.log(
      `[ToolExecutor] Initialized with ${this.tools.size} tools: ${Array.from(
        this.tools.keys()
      ).join(', ')}`
    );
  }

  /**
   * Execute a single tool call
   *
   * @param toolCall - Tool call to execute
   * @returns Tool execution result
   *
   * @example
   * ```typescript
   * const call = new ToolCall({
   *   id: 'call_123',
   *   name: 'calculator',
   *   arguments: { x: 5, y: 3, op: 'add' },
   *   providerFormat: ToolCallFormat.OPENAI
   * });
   *
   * const result = await executor.execute(call);
   * if (result.success) {
   *   console.log('Result:', result.result);
   * } else {
   *   console.error('Error:', result.error);
   * }
   * ```
   */
  async execute(toolCall: ToolCall): Promise<ToolResult> {
    const startTime = Date.now();

    // Get the tool
    const tool = this.tools.get(toolCall.name);
    if (!tool) {
      const errorMsg = `Tool '${toolCall.name}' not found. Available: ${Array.from(
        this.tools.keys()
      ).join(', ')}`;
      console.error(`[ToolExecutor] ${errorMsg}`);
      return new ToolResult({
        callId: toolCall.id,
        name: toolCall.name,
        result: null,
        error: errorMsg,
      });
    }

    // Check if tool has executable function
    if (!tool.function) {
      const errorMsg = `Tool '${toolCall.name}' has no executable function`;
      console.error(`[ToolExecutor] ${errorMsg}`);
      return new ToolResult({
        callId: toolCall.id,
        name: toolCall.name,
        result: null,
        error: errorMsg,
      });
    }

    // Execute the tool
    try {
      console.log(
        `[ToolExecutor] Executing tool '${toolCall.name}' with args:`,
        toolCall.arguments
      );

      // Handle both sync and async functions
      let result: any;
      const funcResult = tool.function(toolCall.arguments);

      // Check if result is a Promise
      if (funcResult && typeof funcResult.then === 'function') {
        result = await funcResult;
      } else {
        result = funcResult;
      }

      const executionTime = Date.now() - startTime;

      console.log(`[ToolExecutor] Tool '${toolCall.name}' succeeded in ${executionTime}ms`);

      return new ToolResult({
        callId: toolCall.id,
        name: toolCall.name,
        result,
        executionTimeMs: executionTime,
      });
    } catch (e: any) {
      const executionTime = Date.now() - startTime;
      const errorMsg = `${e.constructor?.name || 'Error'}: ${e.message || String(e)}`;

      console.error(
        `[ToolExecutor] Tool '${toolCall.name}' failed after ${executionTime}ms: ${errorMsg}`
      );

      return new ToolResult({
        callId: toolCall.id,
        name: toolCall.name,
        result: null,
        error: errorMsg,
        executionTimeMs: executionTime,
      });
    }
  }

  /**
   * Execute multiple tool calls in parallel
   *
   * @param toolCalls - List of tool calls to execute
   * @param maxParallel - Maximum number of parallel executions (default: 5)
   * @returns List of tool results in same order as tool_calls
   *
   * @example
   * ```typescript
   * const results = await executor.executeParallel([
   *   weatherCall,
   *   calculatorCall,
   *   searchCall
   * ], 3);
   *
   * results.forEach(result => {
   *   console.log(`${result.name}: ${result.success ? 'OK' : 'FAIL'}`);
   * });
   * ```
   */
  async executeParallel(
    toolCalls: ToolCall[],
    maxParallel: number = 5
  ): Promise<ToolResult[]> {
    if (!toolCalls || toolCalls.length === 0) {
      return [];
    }

    console.log(
      `[ToolExecutor] Executing ${toolCalls.length} tools in parallel (max=${maxParallel})`
    );

    // Create a semaphore-like queue for limiting concurrency
    const results: ToolResult[] = new Array(toolCalls.length);
    const executing: Promise<void>[] = [];

    for (let i = 0; i < toolCalls.length; i++) {
      const index = i;
      const call = toolCalls[i];

      // Execute the call
      const promise = this.execute(call).then((result) => {
        results[index] = result;
      });

      executing.push(promise);

      // If we've hit the max parallel limit, wait for one to complete
      if (executing.length >= maxParallel) {
        await Promise.race(executing);
        // Remove completed promises
        const stillExecuting = executing.filter((p) => {
          // Check if promise is still pending
          let isPending = true;
          p.then(() => {
            isPending = false;
          }).catch(() => {
            isPending = false;
          });
          return isPending;
        });
        executing.length = 0;
        executing.push(...stillExecuting);
      }
    }

    // Wait for all remaining executions to complete
    await Promise.all(executing);

    // Log summary
    const successful = results.filter((r) => r.success).length;
    console.log(
      `[ToolExecutor] Parallel execution complete: ${successful}/${results.length} succeeded`
    );

    return results;
  }

  /**
   * Get tool configuration by name
   *
   * @param name - Tool name
   * @returns Tool configuration or undefined
   *
   * @example
   * ```typescript
   * const tool = executor.getTool('calculator');
   * if (tool) {
   *   console.log(tool.description);
   * }
   * ```
   */
  getTool(name: string): ToolConfig | undefined {
    return this.tools.get(name);
  }

  /**
   * Check if tool exists
   *
   * @param name - Tool name
   * @returns True if tool exists
   *
   * @example
   * ```typescript
   * if (executor.hasTool('calculator')) {
   *   console.log('Calculator available');
   * }
   * ```
   */
  hasTool(name: string): boolean {
    return this.tools.has(name);
  }

  /**
   * Get list of available tool names
   *
   * @returns Array of tool names
   *
   * @example
   * ```typescript
   * const tools = executor.listTools();
   * console.log('Available tools:', tools.join(', '));
   * ```
   */
  listTools(): string[] {
    return Array.from(this.tools.keys());
  }

  /**
   * Get number of available tools
   *
   * @returns Tool count
   */
  get toolCount(): number {
    return this.tools.size;
  }
}
