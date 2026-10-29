export type PluginState = "active" | "pending" | "disabled" | "failed";

export type PluginSetting = {
  key: string;
  label: string;
  type: "bool" | "int" | "string" | "enum";
  description: string;
  options: string[];
  value: string | number | boolean;
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
};
