import React from "react";
import { Box, Text } from "ink";

interface HeaderProps {
  title: string;
  preset?: string;
}

export function Header({ title, preset }: HeaderProps) {
  return (
    <Box flexDirection="column">
      <Box
        borderStyle="single"
        borderColor="cyan"
        paddingX={1}
        justifyContent="space-between"
      >
        <Text color="cyan" bold>
          {title}
        </Text>
        {preset && (
          <Text color="yellow" bold>
            [{preset}]
          </Text>
        )}
      </Box>
    </Box>
  );
}
