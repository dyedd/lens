import { Fragment, type ReactElement, type ReactNode } from "react";

import { Switch } from "@/components/ui/Switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/Table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/Tooltip";
import type { PluginExtensionStats, PluginItem } from "@/lib/api/plugins";
import { type Locale, titleForLocale } from "@/lib/I18nContext";

import { PluginSettingsForm } from "./PluginSettingsForm";
import {
  formatExtensionFailures,
  formatExtensionUsage,
  pluginExtensionLabel,
  pluginOriginLabel,
  pluginStateLabel,
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

function OptionalTooltip({
  hint,
  children,
}: {
  hint: string;
  children: ReactElement;
}) {
  if (!hint) return children;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent className="max-w-sm break-all">{hint}</TooltipContent>
    </Tooltip>
  );
}

function ExtensionLine({
  locale,
  extension,
  stats,
}: {
  locale: Locale;
  extension: string;
  stats?: PluginExtensionStats;
}) {
  const usage = stats ? formatExtensionUsage(locale, stats) : "";
  const failures = stats ? formatExtensionFailures(locale, stats) : "";
  return (
    <div className="flex flex-wrap items-baseline gap-x-2">
      <span className="text-foreground">
        {pluginExtensionLabel(locale, extension)}
      </span>
      {usage ? <span className="tabular-nums">{usage}</span> : null}
      {failures ? (
        <OptionalTooltip hint={stats?.last_error ?? ""}>
          <span className="tabular-nums text-destructive">{failures}</span>
        </OptionalTooltip>
      ) : null}
    </div>
  );
}

function PluginDetailRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between md:gap-4">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 font-mono text-xs text-foreground">
        {children}
      </div>
    </div>
  );
}

function PluginDetails({
  locale,
  plugin,
  disabled,
  onChangeSetting,
}: {
  locale: Locale;
  plugin: PluginItem;
  disabled: boolean;
  onChangeSetting: PluginsTableProps["onChangeSetting"];
}) {
  return (
    <div className="space-y-2 rounded-md bg-muted/35 px-3 py-2">
      {plugin.strategies.length ? (
        <PluginDetailRow label={pluginExtensionLabel(locale, "route_strategy")}>
          {plugin.strategies.map((strategy) => (
            <span key={strategy}>{strategy}</span>
          ))}
        </PluginDetailRow>
      ) : null}
      <PluginSettingsForm
        locale={locale}
        plugin={plugin}
        disabled={disabled}
        onChange={(key, value) => onChangeSetting(plugin, key, value)}
      />
    </div>
  );
}

/** Render installed plugins, their extension points, call stats, and details. */
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

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>{titleForLocale(locale, "插件", "Plugin")}</TableHead>
          <TableHead className="w-[18rem]">
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
            const busy = busyPluginId === plugin.id;
            const hasDetails =
              plugin.strategies.length > 0 || plugin.settings.length > 0;
            return (
              <Fragment key={plugin.id}>
                <TableRow>
                  <TableCell className="max-w-[24rem] align-top">
                    <p className="truncate font-medium text-foreground">
                      {plugin.name}
                    </p>
                    <OptionalTooltip hint={plugin.description}>
                      <p className="truncate text-xs text-muted-foreground">
                        {plugin.description}
                      </p>
                    </OptionalTooltip>
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
                    {plugin.extensions.length ? (
                      <div className="space-y-0.5">
                        {plugin.extensions.map((extension) => (
                          <ExtensionLine
                            key={extension}
                            locale={locale}
                            extension={extension}
                            stats={plugin.stats.find(
                              (item) => item.extension === extension,
                            )}
                          />
                        ))}
                      </div>
                    ) : (
                      titleForLocale(locale, "无", "None")
                    )}
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
                {hasDetails ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={4} className="pt-0">
                      <PluginDetails
                        locale={locale}
                        plugin={plugin}
                        disabled={busy}
                        onChangeSetting={onChangeSetting}
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
