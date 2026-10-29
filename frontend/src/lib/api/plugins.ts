export type PluginState = "active" | "disabled" | "failed";

export type PluginItem = {
  id: string;
  name: string;
  description: string;
  version: string;
  state: PluginState;
  error: string;
  extensions: string[];
};
