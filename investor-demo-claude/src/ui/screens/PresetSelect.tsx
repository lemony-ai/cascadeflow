import React from "react";
import { Box, Text } from "ink";
import { PRESETS, type PresetKey } from "../../cascade/presets.js";
import { Menu, type MenuItem } from "../components/Menu.js";

interface PresetSelectProps {
  onSelect: (preset: PresetKey) => void;
}

export function PresetSelect({ onSelect }: PresetSelectProps) {
  const items: MenuItem[] = Object.entries(PRESETS).map(([key, preset]) => ({
    key,
    icon: preset.icon,
    label: `${preset.name}`,
    description: preset.description,
    extra: `Best for: ${preset.bestFor}`,
  }));

  return (
    <Box flexDirection="column" borderStyle="single" borderColor="cyan" paddingX={2} paddingY={1}>
      <Text color="white" bold>
        Select a cascade preset
      </Text>
      <Box marginTop={1}>
        <Menu items={items} onSelect={(key) => onSelect(key as PresetKey)} />
      </Box>
    </Box>
  );
}
