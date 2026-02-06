#!/usr/bin/env node
import React, { useState, useEffect, useCallback } from "react";
import { render, Box, Text, useApp, useInput } from "ink";
import Spinner from "ink-spinner";

// ─── ASCII Art ────────────────────────────────────────────────────────────────

const LOGO = `
   ██████╗ █████╗ ███████╗ ██████╗ █████╗ ██████╗ ███████╗
  ██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝
  ██║     ███████║███████╗██║     ███████║██║  ██║█████╗
  ██║     ██╔══██║╚════██║██║     ██╔══██║██║  ██║██╔══╝
  ╚██████╗██║  ██║███████║╚██████╗██║  ██║██████╔╝███████╗
   ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚═════╝ ╚══════╝
  ███████╗██╗      ██████╗ ██╗    ██╗
  ██╔════╝██║     ██╔═══██╗██║    ██║
  █████╗  ██║     ██║   ██║██║ █╗ ██║
  ██╔══╝  ██║     ██║   ██║██║███╗██║
  ██║     ███████╗╚██████╔╝╚███╔███╔╝
  ╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝`;

// ─── Mock Data ────────────────────────────────────────────────────────────────

interface QueryResult {
  query: string;
  domain: string;
  draftModel: string;
  draftTime: number;
  draftConfidence: number;
  accepted: boolean;
  verifierModel?: string;
  verifierTime?: number;
  draftCost: number;
  verifierCost?: number;
  totalCost: number;
  baselineCost: number;
}

const QUERIES: {
  query: string;
  domain: string;
  draftConfidence: number;
  accepted: boolean;
}[] = [
  {
    query: "What is the capital of France?",
    domain: "general-knowledge",
    draftConfidence: 0.97,
    accepted: true,
  },
  {
    query: "Translate 'hello world' to Spanish",
    domain: "translation",
    draftConfidence: 0.95,
    accepted: true,
  },
  {
    query: "Write a Python quicksort implementation",
    domain: "code-generation",
    draftConfidence: 0.58,
    accepted: false,
  },
  {
    query: "Summarize the key points of transformer architecture",
    domain: "technical-summary",
    draftConfidence: 0.42,
    accepted: false,
  },
  {
    query: "What is 15% of 340?",
    domain: "math",
    draftConfidence: 0.99,
    accepted: true,
  },
  {
    query: "Draft a formal email declining a meeting",
    domain: "writing",
    draftConfidence: 0.91,
    accepted: true,
  },
  {
    query: "Explain quantum entanglement to a 5-year-old",
    domain: "science",
    draftConfidence: 0.63,
    accepted: false,
  },
  {
    query: "List 3 benefits of regular exercise",
    domain: "health",
    draftConfidence: 0.96,
    accepted: true,
  },
  {
    query: "Compare microservices vs monolith architecture with tradeoffs",
    domain: "system-design",
    draftConfidence: 0.35,
    accepted: false,
  },
  {
    query: "Convert 72°F to Celsius",
    domain: "math",
    draftConfidence: 0.99,
    accepted: true,
  },
  {
    query: "Write a haiku about programming",
    domain: "creative-writing",
    draftConfidence: 0.88,
    accepted: true,
  },
  {
    query: "Prove that √2 is irrational",
    domain: "math-proof",
    draftConfidence: 0.29,
    accepted: false,
  },
];

type ProviderOption = "openai" | "anthropic" | "mixed";

interface ProviderConfig {
  draftModel: string;
  verifierModel: string;
  draftCostPer1k: number;
  verifierCostPer1k: number;
}

const PROVIDERS: Record<ProviderOption, ProviderConfig> = {
  openai: {
    draftModel: "GPT-4o-mini",
    verifierModel: "GPT-4o",
    draftCostPer1k: 0.15,
    verifierCostPer1k: 2.5,
  },
  anthropic: {
    draftModel: "Haiku 3.5",
    verifierModel: "Sonnet 4",
    draftCostPer1k: 0.25,
    verifierCostPer1k: 3.0,
  },
  mixed: {
    draftModel: "GPT-4o-mini",
    verifierModel: "Sonnet 4",
    draftCostPer1k: 0.15,
    verifierCostPer1k: 3.0,
  },
};

