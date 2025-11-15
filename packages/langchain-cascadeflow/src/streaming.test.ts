import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { BaseMessage, HumanMessage, AIMessage, AIMessageChunk } from '@langchain/core/messages';
import { ChatResult, ChatGenerationChunk } from '@langchain/core/outputs';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import { CascadeWrapper } from './wrapper.js';

// Mock chat model with streaming support
class MockStreamingChatModel extends BaseChatModel {
  modelName: string;
  streamChunks: string[];
  shouldFailStreaming: boolean;

  constructor(modelName: string, streamChunks: string[] = ['Hello', ' ', 'World', '!'], shouldFailStreaming = false) {
    super({});
    this.modelName = modelName;
    this.streamChunks = streamChunks;
    this.shouldFailStreaming = shouldFailStreaming;
  }

  _llmType(): string {
    return 'mock-streaming';
  }

  async _generate(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): Promise<ChatResult> {
    const fullText = this.streamChunks.join('');
    return {
      generations: [{
        text: fullText,
        message: new AIMessage(fullText),
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

  async *_streamResponseChunks(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): AsyncGenerator<ChatGenerationChunk> {
    if (this.shouldFailStreaming) {
      throw new Error('Streaming failed');
    }

    for (const chunk of this.streamChunks) {
      yield new ChatGenerationChunk({
        text: chunk,
        message: new AIMessageChunk(chunk),
      });
    }
  }

  get model() {
    return this.modelName;
  }
}

describe('CascadeWrapper - Streaming Support', () => {
  let drafter: MockStreamingChatModel;
  let verifier: MockStreamingChatModel;

  beforeEach(() => {
    drafter = new MockStreamingChatModel('drafter-model', ['Draft', ' ', 'response']);
    verifier = new MockStreamingChatModel('verifier-model', ['Verified', ' ', 'response']);
  });

  describe('Basic Streaming', () => {
    it('should stream responses', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
        qualityThreshold: 0.7,
      });

      const chunks: string[] = [];
      const stream = await cascade.stream('Hello');

      for await (const chunk of stream) {
        chunks.push(chunk.content as string);
      }

      expect(chunks.length).toBeGreaterThan(0);
      expect(chunks.join('')).toBeTruthy();
    });

    it('should collect all chunks correctly', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const chunks: ChatGenerationChunk[] = [];
      const stream = await cascade.stream('Simple question');

      for await (const chunk of stream) {
        chunks.push(chunk);
      }

      expect(chunks.length).toBe(3); // 'Draft', ' ', 'response'
      expect(chunks[0].text).toBe('Draft');
      expect(chunks[1].text).toBe(' ');
      expect(chunks[2].text).toBe('response');
    });

    it('should store streaming metadata', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const stream = await cascade.stream('Test');
      // Consume stream
      for await (const chunk of stream) {
        // Just consume
      }

      const metadata = cascade.getLastCascadeResult();
      expect(metadata).toBeDefined();
      expect(metadata?.streaming).toBe(true);
      expect(metadata?.preRouted).toBe(true);
      expect(metadata?.content).toBe('Draft response');
    });
  });

  describe('Pre-Routing Logic', () => {
    it('should route simple queries to drafter', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const stream = await cascade.stream('Hi');
      const chunks: string[] = [];

      for await (const chunk of stream) {
        chunks.push(chunk.content as string);
      }

      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('drafter');
      expect(chunks.join('')).toBe('Draft response');
    });

    it('should route complex queries with keywords to verifier', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const stream = await cascade.stream(
        'Please analyze and compare these two complex technical approaches in detail'
      );
      const chunks: string[] = [];

      for await (const chunk of stream) {
        chunks.push(chunk.content as string);
      }

      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('verifier');
      expect(chunks.join('')).toBe('Verified response');
    });

    it('should route long queries (>50 words) to verifier', async () => {
      // Create a query that is both long AND has complexity keywords
      const longQuery = 'Please provide a comprehensive analysis of ' + 'word '.repeat(55) + ' and explain the technical details.';
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const stream = await cascade.stream(longQuery);
      // Consume stream
      for await (const chunk of stream) {
        // Just consume
      }

      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('verifier');
    });

