/**
 * ToolValidator Tests
 *
 * Comprehensive test suite for ToolValidator with 5-level validation.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { ToolValidator, formatToolQualityScore } from '../../tools/validator';
import type { ToolQualityScore, ComplexityLevel } from '../../tools/validator';

describe('ToolValidator', () => {
  let validator: ToolValidator;

  // Test tool configurations
  const weatherTool = {
    name: 'get_weather',
    description: 'Get weather',
    parameters: {
      type: 'object',
      properties: {
        location: { type: 'string' },
        unit: { type: 'string', enum: ['celsius', 'fahrenheit'] },
      },
      required: ['location'],
    },
  };

  const calculatorTool = {
    name: 'calculator',
    description: 'Calculate',
    parameters: {
      type: 'object',
      properties: {
        x: { type: 'number' },
        y: { type: 'number' },
        op: { type: 'string' },
      },
      required: ['x', 'y', 'op'],
    },
  };

  const availableTools = [weatherTool, calculatorTool];

  beforeEach(() => {
    validator = new ToolValidator();
  });

  describe('constructor', () => {
    it('should initialize with default options', () => {
      const v = new ToolValidator();
      expect(v).toBeInstanceOf(ToolValidator);
    });

    it('should support verbose mode', () => {
      const v = new ToolValidator({ verbose: true });
      expect(v).toBeInstanceOf(ToolValidator);
    });
  });

  describe('validate - simple scoring', () => {
    it('should validate valid tool call', () => {
      const toolCall = {
        name: 'get_weather',
        arguments: { location: 'Paris' },
      };

      const score = validator.validate(toolCall, availableTools);

      expect(score).toBeGreaterThan(0.8);
      expect(score).toBeLessThanOrEqual(1.0);
    });

    it('should handle array of tool calls', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: { location: 'Paris' } },
        { name: 'calculator', arguments: { x: 5, y: 3, op: 'add' } },
      ];

      const score = validator.validate(toolCalls, availableTools);

      expect(score).toBeGreaterThan(0.8);
    });

    it('should return 0 for empty tool calls', () => {
      const score = validator.validate([], availableTools);
      expect(score).toBe(0.0);
    });

    it('should handle missing available tools', () => {
      const toolCall = {
        name: 'get_weather',
        arguments: { location: 'Paris' },
      };

      const score = validator.validate(toolCall);
      expect(score).toBeGreaterThan(0.6);
    });
  });

  describe('validateToolCalls - full validation', () => {
    it('should validate valid tool calls', () => {
      const toolCalls = [
        {
          name: 'get_weather',
          arguments: { location: 'Paris', unit: 'celsius' },
        },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.isValid).toBe(true);
      expect(result.overallScore).toBeGreaterThan(0.8);
      expect(result.jsonValid).toBe(true);
      expect(result.schemaValid).toBe(true);
      expect(result.toolExists).toBe(true);
      expect(result.requiredFieldsPresent).toBe(true);
      expect(result.parametersSensible).toBe(true);
      expect(result.issues).toHaveLength(0);
    });

    it('should validate with adaptive threshold - trivial', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: { location: 'Paris' } },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools, 'trivial');

      expect(result.thresholdUsed).toBe(0.70);
      expect(result.complexityLevel).toBe('trivial');
      expect(result.adaptiveThreshold).toBe(true);
    });

    it('should validate with adaptive threshold - simple', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: { location: 'Paris' } },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools, 'simple');

      expect(result.thresholdUsed).toBe(0.75);
      expect(result.complexityLevel).toBe('simple');
      expect(result.adaptiveThreshold).toBe(true);
    });

    it('should validate with adaptive threshold - moderate', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: { location: 'Paris' } },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools, 'moderate');

      expect(result.thresholdUsed).toBe(0.85);
      expect(result.complexityLevel).toBe('moderate');
      expect(result.adaptiveThreshold).toBe(true);
    });

    it('should use default threshold when no complexity', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: { location: 'Paris' } },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.thresholdUsed).toBe(0.80);
      expect(result.adaptiveThreshold).toBe(false);
    });
  });

  describe('Level 1: JSON validation', () => {
    it('should pass for valid JSON objects', () => {
      const toolCalls = [{ name: 'test', arguments: {} }];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.jsonValid).toBe(true);
    });

    it('should fail for non-object tool calls', () => {
      const toolCalls = ['invalid' as any];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.jsonValid).toBe(false);
      expect(result.issues).toContain('Invalid JSON structure');
    });

    it('should fail for null', () => {
      const toolCalls = [null as any];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.jsonValid).toBe(false);
    });
  });

  describe('Level 2: Schema validation', () => {
    it('should pass for valid schema', () => {
      const toolCalls = [{ name: 'test', arguments: {} }];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.schemaValid).toBe(true);
    });

    it('should pass for function-style schema', () => {
      const toolCalls = [
        { function: { name: 'test' }, arguments: {} },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.schemaValid).toBe(true);
    });

    it('should pass with args field', () => {
      const toolCalls = [{ name: 'test', args: {} }];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.schemaValid).toBe(true);
    });

    it('should pass with parameters field', () => {
      const toolCalls = [{ name: 'test', parameters: {} }];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.schemaValid).toBe(true);
    });

    it('should fail when missing name', () => {
      const toolCalls = [{ arguments: {} }];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.schemaValid).toBe(false);
      expect(result.issues).toContain('Schema validation failed');
    });

    it('should fail when missing arguments', () => {
      const toolCalls = [{ name: 'test' }];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.schemaValid).toBe(false);
    });
  });

  describe('Level 3: Tool exists', () => {
    it('should pass when tool exists', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: { location: 'Paris' } },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.toolExists).toBe(true);
    });

    it('should fail when tool does not exist', () => {
      const toolCalls = [
        { name: 'nonexistent_tool', arguments: {} },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.toolExists).toBe(false);
      expect(result.issues).toContain('Tool not found');
    });

    it('should pass when no available tools provided', () => {
      const toolCalls = [{ name: 'anything', arguments: {} }];

      const result = validator.validateToolCalls(toolCalls, []);

      expect(result.toolExists).toBe(true);
    });

    it('should handle function-style name', () => {
      const toolCalls = [
        { function: { name: 'get_weather' }, arguments: {} },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.toolExists).toBe(true);
    });
  });

  describe('Level 4: Required fields', () => {
    it('should pass when all required fields present', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: { location: 'Paris' } },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.requiredFieldsPresent).toBe(true);
    });

    it('should fail when required field missing', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: { unit: 'celsius' } },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.requiredFieldsPresent).toBe(false);
      expect(result.issues).toContain('Required fields missing');
    });

    it('should pass when tool has no required fields', () => {
      const noRequiredTool = {
        name: 'no_required',
        parameters: {
          type: 'object',
          properties: { x: { type: 'number' } },
        },
      };

      const toolCalls = [{ name: 'no_required', arguments: {} }];

      const result = validator.validateToolCalls(toolCalls, [noRequiredTool]);

      expect(result.requiredFieldsPresent).toBe(true);
    });

    it('should parse JSON string arguments', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: '{"location": "Paris"}' },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.requiredFieldsPresent).toBe(true);
    });

    it('should fail for invalid JSON string arguments', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: 'invalid json' },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.requiredFieldsPresent).toBe(false);
    });

    it('should pass when no available tools', () => {
      const toolCalls = [{ name: 'test', arguments: {} }];

      const result = validator.validateToolCalls(toolCalls, []);

      expect(result.requiredFieldsPresent).toBe(true);
    });
  });

  describe('Level 5: Parameters sensible', () => {
    it('should pass for valid object parameters', () => {
      const toolCalls = [
        { name: 'test', arguments: { x: 1, y: 2 } },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.parametersSensible).toBe(true);
    });

    it('should pass for empty object', () => {
      const toolCalls = [{ name: 'test', arguments: {} }];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.parametersSensible).toBe(true);
    });

    it('should pass for JSON string arguments', () => {
      const toolCalls = [
        { name: 'test', arguments: '{"x": 1}' },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.parametersSensible).toBe(true);
    });

    it('should fail for invalid JSON string', () => {
      const toolCalls = [
        { name: 'test', arguments: 'not json' },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.parametersSensible).toBe(false);
      expect(result.issues).toContain("Parameters don't make sense");
    });

    it('should fail for non-object arguments', () => {
      const toolCalls = [
        { name: 'test', arguments: ['array'] as any },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.parametersSensible).toBe(false);
    });

    it('should handle args field', () => {
      const toolCalls = [{ name: 'test', args: { x: 1 } }];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.parametersSensible).toBe(true);
    });

    it('should handle parameters field', () => {
      const toolCalls = [{ name: 'test', parameters: { x: 1 } }];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.parametersSensible).toBe(true);
    });
  });

  describe('multiple tool calls', () => {
    it('should validate multiple valid calls', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: { location: 'Paris' } },
        { name: 'calculator', arguments: { x: 5, y: 3, op: 'add' } },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.isValid).toBe(true);
      expect(result.jsonValid).toBe(true);
      expect(result.schemaValid).toBe(true);
      expect(result.toolExists).toBe(true);
      expect(result.requiredFieldsPresent).toBe(true);
      expect(result.parametersSensible).toBe(true);
    });

    it('should fail if any call is invalid', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: { location: 'Paris' } },
        { name: 'invalid_tool', arguments: {} },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.toolExists).toBe(false);
      expect(result.isValid).toBe(false);
    });
  });

  describe('scoring and thresholds', () => {
    it('should calculate correct score for perfect call', () => {
      const toolCalls = [
        { name: 'get_weather', arguments: { location: 'Paris' } },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      expect(result.overallScore).toBe(1.0);
    });

    it('should calculate partial score for partial validation', () => {
      // Valid JSON and schema, but tool doesn't exist
      const toolCalls = [
        { name: 'nonexistent', arguments: {} },
      ];

      const result = validator.validateToolCalls(toolCalls, availableTools);

      // Should have JSON (0.25) + schema (0.20) + parameters (0.15) = 0.60
      expect(result.overallScore).toBeCloseTo(0.60, 2);
      expect(result.jsonValid).toBe(true);
      expect(result.schemaValid).toBe(true);
      expect(result.toolExists).toBe(false);
    });

    it('should use adaptive threshold correctly', () => {
      // Create a call that scores 0.80 (with tool that doesn't exist)
      const toolCalls = [{ name: 'nonexistent', arguments: {} }];

      const trivialResult = validator.validateToolCalls(
        toolCalls,
        availableTools,
        'trivial'
      );
      const moderateResult = validator.validateToolCalls(
        toolCalls,
        availableTools,
        'moderate'
      );

      // Same score, different thresholds
      expect(trivialResult.overallScore).toBe(moderateResult.overallScore);
      // Score should be 0.80: JSON (0.25) + schema (0.20) + no tool (-0.20) + no required (-0.20) + params (0.15) = 0.60 + requires (0.20) = 0.80
      // Actually: JSON (0.25) + schema (0.20) + params (0.15) = 0.60
      expect(trivialResult.overallScore).toBeCloseTo(0.60, 2);
      // Trivial threshold (0.70) should fail at 0.60
      expect(trivialResult.isValid).toBe(false);
      // Moderate threshold (0.85) should also fail at 0.60
      expect(moderateResult.isValid).toBe(false);
    });
  });

  describe('edge cases', () => {
    it('should handle empty tool calls array', () => {
      const result = validator.validateToolCalls([], availableTools);

      expect(result.jsonValid).toBe(false);
      expect(result.isValid).toBe(false);
    });

    it('should handle complex nested arguments', () => {
      const toolCalls = [
        {
          name: 'test',
          arguments: {
            nested: {
              deep: {
                value: 'test',
              },
            },
            array: [1, 2, 3],
          },
        },
      ];

      const result = validator.validateToolCalls(toolCalls, []);

      expect(result.parametersSensible).toBe(true);
    });

    it('should handle tools with input_schema', () => {
      const anthropicTool = {
        name: 'anthropic_tool',
        input_schema: {
          type: 'object',
          properties: { x: { type: 'number' } },
          required: ['x'],
        },
      };

      const toolCalls = [
        { name: 'anthropic_tool', arguments: { x: 5 } },
      ];

      const result = validator.validateToolCalls(toolCalls, [anthropicTool]);

      expect(result.requiredFieldsPresent).toBe(true);
    });

    it('should handle tools with function.parameters', () => {
      const openaiTool = {
        name: 'openai_tool',
        function: {
          parameters: {
            type: 'object',
            properties: { y: { type: 'string' } },
            required: ['y'],
          },
        },
      };

      const toolCalls = [
        { name: 'openai_tool', arguments: { y: 'test' } },
      ];

      const result = validator.validateToolCalls(toolCalls, [openaiTool]);

      expect(result.requiredFieldsPresent).toBe(true);
    });
  });

  describe('formatToolQualityScore', () => {
    it('should format valid result', () => {
      const score: ToolQualityScore = {
        overallScore: 0.95,
        thresholdUsed: 0.80,
        isValid: true,
        jsonValid: true,
        schemaValid: true,
        toolExists: true,
        requiredFieldsPresent: true,
        parametersSensible: true,
        issues: [],
        adaptiveThreshold: false,
      };

      const formatted = formatToolQualityScore(score);

      expect(formatted).toContain('✓ VALID');
      expect(formatted).toContain('0.95');
      expect(formatted).toContain('0.80');
    });

    it('should format invalid result', () => {
      const score: ToolQualityScore = {
        overallScore: 0.65,
        thresholdUsed: 0.80,
        isValid: false,
        jsonValid: true,
        schemaValid: true,
        toolExists: false,
        requiredFieldsPresent: false,
        parametersSensible: true,
        issues: ['Tool not found', 'Required fields missing'],
        adaptiveThreshold: true,
        complexityLevel: 'moderate',
      };

      const formatted = formatToolQualityScore(score);

      expect(formatted).toContain('✗ INVALID');
      expect(formatted).toContain('0.65');
      expect(formatted).toContain('0.80');
    });
  });
});
