/**
 * Tests for ToolCall parsing and standardization
 *
 * Tests parsing from different provider formats:
 * - OpenAI format
 * - Anthropic format
 * - Ollama format
 * - vLLM format
 * - Generic fromProvider() method
 *
 * Run: pnpm test call.test.ts
 */

import { describe, it, expect } from 'vitest';
import { ToolCall } from '../../tools/call';
import { ToolCallFormat } from '../../tools/formats';

describe('ToolCall', () => {
  describe('constructor', () => {
    it('should create tool call with all fields', () => {
      const call = new ToolCall({
        id: 'call_abc123',
        name: 'get_weather',
        arguments: { location: 'Paris', unit: 'celsius' },
        providerFormat: ToolCallFormat.OPENAI,
      });

      expect(call.id).toBe('call_abc123');
      expect(call.name).toBe('get_weather');
      expect(call.arguments).toEqual({ location: 'Paris', unit: 'celsius' });
      expect(call.providerFormat).toBe(ToolCallFormat.OPENAI);
    });

    it('should create tool call with minimal fields', () => {
      const call = new ToolCall({
        id: 'call_1',
        name: 'simple_tool',
        arguments: {},
        providerFormat: ToolCallFormat.ANTHROPIC,
      });

      expect(call.id).toBe('call_1');
      expect(call.name).toBe('simple_tool');
      expect(call.arguments).toEqual({});
      expect(call.providerFormat).toBe(ToolCallFormat.ANTHROPIC);
    });
  });

  describe('fromOpenAI', () => {
    it('should parse OpenAI format with string arguments', () => {
      const rawCall = {
        id: 'call_abc123',
        type: 'function',
        function: {
          name: 'get_weather',
          arguments: '{"location": "Paris", "unit": "celsius"}',
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);

      expect(call.id).toBe('call_abc123');
      expect(call.name).toBe('get_weather');
      expect(call.arguments).toEqual({ location: 'Paris', unit: 'celsius' });
      expect(call.providerFormat).toBe(ToolCallFormat.OPENAI);
    });

    it('should parse OpenAI format with object arguments', () => {
      const rawCall = {
        id: 'call_xyz',
        type: 'function',
        function: {
          name: 'calculator',
          arguments: { operation: 'add', x: 5, y: 3 },
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);

      expect(call.id).toBe('call_xyz');
      expect(call.name).toBe('calculator');
      expect(call.arguments).toEqual({ operation: 'add', x: 5, y: 3 });
      expect(call.providerFormat).toBe(ToolCallFormat.OPENAI);
    });

    it('should parse OpenAI format with empty arguments', () => {
      const rawCall = {
        id: 'call_empty',
        type: 'function',
        function: {
          name: 'no_args_tool',
          arguments: '{}',
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);

      expect(call.id).toBe('call_empty');
      expect(call.name).toBe('no_args_tool');
      expect(call.arguments).toEqual({});
    });

    it('should handle malformed JSON arguments', () => {
      const rawCall = {
        id: 'call_bad',
        type: 'function',
        function: {
          name: 'broken_tool',
          arguments: '{"invalid": json}', // Invalid JSON
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);

      expect(call.id).toBe('call_bad');
      expect(call.name).toBe('broken_tool');
      expect(call.arguments).toEqual({}); // Should fallback to empty object
    });

    it('should handle missing arguments field', () => {
      const rawCall = {
        id: 'call_missing',
        type: 'function',
        function: {
          name: 'missing_args_tool',
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);

      expect(call.id).toBe('call_missing');
      expect(call.name).toBe('missing_args_tool');
      expect(call.arguments).toEqual({});
    });

    it('should handle missing id field', () => {
      const rawCall = {
        type: 'function',
        function: {
          name: 'no_id_tool',
          arguments: '{"test": true}',
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);

      expect(call.id).toBe('unknown'); // Fallback to 'unknown'
      expect(call.name).toBe('no_id_tool');
      expect(call.arguments).toEqual({ test: true });
    });

    it('should handle missing name field', () => {
      const rawCall = {
        id: 'call_no_name',
        type: 'function',
        function: {
          arguments: '{"data": "value"}',
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);

      expect(call.id).toBe('call_no_name');
      expect(call.name).toBe('unknown'); // Fallback to 'unknown'
      expect(call.arguments).toEqual({ data: 'value' });
    });

    it('should handle nested arguments', () => {
      const rawCall = {
        id: 'call_nested',
        type: 'function',
        function: {
          name: 'complex_tool',
          arguments: '{"config": {"host": "localhost", "port": 8080}, "options": ["a", "b"]}',
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);

      expect(call.arguments).toEqual({
        config: { host: 'localhost', port: 8080 },
        options: ['a', 'b'],
      });
    });
  });

  describe('fromAnthropic', () => {
    it('should parse Anthropic format', () => {
      const rawCall = {
        type: 'tool_use',
        id: 'toolu_abc123',
        name: 'get_weather',
        input: {
          location: 'Paris',
          unit: 'celsius',
        },
      };

      const call = ToolCall.fromAnthropic(rawCall);

      expect(call.id).toBe('toolu_abc123');
      expect(call.name).toBe('get_weather');
      expect(call.arguments).toEqual({ location: 'Paris', unit: 'celsius' });
      expect(call.providerFormat).toBe(ToolCallFormat.ANTHROPIC);
    });

    it('should parse Anthropic format with empty input', () => {
      const rawCall = {
        type: 'tool_use',
        id: 'toolu_empty',
        name: 'no_input_tool',
        input: {},
      };

      const call = ToolCall.fromAnthropic(rawCall);

      expect(call.id).toBe('toolu_empty');
      expect(call.name).toBe('no_input_tool');
      expect(call.arguments).toEqual({});
    });

    it('should parse Anthropic format with missing input', () => {
      const rawCall = {
        type: 'tool_use',
        id: 'toolu_missing',
        name: 'missing_input_tool',
      };

      const call = ToolCall.fromAnthropic(rawCall);

      expect(call.id).toBe('toolu_missing');
      expect(call.name).toBe('missing_input_tool');
      expect(call.arguments).toEqual({});
    });

    it('should handle missing id in Anthropic format', () => {
      const rawCall = {
        type: 'tool_use',
        name: 'no_id_tool',
        input: { data: 'test' },
      };

      const call = ToolCall.fromAnthropic(rawCall);

      expect(call.id).toBe('unknown');
      expect(call.name).toBe('no_id_tool');
      expect(call.arguments).toEqual({ data: 'test' });
    });

    it('should handle missing name in Anthropic format', () => {
      const rawCall = {
        type: 'tool_use',
        id: 'toolu_no_name',
        input: { data: 'test' },
      };

      const call = ToolCall.fromAnthropic(rawCall);

      expect(call.id).toBe('toolu_no_name');
      expect(call.name).toBe('unknown');
      expect(call.arguments).toEqual({ data: 'test' });
    });

    it('should parse Anthropic format with complex input', () => {
      const rawCall = {
        type: 'tool_use',
        id: 'toolu_complex',
        name: 'search_tool',
        input: {
          query: 'TypeScript',
          filters: {
            date_range: '2024',
            categories: ['programming', 'docs'],
          },
          max_results: 10,
        },
      };

      const call = ToolCall.fromAnthropic(rawCall);

      expect(call.arguments).toEqual({
        query: 'TypeScript',
        filters: {
          date_range: '2024',
          categories: ['programming', 'docs'],
        },
        max_results: 10,
      });
    });
  });

  describe('fromOllama', () => {
    it('should parse Ollama format (same as OpenAI)', () => {
      const rawCall = {
        id: 'call_ollama',
        type: 'function',
        function: {
          name: 'get_weather',
          arguments: '{"location": "Tokyo"}',
        },
      };

      const call = ToolCall.fromOllama(rawCall);

      expect(call.id).toBe('call_ollama');
      expect(call.name).toBe('get_weather');
      expect(call.arguments).toEqual({ location: 'Tokyo' });
      expect(call.providerFormat).toBe(ToolCallFormat.OPENAI); // Uses OpenAI format
    });

    it('should handle Ollama format with object arguments', () => {
      const rawCall = {
        id: 'call_ollama_obj',
        type: 'function',
        function: {
          name: 'calculator',
          arguments: { x: 10, y: 20, op: 'multiply' },
        },
      };

      const call = ToolCall.fromOllama(rawCall);

      expect(call.arguments).toEqual({ x: 10, y: 20, op: 'multiply' });
    });
  });

  describe('fromVLLM', () => {
    it('should parse vLLM format (same as OpenAI)', () => {
      const rawCall = {
        id: 'call_vllm',
        type: 'function',
        function: {
          name: 'search',
          arguments: '{"query": "vLLM"}',
        },
      };

      const call = ToolCall.fromVLLM(rawCall);

      expect(call.id).toBe('call_vllm');
      expect(call.name).toBe('search');
      expect(call.arguments).toEqual({ query: 'vLLM' });
      expect(call.providerFormat).toBe(ToolCallFormat.OPENAI); // Uses OpenAI format
    });

    it('should handle vLLM format with complex arguments', () => {
      const rawCall = {
        id: 'call_vllm_complex',
        type: 'function',
        function: {
          name: 'advanced_search',
          arguments: '{"query": "test", "options": {"limit": 5}}',
        },
      };

      const call = ToolCall.fromVLLM(rawCall);

      expect(call.arguments).toEqual({
        query: 'test',
        options: { limit: 5 },
      });
    });
  });

  describe('fromProvider', () => {
    describe('OpenAI-compatible providers', () => {
      it('should parse from openai provider', () => {
        const rawCall = {
          id: 'call_1',
          function: {
            name: 'test_tool',
            arguments: '{"param": "value"}',
          },
        };

        const call = ToolCall.fromProvider('openai', rawCall);

        expect(call.name).toBe('test_tool');
        expect(call.arguments).toEqual({ param: 'value' });
      });

      it('should parse from groq provider (OpenAI format)', () => {
        const rawCall = {
          id: 'call_groq',
          function: {
            name: 'groq_tool',
            arguments: '{"data": "test"}',
          },
        };

        const call = ToolCall.fromProvider('groq', rawCall);

        expect(call.name).toBe('groq_tool');
        expect(call.providerFormat).toBe(ToolCallFormat.OPENAI);
      });

      it('should parse from together provider (OpenAI format)', () => {
        const rawCall = {
          id: 'call_together',
          function: {
            name: 'together_tool',
            arguments: '{"value": 123}',
          },
        };

        const call = ToolCall.fromProvider('together', rawCall);

        expect(call.name).toBe('together_tool');
        expect(call.providerFormat).toBe(ToolCallFormat.OPENAI);
      });

      it('should parse from huggingface provider (OpenAI format)', () => {
        const rawCall = {
          id: 'call_hf',
          function: {
            name: 'hf_tool',
            arguments: '{}',
          },
        };

        const call = ToolCall.fromProvider('huggingface', rawCall);

        expect(call.name).toBe('hf_tool');
        expect(call.providerFormat).toBe(ToolCallFormat.OPENAI);
      });
    });

    describe('Anthropic provider', () => {
      it('should parse from anthropic provider', () => {
        const rawCall = {
          type: 'tool_use',
          id: 'toolu_123',
          name: 'claude_tool',
          input: { param: 'value' },
        };

        const call = ToolCall.fromProvider('anthropic', rawCall);

        expect(call.name).toBe('claude_tool');
        expect(call.arguments).toEqual({ param: 'value' });
        expect(call.providerFormat).toBe(ToolCallFormat.ANTHROPIC);
      });
    });

    describe('Ollama provider', () => {
      it('should parse from ollama provider', () => {
        const rawCall = {
          id: 'call_ollama',
          function: {
            name: 'ollama_tool',
            arguments: '{"local": true}',
          },
        };

        const call = ToolCall.fromProvider('ollama', rawCall);

        expect(call.name).toBe('ollama_tool');
        expect(call.arguments).toEqual({ local: true });
      });
    });

    describe('vLLM provider', () => {
      it('should parse from vllm provider', () => {
        const rawCall = {
          id: 'call_vllm',
          function: {
            name: 'vllm_tool',
            arguments: '{"endpoint": "/api/v1"}',
          },
        };

        const call = ToolCall.fromProvider('vllm', rawCall);

        expect(call.name).toBe('vllm_tool');
        expect(call.arguments).toEqual({ endpoint: '/api/v1' });
      });
    });

    describe('case insensitivity', () => {
      it('should handle uppercase provider names', () => {
        const rawCall = {
          id: 'call_upper',
          function: {
            name: 'test',
            arguments: '{}',
          },
        };

        const call = ToolCall.fromProvider('OPENAI', rawCall);
        expect(call.name).toBe('test');
      });

      it('should handle mixed case provider names', () => {
        const rawCall = {
          type: 'tool_use',
          id: 'toolu_mixed',
          name: 'test',
          input: {},
        };

        const call = ToolCall.fromProvider('AnThRoPiC', rawCall);
        expect(call.name).toBe('test');
        expect(call.providerFormat).toBe(ToolCallFormat.ANTHROPIC);
      });
    });

    describe('unknown providers', () => {
      it('should try OpenAI format as fallback for unknown provider', () => {
        const rawCall = {
          id: 'call_unknown',
          function: {
            name: 'unknown_provider_tool',
            arguments: '{"test": true}',
          },
        };

        const call = ToolCall.fromProvider('unknown_provider', rawCall);

        expect(call.name).toBe('unknown_provider_tool');
        expect(call.arguments).toEqual({ test: true });
      });

      it('should use fallback values for unknown provider with invalid format', () => {
        const rawCall = {
          invalid: 'format',
        };

        // Should use OpenAI format as fallback, which uses 'unknown' for missing fields
        const call = ToolCall.fromProvider('unknown_provider', rawCall);

        expect(call.id).toBe('unknown');
        expect(call.name).toBe('unknown');
        expect(call.arguments).toEqual({});
      });
    });
  });

  describe('toJSON', () => {
    it('should convert tool call to JSON object', () => {
      const call = new ToolCall({
        id: 'call_json',
        name: 'json_tool',
        arguments: { key: 'value' },
        providerFormat: ToolCallFormat.OPENAI,
      });

      const json = call.toJSON();

      expect(json).toEqual({
        id: 'call_json',
        name: 'json_tool',
        arguments: { key: 'value' },
        providerFormat: ToolCallFormat.OPENAI,
      });
    });

    it('should serialize complex arguments', () => {
      const call = new ToolCall({
        id: 'call_complex',
        name: 'complex_tool',
        arguments: {
          nested: {
            deep: {
              value: 123,
            },
          },
          array: [1, 2, 3],
        },
        providerFormat: ToolCallFormat.ANTHROPIC,
      });

      const json = call.toJSON();

      expect(json.arguments).toEqual({
        nested: {
          deep: {
            value: 123,
          },
        },
        array: [1, 2, 3],
      });
    });

    it('should be serializable to JSON string', () => {
      const call = new ToolCall({
        id: 'call_stringify',
        name: 'stringify_tool',
        arguments: { test: true },
        providerFormat: ToolCallFormat.OPENAI,
      });

      const jsonString = JSON.stringify(call.toJSON());
      const parsed = JSON.parse(jsonString);

      expect(parsed.id).toBe('call_stringify');
      expect(parsed.name).toBe('stringify_tool');
      expect(parsed.arguments).toEqual({ test: true });
    });
  });

  describe('edge cases', () => {
    it('should handle empty provider string', () => {
      const rawCall = {
        id: 'call_empty_provider',
        function: {
          name: 'test',
          arguments: '{}',
        },
      };

      // Empty string should try OpenAI format as fallback
      const call = ToolCall.fromProvider('', rawCall);
      expect(call.name).toBe('test');
    });

    it('should handle null arguments in OpenAI format', () => {
      const rawCall = {
        id: 'call_null_args',
        function: {
          name: 'test',
          arguments: null,
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);
      expect(call.arguments).toEqual({}); // Should default to empty object
    });

    it('should handle undefined arguments in OpenAI format', () => {
      const rawCall = {
        id: 'call_undefined_args',
        function: {
          name: 'test',
          arguments: undefined,
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);
      expect(call.arguments).toEqual({}); // Should default to empty object
    });

    it('should handle numeric arguments in JSON string', () => {
      const rawCall = {
        id: 'call_numbers',
        function: {
          name: 'math_tool',
          arguments: '{"x": 123.45, "y": -67, "z": 0}',
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);
      expect(call.arguments).toEqual({ x: 123.45, y: -67, z: 0 });
    });

    it('should handle boolean arguments in JSON string', () => {
      const rawCall = {
        id: 'call_booleans',
        function: {
          name: 'bool_tool',
          arguments: '{"enabled": true, "disabled": false}',
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);
      expect(call.arguments).toEqual({ enabled: true, disabled: false });
    });

    it('should handle null values in arguments', () => {
      const rawCall = {
        id: 'call_null_values',
        function: {
          name: 'null_tool',
          arguments: '{"nullable": null, "value": "test"}',
        },
      };

      const call = ToolCall.fromOpenAI(rawCall);
      expect(call.arguments).toEqual({ nullable: null, value: 'test' });
    });
  });

  describe('real-world examples', () => {
    it('should parse real OpenAI weather tool call', () => {
      const realCall = {
        id: 'call_ZvKwW1JcT3XFTmHUv1aBCyKZ',
        type: 'function',
        function: {
          name: 'get_current_weather',
          arguments: '{\n  "location": "San Francisco, CA",\n  "unit": "fahrenheit"\n}',
        },
      };

      const call = ToolCall.fromOpenAI(realCall);

      expect(call.id).toBe('call_ZvKwW1JcT3XFTmHUv1aBCyKZ');
      expect(call.name).toBe('get_current_weather');
      expect(call.arguments).toEqual({
        location: 'San Francisco, CA',
        unit: 'fahrenheit',
      });
    });

    it('should parse real Anthropic calculator tool call', () => {
      const realCall = {
        type: 'tool_use',
        id: 'toolu_01A09q90qw90lq917835lq9',
        name: 'calculator',
        input: {
          operation: 'multiply',
          a: 1984135,
          b: 9343116,
        },
      };

      const call = ToolCall.fromAnthropic(realCall);

      expect(call.id).toBe('toolu_01A09q90qw90lq917835lq9');
      expect(call.name).toBe('calculator');
      expect(call.arguments).toEqual({
        operation: 'multiply',
        a: 1984135,
        b: 9343116,
      });
    });

    it('should parse real multi-parameter search tool call', () => {
      const realCall = {
        id: 'call_search_123',
        type: 'function',
        function: {
          name: 'web_search',
          arguments:
            '{"query":"TypeScript generics","filters":{"date":"last_year","language":"en"},"max_results":10,"include_snippets":true}',
        },
      };

      const call = ToolCall.fromOpenAI(realCall);

      expect(call.arguments).toEqual({
        query: 'TypeScript generics',
        filters: {
          date: 'last_year',
          language: 'en',
        },
        max_results: 10,
        include_snippets: true,
      });
    });
  });
});
