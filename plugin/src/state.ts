import type { PluginConfig } from "./config.js";

export interface PluginRuntimeState {
  config: PluginConfig | null;
}

let runtimeState: PluginRuntimeState = {
  config: null,
};

export function getState(): PluginRuntimeState {
  return runtimeState;
}

export function setState(partial: Partial<PluginRuntimeState>): void {
  runtimeState = { ...runtimeState, ...partial };
}

export function requireConfig(): PluginConfig {
  const config = runtimeState.config;
  if (config === null) {
    throw new Error("grimoire: plugin not initialized");
  }
  return config;
}
