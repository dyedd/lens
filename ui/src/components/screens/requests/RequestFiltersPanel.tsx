import { Filter, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/Field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { ToolbarSearchInput } from "@/components/ui/ToolbarSearchInput";
import type { ProtocolKind, RequestLogFilterOption } from "@/lib/api";
import { titleForLocale, type Locale } from "@/lib/I18nContext";

import {
  filterOptionLabel,
  gatewayKeyFilterOptionLabel,
  type SortMode,
  type StatusFilter,
} from "./requestLogUtils";

type RequestFiltersPanelProps = {
  activeFilterCount: number;
  channelFilter: string;
  channelOptions: RequestLogFilterOption[];
  clearingLogs: boolean;
  gatewayKeyOptions: RequestLogFilterOption[];
  keyword: string;
  locale: Locale;
  protocolFilter: "all" | ProtocolKind;
  selectedGatewayKeyId: string;
  showGatewayKeyFilter: boolean;
  sortMode: SortMode;
  statusFilter: StatusFilter;
  onChannelChange: (value: string) => void;
  onClear: () => void;
  onGatewayKeyChange: (value: string) => void;
  onKeywordChange: (value: string) => void;
  onProtocolChange: (value: "all" | ProtocolKind) => void;
  onSortChange: (value: SortMode) => void;
  onStatusChange: (value: StatusFilter) => void;
};

/** Render request log filters and cleanup action. */
export function RequestFiltersPanel(props: RequestFiltersPanelProps) {
  const {
    activeFilterCount,
    channelFilter,
    channelOptions,
    clearingLogs,
    gatewayKeyOptions,
    keyword,
    locale,
    protocolFilter,
    selectedGatewayKeyId,
    showGatewayKeyFilter,
    sortMode,
    statusFilter,
    onChannelChange,
    onClear,
    onGatewayKeyChange,
    onKeywordChange,
    onProtocolChange,
    onSortChange,
    onStatusChange,
  } = props;
  return (
    <aside className="order-1 xl:order-2">
      <div className="rounded-2xl border bg-card p-4 xl:sticky xl:top-4">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="inline-flex size-9 items-center justify-center rounded-xl bg-primary/[0.08] text-primary">
              <Filter size={16} />
            </span>
            <div>
              <div className="text-sm font-semibold text-foreground">
                {titleForLocale(locale, "筛选", "Filters")}
              </div>
              <div className="text-xs text-muted-foreground">
                {locale === "zh-CN"
                  ? `已启用 ${activeFilterCount} 项`
                  : `${activeFilterCount} active`}
              </div>
            </div>
          </div>
        </div>
        <FieldSet className="gap-4">
          <FieldLegend>
            {titleForLocale(locale, "筛选条件", "Refine results")}
          </FieldLegend>
          <FieldGroup className="gap-4">
            <Field>
              <FieldLabel>
                {titleForLocale(locale, "关键词", "Keyword")}
              </FieldLabel>
              <ToolbarSearchInput
                value={keyword}
                onChange={onKeywordChange}
                onClear={() => onKeywordChange("")}
                placeholder={titleForLocale(
                  locale,
                  "模型 / 渠道 / API Key / 错误 / 状态码",
                  "Model / channel / API key / error / status",
                )}
                className="max-w-none"
              />
            </Field>
            <Field>
              <FieldLabel>
                {titleForLocale(locale, "状态", "Status")}
              </FieldLabel>
              <div className="grid grid-cols-2 gap-2">
                {[
                  {
                    key: "all" as const,
                    label: titleForLocale(locale, "全部", "All"),
                  },
                  {
                    key: "running" as const,
                    label: titleForLocale(locale, "进行中", "Running"),
                  },
                  {
                    key: "success" as const,
                    label: titleForLocale(locale, "成功", "Success"),
                  },
                  {
                    key: "failed" as const,
                    label: titleForLocale(locale, "失败", "Failed"),
                  },
                ].map((option) => (
                  <Button
                    key={option.key}
                    type="button"
                    variant={
                      statusFilter === option.key ? "default" : "outline"
                    }
                    size="sm"
                    onClick={() => onStatusChange(option.key)}
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
            </Field>
            <Field>
              <FieldLabel htmlFor="request-log-protocol">
                {titleForLocale(locale, "协议", "Protocol")}
              </FieldLabel>
              <Select
                value={protocolFilter}
                onValueChange={(value) =>
                  onProtocolChange(value as "all" | ProtocolKind)
                }
              >
                <SelectTrigger id="request-log-protocol" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">
                    {titleForLocale(locale, "全部协议", "All protocols")}
                  </SelectItem>
                  <SelectItem value="openai_chat">OpenAI Chat</SelectItem>
                  <SelectItem value="openai_responses">
                    OpenAI Responses
                  </SelectItem>
                  <SelectItem value="openai_embedding">
                    OpenAI Embedding
                  </SelectItem>
                  <SelectItem value="rerank">Rerank</SelectItem>
                  <SelectItem value="anthropic">Anthropic</SelectItem>
                  <SelectItem value="gemini">Gemini</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="request-log-channel">
                {titleForLocale(locale, "渠道", "Channel")}
              </FieldLabel>
              <Combobox
                id="request-log-channel"
                className="w-full"
                value={channelFilter}
                onChange={(event) => onChannelChange(event.target.value)}
              >
                <ComboboxOption value="all">
                  {titleForLocale(locale, "全部渠道", "All channels")}
                </ComboboxOption>
                {channelOptions.map((channel) => (
                  <ComboboxOption key={channel.id} value={channel.id}>
                    {filterOptionLabel(channel)}
                  </ComboboxOption>
                ))}
              </Combobox>
            </Field>
            {showGatewayKeyFilter ? (
              <Field>
                <FieldLabel htmlFor="request-log-gateway-key">
                  API Key
                </FieldLabel>
                <Combobox
                  id="request-log-gateway-key"
                  className="w-full"
                  value={selectedGatewayKeyId}
                  onChange={(event) => onGatewayKeyChange(event.target.value)}
                >
                  <ComboboxOption value="all">
                    {titleForLocale(locale, "全部 API Key", "All API keys")}
                  </ComboboxOption>
                  {gatewayKeyOptions.map((item) => (
                    <ComboboxOption key={item.id} value={item.id}>
                      {gatewayKeyFilterOptionLabel(item, locale)}
                    </ComboboxOption>
                  ))}
                </Combobox>
              </Field>
            ) : null}
            <Field>
              <FieldLabel htmlFor="request-log-sort">
                {titleForLocale(locale, "排序", "Sort by")}
              </FieldLabel>
              <Select
                value={sortMode}
                onValueChange={(value) => onSortChange(value as SortMode)}
              >
                <SelectTrigger id="request-log-sort" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="latest">
                    {titleForLocale(locale, "最新优先", "Latest first")}
                  </SelectItem>
                  <SelectItem value="cost">
                    {titleForLocale(locale, "费用优先", "Highest cost")}
                  </SelectItem>
                  <SelectItem value="latency">
                    {titleForLocale(locale, "耗时优先", "Longest latency")}
                  </SelectItem>
                  <SelectItem value="tokens">
                    {titleForLocale(locale, "Token 优先", "Most tokens")}
                  </SelectItem>
                </SelectContent>
              </Select>
            </Field>
          </FieldGroup>
        </FieldSet>
        <div className="mt-4 border-t pt-4">
          <Button
            type="button"
            variant="outline"
            className="w-full text-destructive hover:text-destructive"
            onClick={onClear}
            disabled={clearingLogs}
          >
            <Trash2 data-icon="inline-start" />
            {clearingLogs
              ? titleForLocale(locale, "清空中...", "Clearing...")
              : titleForLocale(locale, "清空请求日志", "Clear request logs")}
          </Button>
        </div>
      </div>
    </aside>
  );
}
