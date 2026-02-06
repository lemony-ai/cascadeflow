import React from "react";
import { Box, Text } from "ink";
import type { MetricsTracker } from "../../cascade/metrics.js";

interface FooterProps {
  metrics: MetricsTracker;
}

export function Footer({ metrics }: FooterProps) {
  const hasData = metrics.totalQueries > 0;

  return (
    <Box
      borderStyle="single"
      borderColor="gray"
      paddingX={1}
      justifyContent="space-between"
    >
      <Text>
        <Text color="green" bold>
          {"\uD83D\uDCB0"} {hasData ? `${metrics.savingsPercent.toFixed(0)}%` : "--%"}
        </Text>
        <Text color="gray"> saved</Text>
      </Text>
      <Text>
        <Text color="cyan" bold>
          {"\u2705"} {hasData ? `${metrics.acceptRate.toFixed(0)}%` : "--%"}
        </Text>
        <Text color="gray"> accept</Text>
      </Text>
      <Text>
        <Text color="yellow" bold>
          {"\u2B06\uFE0F"} {hasData ? `${metrics.escalateRate.toFixed(0)}%` : "--%"}
        </Text>
        <Text color="gray"> esc</Text>
      </Text>
      <Text>
        <Text color="magenta" bold>
          {"\u23F1\uFE0F"} {hasData ? `+${metrics.avgOverheadMs.toFixed(0)}ms` : "--ms"}
        </Text>
      </Text>
    </Box>
  );
}
