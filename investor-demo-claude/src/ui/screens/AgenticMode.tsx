import React, { useState, useCallback, useEffect, useRef } from "react";
import { Box, Text, useInput } from "ink";
import Spinner from "ink-spinner";
import { Header } from "../components/Header.js";
import { Footer } from "../components/Footer.js";
import { Menu, type MenuItem } from "../components/Menu.js";
import { cascadeComplete, type CascadeMessage } from "../../cascade/client.js";
import { MetricsTracker, type QueryStat } from "../../cascade/metrics.js";

interface AgenticModeProps {
  preset: string;
  draftModel: string;
  verifierModel: string;
  apiKey: string;
  metrics: MetricsTracker;
  onBack: () => void;
}

interface ToolStep {
  stepNumber: number;
  tool: string;
  args: string;
  route: "accepted" | "escalated" | "direct" | "running" | "pending";
  model?: string;
  result?: string;
  stat?: QueryStat;
}

interface ScenarioResult {
  name: string;
  steps: ToolStep[];
  totalSaved: number;
  savingsPercent: number;
}

const SCENARIOS: MenuItem[] = [
  {
    key: "search",
    icon: "\uD83D\uDD0D",
    label: "Web Search Agent",
    description: "Search queries with result synthesis",
  },
  {
    key: "data",
    icon: "\uD83D\uDCCA",
    label: "Data Analysis Agent",
    description: "CSV parsing, calculations, visualization",
  },
  {
    key: "code",
    icon: "\uD83D\uDCBB",
    label: "Code Assistant",
    description: "Code generation with tool validation",
  },
];

// Scenario definitions: each has a series of simulated tool calls
// that we send as real cascade requests
const SCENARIO_PROMPTS: Record<
  string,
  { tool: string; args: string; prompt: string }[]
> = {
  search: [
    {
      tool: "web_search",
      args: '"AI regulations 2026"',
      prompt: "Search the web for: AI regulations 2026. Return a brief list of 3 key results.",
    },
    {
      tool: "summarize",
      args: "articles",
      prompt:
        "Summarize these key developments in AI regulation: 1) EU AI Act enforcement began 2) US executive orders on AI safety 3) International AI governance frameworks. Provide a concise 3-sentence synthesis.",
    },
  ],
  data: [
    {
      tool: "parse_csv",
      args: "sales_data.csv",
      prompt: "Parse this CSV data and describe the schema: columns are date, product, quantity, revenue. There are 1000 rows of sales data.",
    },
    {
      tool: "calculate",
      args: "aggregate(revenue, by=product)",
      prompt:
        "Calculate total revenue by product category for: Electronics=$450K, Clothing=$320K, Food=$180K, Books=$95K. Show the breakdown.",
    },
    {
      tool: "visualize",
      args: "bar_chart(revenue_by_product)",
      prompt:
        "Describe a bar chart visualization of revenue by product: Electronics $450K, Clothing $320K, Food $180K, Books $95K.",
    },
  ],
  code: [
    {
      tool: "generate_code",
      args: "fibonacci(n)",
      prompt: "Write a Python function that computes the nth Fibonacci number efficiently using memoization.",
    },
    {
      tool: "validate",
      args: "run_tests(fibonacci)",
      prompt: "Validate this Fibonacci implementation: test cases fibonacci(0)=0, fibonacci(1)=1, fibonacci(10)=55, fibonacci(20)=6765. Report pass/fail for each.",
    },
  ],
};

