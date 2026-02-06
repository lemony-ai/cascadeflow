// Stats tracking for cascade operations

import { calculateCost, calculateSavings } from "../utils/pricing.js";
import type { CascadeResponse } from "./client.js";

export interface QueryStat {
  query: string;
  route: "draft_accepted" | "escalated" | "direct";
  draftModel: string;
  verifierModel: string;
  confidence?: number;
  domain?: string;
  draftTimeMs?: number;
  verifierTimeMs?: number;
  totalTimeMs: number;
  inputTokens: number;
  outputTokens: number;
  actualCost: number;
  baselineCost: number;
  response: string;
}

export class MetricsTracker {
  private stats: QueryStat[] = [];

  record(
    query: string,
    response: CascadeResponse,
    draftModel: string,
    verifierModel: string,
    totalTimeMs: number
  ): QueryStat {
    const cascade = response.cascade;
    const usage = response.usage;

    const route = cascade?.route ?? "draft_accepted";
    const inputTokens = usage?.prompt_tokens ?? 0;
    const outputTokens = usage?.completion_tokens ?? 0;

    // Actual cost based on which models were used
    let actualCost: number;
    if (route === "draft_accepted") {
      actualCost = calculateCost(draftModel, inputTokens, outputTokens);
    } else if (route === "escalated") {
      // Draft cost + verifier cost
      const draftCost = calculateCost(draftModel, inputTokens, outputTokens);
      const verifierCost = calculateCost(verifierModel, inputTokens, outputTokens);
      actualCost = draftCost + verifierCost;
    } else {
      actualCost = calculateCost(verifierModel, inputTokens, outputTokens);
    }

    // Baseline: what it would cost using verifier for everything
    const baselineCost = calculateCost(verifierModel, inputTokens, outputTokens);

    const stat: QueryStat = {
      query,
      route,
      draftModel,
      verifierModel,
      confidence: cascade?.confidence,
      domain: cascade?.domain,
      draftTimeMs: cascade?.draft_time_ms,
      verifierTimeMs: cascade?.verifier_time_ms,
      totalTimeMs,
      inputTokens,
      outputTokens,
      actualCost,
      baselineCost,
      response: response.choices?.[0]?.message?.content ?? "",
    };

    this.stats.push(stat);
    return stat;
  }

  getStats(): QueryStat[] {
    return [...this.stats];
  }

  clear(): void {
    this.stats = [];
  }

  get totalQueries(): number {
    return this.stats.length;
  }

  get acceptedCount(): number {
    return this.stats.filter((s) => s.route === "draft_accepted").length;
  }

  get escalatedCount(): number {
    return this.stats.filter((s) => s.route === "escalated").length;
  }

  get directCount(): number {
    return this.stats.filter((s) => s.route === "direct").length;
  }

  get acceptRate(): number {
    if (this.stats.length === 0) return 0;
    return (this.acceptedCount / this.stats.length) * 100;
  }

  get escalateRate(): number {
    if (this.stats.length === 0) return 0;
    return (this.escalatedCount / this.stats.length) * 100;
  }

  get directRate(): number {
    if (this.stats.length === 0) return 0;
    return (this.directCount / this.stats.length) * 100;
  }

  get totalActualCost(): number {
    return this.stats.reduce((s, q) => s + q.actualCost, 0);
  }

  get totalBaselineCost(): number {
    return this.stats.reduce((s, q) => s + q.baselineCost, 0);
  }

  get savingsPercent(): number {
    return calculateSavings(this.totalActualCost, this.totalBaselineCost);
  }

  get avgOverheadMs(): number {
    if (this.stats.length === 0) return 0;
    // Overhead = extra time from cascade logic (draft attempt on escalated queries)
    const escalated = this.stats.filter((s) => s.route === "escalated");
    if (escalated.length === 0) return 0;
    const totalDraftTime = escalated.reduce(
      (s, q) => s + (q.draftTimeMs ?? 0),
      0
    );
    return totalDraftTime / this.stats.length;
  }
}
