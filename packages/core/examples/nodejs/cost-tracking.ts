/**
 * cascadeflow - Cost Tracking Example (TypeScript)
 *
 * Comprehensive cost tracking and budget management with cascadeflow.
 *
 * This example demonstrates:
 * - Real-time cost tracking across queries
 * - Per-model and per-provider cost analysis
 * - Budget limits and alerts
 * - Cost history and trends
 * - Manual cost tracking implementation (TypeScript doesn't have telemetry module yet)
 *
 * Requirements:
 *     - @cascadeflow/core
 *     - OpenAI API key
 *
 * Setup:
 *     npm install @cascadeflow/core
 *     export OPENAI_API_KEY="your-key-here"
 *     npx tsx cost-tracking.ts
 *
 * What You'll See:
 *     - Cost tracking for multiple queries
 *     - Budget warnings when approaching limits
 *     - Detailed breakdowns by model and provider
 *     - Cost optimization insights
 *
 * Documentation:
 *     📖 Cost Tracking Guide: docs/guides/cost_tracking.md
 *     📚 Examples README: examples/README.md
 */

import { CascadeAgent, type ModelConfig, type CascadeResult } from '@cascadeflow/core';

// ═══════════════════════════════════════════════════════════════════════
// Simple Cost Tracker Implementation
// ═══════════════════════════════════════════════════════════════════════
// Note: TypeScript doesn't have telemetry module yet, so we implement basic tracking

interface CostEntry {
  timestamp: Date;
  model: string;
  provider: string;
  tokens: number;
  cost: number;
  queryId: string;
  metadata?: Record<string, any>;
}

class SimpleCostTracker {
  private entries: CostEntry[] = [];
  private budgetLimit: number;
  private warnThreshold: number;
  private verbose: boolean;

  constructor(budgetLimit: number, warnThreshold: number = 0.8, verbose: boolean = true) {
    this.budgetLimit = budgetLimit;
    this.warnThreshold = warnThreshold;
    this.verbose = verbose;
  }

  addCost(entry: Omit<CostEntry, 'timestamp'>) {
    const fullEntry: CostEntry = {
      ...entry,
      timestamp: new Date(),
    };
    this.entries.push(fullEntry);

    // Check budget
    const totalCost = this.getTotalCost();
    if (totalCost >= this.budgetLimit) {
      console.warn(`⚠️  Budget limit reached: $${totalCost.toFixed(6)} >= $${this.budgetLimit.toFixed(2)}`);
    } else if (totalCost >= this.budgetLimit * this.warnThreshold) {
      const pct = (totalCost / this.budgetLimit) * 100;
      console.warn(`⚠️  Budget warning: $${totalCost.toFixed(6)} (${pct.toFixed(0)}% of limit)`);
    }
  }

  getTotalCost(): number {
    return this.entries.reduce((sum, e) => sum + e.cost, 0);
  }

  getCostByModel(): Record<string, { count: number; cost: number; tokens: number }> {
    const byModel: Record<string, { count: number; cost: number; tokens: number }> = {};
    for (const entry of this.entries) {
      if (!byModel[entry.model]) {
        byModel[entry.model] = { count: 0, cost: 0, tokens: 0 };
      }
      byModel[entry.model].count++;
      byModel[entry.model].cost += entry.cost;
      byModel[entry.model].tokens += entry.tokens;
    }
    return byModel;
  }

  getCostByProvider(): Record<string, { count: number; cost: number; tokens: number }> {
    const byProvider: Record<string, { count: number; cost: number; tokens: number }> = {};
    for (const entry of this.entries) {
      if (!byProvider[entry.provider]) {
        byProvider[entry.provider] = { count: 0, cost: 0, tokens: 0 };
      }
      byProvider[entry.provider].count++;
      byProvider[entry.provider].cost += entry.cost;
      byProvider[entry.provider].tokens += entry.tokens;
    }
    return byProvider;
  }

  getRecentEntries(n: number): CostEntry[] {
    return this.entries.slice(-n);
  }

