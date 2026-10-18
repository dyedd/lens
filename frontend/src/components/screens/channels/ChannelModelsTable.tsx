import { Activity, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Input } from "@/components/ui/Input";
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
import {
  contextWindowSourceLabel,
  formatContextWindow,
  parseContextWindowInput,
} from "@/lib/contextWindow";
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
  onUpdateContextWindow: (key: string, contextWindow: number | null) => void;
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
  onUpdateContextWindow,
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
            {locale === "zh-CN" ? "模型名（上游）" : "Upstream model"}
          </TableHead>
          <TableHead className="w-[150px]">
            {locale === "zh-CN" ? "API Key" : "Keys"}
          </TableHead>
          <TableHead className="w-[180px]">
            {locale === "zh-CN" ? "转发协议" : "Forwarding"}
          </TableHead>
          <TableHead className="w-[92px]">
            {locale === "zh-CN" ? "上下文" : "Context"}
          </TableHead>
          <TableHead className="w-[72px]" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.length === 0 ? (
          <TableRow className="hover:bg-transparent">
            <TableCell
              colSpan={8}
              className="h-28 text-center text-muted-foreground"
            >
              {!hasModels
                ? locale === "zh-CN"
                  ? "还没有模型。先获取模型列表，或手动添加模型。"
                  : "No models yet. Fetch the model list or add models manually."
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
                          {locale === "zh-CN" ? "待处理" : "Needs review"}
                        </Badge>
                      </TooltipTrigger>
                      <TooltipContent>
                        {locale === "zh-CN"
                          ? "上游已移除，已暂停调用"
                          : "Removed upstream; calls are paused"}
                      </TooltipContent>
                    </Tooltip>
                  ) : null}
                </div>
                {hasMultipleBaseUrls ? (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <p className="truncate text-xs leading-4">
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
              <TableCell className="w-[180px] py-1.5">
                <ProtocolDropdown
                  value={model.protocols}
                  locale={locale}
                  className="h-7 px-2 py-0 text-xs has-[>svg]:px-2"
                  onChange={(protocols) =>
                    onUpdateProtocols(model.key, protocols)
                  }
                />
              </TableCell>
              <TableCell className="w-[92px] py-1.5">
                <ContextWindowInput
                  // Remount when the saved value changes so the draft resets.
                  key={model.contextWindow ?? "auto"}
                  model={model}
                  locale={locale}
                  onCommit={(contextWindow) =>
                    onUpdateContextWindow(model.key, contextWindow)
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
                      locale === "zh-CN" ? "删除模型" : "Delete model"
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

/**
 * Edits a model's context window override inline. Empty falls back to the
 * upstream-reported or name-detected value shown as the placeholder.
 */
function ContextWindowInput({
  model,
  locale,
  onCommit,
}: {
  model: AggregatedModel;
  locale: Locale;
  onCommit: (contextWindow: number | null) => void;
}) {
  const savedText =
    model.contextWindow === null
      ? ""
      : formatContextWindow(model.contextWindow);
  const [draft, setDraft] = useState(savedText);
  const isZh = locale === "zh-CN";
  const autoText =
    model.autoContextWindow === null
      ? ""
      : formatContextWindow(model.autoContextWindow);

  function commit() {
    if (draft.trim() === savedText) {
      setDraft(savedText);
      return;
    }
    const parsed = parseContextWindowInput(draft);
    if (parsed === undefined) {
      toast.error(
        isZh
          ? "上下文格式无效，示例：200K、1M、128000"
          : "Invalid context window. Examples: 200K, 1M, 128000",
      );
      setDraft(savedText);
      return;
    }
    if (parsed === model.contextWindow) {
      setDraft(savedText);
      return;
    }
    onCommit(parsed);
  }

  const hint =
    model.contextWindow !== null
      ? `${contextWindowSourceLabel("manual", locale)} · ${model.contextWindow.toLocaleString()} tokens`
      : model.autoContextWindowSource !== null &&
          model.autoContextWindow !== null
        ? `${contextWindowSourceLabel(model.autoContextWindowSource, locale)} · ${model.autoContextWindow.toLocaleString()} tokens`
        : isZh
          ? "未知时使用模型组默认上下文"
          : "Unknown; the model group default applies";

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Input
          value={draft}
          placeholder={autoText || (isZh ? "默认" : "Default")}
          inputMode="numeric"
          aria-label={
            isZh
              ? `${model.modelName} 上下文窗口`
              : `${model.modelName} context window`
          }
          className="h-7 px-2 font-mono text-xs placeholder:font-sans"
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              event.currentTarget.blur();
            } else if (event.key === "Escape") {
              event.stopPropagation();
              setDraft(savedText);
            }
          }}
        />
      </TooltipTrigger>
      <TooltipContent side="top">{hint}</TooltipContent>
    </Tooltip>
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
  return (
    <CredentialBadges
      keys={keys}
      totalCount={model.credentialCount}
      details={model.members.map((member) =>
        [
          member.credentialTitle,
          showBaseUrl ? formatBaseUrlLabel(model.baseUrl) : "",
        ]
          .filter(Boolean)
          .join(" · "),
      )}
      locale={locale}
    />
  );
}
