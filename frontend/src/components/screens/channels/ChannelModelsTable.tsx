import { Activity, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
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
import type { ProtocolKind } from "@/lib/api/protocols";
import { CredentialBadges } from "./CredentialBadges";
import { formatBaseUrlLabel } from "./channelModels";
import type { AggregatedModel, Locale } from "./channelTypes";
import { ProtocolDropdown } from "./ProtocolDropdown";

type Props = {
  locale: Locale;
  items: AggregatedModel[];
  hasModels: boolean;
  hasMultipleBaseUrls: boolean;
  selected: ReadonlySet<string>;
  testing: boolean;
  onSelectAll: (checked: boolean) => void;
  onSelectOne: (key: string, checked: boolean) => void;
  onToggleEnabled: (key: string, enabled: boolean) => void;
  onUpdateProtocols: (key: string, protocols: ProtocolKind[]) => void;
  onDelete: (key: string) => void;
  onTest: (key: string) => void;
};

export function ChannelModelsTable({
  locale,
  items,
  hasModels,
  hasMultipleBaseUrls,
  selected,
  testing,
  onSelectAll,
  onSelectOne,
  onToggleEnabled,
  onUpdateProtocols,
  onDelete,
  onTest,
}: Props) {
  const allSelected =
    items.length > 0 && items.every((model) => selected.has(model.key));
  const someSelected = items.some((model) => selected.has(model.key));
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="w-[44px] text-center">
            <div className="flex h-7 items-center justify-center">
              <Checkbox
                checked={
                  allSelected ? true : someSelected ? "indeterminate" : false
                }
                onCheckedChange={(checked) => onSelectAll(checked === true)}
                aria-label={
                  locale === "zh-CN" ? "全选模型" : "Select all models"
                }
              />
            </div>
          </TableHead>
          <TableHead className="w-[56px]">
            {locale === "zh-CN" ? "状态" : "Status"}
          </TableHead>
          <TableHead>
            {locale === "zh-CN" ? "上游模型名" : "Upstream model"}
          </TableHead>
          <TableHead className="w-[150px]">
            {locale === "zh-CN" ? "密钥" : "Keys"}
          </TableHead>
          <TableHead className="w-[64px]">
            {locale === "zh-CN" ? "来源" : "Source"}
          </TableHead>
          <TableHead className="w-[180px]">
            {locale === "zh-CN" ? "转发方式" : "Forwarding"}
          </TableHead>
          <TableHead className="w-[72px]" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={7}
              className="h-28 text-center text-muted-foreground"
            >
              {!hasModels
                ? locale === "zh-CN"
                  ? "还没有模型。获取上游模型，或手动添加。"
                  : "No models yet. Fetch upstream models, or add them manually."
                : locale === "zh-CN"
                  ? "没有匹配的模型。"
                  : "No matching models."}
            </TableCell>
          </TableRow>
        ) : (
          items.map((model) => (
            <TableRow
              key={model.key}
              data-state={selected.has(model.key) ? "selected" : undefined}
            >
              <TableCell className="w-[44px] py-1.5 text-center">
                <div className="flex h-7 items-center justify-center">
                  <Checkbox
                    checked={selected.has(model.key)}
                    onCheckedChange={(checked) =>
                      onSelectOne(model.key, checked === true)
                    }
                    aria-label={
                      locale === "zh-CN"
                        ? `选择 ${model.modelName}`
                        : `Select ${model.modelName}`
                    }
                  />
                </div>
              </TableCell>
              <TableCell className="py-1.5">
                <div className="flex h-7 items-center">
                  <Switch
                    size="sm"
                    checked={model.enabled}
                    onCheckedChange={(checked) =>
                      onToggleEnabled(model.key, checked)
                    }
                  />
                </div>
              </TableCell>
              <TableCell className="max-w-[220px] py-1.5 font-mono text-xs text-muted-foreground">
                <div className="flex min-h-7 min-w-0 items-center gap-1.5">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="truncate">{model.modelName}</span>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-sm break-all">
                      {model.modelName}
                    </TooltipContent>
                  </Tooltip>
                  {model.upstreamMissing ? (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Badge
                          variant="destructive"
                          className="shrink-0 font-sans"
                          tabIndex={0}
                        >
                          {locale === "zh-CN" ? "待确认" : "Review"}
                        </Badge>
                      </TooltipTrigger>
                      <TooltipContent>
                        {locale === "zh-CN"
                          ? "上游已不再提供，暂停调用"
                          : "No longer listed upstream; paused"}
                      </TooltipContent>
                    </Tooltip>
                  ) : null}
                </div>
                {hasMultipleBaseUrls ? (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <p className="truncate text-[11px] leading-4">
                        {formatBaseUrlLabel(model.baseUrl)}
                      </p>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-sm break-all">
                      {model.baseUrl}
                    </TooltipContent>
                  </Tooltip>
                ) : null}
              </TableCell>
              <TableCell className="w-[150px] py-1.5">
                <ModelKeyBadges
                  model={model}
                  showBaseUrl={hasMultipleBaseUrls}
                  locale={locale}
                />
              </TableCell>
              <TableCell className="w-[64px] py-1.5 text-xs text-muted-foreground">
                {model.source === "synced"
                  ? locale === "zh-CN"
                    ? "同步"
                    : "Synced"
                  : locale === "zh-CN"
                    ? "手动"
                    : "Manual"}
              </TableCell>
              <TableCell className="w-[180px] py-1.5">
                <ProtocolDropdown
                  value={model.protocols}
                  locale={locale}
                  className="h-7 px-2 py-0 text-[11px] has-[>svg]:px-2"
                  onChange={(protocols) =>
                    onUpdateProtocols(model.key, protocols)
                  }
                />
              </TableCell>
              <TableCell className="w-[72px] py-1.5">
                <div className="flex h-7 items-center justify-end gap-0.5">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="inline-flex">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          className="size-6 text-muted-foreground"
                          disabled={testing || !model.testKey}
                          aria-label={
                            locale === "zh-CN" ? "测试模型" : "Test model"
                          }
                          onClick={() => {
                            if (model.testKey) onTest(model.testKey);
                          }}
                        >
                          <Activity className="size-3.5 stroke-1" />
                        </Button>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent side="top">
                      {model.testKey
                        ? locale === "zh-CN"
                          ? "测试"
                          : "Test"
                        : locale === "zh-CN"
                          ? "无法测试"
                          : "Cannot test"}
                    </TooltipContent>
                  </Tooltip>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    className="size-6 text-muted-foreground"
                    aria-label={
                      locale === "zh-CN" ? "删除绑定" : "Delete binding"
                    }
                    onClick={() => onDelete(model.key)}
                  >
                    <Trash2 className="size-3.5 stroke-1" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}

/** Shows which keys provide one aggregated model row. */
function ModelKeyBadges({
  model,
  showBaseUrl,
  locale,
}: {
  model: AggregatedModel;
  showBaseUrl: boolean;
  locale: Locale;
}) {
  const keys = [
    ...new Map(
      model.members.map((member) => [
        member.credentialId,
        { id: member.credentialId, label: member.credentialName },
      ]),
    ).values(),
  ];
  const sourceLabel = (source: AggregatedModel["source"]) =>
    source === "synced"
      ? locale === "zh-CN"
        ? "同步"
        : "Synced"
      : locale === "zh-CN"
        ? "手动"
        : "Manual";
  return (
    <CredentialBadges
      keys={keys}
      totalCount={model.credentialCount}
      details={model.members.map((member) =>
        [
          member.credentialTitle,
          showBaseUrl ? formatBaseUrlLabel(model.baseUrl) : "",
          sourceLabel(member.source),
        ]
          .filter(Boolean)
          .join(" · "),
      )}
      locale={locale}
    />
  );
}