  printSummary() {
    console.log('💰 COST TRACKER SUMMARY');
    console.log('='.repeat(60));

    const totalCost = this.getTotalCost();
    const remaining = this.budgetLimit - totalCost;
    const usedPct = (totalCost / this.budgetLimit) * 100;

    console.log('\nBudget Status:');
    console.log(`  Total Cost:       $${totalCost.toFixed(6)}`);
    console.log(`  Budget Limit:     $${this.budgetLimit.toFixed(2)}`);
    console.log(`  Remaining:        $${remaining.toFixed(6)}`);
    console.log(`  Used:             ${usedPct.toFixed(1)}%`);

    console.log('\nCost by Model:');
    const byModel = this.getCostByModel();
    for (const [model, stats] of Object.entries(byModel)) {
      console.log(`  ${model}:`);
      console.log(`    Queries: ${stats.count}`);
      console.log(`    Cost:    $${stats.cost.toFixed(6)}`);
      console.log(`    Tokens:  ${stats.tokens.toLocaleString()}`);
    }

    console.log('\nCost by Provider:');
    const byProvider = this.getCostByProvider();
    for (const [provider, stats] of Object.entries(byProvider)) {
      console.log(`  ${provider}:`);
      console.log(`    Queries: ${stats.count}`);
      console.log(`    Cost:    $${stats.cost.toFixed(6)}`);
      console.log(`    Tokens:  ${stats.tokens.toLocaleString()}`);
    }

    console.log('='.repeat(60));
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Simple Metrics Collector
// ═══════════════════════════════════════════════════════════════════════

interface MetricEntry {
  result: CascadeResult;
  routingStrategy: string;
  complexity: string;
}

class SimpleMetricsCollector {
  private entries: MetricEntry[] = [];

  record(result: CascadeResult, routingStrategy: string, complexity: string) {
    this.entries.push({ result, routingStrategy, complexity });
  }

  getSummary() {
    const totalQueries = this.entries.length;
    const cascadeUsed = this.entries.filter(e => e.routingStrategy === 'cascade').length;
    const cascadeRate = totalQueries > 0 ? (cascadeUsed / totalQueries) * 100 : 0;
    const avgLatency = totalQueries > 0
      ? this.entries.reduce((sum, e) => sum + (e.result.latencyMs || 0), 0) / totalQueries
      : 0;
    const totalCost = this.entries.reduce((sum, e) => sum + e.result.totalCost, 0);

    return {
      total_queries: totalQueries,
      cascade_used: cascadeUsed,
      cascade_rate: cascadeRate,
      avg_latency_ms: avgLatency,
      total_cost: totalCost,
    };
  }
}

// ═══════════════════════════════════════════════════════════════════════
// Main Example
// ═══════════════════════════════════════════════════════════════════════

async function main() {
  // STEP 1: Check API Key
  if (!process.env.OPENAI_API_KEY) {
    console.error("❌ Set OPENAI_API_KEY first: export OPENAI_API_KEY='sk-...'");
    return;
  }

  console.log('💰 cascadeflow Cost Tracking\n');

  // STEP 2: Setup Cost Tracker with Budget
  const costTracker = new SimpleCostTracker(
    1.00,  // $1.00 budget limit
    0.8,   // Warn at 80%
    true   // Verbose
  );

  console.log('✓ Cost tracker initialized');
  console.log('  Budget limit: $1.00');
  console.log('  Warn threshold: 80%\n');

  // STEP 3: Setup Agent with Cascade
  const models: ModelConfig[] = [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,  // Cost per 1K tokens
    },
    {
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.00625,
    },
  ];

  const agent = new CascadeAgent({
    models,
    quality: {
      threshold: 0.40,  // CASCADE-OPTIMIZED: Much lower than production (0.7)
      requireMinimumTokens: 5,  // Relaxed from 10 for short answers
    },
  });

  console.log('✓ Agent ready with 2-tier cascade\n');

  // STEP 4: Setup Metrics Collector
  const metrics = new SimpleMetricsCollector();
  console.log('✓ Metrics collector initialized\n');

  // EXAMPLE 1: Track Multiple Queries
  const queries = [
    'What is Python?',
    'Explain quantum computing',
    'What are the health benefits of green tea?',
    'Describe the history of the Eiffel Tower',
    'Explain machine learning in detail',
  ];

  console.log('='.repeat(60));
  console.log('Running queries with cost tracking...\n');

  for (let i = 0; i < queries.length; i++) {
    const query = queries[i];
    console.log(`Query ${i + 1}/${queries.length}: ${query.substring(0, 50)}...`);

    // Execute query
    const result = await agent.run(query, { maxTokens: 150 });

    // Extract cost information
    const totalCost = result.totalCost;
    const draftCost = result.draftCost || 0;
    const verifierCost = result.verifierCost || 0;

    // Estimate tokens (rough approximation from content)
    const totalTokens = Math.ceil(result.content.split(/\s+/).length * 1.3);

    // Track costs
    if (draftCost > 0 && result.draftModel) {
      costTracker.addCost({
        model: result.draftModel,
        provider: 'openai',
        tokens: Math.floor(totalTokens * 0.5),
        cost: draftCost,
        queryId: `query-${i + 1}`,
        metadata: {
          query: query.substring(0, 50),
          cascaded: result.cascaded,
          role: 'draft',
          draftAccepted: result.draftAccepted,
        },
      });
    }

    if (verifierCost > 0 && result.verifierModel) {
      costTracker.addCost({
        model: result.verifierModel,
        provider: 'openai',
        tokens: Math.floor(totalTokens * 0.5),
        cost: verifierCost,
        queryId: `query-${i + 1}`,
        metadata: {
          query: query.substring(0, 50),
          cascaded: result.cascaded,
          role: 'verifier',
          draftAccepted: result.draftAccepted,
        },
      });
    }

    // If no breakdown, track total
    if (draftCost === 0 && verifierCost === 0 && totalCost > 0) {
      costTracker.addCost({
        model: result.modelUsed,
        provider: 'openai',
        tokens: totalTokens,
        cost: totalCost,
        queryId: `query-${i + 1}`,
        metadata: {
          query: query.substring(0, 50),
          cascaded: result.cascaded,
          no_breakdown: true,
        },
      });
    }

    // Track in metrics collector
    metrics.record(
      result,
      result.routingStrategy === 'direct' ? 'direct' : 'cascade',
      result.routingStrategy === 'direct' ? 'simple' : 'complex'
    );

    // Show result
    console.log(`  💰 Cost: $${totalCost.toFixed(6)}`);

    if (result.routingStrategy === 'direct') {
      // Direct routing - only one model used
      console.log(`  🎯 Model: ${result.modelUsed}`);
    } else if (result.draftAccepted) {
      // Draft was accepted - only draft model was actually used
      console.log(`  🎯 Model: ${result.draftModel || result.modelUsed} (draft accepted)`);
      console.log('  ✅ Saved cost by using cheap model!');
    } else if (result.cascaded) {
      // Draft was rejected - both models were used
      console.log(`  🎯 Model: ${result.verifierModel || result.modelUsed} (after cascade)`);
      console.log('  🔄 Draft rejected, used verifier for quality');
    } else {
      // Fallback - shouldn't happen with correct routing
      console.log(`  🎯 Model: ${result.modelUsed}`);
    }
    console.log();
  }

  // STEP 5: Display Cost Tracker Summary
  console.log('='.repeat(60));
  costTracker.printSummary();

  // STEP 6: Display Metrics Summary
  const metricsSummary = metrics.getSummary();

  console.log('\n='.repeat(60));
  console.log('METRICS SUMMARY');
  console.log('='.repeat(60));
  console.log(`Total Queries:     ${metricsSummary.total_queries}`);
  console.log(`Cascaded Queries:  ${metricsSummary.cascade_used}`);
  console.log(`Cascade Rate:      ${metricsSummary.cascade_rate.toFixed(1)}%`);
  console.log(`Avg Latency:       ${metricsSummary.avg_latency_ms.toFixed(0)}ms`);
  console.log(`Total Cost:        $${metricsSummary.total_cost.toFixed(6)}`);
  console.log('='.repeat(60) + '\n');

  // STEP 7: Advanced Cost Analysis
  console.log('='.repeat(60));
  console.log('ADVANCED COST ANALYSIS');
  console.log('='.repeat(60));

  // Get recent entries
  const recent = costTracker.getRecentEntries(3);
  console.log(`\nMost Recent ${recent.length} Entries:`);
  for (const entry of recent) {
    const time = entry.timestamp.toLocaleTimeString('en-US', { hour12: false });
    console.log(
      `  ${time} | ${entry.model.padEnd(15)} | $${entry.cost.toFixed(6)} | ${entry.tokens.toLocaleString()} tokens`
    );
  }

  console.log('='.repeat(60) + '\n');

  // KEY TAKEAWAYS
  console.log('📚 Key takeaways:');
  console.log('\n  Cost Tracking Components:');
  console.log('  ├─ SimpleCostTracker: Monitors costs across queries');
  console.log('  ├─ SimpleMetricsCollector: Aggregates all statistics');
  console.log('  └─ Budget alerts: Warns and prevents overspending');

  console.log('\n  Integration:');
  console.log('  ├─ Extract costs from CascadeResult');
  console.log('  ├─ Track costs over time');
  console.log('  └─ Aggregate comprehensive analytics');

  console.log('\n  Cost Optimization:');
  console.log('  ├─ Track per-model costs to identify expensive patterns');
  console.log('  ├─ Monitor cascade rate to optimize quality/cost balance');
  console.log('  └─ Set budgets to prevent unexpected spending');

  console.log('\n  CascadeResult Structure:');
  console.log('  ├─ result.totalCost - Total cost for this query');
  console.log('  ├─ result.draftCost, result.verifierCost - Breakdown by model');
  console.log('  ├─ result.draftModel, result.verifierModel - Models used');
  console.log('  └─ result.cascaded, result.draftAccepted - Routing info');

  console.log('\n📚 Learn more: docs/guides/cost_tracking.md\n');
}

main().catch(error => {
  console.error('\n❌ Error:', error.message);
  console.log('💡 Tip: Make sure OPENAI_API_KEY is set correctly');
});
