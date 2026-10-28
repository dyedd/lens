import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";
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
        {
          method: "PUT",
          body: JSON.stringify({ enabled }),
        },
      ),
    onSuccess: (plugin) => {
      queryClient.setQueryData<PluginItem[]>(["plugins"], (current) =>
        (current ?? []).map((item) => (item.id === plugin.id ? plugin : item)),
      );
      void queryClient.invalidateQueries({ queryKey: ["cronjobs"] });
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

  const plugins = pluginsQuery.data ?? [];

  return (
    <>
      <DashboardHeaderActions>
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
      </DashboardHeaderActions>
      <SettingsSection title={titleForLocale(locale, "插件", "Plugins")}>
        <PluginsTable
          locale={locale}
          plugins={plugins}
          isFetching={pluginsQuery.isFetching}
          pluginsIsError={pluginsQuery.isError}
          togglingPluginId={
            togglePlugin.isPending
              ? togglePlugin.variables?.plugin.id
              : undefined
          }
          onToggleEnabled={(plugin, enabled) =>
            togglePlugin.mutate({ plugin, enabled })
          }
        />
      </SettingsSection>
    </>
  );
}