function buildResult(
  q: (typeof QUERIES)[number],
  provider: ProviderConfig
): QueryResult {
  const draftTime = 80 + Math.random() * 200;
  const draftCost = provider.draftCostPer1k * (0.3 + Math.random() * 0.4);
  const verifierTime = q.accepted
    ? undefined
    : 400 + Math.random() * 800;
  const verifierCost = q.accepted
    ? undefined
    : provider.verifierCostPer1k * (0.5 + Math.random() * 0.6);

  return {
    query: q.query,
    domain: q.domain,
    draftModel: provider.draftModel,
    draftTime,
    draftConfidence: q.draftConfidence,
    accepted: q.accepted,
    verifierModel: q.accepted ? undefined : provider.verifierModel,
    verifierTime,
    draftCost,
    verifierCost,
    totalCost: draftCost + (verifierCost ?? 0),
    baselineCost: provider.verifierCostPer1k * (0.5 + Math.random() * 0.6),
  };
}

// ─── Components ───────────────────────────────────────────────────────────────

function HorizontalRule() {
  return (
    <Box marginY={0}>
      <Text color="gray">
        {"─".repeat(68)}
      </Text>
    </Box>
  );
}

function ProgressBar({
  percent,
  width = 30,
  color = "green",
}: {
  percent: number;
  width?: number;
  color?: string;
}) {
  const filled = Math.round((percent / 100) * width);
  const empty = width - filled;
  return (
    <Text>
      <Text color="gray">[</Text>
      <Text color={color}>{"█".repeat(filled)}</Text>
      <Text color="gray">{"░".repeat(empty)}</Text>
      <Text color="gray">]</Text>
      <Text color="white" bold>
        {" "}
        {percent.toFixed(1)}%
      </Text>
    </Text>
  );
}

// ─── Welcome Screen ──────────────────────────────────────────────────────────

function WelcomeScreen({ onContinue }: { onContinue: () => void }) {
  const [blink, setBlink] = useState(true);

  useEffect(() => {
    const timer = setInterval(() => setBlink((b) => !b), 600);
    return () => clearInterval(timer);
  }, []);

  useInput((_input, _key) => {
    onContinue();
  });

  return (
    <Box flexDirection="column" alignItems="center" paddingY={1}>
      <Text color="cyan" bold>
        {LOGO}
      </Text>
      <Box marginTop={1}>
        <Text color="yellow" bold>
          {"  ⚡ Intelligent LLM Cascade Routing ⚡"}
        </Text>
      </Box>
      <Box marginTop={1} flexDirection="column" alignItems="center">
        <Text color="gray">
          Route queries through draft → verify pipelines.
        </Text>
        <Text color="gray">
          Accept cheap fast answers. Escalate only when needed.
        </Text>
        <Text color="green" bold>
          Save 40-70% on LLM costs with zero quality loss.
        </Text>
      </Box>
      <Box marginTop={2}>
        <Text color={blink ? "white" : "gray"} bold>
          {"  ▶  Press any key to begin  ◀"}
        </Text>
      </Box>
    </Box>
  );
}

// ─── Provider Selection ──────────────────────────────────────────────────────

function ProviderSelect({
  onSelect,
}: {
  onSelect: (p: ProviderOption) => void;
}) {
  const options: { key: ProviderOption; label: string; desc: string }[] = [
    {
      key: "openai",
      label: "OpenAI",
      desc: "GPT-4o-mini → GPT-4o",
    },
    {
      key: "anthropic",
      label: "Anthropic",
      desc: "Haiku 3.5 → Sonnet 4",
    },
    {
      key: "mixed",
      label: "Mixed",
      desc: "GPT-4o-mini → Sonnet 4",
    },
  ];

  const [selected, setSelected] = useState(0);

  useInput((_input, key) => {
    if (key.upArrow) setSelected((s) => Math.max(0, s - 1));
    if (key.downArrow) setSelected((s) => Math.min(options.length - 1, s + 1));
    if (key.return) onSelect(options[selected]!.key);
  });

  return (
    <Box flexDirection="column" paddingX={4} paddingY={1}>
      <Text color="cyan" bold>
        {"  ┌─────────────────────────────────────────┐"}
      </Text>
      <Text color="cyan" bold>
        {"  │     SELECT CASCADE PROVIDER PAIR        │"}
      </Text>
      <Text color="cyan" bold>
        {"  └─────────────────────────────────────────┘"}
      </Text>
      <Box marginTop={1} />
      {options.map((opt, i) => (
        <Box key={opt.key} paddingX={2}>
          <Text
            color={i === selected ? "green" : "gray"}
            bold={i === selected}
          >
            {i === selected ? " ❯ " : "   "}
          </Text>
          <Text
            color={i === selected ? "white" : "gray"}
            bold={i === selected}
          >
            {opt.label}
          </Text>
          <Text color="gray"> — </Text>
          <Text color={i === selected ? "yellow" : "gray"}>{opt.desc}</Text>
        </Box>
      ))}
      <Box marginTop={1} paddingX={2}>
        <Text color="gray" italic>
          {"  ↑/↓ to navigate, Enter to select"}
        </Text>
      </Box>
    </Box>
  );
}

