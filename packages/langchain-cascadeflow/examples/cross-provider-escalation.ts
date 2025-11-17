/**
 * Cross-Provider Escalation Demo - Haiku → GPT-5
 *
 * This example demonstrates cross-provider cascading with challenging queries
 * designed to trigger escalations from Claude Haiku to GPT-5.
 *
 * Purpose: Show both ChatAnthropic AND ChatOpenAI traces in LangSmith
 *
 * Requirements:
 *   - OPENAI_API_KEY
 *   - ANTHROPIC_API_KEY
 *   - LANGSMITH_API_KEY
 *   - LANGSMITH_PROJECT
 *   - LANGSMITH_TRACING=true
 */

import { ChatOpenAI } from '@langchain/openai';
import { ChatAnthropic } from '@langchain/anthropic';
import { CascadeFlow } from '../src/index.js';

const COLORS = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
  bold: '\x1b[1m',
};

// Hard/Expert queries that are likely to trigger escalations
const EXPERT_QUERIES = [
  {
    type: 'Expert',
    query: 'Design a distributed consensus algorithm for a multi-region database system with network partitions, Byzantine fault tolerance, and linearizable consistency guarantees. Include formal correctness proofs.',
  },
  {
    type: 'Expert',
    query: 'Implement a type-safe dependency injection container in TypeScript that supports circular dependencies, lazy instantiation, scoped lifetimes (singleton, transient, scoped), and compile-time validation of dependency graphs.',
  },
  {
    type: 'Hard',
    query: 'Design a real-time collaborative text editor conflict resolution algorithm (CRDT or OT) that handles concurrent edits, maintains strong eventual consistency, and optimizes for low latency in peer-to-peer networks.',
  },
  {
    type: 'Expert',
    query: 'Create a zero-downtime database migration strategy for a sharded PostgreSQL cluster with 1TB+ data, handling schema changes, data transformations, and rollback capabilities while maintaining ACID guarantees.',
  },
  {
    type: 'Hard',
    query: 'Implement a distributed rate limiter using Redis that supports sliding window counters, per-tenant limits, burst allowances, and graceful degradation under high load. Include fault tolerance for Redis failures.',
  },
  {
    type: 'Expert',
    query: 'Design a compacting garbage collector for a JIT-compiled language with precise stack scanning, generational collection, concurrent marking, and incremental sweeping to minimize pause times below 10ms.',
  },
  {
    type: 'Hard',
    query: 'Build a circuit breaker pattern implementation with exponential backoff, jitter, half-open state testing, bulkhead isolation, and integration with distributed tracing for microservices resilience.',
  },
  {
    type: 'Expert',
    query: 'Implement a sound type checker for a gradually-typed language with structural subtyping, intersection/union types, generic variance, and flow-sensitive type refinement. Prove soundness and completeness.',
  },
];