export function AgenticMode({
  preset,
  draftModel,
  verifierModel,
  apiKey,
  metrics,
  onBack,
}: AgenticModeProps) {
  const [view, setView] = useState<"select" | "running" | "result">("select");
  const [scenario, setScenario] = useState<string>("");
  const [steps, setSteps] = useState<ToolStep[]>([]);
  const [currentStep, setCurrentStep] = useState(0);
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const runningRef = useRef(false);

  const runScenario = useCallback(
    async (scenarioKey: string) => {
      const prompts = SCENARIO_PROMPTS[scenarioKey];
      if (!prompts) return;

      runningRef.current = true;

      // Initialize steps as pending
      const initialSteps: ToolStep[] = prompts.map((p, i) => ({
        stepNumber: i + 1,
        tool: p.tool,
        args: p.args,
        route: "pending" as const,
      }));
      setSteps(initialSteps);

      const completedSteps: ToolStep[] = [];

      for (let i = 0; i < prompts.length; i++) {
        if (!runningRef.current) break;

        setCurrentStep(i);
        // Mark current step as running
        setSteps((prev) =>
          prev.map((s, j) => (j === i ? { ...s, route: "running" } : s))
        );

        const p = prompts[i]!;
        try {
          const messages: CascadeMessage[] = [
            {
              role: "system",
              content:
                "You are a helpful AI assistant performing tool operations. Be concise.",
            },
            { role: "user", content: p.prompt },
          ];

          const startTime = Date.now();
          const response = await cascadeComplete({
            messages,
            draftModel,
            verifierModel,
            apiKey,
            maxTokens: 300,
          });
          const totalTimeMs = Date.now() - startTime;

          const stat = metrics.record(
            `tool:${p.tool}(${p.args})`,
            response,
            draftModel,
            verifierModel,
            totalTimeMs
          );

          const routeLabel =
            stat.route === "draft_accepted"
              ? "accepted"
              : stat.route === "escalated"
              ? "escalated"
              : "direct";

          const updatedStep: ToolStep = {
            stepNumber: i + 1,
            tool: p.tool,
            args: p.args,
            route: routeLabel as "accepted" | "escalated" | "direct",
            model:
              routeLabel === "accepted" ? draftModel : verifierModel,
            result:
              response.choices?.[0]?.message?.content?.slice(0, 60) ??
              "Done",
            stat,
          };

          completedSteps.push(updatedStep);
          setSteps((prev) =>
            prev.map((s, j) => (j === i ? updatedStep : s))
          );
        } catch (err) {
          const errMsg = err instanceof Error ? err.message : String(err);
          const failedStep: ToolStep = {
            stepNumber: i + 1,
            tool: p.tool,
            args: p.args,
            route: "accepted",
            result: `Error: ${errMsg.slice(0, 50)}`,
          };
          completedSteps.push(failedStep);
          setSteps((prev) =>
            prev.map((s, j) => (j === i ? failedStep : s))
          );
        }
      }

      // Build result
      const totalActual = completedSteps.reduce(
        (s, st) => s + (st.stat?.actualCost ?? 0),
        0
      );
      const totalBaseline = completedSteps.reduce(
        (s, st) => s + (st.stat?.baselineCost ?? 0),
        0
      );

      setResult({
        name: SCENARIOS.find((s) => s.key === scenarioKey)?.label ?? scenarioKey,
        steps: completedSteps,
        totalSaved: totalBaseline - totalActual,
        savingsPercent:
          totalBaseline > 0
            ? ((1 - totalActual / totalBaseline) * 100)
            : 0,
      });
      setView("result");
    },
    [draftModel, verifierModel, apiKey, metrics]
  );

  useEffect(() => {
    if (view === "running" && scenario) {
      runScenario(scenario);
    }
    return () => {
      runningRef.current = false;
    };
  }, [view, scenario, runScenario]);

  useInput((_input, key) => {
    if (key.escape) {
      if (view === "result" || view === "running") {
        runningRef.current = false;
        setView("select");
        setSteps([]);
        setResult(null);
      } else {
        onBack();
      }
    }
    if (_input === "r" && view === "result") {
      setView("running");
      setSteps([]);
      setResult(null);
    }
  });

  if (view === "select") {
    return (
      <Box flexDirection="column">
        <Header title={"\uD83D\uDEE0\uFE0F  Agentic Mode"} preset={preset} />
        <Box flexDirection="column" paddingX={1} paddingY={1}>
          <Text color="white" bold>
            Select a demo scenario:
          </Text>
          <Box marginTop={1}>
            <Menu
              items={SCENARIOS}
              onSelect={(key) => {
                setScenario(key);
                setView("running");
              }}
            />
          </Box>
        </Box>
        <Footer metrics={metrics} />
      </Box>
    );
  }

  // Running or result view
  const scenarioLabel =
    SCENARIOS.find((s) => s.key === scenario)?.icon +
    " " +
    (SCENARIOS.find((s) => s.key === scenario)?.label ?? scenario);

  return (
    <Box flexDirection="column">
      <Header title={scenarioLabel} preset={preset} />

      <Box flexDirection="column" paddingX={1} paddingY={1}>
        <Box
          flexDirection="column"
          borderStyle="single"
          borderColor="gray"
          paddingX={1}
        >
          <Text color="white" bold>
            Agent Activity
          </Text>
          <Box marginTop={1} flexDirection="column">
            {steps.map((step, i) => (
              <Box key={i} flexDirection="column" marginBottom={1}>
                <Box>
                  <Text color="gray">
                    {step.stepNumber}.{" "}
                  </Text>
                  <Text color="blue" bold>
                    {"\uD83D\uDD27"} tool:{step.tool}({step.args})
                  </Text>
                </Box>
                <Box paddingLeft={3}>
                  {step.route === "running" ? (
                    <Box>
                      <Text color="yellow">
                        <Spinner type="dots" />
                      </Text>
                      <Text color="yellow"> Processing...</Text>
                    </Box>
                  ) : step.route === "pending" ? (
                    <Text color="gray">{"\u25CB"} Waiting...</Text>
                  ) : (
                    <Box flexDirection="column">
                      <Box>
                        <Text color="gray">{"\u251C\u2500"} </Text>
                        <Text color="gray">
                          {step.route === "accepted"
                            ? `Draft: ${draftModel} `
                            : `Verify: ${verifierModel} `}
                        </Text>
                        {step.route === "accepted" ? (
                          <Text color="green">{"\u2705"} accepted</Text>
                        ) : step.route === "escalated" ? (
                          <Text color="yellow">
                            {"\u2B06\uFE0F"} escalated
                          </Text>
                        ) : (
                          <Text color="blue">{"\u27A1\uFE0F"} direct</Text>
                        )}
                      </Box>
                      {step.result && (
                        <Box>
                          <Text color="gray">
                            {"\u2514\u2500"} Result: {step.result}
                          </Text>
                        </Box>
                      )}
                    </Box>
                  )}
                </Box>
              </Box>
            ))}
          </Box>

          {result && (
            <Box marginTop={1}>
              <Text color="green" bold>
                {"\uD83D\uDCB0"} Total saved: ${result.totalSaved.toFixed(4)} (
                {result.savingsPercent.toFixed(0)}% vs direct)
              </Text>
            </Box>
          )}
        </Box>
      </Box>

      <Box paddingX={1}>
        <Text color="gray" dimColor>
          [ESC] Back{view === "result" ? "  [r] Replay" : ""}
        </Text>
      </Box>
      <Footer metrics={metrics} />
    </Box>
  );
}
