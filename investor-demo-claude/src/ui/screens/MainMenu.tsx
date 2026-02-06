import React from "react";
import { Box, Text, useInput, useApp } from "ink";
import { Header } from "../components/Header.js";
import { Footer } from "../components/Footer.js";
import { Menu, type MenuItem } from "../components/Menu.js";
import type { MetricsTracker } from "../../cascade/metrics.js";

export type TestCategory = "chat" | "agentic" | "agent";

interface MainMenuProps {
  preset: string;
  metrics: MetricsTracker;
  onSelect: (category: TestCategory) => void;
  onQuit: () => void;
}

const CATEGORIES: MenuItem[] = [
  {
    key: "chat",
    icon: "\uD83D\uDCAC",
    label: "Chat",
    description: "Text prompts, Q&A, conversations",
  },
  {
    key: "agentic",
    icon: "\uD83D\uDEE0\uFE0F",
    label: "Agentic",
    description: "Tool calls, reasoning chains, function calling",
  },
  {
    key: "agent",
    icon: "\uD83E\uDD16",
    label: "Full Agent",
    description: "Sub-agents, arrays, loops, hooks",
  },
];

export function MainMenu({ preset, metrics, onSelect, onQuit }: MainMenuProps) {
  useInput((input) => {
    if (input === "q") onQuit();
  });

  return (
    <Box flexDirection="column">
      <Header title="CascadeFlow Demo" preset={preset} />
      <Box flexDirection="column" paddingX={1} paddingY={1}>
        <Text color="white" bold>
          Select a test category:
        </Text>
        <Box marginTop={1}>
          <Menu
            items={CATEGORIES}
            onSelect={(key) => onSelect(key as TestCategory)}
          />
        </Box>
      </Box>
      <Box paddingX={1}>
        <Text color="gray" dimColor>
          [q] Quit  [s] Settings  [h] Help
        </Text>
      </Box>
      <Footer metrics={metrics} />
    </Box>
  );
}