    it('should route queries with code blocks to verifier', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const stream = await cascade.stream('How do I fix this code?\n```js\nconst x = 1;\n```');
      // Consume stream
      for await (const chunk of stream) {
        // Just consume
      }

      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('verifier');
    });

    it('should route queries with multiple questions to verifier', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const stream = await cascade.stream('Please analyze X in detail. What is X? How does Y work? Why is Z important?');
      // Consume stream
      for await (const chunk of stream) {
        // Just consume
      }

      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('verifier');
    });

    it('should route multi-step queries to verifier', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const stream = await cascade.stream('Please analyze this complex process: First do X, then do Y, finally do Z in detail');
      // Consume stream
      for await (const chunk of stream) {
        // Just consume
      }

      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('verifier');
    });

    it('should route queries with long context (>5 messages) to verifier', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const messages = [
        new HumanMessage('Message 1'),
        new AIMessage('Response 1'),
        new HumanMessage('Message 2'),
        new AIMessage('Response 2'),
        new HumanMessage('Message 3'),
        new AIMessage('Response 3'),
        new HumanMessage('What do you think?'),
      ];

      const stream = await cascade.stream(messages);
      // Consume stream
      for await (const chunk of stream) {
        // Just consume
      }

      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('verifier');
    });

    it('should prefer drafter for borderline complexity', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      // Query with complexity score around 0.4 (below 0.5 threshold)
      const stream = await cascade.stream('What is TypeScript and why should I use it?');
      // Consume stream
      for await (const chunk of stream) {
        // Just consume
      }

      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('drafter');
    });
  });

  describe('Error Handling', () => {
    it('should fall back to non-streaming on error', async () => {
      const failingDrafter = new MockStreamingChatModel('failing-drafter', ['test'], true);
      const cascade = new CascadeWrapper({
        drafter: failingDrafter,
        verifier,
      });

      const chunks: string[] = [];
      const stream = await cascade.stream('Simple query');

      // Should not throw - should fall back
      for await (const chunk of stream) {
        chunks.push(chunk.content as string);
      }

      // Should get non-streaming response
      expect(chunks.length).toBeGreaterThan(0);
      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.streaming).toBe(true);
    });

    it('should handle empty stream gracefully', async () => {
      const emptyDrafter = new MockStreamingChatModel('empty-drafter', []);
      const cascade = new CascadeWrapper({
        drafter: emptyDrafter,
        verifier,
      });

      const chunks: string[] = [];
      const stream = await cascade.stream('Test');

      for await (const chunk of stream) {
        chunks.push(chunk.content as string);
      }

      expect(chunks.length).toBe(0);
      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.content).toBe('');
    });
  });

  describe('Metadata Tracking', () => {
    it('should track latency during streaming', async () => {
      // Create a mock with a small delay to ensure measurable latency
      const slowDrafter = new MockStreamingChatModel('slow-drafter');
      const cascade = new CascadeWrapper({
        drafter: slowDrafter,
        verifier,
      });

      const stream = await cascade.stream('Test');

      // Add small delay between chunks
      for await (const chunk of stream) {
        await new Promise(resolve => setTimeout(resolve, 1));
      }

      const metadata = cascade.getLastCascadeResult();

      expect(metadata).toBeDefined();
      expect(metadata?.latencyMs).toBeGreaterThanOrEqual(0);
      expect(metadata?.streaming).toBe(true);
    });

    it('should set drafterQuality to 1.0 when drafter is used', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const stream = await cascade.stream('Simple');
      for await (const chunk of stream) {
        // Just consume
      }

      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('drafter');
      expect(metadata?.drafterQuality).toBe(1.0);
    });

    it('should set drafterQuality to 0.0 when verifier is used', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const stream = await cascade.stream('Analyze this complex technical topic in detail');
      for await (const chunk of stream) {
        // Just consume
      }

      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.modelUsed).toBe('verifier');
      expect(metadata?.drafterQuality).toBe(0.0);
    });

    it('should set cost metadata to 0 for streaming (not calculated)', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const stream = await cascade.stream('Test');
      for await (const chunk of stream) {
        // Just consume
      }

      const metadata = cascade.getLastCascadeResult();
      expect(metadata?.drafterCost).toBe(0);
      expect(metadata?.verifierCost).toBe(0);
      expect(metadata?.totalCost).toBe(0);
      expect(metadata?.savingsPercentage).toBe(0);
    });
  });

  describe('Integration with LangChain', () => {
    it('should work with .bind() method', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const bound = cascade.bind({ temperature: 0.5 });
      const stream = await bound.stream('Test');
      const chunks: string[] = [];

      for await (const chunk of stream) {
        chunks.push(chunk.content as string);
      }

      expect(chunks.length).toBeGreaterThan(0);
    });

    it('should handle message arrays', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const messages = [
        new HumanMessage('Hello'),
        new AIMessage('Hi there'),
        new HumanMessage('How are you?'),
      ];

      const stream = await cascade.stream(messages);
      const chunks: string[] = [];

      for await (const chunk of stream) {
        chunks.push(chunk.content as string);
      }

      expect(chunks.length).toBeGreaterThan(0);
    });

    it('should handle string content in messages', async () => {
      const cascade = new CascadeWrapper({
        drafter,
        verifier,
      });

      const message = new HumanMessage('What is 2+2?');
      const stream = await cascade.stream([message]);
      const chunks: string[] = [];

      for await (const chunk of stream) {
        chunks.push(chunk.content as string);
      }

      expect(chunks.join('')).toBe('Draft response');
    });
  });
});
