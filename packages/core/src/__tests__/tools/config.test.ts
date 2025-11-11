/**
 * ToolConfig Tests
 *
 * Comprehensive test suite for ToolConfig class.
 * Tests tool creation, validation, format conversion, and helper functions.
 */

import { describe, it, expect } from 'vitest';
import {
  ToolConfig,
  createTool,
  tool,
  inferJsonType,
  buildParameterSchema,
  type ToolConfigOptions,
  type ToolParameters,
} from '../../tools/config';

describe('ToolConfig', () => {
  // Test tool configurations
  const weatherToolConfig: ToolConfigOptions = {
    name: 'get_weather',
    description: 'Get current weather for a location',
    parameters: {
      type: 'object',
      properties: {
        location: { type: 'string', description: 'City name' },
        unit: { type: 'string', enum: ['celsius', 'fahrenheit'] },
      },
      required: ['location'],
    },
  };

  const calculatorToolConfig: ToolConfigOptions = {
    name: 'calculator',
    description: 'Perform mathematical calculations',
    parameters: {
      type: 'object',
      properties: {
        expression: { type: 'string', description: 'Math expression to evaluate' },
      },
      required: ['expression'],
    },
  };

  describe('constructor and validation', () => {
    it('should create valid tool config', () => {
      const tool = new ToolConfig(weatherToolConfig);

      expect(tool.name).toBe('get_weather');
      expect(tool.description).toBe('Get current weather for a location');
      expect(tool.parameters.type).toBe('object');
      expect(tool.parameters.properties).toHaveProperty('location');
    });

    it('should store optional function', () => {
      const mockFunc = async (location: string) => ({ temp: 72 });
      const tool = new ToolConfig({
        ...weatherToolConfig,
        function: mockFunc,
      });

      expect(tool.function).toBe(mockFunc);
    });

    it('should throw error for empty name', () => {
      expect(() => {
        new ToolConfig({
          ...weatherToolConfig,
          name: '',
        });
      }).toThrow('Tool name cannot be empty');
    });

    it('should throw error for whitespace-only name', () => {
      expect(() => {
        new ToolConfig({
          ...weatherToolConfig,
          name: '   ',
        });
      }).toThrow('Tool name cannot be empty');
    });

    it('should throw error for empty description', () => {
      expect(() => {
        new ToolConfig({
          ...weatherToolConfig,
          description: '',
        });
      }).toThrow('Tool description cannot be empty');
    });

    it('should throw error for whitespace-only description', () => {
      expect(() => {
        new ToolConfig({
          ...weatherToolConfig,
          description: '   ',
        });
      }).toThrow('Tool description cannot be empty');
    });

    it('should throw error for missing parameters', () => {
      expect(() => {
        new ToolConfig({
          name: 'test',
          description: 'Test tool',
          parameters: undefined as any,
        });
      }).toThrow('Tool parameters must be a dictionary (JSON schema)');
    });

    it('should throw error for non-object parameters', () => {
      expect(() => {
        new ToolConfig({
          name: 'test',
          description: 'Test tool',
          parameters: 'invalid' as any,
        });
      }).toThrow('Tool parameters must be a dictionary (JSON schema)');
    });

    it('should throw error for parameters without type=object', () => {
      expect(() => {
        new ToolConfig({
          name: 'test',
          description: 'Test tool',
          parameters: {
            type: 'string',
            properties: {},
          } as any,
        });
      }).toThrow("Tool parameters must be a JSON schema with type='object'");
    });

    it('should throw error for parameters without properties', () => {
      expect(() => {
        new ToolConfig({
          name: 'test',
          description: 'Test tool',
          parameters: {
            type: 'object',
          } as any,
        });
      }).toThrow('Tool parameters must have a properties object');
    });

    it('should throw error for parameters with non-object properties', () => {
      expect(() => {
        new ToolConfig({
          name: 'test',
          description: 'Test tool',
          parameters: {
            type: 'object',
            properties: 'invalid',
          } as any,
        });
      }).toThrow('Tool parameters must have a properties object');
    });

    it('should accept parameters with additional schema fields', () => {
      const tool = new ToolConfig({
        name: 'test',
        description: 'Test tool',
        parameters: {
          type: 'object',
          properties: { x: { type: 'number' } },
          additionalProperties: false,
          minProperties: 1,
        },
      });

      expect(tool.parameters.additionalProperties).toBe(false);
      expect(tool.parameters.minProperties).toBe(1);
    });
  });

  describe('fromFunction static method', () => {
    it('should create tool from function with explicit schema', () => {
      const getWeather = async (location: string, unit?: string) => {
        return { temp: 72, condition: 'sunny' };
      };

      const tool = ToolConfig.fromFunction(getWeather, {
        description: 'Get weather for a city',
        parameters: {
          type: 'object',
          properties: {
            location: { type: 'string', description: 'City name' },
            unit: { type: 'string', enum: ['celsius', 'fahrenheit'] },
          },
          required: ['location'],
        },
      });

      expect(tool.name).toBe('getWeather');
      expect(tool.description).toBe('Get weather for a city');
      expect(tool.function).toBe(getWeather);
    });

    it('should use custom name when provided', () => {
      const myFunc = () => 'result';
      const tool = ToolConfig.fromFunction(myFunc, {
        name: 'custom_name',
        description: 'Custom tool',
        parameters: {
          type: 'object',
          properties: {},
        },
      });

      expect(tool.name).toBe('custom_name');
    });

    it('should use function name when no name provided', () => {
      const calculateSum = (x: number, y: number) => x + y;
      const tool = ToolConfig.fromFunction(calculateSum, {
        description: 'Add two numbers',
        parameters: {
          type: 'object',
          properties: {
            x: { type: 'number' },
            y: { type: 'number' },
          },
          required: ['x', 'y'],
        },
      });

      expect(tool.name).toBe('calculateSum');
    });

    it('should throw error for anonymous function without name', () => {
      const anonFunc = () => 'result';
      Object.defineProperty(anonFunc, 'name', { value: '' });

      expect(() => {
        ToolConfig.fromFunction(anonFunc, {
          description: 'Test',
          parameters: {
            type: 'object',
            properties: {},
          },
        });
      }).toThrow('Function must have a name or you must provide a name option');
    });
  });

  describe('format conversion methods', () => {
    it('should convert to OpenAI format', () => {
      const tool = new ToolConfig(weatherToolConfig);
      const openaiFormat = tool.toOpenAIFormat();

      expect(openaiFormat.type).toBe('function');
      expect(openaiFormat.function.name).toBe('get_weather');
      expect(openaiFormat.function.description).toBe(
        'Get current weather for a location'
      );
      expect(openaiFormat.function.parameters).toEqual(weatherToolConfig.parameters);
    });

    it('should convert to Anthropic format', () => {
      const tool = new ToolConfig(weatherToolConfig);
      const anthropicFormat = tool.toAnthropicFormat();

      expect(anthropicFormat.name).toBe('get_weather');
      expect(anthropicFormat.description).toBe(
        'Get current weather for a location'
      );
      expect(anthropicFormat.input_schema).toEqual(weatherToolConfig.parameters);
    });

    it('should convert to universal format', () => {
      const tool = new ToolConfig(weatherToolConfig);
      const universalFormat = tool.toUniversalFormat();

      expect(universalFormat.name).toBe('get_weather');
      expect(universalFormat.description).toBe(
        'Get current weather for a location'
      );
      expect(universalFormat.parameters).toEqual(weatherToolConfig.parameters);
    });

    it('should preserve all parameter schema details', () => {
      const complexParams: ToolParameters = {
        type: 'object',
        properties: {
          query: { type: 'string', minLength: 1, maxLength: 100 },
          options: {
            type: 'object',
            properties: {
              limit: { type: 'integer', minimum: 1, maximum: 100 },
              sort: { type: 'string', enum: ['asc', 'desc'] },
            },
          },
        },
        required: ['query'],
      };

      const tool = new ToolConfig({
        name: 'search',
        description: 'Search database',
        parameters: complexParams,
      });

      const openaiFormat = tool.toOpenAIFormat();
      expect(openaiFormat.function.parameters).toEqual(complexParams);

      const anthropicFormat = tool.toAnthropicFormat();
      expect(anthropicFormat.input_schema).toEqual(complexParams);
    });
  });

  describe('clone method', () => {
    it('should create deep copy of tool config', () => {
      const original = new ToolConfig(weatherToolConfig);
      const cloned = original.clone();

      expect(cloned).not.toBe(original);
      expect(cloned.name).toBe(original.name);
      expect(cloned.description).toBe(original.description);
      expect(cloned.parameters).toEqual(original.parameters);
      expect(cloned.parameters).not.toBe(original.parameters);
    });

    it('should preserve function reference', () => {
      const mockFunc = () => 'result';
      const original = new ToolConfig({
        ...weatherToolConfig,
        function: mockFunc,
      });
      const cloned = original.clone();

      expect(cloned.function).toBe(mockFunc);
    });

    it('should create independent parameter copies', () => {
      const original = new ToolConfig(weatherToolConfig);
      const cloned = original.clone();

      // Modify cloned parameters
      cloned.parameters.properties.newProp = { type: 'string' };

      // Original should be unchanged
      expect(original.parameters.properties).not.toHaveProperty('newProp');
    });
  });

  describe('toJSON method', () => {
    it('should serialize to JSON-compatible object', () => {
      const tool = new ToolConfig(weatherToolConfig);
      const json = tool.toJSON();

      expect(json.name).toBe('get_weather');
      expect(json.description).toBe('Get current weather for a location');
      expect(json.parameters).toEqual(weatherToolConfig.parameters);
    });

    it('should exclude function from JSON', () => {
      const mockFunc = () => 'result';
      const tool = new ToolConfig({
        ...weatherToolConfig,
        function: mockFunc,
      });
      const json = tool.toJSON();

      expect(json).not.toHaveProperty('function');
    });

    it('should be serializable with JSON.stringify', () => {
      const tool = new ToolConfig(weatherToolConfig);
      expect(() => JSON.stringify(tool)).not.toThrow();

      const parsed = JSON.parse(JSON.stringify(tool));
      expect(parsed.name).toBe('get_weather');
    });
  });

  describe('createTool factory function', () => {
    it('should create ToolConfig instance', () => {
      const tool = createTool(weatherToolConfig);

      expect(tool).toBeInstanceOf(ToolConfig);
      expect(tool.name).toBe('get_weather');
    });

    it('should validate like constructor', () => {
      expect(() => {
        createTool({
          name: '',
          description: 'Test',
          parameters: { type: 'object', properties: {} },
        });
      }).toThrow('Tool name cannot be empty');
    });
  });

  describe('tool decorator', () => {
    it('should create ToolConfig from decorated function', () => {
      const getWeather = (city: string) => ({ temp: 72 });

      const weatherTool = tool({
        description: 'Get weather for a city',
        parameters: {
          type: 'object',
          properties: {
            city: { type: 'string', description: 'City name' },
          },
          required: ['city'],
        },
      })(getWeather);

      expect(weatherTool).toBeInstanceOf(ToolConfig);
      expect(weatherTool.name).toBe('getWeather');
      expect(weatherTool.description).toBe('Get weather for a city');
      expect(weatherTool.function).toBe(getWeather);
    });

    it('should support custom name in decorator', () => {
      const myFunc = () => 'result';

      const customTool = tool({
        name: 'custom_tool',
        description: 'Custom tool',
        parameters: {
          type: 'object',
          properties: {},
        },
      })(myFunc);

      expect(customTool.name).toBe('custom_tool');
    });
  });

  describe('inferJsonType helper', () => {
    it('should infer integer type', () => {
      expect(inferJsonType(42)).toBe('integer');
      expect(inferJsonType(0)).toBe('integer');
      expect(inferJsonType(-100)).toBe('integer');
    });

    it('should infer number type for floats', () => {
      expect(inferJsonType(3.14)).toBe('number');
      expect(inferJsonType(-2.5)).toBe('number');
    });

    it('should infer string type', () => {
      expect(inferJsonType('hello')).toBe('string');
      expect(inferJsonType('')).toBe('string');
    });

    it('should infer boolean type', () => {
      expect(inferJsonType(true)).toBe('boolean');
      expect(inferJsonType(false)).toBe('boolean');
    });

    it('should infer array type', () => {
      expect(inferJsonType([1, 2, 3])).toBe('array');
      expect(inferJsonType([])).toBe('array');
    });

    it('should infer object type', () => {
      expect(inferJsonType({ a: 1 })).toBe('object');
      expect(inferJsonType({})).toBe('object');
    });

    it('should handle null and undefined', () => {
      expect(inferJsonType(null)).toBe('string');
      expect(inferJsonType(undefined)).toBe('string');
    });
  });

  describe('buildParameterSchema helper', () => {
    it('should build schema with properties', () => {
      const schema = buildParameterSchema({
        name: { type: 'string', description: 'User name' },
        age: { type: 'integer', minimum: 0 },
      });

      expect(schema.type).toBe('object');
      expect(schema.properties).toHaveProperty('name');
      expect(schema.properties).toHaveProperty('age');
      expect(schema.required).toBeUndefined();
    });

    it('should include required fields', () => {
      const schema = buildParameterSchema(
        {
          name: { type: 'string' },
          age: { type: 'integer' },
        },
        ['name']
      );

      expect(schema.required).toEqual(['name']);
    });

    it('should handle empty required array', () => {
      const schema = buildParameterSchema(
        {
          name: { type: 'string' },
        },
        []
      );

      expect(schema.required).toBeUndefined();
    });

    it('should handle complex nested schemas', () => {
      const schema = buildParameterSchema({
        user: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            address: {
              type: 'object',
              properties: {
                street: { type: 'string' },
                city: { type: 'string' },
              },
            },
          },
        },
      });

      expect(schema.type).toBe('object');
      expect(schema.properties.user.properties).toHaveProperty('name');
      expect(schema.properties.user.properties).toHaveProperty('address');
    });
  });

  describe('edge cases', () => {
    it('should handle empty properties object', () => {
      const tool = new ToolConfig({
        name: 'no_params',
        description: 'Tool with no parameters',
        parameters: {
          type: 'object',
          properties: {},
        },
      });

      expect(tool.parameters.properties).toEqual({});
    });

    it('should handle parameters with no required fields', () => {
      const tool = new ToolConfig({
        name: 'optional_params',
        description: 'All optional params',
        parameters: {
          type: 'object',
          properties: {
            x: { type: 'number' },
            y: { type: 'number' },
          },
        },
      });

      expect(tool.parameters.required).toBeUndefined();
    });

    it('should handle async functions', () => {
      const asyncFunc = async (x: number) => x * 2;
      const tool = ToolConfig.fromFunction(asyncFunc, {
        description: 'Async tool',
        parameters: {
          type: 'object',
          properties: { x: { type: 'number' } },
          required: ['x'],
        },
      });

      expect(tool.function).toBe(asyncFunc);
    });

    it('should handle very long descriptions', () => {
      const longDesc = 'A'.repeat(1000);
      const tool = new ToolConfig({
        name: 'long_desc',
        description: longDesc,
        parameters: {
          type: 'object',
          properties: {},
        },
      });

      expect(tool.description).toBe(longDesc);
      expect(tool.description.length).toBe(1000);
    });

    it('should handle special characters in name', () => {
      const tool = new ToolConfig({
        name: 'get_weather_v2',
        description: 'Weather tool v2',
        parameters: {
          type: 'object',
          properties: {},
        },
      });

      expect(tool.name).toBe('get_weather_v2');
    });

    it('should handle complex enum constraints', () => {
      const tool = new ToolConfig({
        name: 'enum_test',
        description: 'Test enums',
        parameters: {
          type: 'object',
          properties: {
            status: {
              type: 'string',
              enum: ['pending', 'active', 'completed', 'archived'],
            },
          },
          required: ['status'],
        },
      });

      expect(tool.parameters.properties.status.enum).toHaveLength(4);
    });
  });

  describe('real-world usage examples', () => {
    it('should create database query tool', () => {
      const dbTool = new ToolConfig({
        name: 'query_database',
        description: 'Execute SQL query on database',
        parameters: {
          type: 'object',
          properties: {
            query: { type: 'string', description: 'SQL query to execute' },
            database: { type: 'string', description: 'Database name' },
            timeout: { type: 'integer', minimum: 1, maximum: 300 },
          },
          required: ['query', 'database'],
        },
      });

      expect(dbTool.name).toBe('query_database');
      expect(dbTool.parameters.required).toContain('query');
    });

    it('should create API call tool', () => {
      const apiTool = new ToolConfig({
        name: 'call_api',
        description: 'Make HTTP API request',
        parameters: {
          type: 'object',
          properties: {
            url: { type: 'string', format: 'uri' },
            method: { type: 'string', enum: ['GET', 'POST', 'PUT', 'DELETE'] },
            headers: { type: 'object' },
            body: { type: 'object' },
          },
          required: ['url', 'method'],
        },
      });

      expect(apiTool.toOpenAIFormat().function.parameters.properties.method.enum).toContain(
        'GET'
      );
    });

    it('should create file operation tool', () => {
      const fileTool = new ToolConfig({
        name: 'read_file',
        description: 'Read file contents',
        parameters: {
          type: 'object',
          properties: {
            path: { type: 'string', description: 'File path' },
            encoding: { type: 'string', enum: ['utf-8', 'ascii', 'base64'] },
          },
          required: ['path'],
        },
      });

      const anthropicFormat = fileTool.toAnthropicFormat();
      expect(anthropicFormat.input_schema.properties.encoding.enum).toContain(
        'utf-8'
      );
    });
  });
});
