import fs from 'node:fs';

import { QueryResponseAlignmentScorer } from '../../packages/core/src/alignment';

type TestCase = {
  id: string;
  query: string;
  response: string;
};

type Result = {
  id: string;
  alignmentScore: number;
  reasoning: string;
  features: Record<string, unknown>;
  isTrivial: boolean;
  baselineUsed: number;
};

function readInput(): TestCase[] {
  const argPath = process.argv[2];
  if (argPath) {
    const content = fs.readFileSync(argPath, 'utf-8');
    return JSON.parse(content) as TestCase[];
  }

  const stdin = fs.readFileSync(0, 'utf-8').trim();
  if (!stdin) {
    return [];
  }
  return JSON.parse(stdin) as TestCase[];
}

function main(): void {
  const cases = readInput();
  const scorer = new QueryResponseAlignmentScorer();

  const results: Result[] = cases.map((testCase) => {
    const analysis = scorer.score(testCase.query, testCase.response, 0.5, true);

    return {
      id: testCase.id,
      alignmentScore: analysis.alignmentScore,
      reasoning: analysis.reasoning,
      features: analysis.features,
      isTrivial: analysis.isTrivial,
      baselineUsed: analysis.baselineUsed,
    };
  });

  process.stdout.write(`${JSON.stringify(results, null, 2)}\n`);
}

main();
