import React, { useState } from "react";
import { Box, Text, useInput } from "ink";

export type Provider = "openai" | "anthropic";

interface ProviderSelectProps {
  onSelect: (provider: Provider) => void;
}

const PROVIDERS: { key: Provider; label: string }[] = [
  { key: "openai", label: "OpenAI" },
  { key: "anthropic", label: "Anthropic" },
];

export function ProviderSelect({ onSelect }: ProviderSelectProps) {
  const [selected, setSelected] = useState(0);

  useInput((_input, key) => {
    if (key.upArrow) setSelected((s) => Math.max(0, s - 1));
    if (key.downArrow) setSelected((s) => Math.min(PROVIDERS.length - 1, s + 1));
    if (key.return) {
      const item = PROVIDERS[selected];
      if (item) onSelect(item.key);
    }
  });

  return (
    <Box flexDirection="column" borderStyle="single" borderColor="cyan" paddingX={2} paddingY={1}>
      <Text color="white" bold>
        Select your AI provider
      </Text>
      <Box marginTop={1} flexDirection="column">
        {PROVIDERS.map((p, i) => (
          <Box key={p.key} paddingX={1}>
            <Text color={i === selected ? "green" : "gray"} bold={i === selected}>
              {i === selected ? "\u25B8 " : "  "}
            </Text>
            <Text color={i === selected ? "white" : "gray"} bold={i === selected}>
              {p.label}
            </Text>
          </Box>
        ))}
      </Box>
      <Box marginTop={1}>
        <Text color="gray" dimColor>
          Use {"\u2191\u2193"} to navigate, ENTER to select
        </Text>
      </Box>
    </Box>
  );
}
