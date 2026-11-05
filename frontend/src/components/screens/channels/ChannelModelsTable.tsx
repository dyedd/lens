import { Activity, Trash2, Wand2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
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
import { apiRequest, getApiErrorMessage } from "@/lib/api/client";
import type { ProtocolKind } from "@/lib/api/protocols";
import {
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
  detecting: boolean;
  onSelectAll: (checked: boolean) => void;
  onSelectOne: (key: string, checked: boolean) => void;
  onToggleEnabled: (key: string, enabled: boolean) => void;
  onUpdateProtocols: (key: string, protocols: ProtocolKind[]) => void;
  onDetectProtocols: (keys: string[]) => Promise<void>;
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
  detecting,
  onSelectAll,
  onSelectOne,
  onToggleEnabled,
  onUpdateProtocols,
  onDetectProtocols,
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
          <TableHead className="w-[160px]">
            {locale === "zh-CN" ? "上游协议" : "Upstream protocol"}
          </TableHead>
          <TableHead className="w-[128px] min-w-[128px]">
            {locale === "zh-CN" ? "上下文" : "Context"}
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
                </div>
                {hasMultipleBaseUrls ? (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <p className="truncate text-xs leading-4">
                        {model.baseUrls.map(formatBaseUrlLabel).join(" · ")}
                      </p>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-sm break-all">
                      {model.baseUrls.join(" · ")}
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
              <TableCell className="w-[160px] py-1.5">
                <div className="flex items-center gap-0.5">
                  <ProtocolDropdown
                    value={model.protocols}
                    locale={locale}
                    disabled={detecting}
                    className="h-7 min-h-7 min-w-0 max-w-[110px] flex-1 gap-1 px-1.5 py-0 text-xs leading-4 has-[>svg]:px-1.5"
                    onChange={(protocols) =>
                      onUpdateProtocols(model.key, protocols)
                    }
                  />
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="inline-flex">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          className="shrink-0 text-muted-foreground"
                          disabled={detecting}
                          aria-label={
                            locale === "zh-CN"
                              ? `自动识别 ${model.modelName} 上游协议`
                              : `Detect ${model.modelName} upstream protocol`
                          }
                          onClick={() => void onDetectProtocols([model.key])}
                        >
                          <Wand2 className="size-3 stroke-1" />
                        </Button>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      {locale === "zh-CN" ? "自动识别协议" : "Detect protocol"}
                    </TooltipContent>
                  </Tooltip>
                </div>
              </TableCell>
              <TableCell className="w-[128px] min-w-[128px] py-1.5">
                <ContextWindowInput
                  // 保存值变化后重建输入框，更新草稿。
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

/** 编辑上下文，或主动用识别结果覆盖当前值。 */
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
  const [detecting, setDetecting] = useState(false);

  async function detectContext() {
    setDetecting(true);
    try {
      const values = await apiRequest<Record<string, number | null>>(
        "/admin/model-context-detections",
        {
          method: "POST",
          body: JSON.stringify({ model_names: [model.modelName] }),
        },
      );
      const value = values[model.modelName] ?? null;
      onCommit(value);
      setDraft(value === null ? "" : formatContextWindow(value));
    } catch (error) {
      toast.error(
        getApiErrorMessage(error, isZh ? "自动识别失败" : "Detection failed"),
      );
    } finally {
      setDetecting(false);
    }
  }

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

  const hint = isZh
    ? "留空交给上游判断"
    : "Leave empty for the upstream to decide";

  return (
    <div className="flex items-center gap-0.5">
      <Tooltip>
        <TooltipTrigger asChild>
          <Input
            value={draft}
            disabled={detecting}
            placeholder={isZh ? "默认" : "Default"}
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
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className="size-6 shrink-0 text-muted-foreground"
              disabled={detecting}
              aria-label={isZh ? "自动识别上下文" : "Detect context"}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => void detectContext()}
            >
              <Wand2 className="size-3.5 stroke-1" />
            </Button>
          </span>
        </TooltipTrigger>
        <TooltipContent>{isZh ? "自动识别" : "Auto-detect"}</TooltipContent>
      </Tooltip>
    </div>
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
          showBaseUrl ? formatBaseUrlLabel(member.baseUrl) : "",
        ]
          .filter(Boolean)
          .join(" · "),
      )}
      locale={locale}
    />
  );
}
