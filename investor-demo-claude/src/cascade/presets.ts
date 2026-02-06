// Cascade preset configurations

export interface PresetConfig {
  name: string;
  icon: string;
  draftModel: string;
  verifierModel: string;
  description: string;
  bestFor: string;
}

export const PRESETS: Record<string, PresetConfig> = {
  performance: {
    name: "Performance",
    icon: "\u26A1",
    draftModel: "gpt-4o-mini",
    verifierModel: "gpt-4o",
    description: "Draft: gpt-4o-mini \u2192 Verify: gpt-4o",
    bestFor: "Tool calls, agent loops",
  },
  quality: {
    name: "Quality",
    icon: "\uD83C\uDFAF",
    draftModel: "claude-haiku",
    verifierModel: "claude-opus",
    description: "Draft: claude-haiku \u2192 Verify: claude-opus",
    bestFor: "Complex reasoning, analysis",
  },
  balanced: {
    name: "Balanced",
    icon: "\uD83D\uDD00",
    draftModel: "gpt-4o-mini",
    verifierModel: "claude-opus",
    description: "Draft: gpt-4o-mini \u2192 Verify: claude-opus",
    bestFor: "General use, cost optimization",
  },
};

export type PresetKey = keyof typeof PRESETS;
