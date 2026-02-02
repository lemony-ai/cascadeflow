import fs from 'node:fs';
import path from 'node:path';

import { QueryResponseAlignmentScorer } from '../packages/core/src/alignment';

type AlignmentCase = {
  id: string;
  query: string;
  response: string;
  difficulty?: number;
};

const inputPath = process.argv[2];
if (!inputPath) {
  console.error('Usage: tsx scripts/alignment-parity.ts <cases.json>');
  process.exit(1);
}

const absolutePath = path.resolve(inputPath);
const raw = fs.readFileSync(absolutePath, 'utf8');
const cases: AlignmentCase[] = JSON.parse(raw);

const scorer = new QueryResponseAlignmentScorer();
const results = cases.map((testCase) => {
  const analysis = scorer.score(
    testCase.query,
    testCase.response,
    testCase.difficulty ?? 0.5,
    true
  );
  return { id: testCase.id, score: analysis.alignmentScore };
});

process.stdout.write(JSON.stringify({ results }, null, 2));
