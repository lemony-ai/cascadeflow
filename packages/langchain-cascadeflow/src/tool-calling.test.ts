import { describe, it, expect, beforeEach } from 'vitest';
import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { BaseMessage, HumanMessage, AIMessage } from '@langchain/core/messages';
import { ChatResult } from '@langchain/core/outputs';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import { CascadeWrapper } from './wrapper.js';

// Mock chat model with tool support
class MockToolChatModel extends BaseChatModel {
  modelName: string;
  boundTools: any[] = [];
  structuredOutput: any = null;

  constructor(modelName: string) {
    super({});
    this.modelName = modelName;
  }

  _llmType(): string {
    return 'mock-tool';
  }

  async _generate(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): Promise<ChatResult> {
    let responseText = 'Default response';

    // If tools are bound, simulate tool calls
    if (this.boundTools.length > 0) {
      const toolNames = this.boundTools.map((t: any) => t.name || 'unknown').join(', ');
      responseText = `Tools available: ${toolNames}. Calling calculator tool.`;
    }

    // If structured output is defined, return structured data
    if (this.structuredOutput) {
      responseText = JSON.stringify({
        name: 'Test Result',
        age: 25,
        email: 'test@example.com',
      });
    }

    return {
      generations: [{
        text: responseText,
        message: new AIMessage({
          content: responseText,
          additional_kwargs: this.boundTools.length > 0 ? {
            tool_calls: [{
              id: 'call_123',
              type: 'function',
              function: {
                name: 'calculator',
                arguments: JSON.stringify({ operation: 'add', a: 5, b: 3 }),
              },
            }],
          } : {},
        }),
      }],
      llmOutput: {
        tokenUsage: {
          promptTokens: 10,
          completionTokens: 20,
          totalTokens: 30,
        },
      },
    };
  }

  bindTools(tools: any[], kwargs?: any): MockToolChatModel {
    const newModel = new MockToolChatModel(this.modelName);
    newModel.boundTools = tools;
    return newModel;
  }

  withStructuredOutput(schema: any, config?: any): MockToolChatModel {
    const newModel = new MockToolChatModel(this.modelName);
    newModel.structuredOutput = schema;
    return newModel;
  }

  get model() {
    return this.modelName;
  }
}

