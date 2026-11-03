export type PluginState = "active" | "pending" | "disabled" | "failed";

export type PluginSetting = {
  key: string;
  label: string;
  type: "bool" | "int" | "float" | "string" | "enum";
  description: string;
  options: string[];
  min_value: number | null;
  max_value: number | null;
  secret: boolean;
  is_set: boolean;
  value: string | number | boolean;
};

export type PluginExtensionStats = {
  extension: string;
  calls: number;
  failures: number;
  avg_ms: number;
  last_outcome: string;
  last_error: string;
  dropped: number;
};

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
  requires: string[];
  extensions: string[];
  settings: PluginSetting[];
  strategies: string[];
  stats: PluginExtensionStats[];
};
