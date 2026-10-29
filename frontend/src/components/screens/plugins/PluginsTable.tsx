import { Fragment } from "react";

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

import { PluginSettingsForm } from "./PluginSettingsForm";
import {
  pluginDescription,
  pluginExtensionLabels,
  pluginOriginLabel,
  pluginStateLabel,
  pluginTitle,
} from "./pluginView";

type PluginsTableProps = {
  locale: Locale;
  plugins: PluginItem[];
  isFetching: boolean;
  pluginsIsError: boolean;
  busyPluginId?: string;
  onToggleEnabled: (plugin: PluginItem, enabled: boolean) => void;
  onChangeSetting: (
    plugin: PluginItem,
    key: string,
    value: string | number | boolean,
  ) => void;
};

/** Render installed plugins, their extension points, and settings. */
export function PluginsTable({
  locale,
  plugins,
  isFetching,
  pluginsIsError,
  busyPluginId,
  onToggleEnabled,
  onChangeSetting,
}: PluginsTableProps) {
  if (pluginsIsError) return null;
  const listSeparator = titleForLocale(locale, "、", ", ");

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>{titleForLocale(locale, "插件", "Plugin")}</TableHead>
          <TableHead className="w-[15rem]">
            {titleForLocale(locale, "扩展点", "Extension points")}
          </TableHead>
          <TableHead className="w-[132px]">
            {titleForLocale(locale, "状态", "Status")}
          </TableHead>
          <TableHead className="w-[64px]">
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
            const extensions = pluginExtensionLabels(locale, plugin);
            const busy = busyPluginId === plugin.id;
            return (
              <Fragment key={plugin.id}>
                <TableRow>
                  <TableCell className="max-w-[24rem] align-top">
                    <p className="truncate font-medium text-foreground">
                      {pluginTitle(locale, plugin)}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {pluginDescription(locale, plugin)}
                    </p>
                    <p className="truncate font-mono text-[11px] text-muted-foreground/80">
                      {pluginOriginLabel(locale, plugin)}
                    </p>
                    {plugin.error ? (
                      <p className="mt-1 whitespace-pre-wrap text-xs text-destructive">
                        {plugin.error}
                      </p>
                    ) : null}
                  </TableCell>
                  <TableCell className="align-top text-xs text-muted-foreground">
                    {extensions.length
                      ? extensions.join(listSeparator)
                      : titleForLocale(locale, "无", "None")}
                  </TableCell>
                  <TableCell className="align-top">
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={plugin.state !== "disabled"}
                        disabled={busy}
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
                {plugin.settings.length ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={4} className="pt-0">
                      <PluginSettingsForm
                        plugin={plugin}
                        disabled={busy}
                        onChange={(key, value) =>
                          onChangeSetting(plugin, key, value)
                        }
                      />
                    </TableCell>
                  </TableRow>
                ) : null}
              </Fragment>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}