describe('CascadeWrapper - Tool Calling Support', () => {
  let drafter: MockToolChatModel;
  let verifier: MockToolChatModel;

  beforeEach(() => {
    drafter = new MockToolChatModel('drafter-tool-model');
    verifier = new MockToolChatModel('verifier-tool-model');
  });

  describe('.bindTools() Method', () => {
    it('should bind tools to both drafter and verifier', () => {
      const tools = [
        {
          name: 'calculator',
          description: 'Performs basic arithmetic operations',
          parameters: {
            type: 'object',
            properties: {
              operation: { type: 'string' },
              a: { type: 'number' },
              b: { type: 'number' },
            },
          },
        },
      ];

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const boundCascade = cascade.bindTools(tools);

      expect(boundCascade).toBeInstanceOf(CascadeWrapper);
      expect((boundCascade as any).drafter.boundTools).toEqual(tools);
      expect((boundCascade as any).verifier.boundTools).toEqual(tools);
    });

    it('should preserve tools when invoking cascade', async () => {
      const tools = [
        {
          name: 'calculator',
          description: 'Math operations',
        },
      ];

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.9, // Force verifier usage
      });

      const boundCascade = cascade.bindTools(tools);
      const result = await boundCascade.invoke('What is 5 + 3?');

      expect(result.content).toContain('Tools available');
      expect(result.content).toContain('calculator');
    });

    it('should handle multiple tools', () => {
      const tools = [
        { name: 'calculator' },
        { name: 'weather' },
        { name: 'search' },
      ];

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const boundCascade = cascade.bindTools(tools);

      expect((boundCascade as any).drafter.boundTools).toHaveLength(3);
      expect((boundCascade as any).verifier.boundTools).toHaveLength(3);
    });

    it('should handle tool binding with kwargs', () => {
      const tools = [{ name: 'test-tool' }];
      const kwargs = { temperature: 0.5, maxTokens: 100 };

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const boundCascade = cascade.bindTools(tools, kwargs);

      expect(boundCascade).toBeInstanceOf(CascadeWrapper);
    });

    it('should throw error if drafter does not support bindTools', () => {
      class BasicModel extends BaseChatModel {
        _llmType() {
          return 'basic';
        }
        async _generate(): Promise<ChatResult> {
          return {
            generations: [{ text: 'test', message: new AIMessage('test') }],
            llmOutput: {},
          };
        }
      }

      const basicDrafter = new BasicModel({});
      const cascade = new CascadeWrapper({
        drafter: basicDrafter,
        verifier,
      });

      expect(() => cascade.bindTools([{ name: 'test' }])).toThrow('does not support bindTools');
    });
  });

  describe('.withStructuredOutput() Method', () => {
    it('should bind structured output to both models', () => {
      const schema = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          age: { type: 'number' },
          email: { type: 'string', format: 'email' },
        },
        required: ['name', 'age', 'email'],
      };

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const structuredCascade = cascade.withStructuredOutput(schema);

      expect(structuredCascade).toBeInstanceOf(CascadeWrapper);
      expect((structuredCascade as any).drafter.structuredOutput).toBeDefined();
      expect((structuredCascade as any).verifier.structuredOutput).toBeDefined();
    });

    it('should return structured output when invoked', async () => {
      const schema = {
        type: 'object',
        properties: {
          name: { type: 'string' },
          age: { type: 'number' },
        },
      };

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.5,
      });

      const structuredCascade = cascade.withStructuredOutput(schema);
      const result = await structuredCascade.invoke('Extract user info');

      expect(result.content).toContain('name');
      expect(result.content).toContain('age');
    });

    it('should handle structured output with config', () => {
      const schema = { type: 'object', properties: {} };
      const config = { strict: true };

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const structuredCascade = cascade.withStructuredOutput(schema, config);

      expect(structuredCascade).toBeInstanceOf(CascadeWrapper);
    });

    it('should throw error if drafter does not support withStructuredOutput', () => {
      class BasicModel extends BaseChatModel {
        _llmType() {
          return 'basic';
        }
        async _generate(): Promise<ChatResult> {
          return {
            generations: [{ text: 'test', message: new AIMessage('test') }],
            llmOutput: {},
          };
        }
      }

      const basicDrafter = new BasicModel({});
      const cascade = new CascadeWrapper({
        drafter: basicDrafter,
        verifier,
      });

      expect(() => cascade.withStructuredOutput({ type: 'object' })).toThrow(
        'Chat model must implement ".bindTools()" to use withStructuredOutput.'
      );
    });
  });

  describe('Tool Call Preservation', () => {
    it('should preserve tool calls in cascade response', async () => {
      const tools = [{ name: 'calculator', description: 'Math tool' }];

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.9, // Force verifier
      });

      const boundCascade = cascade.bindTools(tools);
      const result = await boundCascade.invoke('Calculate 5 + 3');

      const aiMessage = result as AIMessage;
      expect(aiMessage.additional_kwargs?.tool_calls).toBeDefined();
      expect(aiMessage.additional_kwargs?.tool_calls).toHaveLength(1);
      expect(aiMessage.additional_kwargs?.tool_calls?.[0].function.name).toBe('calculator');
    });

    it('should preserve tool calls when using drafter', async () => {
      const tools = [{ name: 'calculator' }];

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.1, // Use drafter
      });

      const boundCascade = cascade.bindTools(tools);
      const result = await boundCascade.invoke('Simple calculation');

      expect(result).toBeDefined();
      expect(result.content).toContain('calculator');

      const metadata = boundCascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('drafter');
    });

    it('should preserve tool call arguments correctly', async () => {
      const tools = [{ name: 'calculator' }];

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.9,
      });

      const boundCascade = cascade.bindTools(tools);
      const result = await boundCascade.invoke('Add 5 and 3');

      const aiMessage = result as AIMessage;
      const toolCall = aiMessage.additional_kwargs?.tool_calls?.[0];

      expect(toolCall).toBeDefined();
      expect(toolCall.function.name).toBe('calculator');

      const args = JSON.parse(toolCall.function.arguments);
      expect(args).toHaveProperty('operation', 'add');
      expect(args).toHaveProperty('a', 5);
      expect(args).toHaveProperty('b', 3);
    });
  });

  describe('Chaining Tool Binding', () => {
    it('should support chaining .bind() with .bindTools()', () => {
      const tools = [{ name: 'test-tool' }];

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const boundCascade = cascade
        .bind({ temperature: 0.7 })
        .bindTools(tools);

      expect(boundCascade).toBeInstanceOf(CascadeWrapper);
    });

    it('should support chaining .bindTools() with .bind()', () => {
      const tools = [{ name: 'test-tool' }];

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const boundCascade = cascade
        .bindTools(tools)
        .bind({ temperature: 0.7 });

      expect(boundCascade).toBeInstanceOf(CascadeWrapper);
    });

    it('should support chaining .bindTools() with .withStructuredOutput()', () => {
      const tools = [{ name: 'extractor' }];
      const schema = {
        type: 'object',
        properties: { name: { type: 'string' } },
      };

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const boundCascade = cascade
        .bindTools(tools)
        .withStructuredOutput(schema);

      expect(boundCascade).toBeInstanceOf(CascadeWrapper);
    });
  });

  describe('Tool Calling with Cascade Quality Checks', () => {
    it('should execute tools with drafter when quality is sufficient', async () => {
      const tools = [{ name: 'simple-tool' }];

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.1, // Low threshold, use drafter
      });

      const boundCascade = cascade.bindTools(tools);
      const result = await boundCascade.invoke('Use simple tool');

      const metadata = boundCascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('drafter');
    });

    it('should execute tools with verifier when quality is insufficient', async () => {
      const tools = [{ name: 'complex-tool' }];

      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.99, // High threshold, force verifier
      });

      const boundCascade = cascade.bindTools(tools);
      const result = await boundCascade.invoke('Complex tool usage');

      const metadata = boundCascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('verifier');
    });
  });

  describe('Error Handling with Tools', () => {
    it('should handle missing tools gracefully', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      // Don't bind any tools
      const result = await cascade.invoke('Use a tool');

      expect(result).toBeDefined();
      expect(result.content).toBe('Default response');
    });

    it('should handle empty tool array', () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const boundCascade = cascade.bindTools([]);

      expect(boundCascade).toBeInstanceOf(CascadeWrapper);
      expect((boundCascade as any).drafter.boundTools).toEqual([]);
    });

    it('should handle tool calls when model does not return tool calls', async () => {
      class NoToolCallModel extends BaseChatModel {
        modelName: string;

        constructor(modelName: string) {
          super({});
          this.modelName = modelName;
        }

        _llmType(): string {
          return 'no-tool';
        }

        async _generate(): Promise<ChatResult> {
          return {
            generations: [{
              text: 'Response without tool calls',
              message: new AIMessage('Response without tool calls'),
            }],
            llmOutput: {},
          };
        }

        // Does not implement bindTools
        get model() {
          return this.modelName;
        }
      }

      const noToolDrafter = new NoToolCallModel('no-tool-drafter');
      const noToolVerifier = new NoToolCallModel('no-tool-verifier');
      const cascade = new CascadeWrapper({
        drafter: noToolDrafter,
        verifier: noToolVerifier,
      });

      // Should work without binding tools
      const result = await cascade.invoke('Test');

      expect(result.content).toBe('Response without tool calls');
    });
  });
});