// ─── Query Execution View ────────────────────────────────────────────────────

type QueryPhase =
  | "idle"
  | "drafting"
  | "evaluating"
  | "accepted"
  | "escalating"
  | "verifying"
  | "verified"
  | "done";

function QueryRunner({
  provider,
  onComplete,
}: {
  provider: ProviderOption;
  onComplete: (results: QueryResult[]) => void;
}) {
  const config = PROVIDERS[provider];
  const [results, setResults] = useState<QueryResult[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [phase, setPhase] = useState<QueryPhase>("idle");
  const [currentResult, setCurrentResult] = useState<QueryResult | null>(null);
  const [runningCostSaved, setRunningCostSaved] = useState(0);
  const [runningTotalBaseline, setRunningTotalBaseline] = useState(0);

  const processQuery = useCallback(
    (idx: number) => {
      if (idx >= QUERIES.length) {
        return;
      }

      const q = QUERIES[idx]!;
      const result = buildResult(q, config);
      setCurrentResult(result);
      setPhase("drafting");

      setTimeout(() => {
        setPhase("evaluating");
        setTimeout(() => {
          if (result.accepted) {
            setPhase("accepted");
            setTimeout(() => {
              setPhase("done");
              setResults((prev) => [...prev, result]);
              setRunningCostSaved(
                (prev) => prev + (result.baselineCost - result.totalCost)
              );
              setRunningTotalBaseline(
                (prev) => prev + result.baselineCost
              );
              setCurrentIdx(idx + 1);
            }, 400);
          } else {
            setPhase("escalating");
            setTimeout(() => {
              setPhase("verifying");
              setTimeout(() => {
                setPhase("verified");
                setTimeout(() => {
                  setPhase("done");
                  setResults((prev) => [...prev, result]);
                  setRunningCostSaved(
                    (prev) => prev + (result.baselineCost - result.totalCost)
                  );
                  setRunningTotalBaseline(
                    (prev) => prev + result.baselineCost
                  );
                  setCurrentIdx(idx + 1);
                }, 400);
              }, 600);
            }, 350);
          }
        }, 350);
      }, 500);
    },
    [config]
  );

  useEffect(() => {
    if (currentIdx < QUERIES.length) {
      const timer = setTimeout(() => processQuery(currentIdx), 300);
      return () => clearTimeout(timer);
    } else if (currentIdx === QUERIES.length && results.length === QUERIES.length) {
      onComplete(results);
    }
  }, [currentIdx, processQuery, results, onComplete]);

  const savingsPercent =
    runningTotalBaseline > 0
      ? (runningCostSaved / runningTotalBaseline) * 100
      : 0;

  const completedCount = results.length;
  const acceptedCount = results.filter((r) => r.accepted).length;

  return (
    <Box flexDirection="column" paddingX={2} paddingY={1}>
      {/* Header */}
      <Box flexDirection="column">
        <Text color="cyan" bold>
          {"  ┌─────────────────────────────────────────────────────────────┐"}
        </Text>
        <Text color="cyan" bold>
          {"  │           CASCADE ROUTING — LIVE EXECUTION                 │"}
        </Text>
        <Text color="cyan" bold>
          {"  └─────────────────────────────────────────────────────────────┘"}
        </Text>
      </Box>

      {/* Provider info */}
      <Box marginTop={1} paddingX={2}>
        <Text color="gray">Provider: </Text>
        <Text color="yellow" bold>
          {config.draftModel}
        </Text>
        <Text color="gray"> → </Text>
        <Text color="magenta" bold>
          {config.verifierModel}
        </Text>
      </Box>

      {/* Progress bar */}
      <Box paddingX={2} marginTop={1}>
        <Text color="gray">Progress: </Text>
        <ProgressBar
          percent={(completedCount / QUERIES.length) * 100}
          width={35}
          color="cyan"
        />
        <Text color="gray">
          {" "}
          {completedCount}/{QUERIES.length}
        </Text>
      </Box>

      <HorizontalRule />

      {/* Current query processing */}
      {currentResult && phase !== "done" && (
        <Box flexDirection="column" paddingX={2} marginY={1}>
          <Box>
            <Text color="white" bold>
              Query {currentIdx + 1}:{" "}
            </Text>
            <Text color="white" italic>
              "{currentResult.query}"
            </Text>
          </Box>
          <Box marginTop={0}>
            <Text color="gray">Domain: </Text>
            <Text color="blue">{currentResult.domain}</Text>
          </Box>
          <Box marginTop={1} flexDirection="column">
            {/* Draft phase */}
            <Box>
              {phase === "drafting" ? (
                <Text color="yellow">
                  <Spinner type="dots" />{" "}
                </Text>
              ) : (
                <Text color="green">✔ </Text>
              )}
              <Text color={phase === "drafting" ? "yellow" : "green"}>
                Draft: {config.draftModel}
              </Text>
              {phase !== "drafting" && (
                <Text color="gray">
                  {" "}
                  ({currentResult.draftTime.toFixed(0)}ms, $
                  {currentResult.draftCost.toFixed(4)})
                </Text>
              )}
            </Box>

            {/* Evaluate phase */}
            {(phase === "evaluating" ||
              phase === "accepted" ||
              phase === "escalating" ||
              phase === "verifying" ||
              phase === "verified") && (
              <Box>
                {phase === "evaluating" ? (
                  <Text color="yellow">
                    <Spinner type="dots" />{" "}
                  </Text>
                ) : (
                  <Text color="green">✔ </Text>
                )}
                <Text
                  color={phase === "evaluating" ? "yellow" : "green"}
                >
                  Confidence: {(currentResult.draftConfidence * 100).toFixed(0)}%
                </Text>
                {phase !== "evaluating" && (
                  <Text>
                    {" "}
                    →{" "}
                    {currentResult.accepted ? (
                      <Text color="green" bold>
                        ACCEPTED
                      </Text>
                    ) : (
                      <Text color="red" bold>
                        REJECTED (below threshold)
                      </Text>
                    )}
                  </Text>
                )}
              </Box>
            )}

            {/* Escalation */}
            {(phase === "escalating" ||
              phase === "verifying" ||
              phase === "verified") &&
              !currentResult.accepted && (
                <Box>
                  <Text color="magenta">↗ </Text>
                  <Text color="magenta">
                    Escalating to {config.verifierModel}...
                  </Text>
                </Box>
              )}

            {/* Verifier */}
            {(phase === "verifying" || phase === "verified") &&
              !currentResult.accepted && (
                <Box>
                  {phase === "verifying" ? (
                    <Text color="magenta">
                      <Spinner type="dots" />{" "}
                    </Text>
                  ) : (
                    <Text color="green">✔ </Text>
                  )}
                  <Text
                    color={phase === "verifying" ? "magenta" : "green"}
                  >
                    Verifier: {config.verifierModel}
                  </Text>
                  {phase === "verified" && currentResult.verifierTime && (
                    <Text color="gray">
                      {" "}
                      ({currentResult.verifierTime.toFixed(0)}ms, $
                      {currentResult.verifierCost?.toFixed(4)})
                    </Text>
                  )}
                </Box>
              )}
          </Box>
        </Box>
      )}

      <HorizontalRule />

      {/* Live stats */}
      <Box paddingX={2} marginTop={0} flexDirection="column">
        <Text color="white" bold>
          Live Stats
        </Text>
        <Box marginTop={0}>
          <Box width={30}>
            <Text color="gray">Accepted by draft: </Text>
            <Text color="green" bold>
              {acceptedCount}
            </Text>
            <Text color="gray">/{completedCount}</Text>
          </Box>
          <Box>
            <Text color="gray">Escalated: </Text>
            <Text color="red" bold>
              {completedCount - acceptedCount}
            </Text>
            <Text color="gray">/{completedCount}</Text>
          </Box>
        </Box>
        <Box marginTop={0}>
          <Text color="gray">Cost savings: </Text>
          <ProgressBar
            percent={Math.max(0, savingsPercent)}
            width={25}
            color={savingsPercent > 40 ? "green" : "yellow"}
          />
        </Box>
      </Box>

      {/* Completed query log */}
      {results.length > 0 && (
        <Box flexDirection="column" paddingX={2} marginTop={1}>
          <Text color="gray" bold>
            Recent:
          </Text>
          {results.slice(-4).map((r, i) => (
            <Box key={i}>
              <Text color={r.accepted ? "green" : "magenta"}>
                {r.accepted ? " ✔" : " ↗"}
              </Text>
              <Text color="gray">
                {" "}
                {r.query.length > 45
                  ? r.query.slice(0, 42) + "..."
                  : r.query}
              </Text>
              <Text color="gray"> → </Text>
              <Text color={r.accepted ? "green" : "yellow"}>
                ${r.totalCost.toFixed(4)}
              </Text>
              <Text color="gray"> (saved </Text>
              <Text color="green">
                ${(r.baselineCost - r.totalCost).toFixed(4)}
              </Text>
              <Text color="gray">)</Text>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}

// ─── Summary Screen ──────────────────────────────────────────────────────────

function SummaryScreen({
  results,
  provider,
}: {
  results: QueryResult[];
  provider: ProviderOption;
}) {
  const { exit } = useApp();
  const config = PROVIDERS[provider];

  const totalQueries = results.length;
  const accepted = results.filter((r) => r.accepted).length;
  const escalated = totalQueries - accepted;
  const acceptRate = (accepted / totalQueries) * 100;

  const totalCost = results.reduce((s, r) => s + r.totalCost, 0);
  const baselineCost = results.reduce((s, r) => s + r.baselineCost, 0);
  const savings = baselineCost - totalCost;
  const savingsPercent = (savings / baselineCost) * 100;

  const avgLatencyDraft =
    results.reduce((s, r) => s + r.draftTime, 0) / totalQueries;
  const escalatedResults = results.filter((r) => !r.accepted);
  const avgLatencyVerifier =
    escalatedResults.length > 0
      ? escalatedResults.reduce((s, r) => s + (r.verifierTime ?? 0), 0) /
        escalatedResults.length
      : 0;
  const avgLatencyOverall =
    results.reduce(
      (s, r) => s + r.draftTime + (r.verifierTime ?? 0),
      0
    ) / totalQueries;

  useInput((_input, key) => {
    if (key.return || _input === "q") {
      exit();
    }
  });

  return (
    <Box flexDirection="column" paddingX={2} paddingY={1}>
      <Text color="cyan" bold>
        {"  ┌─────────────────────────────────────────────────────────────┐"}
      </Text>
      <Text color="cyan" bold>
        {"  │              CASCADE ROUTING — FINAL REPORT                │"}
      </Text>
      <Text color="cyan" bold>
        {"  └─────────────────────────────────────────────────────────────┘"}
      </Text>

      <Box marginTop={1} paddingX={2}>
        <Text color="gray">Pipeline: </Text>
        <Text color="yellow" bold>
          {config.draftModel}
        </Text>
        <Text color="gray"> → </Text>
        <Text color="magenta" bold>
          {config.verifierModel}
        </Text>
      </Box>

      <HorizontalRule />

      {/* Query Stats */}
      <Box flexDirection="column" paddingX={4} marginTop={0}>
        <Text color="white" bold underline>
          Query Statistics
        </Text>
        <Box marginTop={1} flexDirection="column">
          <Box>
            <Box width={32}>
              <Text color="gray">Total queries:</Text>
            </Box>
            <Text color="white" bold>
              {totalQueries}
            </Text>
          </Box>
          <Box>
            <Box width={32}>
              <Text color="gray">Accepted by draft model:</Text>
            </Box>
            <Text color="green" bold>
              {accepted}
            </Text>
            <Text color="gray"> ({acceptRate.toFixed(1)}%)</Text>
          </Box>
          <Box>
            <Box width={32}>
              <Text color="gray">Escalated to verifier:</Text>
            </Box>
            <Text color="magenta" bold>
              {escalated}
            </Text>
            <Text color="gray">
              {" "}
              ({(100 - acceptRate).toFixed(1)}%)
            </Text>
          </Box>
        </Box>
      </Box>

      <Box paddingX={4} marginTop={0}>
        <Text color="gray">Acceptance: </Text>
        <ProgressBar percent={acceptRate} width={35} color="green" />
      </Box>

      <HorizontalRule />

      {/* Cost Analysis */}
      <Box flexDirection="column" paddingX={4}>
        <Text color="white" bold underline>
          Cost Analysis
        </Text>
        <Box marginTop={1} flexDirection="column">
          <Box>
            <Box width={32}>
              <Text color="gray">Baseline cost (all verifier):</Text>
            </Box>
            <Text color="red" bold>
              ${baselineCost.toFixed(4)}
            </Text>
          </Box>
          <Box>
            <Box width={32}>
              <Text color="gray">Cascade cost:</Text>
            </Box>
            <Text color="green" bold>
              ${totalCost.toFixed(4)}
            </Text>
          </Box>
          <Box>
            <Box width={32}>
              <Text color="gray">Total saved:</Text>
            </Box>
            <Text color="green" bold>
              ${savings.toFixed(4)}
            </Text>
          </Box>
        </Box>
      </Box>

      <Box paddingX={4} marginTop={0}>
        <Text color="gray">Savings:    </Text>
        <ProgressBar
          percent={savingsPercent}
          width={35}
          color={savingsPercent > 50 ? "green" : "yellow"}
        />
      </Box>

      <HorizontalRule />

      {/* Latency */}
      <Box flexDirection="column" paddingX={4}>
        <Text color="white" bold underline>
          Latency
        </Text>
        <Box marginTop={1} flexDirection="column">
          <Box>
            <Box width={32}>
              <Text color="gray">Avg draft latency:</Text>
            </Box>
            <Text color="green" bold>
              {avgLatencyDraft.toFixed(0)}ms
            </Text>
          </Box>
          <Box>
            <Box width={32}>
              <Text color="gray">Avg verifier latency:</Text>
            </Box>
            <Text color="yellow" bold>
              {avgLatencyVerifier.toFixed(0)}ms
            </Text>
          </Box>
          <Box>
            <Box width={32}>
              <Text color="gray">Avg overall latency:</Text>
            </Box>
            <Text color="cyan" bold>
              {avgLatencyOverall.toFixed(0)}ms
            </Text>
          </Box>
        </Box>
      </Box>

      <HorizontalRule />

      {/* Per-query breakdown */}
      <Box flexDirection="column" paddingX={4}>
        <Text color="white" bold underline>
          Per-Query Breakdown
        </Text>
        <Box marginTop={1} flexDirection="column">
          <Box>
            <Box width={4}>
              <Text color="gray" bold>
                #
              </Text>
            </Box>
            <Box width={36}>
              <Text color="gray" bold>
                Query
              </Text>
            </Box>
            <Box width={10}>
              <Text color="gray" bold>
                Route
              </Text>
            </Box>
            <Box width={10}>
              <Text color="gray" bold>
                Cost
              </Text>
            </Box>
            <Box width={10}>
              <Text color="gray" bold>
                Saved
              </Text>
            </Box>
          </Box>
          {results.map((r, i) => (
            <Box key={i}>
              <Box width={4}>
                <Text color="gray">{i + 1}.</Text>
              </Box>
              <Box width={36}>
                <Text color="white">
                  {r.query.length > 33
                    ? r.query.slice(0, 30) + "..."
                    : r.query}
                </Text>
              </Box>
              <Box width={10}>
                <Text color={r.accepted ? "green" : "magenta"}>
                  {r.accepted ? "draft" : "verify"}
                </Text>
              </Box>
              <Box width={10}>
                <Text color="yellow">${r.totalCost.toFixed(3)}</Text>
              </Box>
              <Box width={10}>
                <Text color="green">
                  {(
                    ((r.baselineCost - r.totalCost) / r.baselineCost) *
                    100
                  ).toFixed(0)}
                  %
                </Text>
              </Box>
            </Box>
          ))}
        </Box>
      </Box>

      <HorizontalRule />

      <Box paddingX={2} marginTop={1} flexDirection="column" alignItems="center">
        <Text color="green" bold>
          {"  ✨ CascadeFlow saved " +
            savingsPercent.toFixed(1) +
            "% on LLM costs with zero quality loss ✨"}
        </Text>
        <Box marginTop={1}>
          <Text color="gray" italic>
            Press Enter or 'q' to exit
          </Text>
        </Box>
      </Box>
    </Box>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────

type Screen = "welcome" | "provider" | "running" | "summary";

function App() {
  const [screen, setScreen] = useState<Screen>("welcome");
  const [provider, setProvider] = useState<ProviderOption>("anthropic");
  const [results, setResults] = useState<QueryResult[]>([]);

  const handleProviderSelect = useCallback((p: ProviderOption) => {
    setProvider(p);
    setScreen("running");
  }, []);

  const handleComplete = useCallback((r: QueryResult[]) => {
    setResults(r);
    setScreen("summary");
  }, []);

  switch (screen) {
    case "welcome":
      return <WelcomeScreen onContinue={() => setScreen("provider")} />;
    case "provider":
      return <ProviderSelect onSelect={handleProviderSelect} />;
    case "running":
      return (
        <QueryRunner provider={provider} onComplete={handleComplete} />
      );
    case "summary":
      return <SummaryScreen results={results} provider={provider} />;
  }
}

render(<App />);
