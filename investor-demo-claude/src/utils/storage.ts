// Local config storage using conf

import Conf from "conf";

interface DemoConfig {
  provider?: string;
  apiKey?: string;
  preset?: string;
}

let store: Conf<DemoConfig> | null = null;

function getStore(): Conf<DemoConfig> {
  if (!store) {
    store = new Conf<DemoConfig>({ projectName: "cascadeflow-demo" });
  }
  return store;
}

export function getApiKey(): string | undefined {
  return getStore().get("apiKey");
}

export function setApiKey(key: string): void {
  getStore().set("apiKey", key);
}

export function getProvider(): string | undefined {
  return getStore().get("provider");
}

export function setProvider(provider: string): void {
  getStore().set("provider", provider);
}

export function getPreset(): string | undefined {
  return getStore().get("preset");
}

export function setPreset(preset: string): void {
  getStore().set("preset", preset);
}
