import { describe, expect, it } from 'vitest';
import { processDataStream } from 'ai';
import { CascadeAgent } from '../agent';
import { createChatHandler } from '../vercel-ai/ui';
import type { Tool } from '../types';

const describeIf = (condition: boolean) => (condition ? describe : describe.skip);

type ToolCallPart = {
  toolCallId: string;
  toolName: string;
  args: Record<string, unknown> | string;
};

async function collectDataStream(response: Response): Promise<{ text: string; toolCalls: ToolCallPart[] }> {
  let text = '';
  const toolCalls: ToolCallPart[] = [];

  await processDataStream({
    stream: response.body!,
    onTextPart(value: string) {
      text += value;
    },
    onToolCallPart(value: any) {
      toolCalls.push(value as ToolCallPart);
    },
  });

  return { text, toolCalls };
}

describeIf(Boolean(process.env.OPENAI_API_KEY))('VercelAI agent progression (E2E)', () => {
  const tools: Tool[] = [
    {
      type: 'function',
      function: {
        name: 'get_weather',
        description: 'Get weather for a city',
        parameters: {
          type: 'object',
          properties: {
            location: { type: 'string' },
          },
          required: ['location'],
        },
      },
    },
    {
      type: 'function',
      function: {
        name: 'get_calendar',
        description: 'Get calendar slots for a date',
        parameters: {
          type: 'object',
          properties: {
            date: { type: 'string' },
          },
          required: ['date'],
        },
      },
    },
  ];

  const agent = new CascadeAgent({
    models: [
      {
        name: process.env.OPENAI_TOOL_MODEL ?? 'gpt-4o-mini',
        provider: 'openai',
        cost: 0.15,
        apiKey: process.env.OPENAI_API_KEY,
      },
    ],
  });

  it(
    'stage 1: trivial text chat works with message list',
    async () => {
      const handler = createChatHandler(agent, { protocol: 'data' });
      const req = new Request('http://local/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [
            { role: 'user', content: 'Reply with EXACTLY: TRIVIAL_OK' },
          ],
        }),
      });

      const res = await handler(req);
      expect(res.ok).toBe(true);

      const { text } = await collectDataStream(res);
      expect(text.toUpperCase()).toContain('TRIVIAL_OK');
    },
    60000
  );

  it(
    'stage 2: single tool call can be forced and emitted in stream',
    async () => {
      const handler = createChatHandler(agent, {
        protocol: 'data',
        tools,
        systemPrompt:
          "You MUST call the tool 'get_weather' exactly once with {\"location\":\"Berlin\"}. No normal text.",
        extra: {
          tool_choice: { type: 'function', function: { name: 'get_weather' } },
        },
      });

      const req = new Request('http://local/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'user', content: 'Plan my day.' }],
        }),
      });

      const res = await handler(req);
      expect(res.ok).toBe(true);

      const { toolCalls } = await collectDataStream(res);
      expect(toolCalls.length).toBeGreaterThan(0);
      expect(toolCalls[0]?.toolName).toBe('get_weather');
    },
    60000
  );

  it(
    'stage 3/4: tool-loop style continuation works with multi-tool message list payload',
    async () => {
      const handler = createChatHandler(agent, {
        protocol: 'data',
        systemPrompt:
          'Summarize tool results in one line with format WEATHER=<weather>; SLOTS=<slots>.',
      });

      const req = new Request('http://local/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [
            { role: 'user', content: 'Use tools and summarize.' },
            {
              role: 'assistant',
              content: '',
              tool_calls: [
                {
                  id: 'call_weather',
                  type: 'function',
                  function: { name: 'get_weather', arguments: '{"location":"Berlin"}' },
                },
                {
                  id: 'call_calendar',
                  type: 'function',
                  function: { name: 'get_calendar', arguments: '{"date":"2026-02-19"}' },
                },
              ],
            },
            {
              role: 'tool',
              tool_call_id: 'call_weather',
              name: 'get_weather',
              content: '{"weather":"sunny"}',
            },
            {
              role: 'tool',
              tool_call_id: 'call_calendar',
              name: 'get_calendar',
              content: '{"slots":"2"}',
            },
          ],
        }),
      });

      const res = await handler(req);
      expect(res.ok).toBe(true);

      const { text } = await collectDataStream(res);
      expect(text.toUpperCase()).toContain('WEATHER=');
      expect(text.toUpperCase()).toContain('SLOTS=');
    },
    60000
  );
});
