import React, { useState, useCallback } from "react";
import { Box, Text, useInput } from "ink";
import Spinner from "ink-spinner";
import { Header } from "../components/Header.js";
import { Footer } from "../components/Footer.js";
import { cascadeComplete, type CascadeMessage } from "../../cascade/client.js";
import { MetricsTracker, type QueryStat } from "../../cascade/metrics.js";

interface ChatModeProps {
  preset: string;
  draftModel: string;
  verifierModel: string;
  apiKey: string;
  metrics: MetricsTracker;
  onBack: () => void;
}

interface ChatEntry {
  role: "user" | "assistant";
  content: string;
  stat?: QueryStat;
}

export function ChatMode({
  preset,
  draftModel,
  verifierModel,
  apiKey,
  metrics,
  onBack,
}: ChatModeProps) {
  const [input, setInput] = useState("");
  const [cursor, setCursor] = useState(0);
  const [history, setHistory] = useState<ChatEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (userMessage: string) => {
      setLoading(true);
      setError(null);

      setHistory((h) => [...h, { role: "user", content: userMessage }]);

      try {
        const messages: CascadeMessage[] = [
          ...history.map(
            (e): CascadeMessage => ({
              role: e.role,
              content: e.content,
            })
          ),
          { role: "user", content: userMessage },
        ];

        const startTime = Date.now();
        const response = await cascadeComplete({
          messages,
          draftModel,
          verifierModel,
          apiKey,
        });
        const totalTimeMs = Date.now() - startTime;

        const stat = metrics.record(
          userMessage,
          response,
          draftModel,
          verifierModel,
          totalTimeMs
        );

        const content =
          response.choices?.[0]?.message?.content ?? "(no response)";

        setHistory((h) => [...h, { role: "assistant", content, stat }]);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        // Remove the user message if we failed
        setHistory((h) => h.slice(0, -1));
      } finally {
        setLoading(false);
      }
    },
    [history, draftModel, verifierModel, apiKey, metrics]
  );

  useInput((ch, key) => {
    if (key.escape) {
      onBack();
      return;
    }
    if (loading) return;

    if (key.return && input.trim().length > 0) {
      const msg = input.trim();
      setInput("");
      setCursor(0);
      sendMessage(msg);
      return;
    }
    if (input === "c" && key.ctrl) {
      setHistory([]);
      return;
    }
    if (key.backspace || key.delete) {
      if (cursor > 0) {
        setInput((v) => v.slice(0, cursor - 1) + v.slice(cursor));
        setCursor((c) => c - 1);
      }
      return;
    }
    if (key.leftArrow) {
      setCursor((c) => Math.max(0, c - 1));
      return;
    }
    if (key.rightArrow) {
      setCursor((c) => Math.min(input.length, c + 1));
      return;
    }
    if (ch && !key.ctrl && !key.meta) {
      setInput((v) => v.slice(0, cursor) + ch + v.slice(cursor));
      setCursor((c) => c + ch.length);
    }
  });

  // Show last N entries to fit terminal
  const visibleHistory = history.slice(-8);

  return (
    <Box flexDirection="column">
      <Header title={"\uD83D\uDCAC Chat Mode"} preset={preset} />

      <Box flexDirection="column" paddingX={1} paddingY={1} minHeight={12}>
        {visibleHistory.map((entry, i) => (
          <Box key={i} flexDirection="column" marginBottom={1}>
            {entry.role === "user" ? (
              <Box>
                <Text color="cyan" bold>
                  You:{" "}
                </Text>
                <Text color="white">{entry.content}</Text>
              </Box>
            ) : (
              <Box
                flexDirection="column"
                borderStyle="single"
                borderColor="gray"
                paddingX={1}
              >
                <Text color="white" wrap="wrap">
                  {entry.content}
                </Text>
                {entry.stat && (
                  <Box marginTop={1} flexDirection="column">
                    <Box>
                      {entry.stat.route === "draft_accepted" ? (
                        <Text color="green" bold>
                          {"\u2705"} Draft accepted
                        </Text>
                      ) : entry.stat.route === "escalated" ? (
                        <Text color="yellow" bold>
                          {"\u2B06\uFE0F"} Escalated to verifier
                        </Text>
                      ) : (
                        <Text color="blue" bold>
                          {"\u27A1\uFE0F"} Direct route
                        </Text>
                      )}
                      {entry.stat.confidence !== undefined && (
                        <Text color="gray">
                          {" "}
                          (confidence: {(entry.stat.confidence * 100).toFixed(0)}%)
                        </Text>
                      )}
                    </Box>
                    <Box>
                      <Text color="green">
                        {"\uD83D\uDCB0"} Saved: ${(entry.stat.baselineCost - entry.stat.actualCost).toFixed(4)}
                      </Text>
                      <Text color="gray">
                        {" "}
                        (vs {verifierModel})
                      </Text>
                    </Box>
                    <Box>
                      <Text color="gray">
                        {"\u23F1\uFE0F"} {entry.stat.totalTimeMs}ms
                        {entry.stat.draftTimeMs
                          ? ` (draft: ${entry.stat.draftTimeMs}ms)`
                          : ""}
                      </Text>
                    </Box>
                  </Box>
                )}
              </Box>
            )}
          </Box>
        ))}

        {loading && (
          <Box>
            <Text color="yellow">
              <Spinner type="dots" />
            </Text>
            <Text color="gray"> Cascading...</Text>
          </Box>
        )}

        {error && (
          <Box>
            <Text color="red">Error: {error}</Text>
          </Box>
        )}
      </Box>

      {/* Input area */}
      <Box paddingX={1} borderStyle="single" borderColor="gray" borderTop borderBottom={false} borderLeft={false} borderRight={false}>
        <Text color="green" bold>
          {">"}{" "}
        </Text>
        <Text color="white">{input}</Text>
        <Text color="cyan">{"\u2588"}</Text>
      </Box>

      <Box paddingX={1}>
        <Text color="gray" dimColor>
          [ESC] Back  [Ctrl+C] Clear history
        </Text>
      </Box>
      <Footer metrics={metrics} />
    </Box>
  );
}
