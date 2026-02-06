import React, { useState } from "react";
import { Box, Text, useInput } from "ink";

export interface MenuItem {
  key: string;
  icon: string;
  label: string;
  description: string;
  extra?: string;
}

interface MenuProps {
  items: MenuItem[];
  onSelect: (key: string) => void;
}

export function Menu({ items, onSelect }: MenuProps) {
  const [selected, setSelected] = useState(0);

  useInput((_input, key) => {
    if (key.upArrow) setSelected((s) => Math.max(0, s - 1));
    if (key.downArrow) setSelected((s) => Math.min(items.length - 1, s + 1));
    if (key.return) {
      const item = items[selected];
      if (item) onSelect(item.key);
    }
  });

  return (
    <Box flexDirection="column">
      {items.map((item, i) => (
        <Box key={item.key} flexDirection="column" paddingX={1}>
          <Box>
            <Text color={i === selected ? "green" : "gray"} bold={i === selected}>
              {i === selected ? " \u25B8 " : "   "}
            </Text>
            <Text color={i === selected ? "white" : "gray"} bold={i === selected}>
              {item.icon} {item.label}
            </Text>
          </Box>
          <Box paddingLeft={4}>
            <Text color="gray" dimColor={i !== selected}>
              {item.description}
            </Text>
          </Box>
          {item.extra && (
            <Box paddingLeft={4}>
              <Text color="gray" dimColor>
                {item.extra}
              </Text>
            </Box>
          )}
        </Box>
      ))}
      <Box paddingX={1} marginTop={1}>
        <Text color="gray" dimColor>
          Use {"\u2191\u2193"} to navigate, ENTER to select
        </Text>
      </Box>
    </Box>
  );
}
