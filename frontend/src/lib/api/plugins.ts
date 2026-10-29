export type PluginState = "active" | "disabled" | "failed";

export type PluginItem = {
  id: string;
  name: string;
  description: string;
  version: string;
  author: string;
  homepage: string;
  source: "builtin" | "external";
  state: PluginState;
  error: string;
  extensions: string[];
};
