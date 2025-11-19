import { describe, it, expect, beforeEach } from 'vitest';
import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { BaseMessage, HumanMessage, AIMessage } from '@langchain/core/messages';
import { ChatResult } from '@langchain/core/outputs';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import { PromptTemplate } from '@langchain/core/prompts';
import { StringOutputParser } from '@langchain/core/output_parsers';
import { RunnableSequence, RunnablePassthrough } from '@langchain/core/runnables';
import { CascadeWrapper } from './wrapper.js';

// Mock chat model for LCEL testing
class MockLCELChatModel extends BaseChatModel {
  modelName: string;
  responsePrefix: string;

  constructor(modelName: string, responsePrefix = '') {
    super({});
    this.modelName = modelName;
    this.responsePrefix = responsePrefix;
  }

  _llmType(): string {
    return 'mock-lcel';
  }

  async _generate(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): Promise<ChatResult> {
    const lastMessage = messages[messages.length - 1];
    const content = typeof lastMessage.content === 'string'
      ? lastMessage.content
      : JSON.stringify(lastMessage.content);

    const response = this.responsePrefix + content.toUpperCase();

    return {
      generations: [{
        text: response,
        message: new AIMessage(response),
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

  get model() {
    return this.modelName;
  }
}

describe('CascadeWrapper - LCEL Composition', () => {
  let drafter: MockLCELChatModel;
  let verifier: MockLCELChatModel;

  beforeEach(() => {
    drafter = new MockLCELChatModel('drafter-lcel', '[DRAFTER] ');
    verifier = new MockLCELChatModel('verifier-lcel', '[VERIFIER] ');
  });

  describe('Pipe Operator (|)', () => {
    it('should work with pipe operator in simple chain', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const parser = new StringOutputParser();
      const chain = cascade.pipe(parser);

      const result = await chain.invoke('test input');

      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
    });

    it('should work in chain: prompt | cascade | parser', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const prompt = PromptTemplate.fromTemplate('Question: {question}');
      const parser = new StringOutputParser();

      const chain = prompt.pipe(cascade).pipe(parser);

      const result = await chain.invoke({ question: 'What is 2+2?' });

      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
      expect(result).toContain('2+2');
    });

    it('should preserve cascade metadata in pipe chains', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.1, // Use drafter
      });

      const parser = new StringOutputParser();
      const chain = cascade.pipe(parser);

      await chain.invoke('simple test');

      const metadata = cascade.getLastCascadeResult();
      expect(metadata).toBeDefined();
      expect(metadata?.modelUsed).toBe('drafter');
    });
  });

  describe('RunnableSequence', () => {
    it('should work in RunnableSequence.from()', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const prompt = PromptTemplate.fromTemplate('Process: {input}');
      const parser = new StringOutputParser();

      const chain = RunnableSequence.from([
        prompt,
        cascade,
        parser,
      ]);

      const result = await chain.invoke({ input: 'test data' });

      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
    });

    it('should handle complex sequences', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const chain = RunnableSequence.from([
        {
          question: (input: string) => input,
          context: () => 'Some context',
        },
        PromptTemplate.fromTemplate('Context: {context}\nQuestion: {question}'),
        cascade,
        new StringOutputParser(),
      ]);

      const result = await chain.invoke('What is LangChain?');

      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
    });
  });

  describe('Batch Processing', () => {
    it('should handle batch() method', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const inputs = [
        'First question',
        'Second question',
        'Third question',
      ];

      const results = await cascade.batch(inputs);

      expect(results).toHaveLength(3);
      results.forEach(result => {
        expect(result).toBeDefined();
        expect(result.content).toBeTruthy();
      });
    });

    it('should preserve metadata for last batch item', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.1,
      });

      await cascade.batch(['test1', 'test2']);

      const metadata = cascade.getLastCascadeResult();
      expect(metadata).toBeDefined();
      expect(metadata?.modelUsed).toBe('drafter');
    });

    it('should handle batch with chain', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const parser = new StringOutputParser();
      const chain = cascade.pipe(parser);

      const results = await chain.batch(['input1', 'input2']);

      expect(results).toHaveLength(2);
      results.forEach(result => {
        expect(typeof result).toBe('string');
      });
    });
  });

  describe('RunnablePassthrough', () => {
    it('should work with RunnablePassthrough.assign()', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const chain = RunnablePassthrough.assign({
        answer: cascade.pipe(new StringOutputParser()),
      });

      const result = await chain.invoke('What is AI?');

      expect(result).toHaveProperty('answer');
      expect(typeof result.answer).toBe('string');
    });
  });

  describe('Method Chaining with LCEL', () => {
    it('should chain .bind() before piping', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const bound = cascade.bind({ temperature: 0.5 });
      const parser = new StringOutputParser();
      const chain = bound.pipe(parser);

      const result = await chain.invoke('test');

      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
    });

    it('should work with .bindTools() in LCEL chain', async () => {
      // Create models with bindTools support
      class ToolModel extends MockLCELChatModel {
        boundTools: any[] = [];

        bindTools(tools: any[]): ToolModel {
          const newModel = new ToolModel(this.modelName, this.responsePrefix);
          newModel.boundTools = tools;
          return newModel;
        }
      }

      const toolDrafter = new ToolModel('tool-drafter', '[DRAFTER] ');
      const toolVerifier = new ToolModel('tool-verifier', '[VERIFIER] ');

      const cascade = new CascadeWrapper({
        drafter: toolDrafter,
        verifier: toolVerifier,
        qualityThreshold: 0.7,
      });

      const tools = [{ name: 'test-tool' }];
      const withTools = cascade.bindTools(tools);
      const parser = new StringOutputParser();
      const chain = withTools.pipe(parser);

      const result = await chain.invoke('test');

      expect(result).toBeTruthy();
    });
  });

  describe('Stream in LCEL Chains', () => {
    it('should stream through LCEL chain', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const parser = new StringOutputParser();
      const chain = cascade.pipe(parser);

      const stream = await chain.stream('test input');
      const chunks: string[] = [];

      for await (const chunk of stream) {
        chunks.push(chunk);
      }

      expect(chunks.length).toBeGreaterThan(0);
    });
  });

  describe('Complex Chain Patterns', () => {
    it('should handle branching with RunnablePassthrough.assign()', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const chain = RunnablePassthrough.assign({
        processed: cascade.pipe(new StringOutputParser()),
      });

      const result = await chain.invoke('test');

      expect(result).toHaveProperty('processed');
      expect(typeof result.processed).toBe('string');
    });

    it('should work with nested chains', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const innerChain = cascade.pipe(new StringOutputParser());
      const outerChain = RunnableSequence.from([
        PromptTemplate.fromTemplate('Input: {text}'),
        innerChain,
      ]);

      const result = await outerChain.invoke({ text: 'nested test' });

      expect(result).toBeTruthy();
      expect(typeof result).toBe('string');
    });
  });

  describe('Error Handling in Chains', () => {
    it('should propagate errors through chain', async () => {
      class FailingModel extends BaseChatModel {
        _llmType() {
          return 'failing';
        }

        async _generate(): Promise<ChatResult> {
          throw new Error('Model failed');
        }
      }

      const failingDrafter = new FailingModel({});
      const failingVerifier = new FailingModel({});

      const cascade = new CascadeWrapper({
        drafter: failingDrafter,
        verifier: failingVerifier,
        qualityThreshold: 0.7,
      });

      const chain = cascade.pipe(new StringOutputParser());

      await expect(chain.invoke('test')).rejects.toThrow('Model failed');
    });
  });
});
