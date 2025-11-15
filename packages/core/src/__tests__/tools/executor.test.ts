/**
 * ToolExecutor Tests
 *
 * Comprehensive test suite for ToolExecutor, ToolCall, ToolResult, and format conversion.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  ToolExecutor,
  ToolConfig,
  ToolCall,
  ToolResult,
  ToolCallFormat,
  toOpenAIFormat,
  toAnthropicFormat,
  toProviderFormat,
  getProviderFormatType,
} from '../../tools';

describe('ToolExecutor', () => {
  // Test tools
  const weatherTool = new ToolConfig({
    name: 'get_weather',
    description: 'Get current weather',
    parameters: {
      type: 'object',
      properties: {
        location: { type: 'string', description: 'City name' },
      },
      required: ['location'],
    },
    function: async ({ location }: { location: string }) => ({
      location,
      temperature: 72,
      condition: 'sunny',
    }),
  });

  const calculatorTool = new ToolConfig({
    name: 'calculator',
    description: 'Perform calculations',
    parameters: {
      type: 'object',
      properties: {
        x: { type: 'number' },
        y: { type: 'number' },
        op: { type: 'string', enum: ['add', 'subtract', 'multiply', 'divide'] },
      },
      required: ['x', 'y', 'op'],
    },
    function: ({ x, y, op }: { x: number; y: number; op: string }) => {
      switch (op) {
        case 'add':
          return x + y;
        case 'subtract':
          return x - y;
        case 'multiply':
          return x * y;
        case 'divide':
          return y !== 0 ? x / y : 'Error: Division by zero';
        default:
          throw new Error(`Unknown operation: ${op}`);
      }
    },
  });

  const errorTool = new ToolConfig({
    name: 'error_tool',
    description: 'Always throws error',
    parameters: {
      type: 'object',
      properties: {},
    },
    function: () => {
      throw new Error('Intentional error for testing');
    },
  });

  let executor: ToolExecutor;

  beforeEach(() => {
    executor = new ToolExecutor([weatherTool, calculatorTool, errorTool]);
  });

  describe('constructor', () => {
    it('should initialize with tools', () => {
      expect(executor).toBeInstanceOf(ToolExecutor);
      expect(executor.toolCount).toBe(3);
    });

    it('should list available tools', () => {
      const tools = executor.listTools();
      expect(tools).toHaveLength(3);
      expect(tools).toContain('get_weather');
      expect(tools).toContain('calculator');
      expect(tools).toContain('error_tool');
    });

    it('should handle empty tools array', () => {
      const emptyExecutor = new ToolExecutor([]);
      expect(emptyExecutor.toolCount).toBe(0);
      expect(emptyExecutor.listTools()).toHaveLength(0);
    });
  });

  describe('execute', () => {
    it('should execute async tool successfully', async () => {
      const call = new ToolCall({
        id: 'call_123',
        name: 'get_weather',
        arguments: { location: 'Paris' },
        providerFormat: ToolCallFormat.OPENAI,
      });

      const result = await executor.execute(call);

      expect(result.success).toBe(true);
      expect(result.callId).toBe('call_123');
      expect(result.name).toBe('get_weather');
      expect(result.result).toEqual({
        location: 'Paris',
        temperature: 72,
        condition: 'sunny',
      });
      expect(result.executionTimeMs).toBeGreaterThanOrEqual(0);
    });

    it('should execute sync tool successfully', async () => {
      const call = new ToolCall({
        id: 'call_456',
        name: 'calculator',
        arguments: { x: 10, y: 5, op: 'add' },
        providerFormat: ToolCallFormat.OPENAI,
      });

      const result = await executor.execute(call);

      expect(result.success).toBe(true);
      expect(result.result).toBe(15);
    });

    it('should handle tool not found', async () => {
      const call = new ToolCall({
        id: 'call_789',
        name: 'nonexistent_tool',
        arguments: {},
        providerFormat: ToolCallFormat.OPENAI,
      });

      const result = await executor.execute(call);

      expect(result.success).toBe(false);
      expect(result.error).toContain('not found');
      expect(result.error).toContain('Available');
    });

    it('should handle tool without function', async () => {
      const noFuncTool = new ToolConfig({
        name: 'no_function',
        description: 'No function',
        parameters: { type: 'object', properties: {} },
      });

      const exec = new ToolExecutor([noFuncTool]);
      const call = new ToolCall({
        id: 'call_abc',
        name: 'no_function',
        arguments: {},
        providerFormat: ToolCallFormat.OPENAI,
      });

      const result = await exec.execute(call);

      expect(result.success).toBe(false);
      expect(result.error).toContain('no executable function');
    });

    it('should handle tool execution error', async () => {
      const call = new ToolCall({
        id: 'call_error',
        name: 'error_tool',
        arguments: {},
        providerFormat: ToolCallFormat.OPENAI,
      });

      const result = await executor.execute(call);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Intentional error');
      expect(result.executionTimeMs).toBeGreaterThanOrEqual(0);
    });

    it('should measure execution time', async () => {
      const call = new ToolCall({
        id: 'call_time',
        name: 'calculator',
        arguments: { x: 5, y: 3, op: 'multiply' },
        providerFormat: ToolCallFormat.OPENAI,
      });

      const result = await executor.execute(call);

      expect(result.executionTimeMs).toBeGreaterThanOrEqual(0);
      expect(result.executionTimeMs).toBeLessThan(1000); // Should be very fast
    });
  });

  describe('executeParallel', () => {
    it('should execute multiple tools in parallel', async () => {
      const calls = [
        new ToolCall({
          id: 'call_1',
          name: 'calculator',
          arguments: { x: 10, y: 5, op: 'add' },
          providerFormat: ToolCallFormat.OPENAI,
        }),
        new ToolCall({
          id: 'call_2',
          name: 'calculator',
          arguments: { x: 20, y: 4, op: 'multiply' },
          providerFormat: ToolCallFormat.OPENAI,
        }),
        new ToolCall({
          id: 'call_3',
          name: 'get_weather',
          arguments: { location: 'Tokyo' },
          providerFormat: ToolCallFormat.OPENAI,
        }),
      ];

      const results = await executor.executeParallel(calls);

      expect(results).toHaveLength(3);
      expect(results[0].result).toBe(15);
      expect(results[1].result).toBe(80);
      expect(results[2].result).toEqual({
        location: 'Tokyo',
        temperature: 72,
        condition: 'sunny',
      });
    });

    it('should handle empty calls array', async () => {
      const results = await executor.executeParallel([]);
      expect(results).toHaveLength(0);
    });

    it('should handle mixed success and failures', async () => {
      const calls = [
        new ToolCall({
          id: 'call_1',
          name: 'calculator',
          arguments: { x: 5, y: 3, op: 'add' },
          providerFormat: ToolCallFormat.OPENAI,
        }),
        new ToolCall({
          id: 'call_2',
          name: 'error_tool',
          arguments: {},
          providerFormat: ToolCallFormat.OPENAI,
        }),
        new ToolCall({
          id: 'call_3',
          name: 'calculator',
          arguments: { x: 10, y: 2, op: 'divide' },
          providerFormat: ToolCallFormat.OPENAI,
        }),
      ];

      const results = await executor.executeParallel(calls);

      expect(results).toHaveLength(3);
      expect(results[0].success).toBe(true);
      expect(results[1].success).toBe(false);
      expect(results[2].success).toBe(true);
    });

    it('should respect max parallel limit', async () => {
      const calls = Array.from({ length: 10 }, (_, i) =>
        new ToolCall({
          id: `call_${i}`,
          name: 'calculator',
          arguments: { x: i, y: 1, op: 'add' },
          providerFormat: ToolCallFormat.OPENAI,
        })
      );

      const results = await executor.executeParallel(calls, 3);

      expect(results).toHaveLength(10);
      results.forEach((result, i) => {
        expect(result.success).toBe(true);
        expect(result.result).toBe(i + 1);
      });
    });

    it('should maintain order of results', async () => {
      const calls = [
        new ToolCall({
          id: 'first',
          name: 'calculator',
          arguments: { x: 1, y: 0, op: 'add' },
          providerFormat: ToolCallFormat.OPENAI,
        }),
        new ToolCall({
          id: 'second',
          name: 'calculator',
          arguments: { x: 2, y: 0, op: 'add' },
          providerFormat: ToolCallFormat.OPENAI,
        }),
        new ToolCall({
          id: 'third',
          name: 'calculator',
          arguments: { x: 3, y: 0, op: 'add' },
          providerFormat: ToolCallFormat.OPENAI,
        }),
      ];

      const results = await executor.executeParallel(calls);

      expect(results[0].callId).toBe('first');
      expect(results[0].result).toBe(1);
      expect(results[1].callId).toBe('second');
      expect(results[1].result).toBe(2);
      expect(results[2].callId).toBe('third');
      expect(results[2].result).toBe(3);
    });
  });

  describe('tool management', () => {
    it('should get tool by name', () => {
      const tool = executor.getTool('calculator');
      expect(tool).toBeDefined();
      expect(tool?.name).toBe('calculator');
    });

    it('should return undefined for unknown tool', () => {
      const tool = executor.getTool('unknown');
      expect(tool).toBeUndefined();
    });

    it('should check if tool exists', () => {
      expect(executor.hasTool('calculator')).toBe(true);
      expect(executor.hasTool('unknown')).toBe(false);
    });

    it('should get tool count', () => {
      expect(executor.toolCount).toBe(3);
    });
  });
});

describe('ToolCall', () => {
  describe('fromOpenAI', () => {
    it('should parse OpenAI tool call', () => {
      const raw = {
        id: 'call_123',
        type: 'function',
        function: {
          name: 'get_weather',
          arguments: '{"location": "Paris"}',
        },
      };

      const call = ToolCall.fromOpenAI(raw);

      expect(call.id).toBe('call_123');
      expect(call.name).toBe('get_weather');
      expect(call.arguments).toEqual({ location: 'Paris' });
      expect(call.providerFormat).toBe(ToolCallFormat.OPENAI);
    });

    it('should handle invalid JSON arguments', () => {
      const raw = {
        id: 'call_456',
        function: {
          name: 'test',
          arguments: 'invalid json',
        },
      };

      const call = ToolCall.fromOpenAI(raw);

      expect(call.arguments).toEqual({});
    });

    it('should handle missing arguments', () => {
      const raw = {
        id: 'call_789',
        function: {
          name: 'test',
        },
      };

      const call = ToolCall.fromOpenAI(raw);

      expect(call.arguments).toEqual({});
    });
  });

  describe('fromAnthropic', () => {
    it('should parse Anthropic tool use', () => {
      const raw = {
        type: 'tool_use',
        id: 'toolu_123',
        name: 'get_weather',
        input: {
          location: 'Paris',
        },
      };

      const call = ToolCall.fromAnthropic(raw);

      expect(call.id).toBe('toolu_123');
      expect(call.name).toBe('get_weather');
      expect(call.arguments).toEqual({ location: 'Paris' });
      expect(call.providerFormat).toBe(ToolCallFormat.ANTHROPIC);
    });

    it('should handle missing input', () => {
      const raw = {
        id: 'toolu_456',
        name: 'test',
      };

      const call = ToolCall.fromAnthropic(raw);

      expect(call.arguments).toEqual({});
    });
  });

  describe('fromProvider', () => {
    it('should route to correct parser', () => {
      const openaiRaw = {
        id: 'call_1',
        function: { name: 'test', arguments: '{}' },
      };
      const anthropicRaw = {
        id: 'toolu_1',
        name: 'test',
        input: {},
      };

      const openaiCall = ToolCall.fromProvider('openai', openaiRaw);
      const anthropicCall = ToolCall.fromProvider('anthropic', anthropicRaw);

      expect(openaiCall.providerFormat).toBe(ToolCallFormat.OPENAI);
      expect(anthropicCall.providerFormat).toBe(ToolCallFormat.ANTHROPIC);
    });

    it('should default to OpenAI format for unknown provider', () => {
      const raw = {
        id: 'call_unknown',
        function: { name: 'test', arguments: '{}' },
      };

      const call = ToolCall.fromProvider('unknown', raw);

      expect(call.providerFormat).toBe(ToolCallFormat.OPENAI);
    });
  });

  describe('toJSON', () => {
    it('should serialize to JSON', () => {
      const call = new ToolCall({
        id: 'call_123',
        name: 'test',
        arguments: { x: 1 },
        providerFormat: ToolCallFormat.OPENAI,
      });

      const json = call.toJSON();

      expect(json.id).toBe('call_123');
      expect(json.name).toBe('test');
      expect(json.arguments).toEqual({ x: 1 });
    });
  });
});

describe('ToolResult', () => {
  describe('constructor', () => {
    it('should create successful result', () => {
      const result = new ToolResult({
        callId: 'call_123',
        name: 'test',
        result: { data: 'value' },
        executionTimeMs: 45.2,
      });

      expect(result.success).toBe(true);
      expect(result.callId).toBe('call_123');
      expect(result.name).toBe('test');
      expect(result.result).toEqual({ data: 'value' });
    });

    it('should create error result', () => {
      const result = new ToolResult({
        callId: 'call_456',
        name: 'test',
        result: null,
        error: 'Something went wrong',
      });

      expect(result.success).toBe(false);
      expect(result.error).toBe('Something went wrong');
    });
  });

  describe('toOpenAIMessage', () => {
    it('should format success as OpenAI message', () => {
      const result = new ToolResult({
        callId: 'call_123',
        name: 'test',
        result: { temp: 72 },
      });

      const msg = result.toOpenAIMessage();

      expect(msg.tool_call_id).toBe('call_123');
      expect(msg.role).toBe('tool');
      expect(msg.name).toBe('test');
      expect(msg.content).toContain('72');
    });

    it('should format error as OpenAI message', () => {
      const result = new ToolResult({
        callId: 'call_456',
        name: 'test',
        result: null,
        error: 'Failed',
      });

      const msg = result.toOpenAIMessage();

      expect(msg.content).toBe('Error: Failed');
    });
  });

  describe('toAnthropicMessage', () => {
    it('should format success as Anthropic message', () => {
      const result = new ToolResult({
        callId: 'toolu_123',
        name: 'test',
        result: { temp: 72 },
      });

      const msg = result.toAnthropicMessage();

      expect(msg.role).toBe('user');
      expect(msg.content).toHaveLength(1);
      expect(msg.content[0].type).toBe('tool_result');
      expect(msg.content[0].tool_use_id).toBe('toolu_123');
      expect(msg.content[0].is_error).toBe(false);
    });

    it('should format error as Anthropic message', () => {
      const result = new ToolResult({
        callId: 'toolu_456',
        name: 'test',
        result: null,
        error: 'Failed',
      });

      const msg = result.toAnthropicMessage();

      expect(msg.content[0].is_error).toBe(true);
      expect(msg.content[0].content).toBe('Error: Failed');
    });
  });

  describe('toProviderMessage', () => {
    it('should route to correct formatter', () => {
      const result = new ToolResult({
        callId: 'call_123',
        name: 'test',
        result: 'data',
      });

      const openaiMsg = result.toProviderMessage('openai');
      const anthropicMsg = result.toProviderMessage('anthropic');

      expect(openaiMsg).toHaveProperty('role', 'tool');
      expect(anthropicMsg).toHaveProperty('role', 'user');
    });
  });
});

describe('Format Conversion', () => {
  const schema = {
    type: 'object',
    properties: {
      location: { type: 'string' },
    },
    required: ['location'],
  };

  describe('toOpenAIFormat', () => {
    it('should convert to OpenAI format', () => {
      const formatted = toOpenAIFormat('get_weather', 'Get weather', schema);

      expect(formatted.type).toBe('function');
      expect(formatted.function.name).toBe('get_weather');
      expect(formatted.function.description).toBe('Get weather');
      expect(formatted.function.parameters).toEqual(schema);
    });
  });

  describe('toAnthropicFormat', () => {
    it('should convert to Anthropic format', () => {
      const formatted = toAnthropicFormat('get_weather', 'Get weather', schema);

      expect(formatted.name).toBe('get_weather');
      expect(formatted.description).toBe('Get weather');
      expect(formatted.input_schema).toEqual(schema);
    });
  });

  describe('toProviderFormat', () => {
    it('should route to correct formatter', () => {
      const openai = toProviderFormat('openai', 'test', 'desc', schema);
      const anthropic = toProviderFormat('anthropic', 'test', 'desc', schema);

      expect(openai).toHaveProperty('type', 'function');
      expect(anthropic).toHaveProperty('input_schema');
    });
  });

  describe('getProviderFormatType', () => {
    it('should return correct format types', () => {
      expect(getProviderFormatType('openai')).toBe(ToolCallFormat.OPENAI);
      expect(getProviderFormatType('anthropic')).toBe(ToolCallFormat.ANTHROPIC);
      expect(getProviderFormatType('ollama')).toBe(ToolCallFormat.OLLAMA);
      expect(getProviderFormatType('unknown')).toBe(ToolCallFormat.OPENAI);
    });
  });
});
