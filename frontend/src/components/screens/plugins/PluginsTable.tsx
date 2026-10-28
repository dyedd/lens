import { Switch } from "@/components/ui/Switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import type { PluginItem } from "@/lib/api/plugins";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

import {
  pluginCronjobTitles,
  pluginDescription,
  pluginStateLabel,
  pluginTitle,
} from "./pluginView";

type PluginsTableProps = {
  locale: Locale;
  plugins: PluginItem[];
  isFetching: boolean;
  pluginsIsError: boolean;
  togglingPluginId?: string;
  onToggleEnabled: (plugin: PluginItem, enabled: boolean) => void;
};

/** Render installed plugins with their contributed scheduled tasks. */
export function PluginsTable({
  locale,
  plugins,
  isFetching,
  pluginsIsError,
  togglingPluginId,
  onToggleEnabled,
}: PluginsTableProps) {
  if (pluginsIsError) return null;
  const taskSeparator = titleForLocale(locale, "、", ", ");

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>{titleForLocale(locale, "插件", "Plugin")}</TableHead>
          <TableHead className="w-[16rem]">
            {titleForLocale(locale, "计划任务", "Scheduled tasks")}
          </TableHead>
          <TableHead className="w-[132px]">
            {titleForLocale(locale, "状态", "Status")}
          </TableHead>
          <TableHead className="w-[72px]">
            {titleForLocale(locale, "版本", "Version")}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {plugins.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={4}
              className="h-32 text-center text-muted-foreground"
            >
              {isFetching
                ? titleForLocale(locale, "加载中...", "Loading...")
                : titleForLocale(locale, "暂无插件", "No plugins")}
            </TableCell>
          </TableRow>
        ) : (
          plugins.map((plugin) => {
            const taskTitles = pluginCronjobTitles(locale, plugin);
            return (
              <TableRow key={plugin.id}>
                <TableCell className="max-w-[24rem] align-top">
                  <p className="truncate font-medium text-foreground">
                    {pluginTitle(locale, plugin)}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {pluginDescription(locale, plugin)}
                  </p>
                  {plugin.error ? (
                    <p className="mt-1 whitespace-pre-wrap text-xs text-destructive">
                      {plugin.error}
                    </p>
                  ) : null}
                </TableCell>
                <TableCell className="align-top text-xs text-muted-foreground">
                  {taskTitles.length
                    ? taskTitles.join(taskSeparator)
                    : titleForLocale(locale, "无", "None")}
                </TableCell>
                <TableCell className="align-top">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={plugin.state !== "disabled"}
                      disabled={togglingPluginId === plugin.id}
                      onCheckedChange={(checked) =>
                        onToggleEnabled(plugin, checked)
                      }
                      aria-label={titleForLocale(
                        locale,
                        plugin.state === "disabled" ? "启用插件" : "停用插件",
                        plugin.state === "disabled"
                          ? "Enable plugin"
                          : "Disable plugin",
                      )}
                    />
                    <span className="text-xs text-muted-foreground">
                      {pluginStateLabel(locale, plugin.state)}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="align-top font-mono text-xs text-muted-foreground">
                  {plugin.version}
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}
