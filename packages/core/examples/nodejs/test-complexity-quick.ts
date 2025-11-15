/**
 * Quick test of complexity detection improvements
 */

import { ComplexityDetector } from '../../src/complexity';

const detector = new ComplexityDetector();

const testQueries = [
  { q: "What color is the sky?", expected: "trivial" },
  { q: "What's the capital of France?", expected: "trivial" },
  { q: "Translate 'hello' to Spanish", expected: "simple" },
  { q: "Explain the difference between lists and tuples in Python", expected: "moderate" },
  { q: "Write a function to reverse a string in Python", expected: "moderate" },
  { q: "Explain quantum entanglement and its implications for quantum computing in detail", expected: "expert" },
  { q: "Design a microservices architecture for a large-scale e-commerce platform with high availability", expected: "expert" },
  { q: "Analyze the philosophical implications of consciousness and free will in the context of determinism", expected: "expert" },
];

console.log('='.repeat(80));
console.log('COMPLEXITY DETECTION TEST');
console.log('='.repeat(80));
console.log();

let correct = 0;
let total = testQueries.length;

for (const test of testQueries) {
  const result = detector.detect(test.q, true);
  const match = result.complexity === test.expected ? '✅' : '❌';

  if (result.complexity === test.expected) correct++;

  console.log(`${match} Query: ${test.q}`);
  console.log(`   Expected: ${test.expected}, Got: ${result.complexity} (conf: ${result.confidence.toFixed(2)})`);

  if (result.metadata?.technicalTerms && result.metadata.technicalTerms.length > 0) {
    console.log(`   Technical Terms: ${result.metadata.technicalTerms.join(', ')}`);
  }
  if (result.metadata?.domains && result.metadata.domains.size > 0) {
    console.log(`   Domains: ${Array.from(result.metadata.domains).join(', ')}`);
  }
  console.log();
}

console.log('='.repeat(80));
console.log(`ACCURACY: ${correct}/${total} (${((correct/total)*100).toFixed(1)}%)`);
console.log('='.repeat(80));
