import { describe, expect, it } from 'vitest';
import { ToolCascadeValidator } from '../../src/tool-cascade/validator';
import type { Tool, ToolCall } from '../../src/types';

const weatherTool: Tool = {
  type: 'function',
  function: {
    name: 'get_weather',
    description: 'Get the weather forecast',
    parameters: {
      type: 'object',
      properties: { location: { type: 'string' } },
      required: ['location'],
    },
  },
};

const deleteTool: Tool = {
  type: 'function',
  function: {
    name: 'delete_file',
    description: 'Delete a file from disk',
    parameters: {
      type: 'object',
      properties: { path: { type: 'string' } },
      required: ['path'],
    },
  },
};

describe('ToolCascadeValidator', () => {
  it('passes structural validation for well-formed tool calls', () => {
    const validator = new ToolCascadeValidator();
    const toolCalls: ToolCall[] = [
      {
        id: '1',
        type: 'function',
        function: {
          name: 'get_weather',
          arguments: JSON.stringify({ location: 'Paris' }),
        },
      },
    ];

    const result = validator.validate(toolCalls, [weatherTool], 'simple');

    expect(result.structural.isValid).toBe(true);
    expect(result.valid).toBe(true);
  });

  it('flags placeholder semantic values', () => {
    const validator = new ToolCascadeValidator();
    const toolCalls: ToolCall[] = [
      {
        id: '2',
        type: 'function',
        function: {
          name: 'get_weather',
          arguments: JSON.stringify({ location: 'TODO' }),
        },
      },
    ];

    const result = validator.validate(toolCalls, [weatherTool], 'simple');

    expect(result.semantic.isValid).toBe(false);
    expect(result.warnings.length).toBeGreaterThan(0);
  });

  it('blocks unsafe destructive operations', () => {
    const validator = new ToolCascadeValidator();
    const toolCalls: ToolCall[] = [
      {
        id: '3',
        type: 'function',
        function: {
          name: 'delete_file',
          arguments: JSON.stringify({ path: 'rm -rf /' }),
        },
      },
    ];

    const result = validator.validate(toolCalls, [deleteTool], 'simple');

    expect(result.safety.isValid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });
});
