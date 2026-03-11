import { describe, expect, it } from 'vitest';

import { CascadeFlowAgentExecutor } from '../CascadeFlowAgent.node';

const aiMessage = (content: string, extras: Record<string, any> = {}) => ({
  role: 'ai',
  content,
  _getType: () => 'ai',
  ...extras,
});

describe('CascadeFlowAgentExecutor', () => {
  it('normalizes plain role/content objects and preserves system prompts', async () => {
    let captured: any[] = [];

    const cascadeModel = {
      invoke: async (messages: any[]) => {
        captured = messages;
        return aiMessage('ok');
      },
      invokeVerifierDirect: async () => aiMessage('verifier'),
      stream: async function* () {
        yield aiMessage('stream');
      },
    } as any;

    const exec = new CascadeFlowAgentExecutor(cascadeModel, [], [], 3);
    await exec.invoke({
      messages: [
        { role: 'system', content: 'You are a helpful assistant.' },
        { role: 'user', content: 'Hello' },
      ],
    });

    expect(captured).toHaveLength(2);
    expect(captured[0].role).toBe('system');
    expect(captured[0].content).toBe('You are a helpful assistant.');
    expect(captured[1].role).toBe('human');
    expect(captured[1].content).toBe('Hello');
  });

  it('executes tool calls and returns final response when tool loop ends', async () => {
    const tool = {
      name: 'echo',
      invoke: async (args: any) => ({ echoed: args }),
    };

    let call = 0;
    const cascadeModel = {
      invoke: async () => {
        call += 1;
        if (call === 1) {
          return aiMessage('calling tool', {
            additional_kwargs: {
              tool_calls: [
                {
                  id: 't1',
                  function: { name: 'echo', arguments: JSON.stringify({ a: 1 }) },
                },
              ],
            },
          });
        }
        return aiMessage('done');
      },
      invokeVerifierDirect: async () => aiMessage('verifier'),
      stream: async function* () {
        yield aiMessage('stream');
      },
    } as any;

    const exec = new CascadeFlowAgentExecutor(cascadeModel, [tool as any], [], 3);
    const result = await exec.invoke('hi');

    expect(result).toMatchObject({ output: 'done' });
    expect(Array.isArray(result.trace)).toBe(true);
    expect(result.trace.length).toBeGreaterThanOrEqual(2);
  });

  it('routes to verifier after tool call when routing rule matches', async () => {
    const tool = {
      name: 'echo',
      invoke: async (args: any) => ({ echoed: args }),
    };

    let verifierCalled = 0;
    const cascadeModel = {
      invoke: async () =>
        aiMessage('calling tool', {
          additional_kwargs: {
            tool_calls: [
              {
                id: 't1',
                function: { name: 'echo', arguments: JSON.stringify({ a: 1 }) },
              },
            ],
          },
        }),
      invokeVerifierDirect: async () => {
        verifierCalled += 1;
        return aiMessage('verifier');
      },
      stream: async function* () {
        yield aiMessage('stream');
      },
    } as any;

    const exec = new CascadeFlowAgentExecutor(
      cascadeModel,
      [tool as any],
      [{ toolName: 'echo', routing: 'verifier' }],
      3,
    );
    const result = await exec.invoke('hi');

    expect(verifierCalled).toBe(1);
    expect(result.output).toBe('verifier');
  });
});
