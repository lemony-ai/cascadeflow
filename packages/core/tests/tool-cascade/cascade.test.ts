import { describe, expect, it } from 'vitest';
import { ToolCascade } from '../../src/tool-cascade/cascade';
import type { ToolCallGenerator } from '../../src/tool-cascade/types';
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

describe('ToolCascade', () => {
  it('retries with feedback until validation passes', async () => {
    const cascade = new ToolCascade({ maxRetries: 1 });

    const generator: ToolCallGenerator = async (_context, feedback): Promise<ToolCall[]> => {
      if (!feedback) {
        return [
          {
            id: 'draft',
            type: 'function',
            function: {
              name: 'get_weather',
              arguments: JSON.stringify({ location: 'TODO' }),
            },
          },
        ];
      }

      return [
        {
          id: 'retry',
          type: 'function',
          function: {
            name: 'get_weather',
            arguments: JSON.stringify({ location: 'Paris' }),
          },
        },
      ];
    };

    const result = await cascade.execute(
      {
        query: 'What is the weather in Paris?',
        tools: [weatherTool],
      },
      generator
    );

    expect(result.accepted).toBe(true);
    expect(result.attempts).toBe(2);
    expect(result.toolCalls[0].function.arguments).toContain('Paris');
  });
});
