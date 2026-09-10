import { describe, expect, it } from 'vitest';

import { AIMessage, HumanMessage, SystemMessage } from '@langchain/core/messages';

import { CascadeFlowAgentExecutor, persistTurnToMemory } from '../CascadeFlowAgent.node';

describe('CascadeFlowAgentExecutor', () => {
  it('normalizes plain role/content objects and preserves system prompts', async () => {
    let captured: any[] = [];

    const cascadeModel = {
      invoke: async (messages: any[]) => {
        captured = messages;
        return new AIMessage('ok');
      },
      invokeVerifierDirect: async () => new AIMessage('verifier'),
      stream: async function* () {
        yield new AIMessage('stream');
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
    expect(captured[0]).toBeInstanceOf(SystemMessage);
    expect(captured[0].content).toBe('You are a helpful assistant.');
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
          const msg = new AIMessage('calling tool');
          (msg as any).additional_kwargs = {
            tool_calls: [
              {
                id: 't1',
                function: { name: 'echo', arguments: JSON.stringify({ a: 1 }) },
              },
            ],
          };
          return msg;
        }
        return new AIMessage('done');
      },
      invokeVerifierDirect: async () => new AIMessage('verifier'),
      stream: async function* () {
        yield new AIMessage('stream');
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
      invoke: async () => {
        const msg = new AIMessage('calling tool');
        (msg as any).additional_kwargs = {
          tool_calls: [
            {
              id: 't1',
              function: { name: 'echo', arguments: JSON.stringify({ a: 1 }) },
            },
          ],
        };
        return msg;
      },
      invokeVerifierDirect: async () => {
        verifierCalled += 1;
        return new AIMessage('verifier');
      },
      stream: async function* () {
        yield new AIMessage('stream');
      },
    } as any;

    const exec = new CascadeFlowAgentExecutor(
      cascadeModel,
      [tool as any],
      [{ toolName: 'echo', routing: 'verifier' }],
      3
    );
    const result = await exec.invoke('hi');

    expect(verifierCalled).toBe(1);
    expect(result.output).toBe('verifier');
  });

  it('passes the connected tools to the cascade model so models can emit tool calls', async () => {
    const tool = {
      name: 'echo',
      description: 'echoes its input',
      invoke: async (args: any) => ({ echoed: args }),
    };

    const invokeOptions: any[] = [];
    const verifierOptions: any[] = [];
    let call = 0;
    const cascadeModel = {
      invoke: async (_messages: any[], options?: any) => {
        invokeOptions.push(options);
        call += 1;
        if (call === 1) {
          const msg = new AIMessage('calling tool');
          (msg as any).additional_kwargs = {
            tool_calls: [{ id: 't1', function: { name: 'echo', arguments: '{}' } }],
          };
          return msg;
        }
        return new AIMessage('done');
      },
      invokeVerifierDirect: async (_messages: any[], options?: any) => {
        verifierOptions.push(options);
        return new AIMessage('verifier');
      },
      stream: async function* () {
        yield new AIMessage('stream');
      },
    } as any;

    const exec = new CascadeFlowAgentExecutor(
      cascadeModel,
      [tool as any],
      [{ toolName: 'echo', routing: 'verifier' }],
      3
    );
    await exec.invoke('hi', { signal: 'keep-me' });

    expect(invokeOptions[0]).toMatchObject({ signal: 'keep-me' });
    expect(invokeOptions[0].tools).toEqual([tool]);
    expect(verifierOptions[0].tools).toEqual([tool]);
  });

  it('does not add a tools option when no tools are connected', async () => {
    let captured: any = 'unset';
    const cascadeModel = {
      invoke: async (_messages: any[], options?: any) => {
        captured = options;
        return new AIMessage('ok');
      },
      invokeVerifierDirect: async () => new AIMessage('verifier'),
      stream: async function* () {
        yield new AIMessage('stream');
      },
    } as any;

    const exec = new CascadeFlowAgentExecutor(cascadeModel, [], [], 3);
    await exec.invoke('hi');

    expect(captured).toBeUndefined();
  });

  it('keeps caller-provided tools instead of overriding them', async () => {
    const connected = { name: 'echo', invoke: async () => 'x' };
    const override = { name: 'other', invoke: async () => 'y' };
    let captured: any;
    const cascadeModel = {
      invoke: async (_messages: any[], options?: any) => {
        captured = options;
        return new AIMessage('ok');
      },
      invokeVerifierDirect: async () => new AIMessage('verifier'),
      stream: async function* () {
        yield new AIMessage('stream');
      },
    } as any;

    const exec = new CascadeFlowAgentExecutor(cascadeModel, [connected as any], [], 3);
    await exec.invoke('hi', { tools: [override] });

    expect(captured.tools).toEqual([override]);
  });
});

describe('persistTurnToMemory', () => {
  it('writes the user and assistant turn through addMessage (LangChain core 1.x API)', async () => {
    const stored: any[] = [];
    const memory = {
      chatHistory: {
        getMessages: async () => [],
        addMessage: async (message: any) => {
          stored.push(message);
        },
      },
    };

    await persistTurnToMemory(memory as any, 'hello', 'hi there');

    expect(stored).toHaveLength(2);
    expect(stored[0]).toBeInstanceOf(HumanMessage);
    expect(stored[0].content).toBe('hello');
    expect(stored[1]).toBeInstanceOf(AIMessage);
    expect(stored[1].content).toBe('hi there');
  });

  it('is a no-op without a memory node', async () => {
    await expect(persistTurnToMemory(null, 'hello', 'hi')).resolves.toBeUndefined();
  });
});
