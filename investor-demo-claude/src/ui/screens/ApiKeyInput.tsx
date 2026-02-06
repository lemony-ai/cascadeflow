import React, { useState } from "react";
import { Box, Text, useInput } from "ink";

interface ApiKeyInputProps {
  provider: string;
  onSubmit: (key: string) => void;
}

export function ApiKeyInput({ provider, onSubmit }: ApiKeyInputProps) {
  const [value, setValue] = useState("");
  const [cursor, setCursor] = useState(0);

  useInput((input, key) => {
    if (key.return && value.length > 0) {
      onSubmit(value);
      return;
    }
    if (key.backspace || key.delete) {
      if (cursor > 0) {
        setValue((v) => v.slice(0, cursor - 1) + v.slice(cursor));
        setCursor((c) => c - 1);
      }
      return;
    }
    if (key.leftArrow) {
      setCursor((c) => Math.max(0, c - 1));
      return;
    }
    if (key.rightArrow) {
      setCursor((c) => Math.min(value.length, c + 1));
      return;
    }
    // Only accept printable characters
    if (input && !key.ctrl && !key.meta) {
      setValue((v) => v.slice(0, cursor) + input + v.slice(cursor));
      setCursor((c) => c + input.length);
    }
  });

  const masked =
    value.length <= 4
      ? "\u2022".repeat(value.length)
      : value.slice(0, 3) + "\u2022".repeat(value.length - 4) + value.slice(-1);

  const providerLabel = provider === "openai" ? "OpenAI" : "Anthropic";

  return (
    <Box flexDirection="column" borderStyle="single" borderColor="cyan" paddingX={2} paddingY={1}>
      <Text color="white" bold>
        Enter your {providerLabel} API key
      </Text>
      <Box marginTop={1} flexDirection="column">
        <Box>
          <Text color="gray">API Key: </Text>
          <Text color="green">{masked || " "}</Text>
          <Text color="cyan">{"\u2588"}</Text>
        </Box>
      </Box>
      <Box marginTop={1} flexDirection="column">
        <Text color="gray" dimColor>
          {"\u2139\uFE0F"}  Your key is stored locally and never transmitted
        </Text>
        <Text color="gray" dimColor>
          {"   "}except to the provider{"'"}s API.
        </Text>
      </Box>
      <Box marginTop={1}>
        <Text color="gray" dimColor>
          Press ENTER to continue
        </Text>
      </Box>
    </Box>
  );
}
