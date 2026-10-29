import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import { SettingsSection } from "@/components/settings/settingsLayout";
import { DashboardHeaderActions } from "@/components/shell/dashboardHeaderActions";
import { Button } from "@/components/ui/Button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { PluginItem } from "@/lib/api/plugins";
import { titleForLocale, useI18n } from "@/lib/I18nContext";

import { PluginsTable } from "./plugins/PluginsTable";

/** Render installed plugins and let the operator switch them on or off. */
export function PluginsScreen() {
  const queryClient = useQueryClient();
  const { locale } = useI18n();
  const pluginsQuery = useQuery({
    queryKey: ["plugins"],
    queryFn: () => apiRequest<PluginItem[]>("/admin/plugins"),
    staleTime: 10_000,
  });

  function replacePlugin(plugin: PluginItem) {
    queryClient.setQueryData<PluginItem[]>(["plugins"], (current) =>
      (current ?? []).map((item) => (item.id === plugin.id ? plugin : item)),
    );
  }

  const togglePlugin = useMutation({
    mutationFn: ({
      plugin,
      enabled,
    }: {
      plugin: PluginItem;
      enabled: boolean;
    }) =>
      apiRequest<PluginItem>(
        `/admin/plugins/${encodeURIComponent(plugin.id)}`,
        { method: "PUT", body: JSON.stringify({ enabled }) },
      ),
    onSuccess: (plugin) => {
      replacePlugin(plugin);
      toast.success(
        titleForLocale(
          locale,
          plugin.state === "disabled" ? "插件已停用" : "插件已启用",
          plugin.state === "disabled" ? "Plugin disabled" : "Plugin enabled",
        ),
      );
    },
    onError: (error) => {
      void queryClient.invalidateQueries({ queryKey: ["plugins"] });
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(locale, "更新插件失败", "Failed to update plugin"),
        ),
      );
    },
  });

  const saveSettings = useMutation({
    mutationFn: ({
      plugin,
      key,
      value,
    }: {
      plugin: PluginItem;
      key: string;
      value: string | number | boolean;
    }) =>
      apiRequest<PluginItem>(
        `/admin/plugins/${encodeURIComponent(plugin.id)}/settings`,
        { method: "PUT", body: JSON.stringify({ values: { [key]: value } }) },
      ),
    onSuccess: (plugin) => {
      replacePlugin(plugin);
      toast.success(
        titleForLocale(locale, "插件设置已保存", "Plugin settings saved"),
      );
    },
    onError: (error) => {
      void queryClient.invalidateQueries({ queryKey: ["plugins"] });
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(locale, "保存插件设置失败", "Failed to save settings"),
        ),
      );
    },
  });

  const reloadPlugins = useMutation({
    mutationFn: () =>
      apiRequest<PluginItem[]>("/admin/plugins/reload", { method: "POST" }),
    onSuccess: (plugins) => {
      queryClient.setQueryData(["plugins"], plugins);
      toast.success(
        titleForLocale(locale, "插件已重新加载", "Plugins reloaded"),
      );
    },
    onError: (error) =>
      toast.error(
        getApiErrorMessage(
          error,
          titleForLocale(
            locale,
            "重新加载插件失败",
            "Failed to reload plugins",
          ),
        ),
      ),
  });

  const plugins = pluginsQuery.data ?? [];
  const busyPluginId = togglePlugin.isPending
    ? togglePlugin.variables?.plugin.id
    : saveSettings.isPending
      ? saveSettings.variables?.plugin.id
      : undefined;

  return (
    <>
      <DashboardHeaderActions>
        <div className="flex items-center justify-end gap-2">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                type="button"
                aria-label={titleForLocale(
                  locale,
                  "重新扫描插件",
                  "Rescan plugins",
                )}
                onClick={() => reloadPlugins.mutate()}
                disabled={reloadPlugins.isPending}
              >
                <RefreshCw data-icon="inline-start" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              {titleForLocale(
                locale,
                "重新扫描插件目录",
                "Rescan plugin directory",
              )}
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                type="button"
                aria-label={titleForLocale(locale, "刷新", "Refresh")}
                onClick={() =>
                  void queryClient.invalidateQueries({ queryKey: ["plugins"] })
                }
                disabled={pluginsQuery.isFetching}
              >
                <RotateCcw data-icon="inline-start" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="end">
              {titleForLocale(locale, "刷新", "Refresh")}
            </TooltipContent>
          </Tooltip>
        </div>
      </DashboardHeaderActions>
      <SettingsSection title={titleForLocale(locale, "插件", "Plugins")}>
        <PluginsTable
          locale={locale}
          plugins={plugins}
          isFetching={pluginsQuery.isFetching}
          pluginsIsError={pluginsQuery.isError}
          busyPluginId={busyPluginId}
          onToggleEnabled={(plugin, enabled) =>
            togglePlugin.mutate({ plugin, enabled })
          }
          onChangeSetting={(plugin, key, value) =>
            saveSettings.mutate({ plugin, key, value })
          }
        />
      </SettingsSection>
    </>
  );
}
