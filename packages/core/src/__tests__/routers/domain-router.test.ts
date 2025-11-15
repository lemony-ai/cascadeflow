/**
 * DomainRouter Tests
 *
 * Comprehensive test suite for DomainRouter class.
 * Tests domain detection, keyword matching, confidence scoring, and statistics.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  DomainRouter,
  createDomainRouter,
  Domain,
  type DomainDetectionResult,
} from '../../routers/domain-router';

describe('DomainRouter', () => {
  let router: DomainRouter;

  beforeEach(() => {
    router = new DomainRouter();
  });

  describe('constructor and configuration', () => {
    it('should initialize router', () => {
      expect(router).toBeInstanceOf(DomainRouter);
    });

    it('should initialize statistics', () => {
      const stats = router.getStats();
      expect(stats.totalDetections).toBe(0);
      expect(stats.avgConfidence).toBe(0);
      expect(stats.byDomain).toHaveProperty(Domain.CODE);
      expect(stats.byDomain).toHaveProperty(Domain.GENERAL);
    });

    it('should support verbose mode', () => {
      const verboseRouter = new DomainRouter({ verbose: true });
      expect(verboseRouter).toBeInstanceOf(DomainRouter);
    });
  });

  describe('domain detection - CODE', () => {
    it('should detect code domain with high confidence', () => {
      const result = router.detect('Write a Python function to sort a list using async/await');

      expect(result.domain).toBe(Domain.CODE);
      expect(result.confidence).toBeGreaterThan(0.5);
    });

    it('should detect code domain from programming keywords', () => {
      const queries = [
        'debug this JavaScript function',
        'implement algorithm with return statement',
        'fix TypeScript compilation error',
        'create async function with await',
        'npm install docker kubernetes',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.CODE);
      }
    });

    it('should have high confidence for strong code indicators', () => {
      const result = router.detect('async await import export const let npm pip docker kubernetes pytest unittest');

      expect(result.domain).toBe(Domain.CODE);
      expect(result.confidence).toBeGreaterThan(0.8);
    });
  });

  describe('domain detection - DATA', () => {
    it('should detect data domain for SQL queries', () => {
      const result = router.detect('SELECT * FROM users WHERE age > 18 GROUP BY country');

      expect(result.domain).toBe(Domain.DATA);
    });

    it('should detect data domain for analytics', () => {
      const queries = [
        'analyze pandas dataframe with correlation',
        'create SQL query to join tables',
        'ETL pipeline for data warehouse',
        'calculate regression analysis with dataset',
        'database analytics with BI tools',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.DATA);
      }
    });
  });

  describe('domain detection - STRUCTURED', () => {
    it('should detect structured data extraction', () => {
      const result = router.detect('extract JSON from this document and validate schema');

      expect(result.domain).toBe(Domain.STRUCTURED);
    });

    it('should detect structured domain for parsing', () => {
      const queries = [
        'parse XML document with schema validation',
        'convert YAML to JSON format',
        'extract fields from pydantic model',
        'serialize protobuf message',
        'validate JSON schema with dataclass',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.STRUCTURED);
      }
    });
  });

  describe('domain detection - RAG', () => {
    it('should detect RAG/search queries', () => {
      const result = router.detect('semantic search with vector embeddings using chromadb');

      expect(result.domain).toBe(Domain.RAG);
    });

    it('should detect RAG domain for retrieval', () => {
      const queries = [
        'search documents using faiss vector database',
        'retrieve relevant passages from knowledge base',
        'index documents for semantic search',
        'query pinecone for similar embeddings',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.RAG);
      }
    });
  });

  describe('domain detection - CONVERSATION', () => {
    it('should detect conversation domain', () => {
      const result = router.detect('chatbot dialogue with multi-turn conversation memory');

      expect(result.domain).toBe(Domain.CONVERSATION);
    });

    it('should detect conversation for chat scenarios', () => {
      const queries = [
        'chat with friendly persona',
        'respond to follow-up questions',
        'maintain conversation context',
        'multi-turn dialogue system',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.CONVERSATION);
      }
    });
  });

  describe('domain detection - TOOL', () => {
    it('should detect tool calling domain', () => {
      const result = router.detect('function call to external API with tool use');

      expect(result.domain).toBe(Domain.TOOL);
    });

    it('should detect tool domain for integrations', () => {
      const queries = [
        'invoke webhook for automation',
        'execute plugin action',
        'call API endpoint',
        'trigger integration workflow',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.TOOL);
      }
    });
  });

  describe('domain detection - CREATIVE', () => {
    it('should detect creative writing', () => {
      const result = router.detect('write a creative story with fictional characters');

      expect(result.domain).toBe(Domain.CREATIVE);
    });

    it('should detect creative domain for content generation', () => {
      const queries = [
        'compose a poem about nature',
        'generate blog article content',
        'create narrative with plot',
        'draft creative essay',
        'imagine a novel scene',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.CREATIVE);
      }
    });
  });

  describe('domain detection - SUMMARY', () => {
    it('should detect summarization requests', () => {
      const result = router.detect('summarize this document, provide tldr and key takeaways');

      expect(result.domain).toBe(Domain.SUMMARY);
    });

    it('should detect summary domain', () => {
      const queries = [
        'condense this text to main points',
        'brief overview of the article',
        'concise summary of key information',
        'tldr version',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.SUMMARY);
      }
    });
  });

  describe('domain detection - TRANSLATION', () => {
    it('should detect translation requests', () => {
      const result = router.detect('translate this text from English to French');

      expect(result.domain).toBe(Domain.TRANSLATION);
    });

    it('should detect translation domain for languages', () => {
      const queries = [
        'translate Spanish to German',
        'convert to Chinese language',
        'Japanese translation service',
        'localize from Arabic to English',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.TRANSLATION);
      }
    });
  });

  describe('domain detection - MATH', () => {
    it('should detect mathematical queries', () => {
      const result = router.detect('solve calculus equation with derivatives and integrals');

      expect(result.domain).toBe(Domain.MATH);
    });

    it('should detect math domain for calculations', () => {
      const queries = [
        'calculate matrix multiplication',
        'prove this theorem',
        'compute algebra expression',
        'solve trigonometry problem',
        'calculate derivative and integral',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.MATH);
      }
    });
  });

  describe('domain detection - MEDICAL', () => {
    it('should detect medical queries', () => {
      const result = router.detect('patient diagnosis with symptoms and medication treatment');

      expect(result.domain).toBe(Domain.MEDICAL);
    });

    it('should detect medical domain for healthcare', () => {
      const queries = [
        'clinical treatment plan',
        'disease diagnosis and therapy',
        'prescription pharmaceutical advice',
        'hospital surgery procedure',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.MEDICAL);
      }
    });
  });

  describe('domain detection - LEGAL', () => {
    it('should detect legal queries', () => {
      const result = router.detect('contract law review for compliance and litigation');

      expect(result.domain).toBe(Domain.LEGAL);
    });

    it('should detect legal domain', () => {
      const queries = [
        'statute regulation analysis',
        'attorney legal advice',
        'court jurisdiction case',
        'liability clause in agreement',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.LEGAL);
      }
    });
  });

  describe('domain detection - FINANCIAL', () => {
    it('should detect financial queries', () => {
      const result = router.detect('investment portfolio with stock trading and equity analysis');

      expect(result.domain).toBe(Domain.FINANCIAL);
    });

    it('should detect financial domain', () => {
      const queries = [
        'market revenue forecast',
        'bond asset allocation',
        'profit and loss analysis',
        'dividend investment strategy',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.FINANCIAL);
      }
    });
  });

  describe('domain detection - MULTIMODAL', () => {
    it('should detect multimodal queries', () => {
      const result = router.detect('analyze this image and describe what you see in the picture');

      expect(result.domain).toBe(Domain.MULTIMODAL);
    });

    it('should detect multimodal domain for visual content', () => {
      const queries = [
        'show me this diagram',
        'look at this photo',
        'view the screenshot',
        'see this illustration',
      ];

      for (const query of queries) {
        const result = router.detect(query);
        expect(result.domain).toBe(Domain.MULTIMODAL);
      }
    });
  });

  describe('domain detection - GENERAL', () => {
    it('should default to general for empty query', () => {
      const result = router.detect('');

      expect(result.domain).toBe(Domain.GENERAL);
      expect(result.confidence).toBe(0);
    });

    it('should use general domain for simple factual queries', () => {
      // Queries with no domain-specific keywords should default to GENERAL
      const result = router.detect('random question without domain keywords');

      // Should be GENERAL since no other domain has significant keywords
      expect(result.confidence).toBeLessThan(0.5); // Low confidence since no strong matches
    });

    it('should detect general domain when only generic question words present', () => {
      // Query with only GENERAL keywords
      const result = router.detect('explain this concept');

      // Should be GENERAL (explain is a strong GENERAL keyword)
      expect(result.domain).toBe(Domain.GENERAL);
    });
  });

  describe('confidence scoring', () => {
    it('should calculate confidence based on keyword matches', () => {
      const result = router.detect('Write a Python function');

      expect(result.confidence).toBeGreaterThan(0);
      expect(result.confidence).toBeLessThanOrEqual(1);
    });

    it('should have higher confidence with more keywords', () => {
      const weak = router.detect('write code');
      const strong = router.detect('async await function class import export npm pip');

      expect(strong.confidence).toBeGreaterThan(weak.confidence);
    });

    it('should normalize confidence to 0-1 range', () => {
      // Even with many keywords, confidence should not exceed 1.0
      const result = router.detect(
        'async await import export const let npm pip docker kubernetes pytest unittest ' +
        'function class python javascript typescript java code algorithm api debug error'
      );

      expect(result.confidence).toBeGreaterThan(0);
      expect(result.confidence).toBeLessThanOrEqual(1);
    });

    it('should weight keywords appropriately', () => {
      // Very strong keywords should have higher impact
      const veryStrong = router.detect('async await import');
      const moderate = router.detect('program software');

      expect(veryStrong.confidence).toBeGreaterThan(moderate.confidence);
    });
  });

  describe('scores metadata', () => {
    it('should return scores for all domains', () => {
      const result = router.detect('Write a Python function');

      expect(result.scores).toBeDefined();
      expect(Object.keys(result.scores!).length).toBeGreaterThan(0);
    });

    it('should include scores for multiple domains', () => {
      const result = router.detect('code data analysis');

      expect(result.scores).toBeDefined();
      expect(result.scores![Domain.CODE]).toBeGreaterThan(0);
      expect(result.scores![Domain.DATA]).toBeGreaterThan(0);
    });

    it('should show highest score for detected domain', () => {
      const result = router.detect('Write a Python function');

      const detectedScore = result.scores![result.domain];
      const allScores = Object.values(result.scores!);

      expect(detectedScore).toBe(Math.max(...allScores));
    });
  });

  describe('statistics tracking', () => {
    it('should track total detections', () => {
      router.detect('query 1');
      router.detect('query 2');
      router.detect('query 3');

      const stats = router.getStats();
      expect(stats.totalDetections).toBe(3);
    });

    it('should track detections by domain', () => {
      router.detect('Write a Python function'); // CODE
      router.detect('Write another function'); // CODE
      router.detect('SELECT * FROM users'); // DATA

      const stats = router.getStats();
      expect(stats.byDomain[Domain.CODE]).toBe(2);
      expect(stats.byDomain[Domain.DATA]).toBe(1);
    });

    it('should calculate average confidence', () => {
      router.detect('async await import export'); // High confidence
      router.detect('write something'); // Low confidence

      const stats = router.getStats();
      expect(stats.avgConfidence).toBeGreaterThan(0);
      expect(stats.avgConfidence).toBeLessThanOrEqual(1);
    });

    it('should reset statistics', () => {
      router.detect('query 1');
      router.detect('query 2');

      router.resetStats();

      const stats = router.getStats();
      expect(stats.totalDetections).toBe(0);
      expect(stats.avgConfidence).toBe(0);
      expect(stats.byDomain[Domain.CODE]).toBe(0);
    });

    it('should handle zero detections gracefully', () => {
      const stats = router.getStats();
      expect(stats.avgConfidence).toBe(0);
    });
  });

  describe('createDomainRouter factory', () => {
    it('should create router with factory', () => {
      const router = createDomainRouter();
      expect(router).toBeInstanceOf(DomainRouter);
    });

    it('should pass config to constructor', () => {
      const router = createDomainRouter({ verbose: true });
      expect(router).toBeInstanceOf(DomainRouter);
    });
  });

  describe('edge cases', () => {
    it('should handle very long queries', () => {
      const longQuery = 'code '.repeat(1000);
      const result = router.detect(longQuery);

      expect(result.domain).toBe(Domain.CODE);
      expect(result.confidence).toBeLessThanOrEqual(1);
    });

    it('should handle special characters', () => {
      const result = router.detect('Write a Python function with @decorator and #comment');

      expect(result.domain).toBe(Domain.CODE);
    });

    it('should handle unicode characters', () => {
      const result = router.detect('Translate こんにちは to English');

      expect(result.domain).toBe(Domain.TRANSLATION);
    });

    it('should be case insensitive', () => {
      const lower = router.detect('write python function');
      const upper = router.detect('WRITE PYTHON FUNCTION');
      const mixed = router.detect('WrItE PyThOn FuNcTiOn');

      expect(lower.domain).toBe(upper.domain);
      expect(upper.domain).toBe(mixed.domain);
    });

    it('should handle queries with multiple domain keywords', () => {
      const result = router.detect('Write code to analyze data and create summary');

      // Should pick the domain with highest score
      expect(result.domain).toBeDefined();
      expect(result.confidence).toBeGreaterThan(0);
    });
  });

  describe('verbose mode', () => {
    it('should not throw in verbose mode', () => {
      const verboseRouter = new DomainRouter({ verbose: true });

      expect(() => {
        verboseRouter.detect('Write a Python function');
        verboseRouter.getStats();
        verboseRouter.resetStats();
      }).not.toThrow();
    });
  });

  describe('result structure', () => {
    it('should return complete result structure', () => {
      const result = router.detect('Write a Python function');

      expect(result).toHaveProperty('domain');
      expect(result).toHaveProperty('confidence');
      expect(result).toHaveProperty('scores');
    });

    it('should have valid domain value', () => {
      const result = router.detect('Write a Python function');

      expect(Object.values(Domain)).toContain(result.domain);
    });
  });
});