async function main() {
  console.log(`${COLORS.magenta}${COLORS.bold}╔════════════════════════════════════════════════════════════════════╗${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}║   CROSS-PROVIDER ESCALATION DEMO - Haiku → GPT-5                  ║${COLORS.reset}`);
  console.log(`${COLORS.magenta}${COLORS.bold}╚════════════════════════════════════════════════════════════════════╝${COLORS.reset}\n`);

  // ========================================================================
  // STEP 1: Verify Configuration
  // ========================================================================

  if (!process.env.LANGSMITH_API_KEY) {
    console.log(`${COLORS.red}❌ LANGSMITH_API_KEY not set${COLORS.reset}`);
    return;
  }

  if (!process.env.ANTHROPIC_API_KEY) {
    console.log(`${COLORS.red}❌ ANTHROPIC_API_KEY not set${COLORS.reset}`);
    return;
  }

  console.log(`${COLORS.green}✓ LangSmith tracing enabled${COLORS.reset}`);
  console.log(`  Project: ${process.env.LANGSMITH_PROJECT || 'default'}`);
  console.log(`  Dashboard: ${COLORS.cyan}https://smith.langchain.com${COLORS.reset}\n`);

  // ========================================================================
  // STEP 2: Create Cross-Provider Cascade
  // ========================================================================

  console.log(`${COLORS.bold}🤖 Creating Cross-Provider Cascade${COLORS.reset}\n`);

  // Drafter: Claude 3.5 Haiku (Anthropic) - Fast, cheap
  const haiku = new ChatAnthropic({
    model: 'claude-3-5-haiku-20241022',
    temperature: 1.0,
  });

  // Verifier: GPT-5 (OpenAI) - Accurate, expensive
  const gpt5 = new ChatOpenAI({
    model: 'gpt-5',
    temperature: 1.0,
  });

  const cascade = new CascadeFlow({
    drafter: haiku,
    verifier: gpt5,
    qualityThreshold: 0.7, // Standard threshold
    enableCostTracking: true,
    costTrackingProvider: 'langsmith',
    enablePreRouter: true, // Enable complexity-based routing
  });

  console.log(`${COLORS.green}✓ Cascade configured${COLORS.reset}`);
  console.log(`  Drafter: ${COLORS.cyan}Claude 3.5 Haiku${COLORS.reset} (Anthropic)`);
  console.log(`  Verifier: ${COLORS.cyan}GPT-5${COLORS.reset} (OpenAI)`);
  console.log(`  Quality Threshold: 0.7`);
  console.log(`  PreRouter: ${COLORS.green}Enabled${COLORS.reset} (hard/expert queries → direct to GPT-5)\n`);

  // ========================================================================
  // STEP 3: Run Expert Queries
  // ========================================================================

  console.log(`${COLORS.bold}🚀 Running ${EXPERT_QUERIES.length} Expert Queries${COLORS.reset}\n`);
  console.log(`${COLORS.yellow}These challenging queries are designed to trigger escalations${COLORS.reset}`);
  console.log(`${COLORS.yellow}Watch for BOTH ChatAnthropic AND ChatOpenAI in LangSmith!${COLORS.reset}\n`);
  console.log(`${COLORS.cyan}${'='.repeat(80)}${COLORS.reset}\n`);

  let cascaded = 0;
  let escalated = 0;

  for (let i = 0; i < EXPERT_QUERIES.length; i++) {
    const { type, query } = EXPERT_QUERIES[i];

    console.log(`${COLORS.blue}Query ${i + 1}/${EXPERT_QUERIES.length}${COLORS.reset} [${COLORS.red}${type}${COLORS.reset}]`);
    console.log(`${query.substring(0, 100)}...`);

    const startTime = Date.now();
    const result = await cascade.invoke(query);
    const elapsed = Date.now() - startTime;

    const stats = cascade.getLastCascadeResult();

    if (stats) {
      const preview = result.content.toString().substring(0, 120);
      console.log(`  Response: ${preview}...`);

      if (stats.modelUsed === 'drafter') {
        console.log(`  ${COLORS.green}✓ CASCADED${COLORS.reset} to Haiku (quality: ${stats.drafterQuality?.toFixed(2)}, ${elapsed}ms)`);
        console.log(`  ${COLORS.cyan}→ LangSmith shows: ChatAnthropic (Haiku)${COLORS.reset}`);
        cascaded++;
      } else {
        console.log(`  ${COLORS.yellow}⚠ ESCALATED${COLORS.reset} to GPT-5 (quality: ${stats.drafterQuality?.toFixed(2)}, ${elapsed}ms)`);
        console.log(`  ${COLORS.magenta}→ LangSmith shows: ChatAnthropic (Haiku) + ChatOpenAI (GPT-5)${COLORS.reset}`);
        escalated++;
      }
    }

    console.log();

    // Small delay to avoid rate limits
    await new Promise(resolve => setTimeout(resolve, 500));
  }

  // ========================================================================
  // STEP 4: Summary
  // ========================================================================

  console.log(`${COLORS.cyan}${'='.repeat(80)}${COLORS.reset}\n`);
  console.log(`${COLORS.magenta}${COLORS.bold}📊 RESULTS SUMMARY${COLORS.reset}\n`);

  const total = EXPERT_QUERIES.length;
  const cascadeRate = (cascaded / total) * 100;
  const escalationRate = (escalated / total) * 100;

  console.log(`${COLORS.bold}Performance:${COLORS.reset}`);
  console.log(`  Total Queries: ${total}`);
  console.log(`  ${COLORS.green}Cascaded (Haiku only):${COLORS.reset} ${cascaded} (${cascadeRate.toFixed(0)}%)`);
  console.log(`  ${COLORS.yellow}Escalated (Haiku → GPT-5):${COLORS.reset} ${escalated} (${escalationRate.toFixed(0)}%)\n`);

  // ========================================================================
  // STEP 5: LangSmith Instructions
  // ========================================================================

  console.log(`${COLORS.magenta}${COLORS.bold}📈 VIEW IN LANGSMITH${COLORS.reset}\n`);

  console.log(`${COLORS.bold}What You'll See:${COLORS.reset}\n`);

  console.log(`${COLORS.green}1. For Cascaded Queries (Haiku only):${COLORS.reset}`);
  console.log(`   • Single trace: ${COLORS.cyan}ChatAnthropic${COLORS.reset} (claude-3-5-haiku)`);
  console.log(`   • Cascade metadata shows: ${COLORS.green}model_used: "drafter"${COLORS.reset}\n`);

  console.log(`${COLORS.yellow}2. For Escalated Queries (Haiku → GPT-5):${COLORS.reset}`);
  console.log(`   • First trace: ${COLORS.cyan}ChatAnthropic${COLORS.reset} (claude-3-5-haiku) - tried first`);
  console.log(`   • Second trace: ${COLORS.cyan}ChatOpenAI${COLORS.reset} (gpt-5) - used for response`);
  console.log(`   • Cascade metadata shows: ${COLORS.yellow}model_used: "verifier"${COLORS.reset}\n`);

  console.log(`${COLORS.bold}How to Find Traces:${COLORS.reset}`);
  console.log(`  1. Go to: ${COLORS.cyan}https://smith.langchain.com${COLORS.reset}`);
  console.log(`  2. Select project: ${COLORS.yellow}${process.env.LANGSMITH_PROJECT || 'default'}${COLORS.reset}`);
  console.log(`  3. Filter by: ${COLORS.yellow}last 1 hour${COLORS.reset}`);
  console.log(`  4. Look for "ChatAnthropic" and "ChatOpenAI" runs`);
  console.log(`  5. Click on each to see token usage and costs\n`);

  console.log(`${COLORS.bold}Expected Results:${COLORS.reset}`);
  if (escalated > 0) {
    console.log(`  ${COLORS.green}✓${COLORS.reset} You should see ${COLORS.yellow}${escalated} escalations${COLORS.reset} showing BOTH providers`);
    console.log(`  ${COLORS.green}✓${COLORS.reset} Escalated queries show dual traces (Anthropic + OpenAI)`);
  }
  if (cascaded > 0) {
    console.log(`  ${COLORS.green}✓${COLORS.reset} You should see ${COLORS.cyan}${cascaded} cascades${COLORS.reset} showing only Anthropic`);
  }
  console.log(`  ${COLORS.green}✓${COLORS.reset} Each trace includes token counts and metadata\n`);

  console.log(`${COLORS.green}${COLORS.bold}✓ Demo Complete!${COLORS.reset}`);
  console.log(`${COLORS.cyan}${'='.repeat(80)}${COLORS.reset}\n`);
}

main().catch(console.error);
