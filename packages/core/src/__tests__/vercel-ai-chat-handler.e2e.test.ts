import { describe, it, expect } from 'vitest';
import { processDataStream } from 'ai';
import { CascadeAgent } from '../agent';
import { createChatHandler } from '../vercel-ai/ui';
import type { Tool } from '../types';

const describeIf = (condition: boolean) => (condition ? describe : describe.skip);

describeIf(Boolean(process.env.OPENAI_API_KEY))('VercelAI.createChatHandler (E2E)', () => {
  it(
    'streams tool call parts via data protocol when the model emits a tool call',
    async () => {
      const tools: Tool[] = [
        {
          type: 'function',
          function: {
            name: 'get_weather',
            description: 'Get weather for a city',
            parameters: {
              type: 'object',
              properties: { location: { type: 'string' } },
              required: ['location'],
            },
          },
        },
      ];

      // Single-model agent to avoid cascade behavior affecting tool-call determinism.
      const agent = new CascadeAgent({
        models: [
          {
            name: process.env.OPENAI_MODEL ?? 'gpt-4o-mini',
            provider: 'openai',
            // Cost values in this repo are per 1M tokens in some places; the exact value is irrelevant for this test.
            cost: 0.15,
            apiKey: process.env.OPENAI_API_KEY,
          },
        ],
      });

      const handler = createChatHandler(agent, {
        protocol: 'data',
        systemPrompt:
          "You MUST call the tool 'get_weather' exactly once with {\"location\":\"Paris\"}. Do not write any other text.",
        tools,
      });

      const req = new Request('http://local/api/chat', {
        method: 'POST',
        body: JSON.stringify({
          messages: [{ role: 'user', content: 'What is the weather?' }],
        }),
        headers: { 'Content-Type': 'application/json' },
      });

      const res = await handler(req);
      expect(res.ok).toBe(true);
      expect(res.body).toBeTruthy();

      const toolCalls: any[] = [];
      await processDataStream({
        stream: res.body!,
        onToolCallPart(value: any) {
          toolCalls.push(value);
        },
      });

      expect(toolCalls.length).toBeGreaterThan(0);
      expect(toolCalls[0]?.toolName).toBe('get_weather');
    },
    60000
  );
});
