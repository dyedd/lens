export type PluginState = "active" | "disabled" | "failed";

export type PluginCronjob = {
  id: string;
  name: string;
};

export type PluginItem = {
  id: string;
  name: string;
  description: string;
  version: string;
  state: PluginState;
  error: string;
  cronjobs: PluginCronjob[];
};
