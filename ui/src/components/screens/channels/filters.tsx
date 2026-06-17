"use client";

import { Filter } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ToolbarSearchInput } from "@/components/ui/toolbar-search-input";
import type { ProtocolKind } from "@/lib/api";
import {
  type ChannelSort,
  type ChannelStatusFilter,
  type Locale,
  protocolOptions,
} from "./shared";

export function ChannelFiltersPanel({
  locale,
  search,
  statusFilter,
  protocolFilter,
  sortBy,
  activeFilterCount,
  onSearchChange,
  onStatusChange,
  onProtocolChange,
  onSortChange,
  onReset,
}: {
  locale: Locale;
  search: string;
  statusFilter: ChannelStatusFilter;
  protocolFilter: "all" | ProtocolKind;
  sortBy: ChannelSort;
  activeFilterCount: number;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: ChannelStatusFilter) => void;
  onProtocolChange: (value: "all" | ProtocolKind) => void;
  onSortChange: (value: ChannelSort) => void;
  onReset: () => void;
}) {
  return (
    <div className="rounded-2xl border bg-card p-4 xl:sticky xl:top-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex size-9 items-center justify-center rounded-xl bg-primary/[0.08] text-primary">
            <Filter size={16} />
          </span>
          <div>
            <div className="text-sm font-semibold text-foreground">
              {locale === "zh-CN" ? "筛选" : "Filters"}
            </div>
            <div className="text-xs text-muted-foreground">
              {locale === "zh-CN"
                ? `已启用 ${activeFilterCount} 项`
                : `${activeFilterCount} active`}
            </div>
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onReset}
          disabled={!activeFilterCount && sortBy === "requests-desc"}
        >
          {locale === "zh-CN" ? "清空" : "Clear"}
        </Button>
      </div>

      <FieldSet className="gap-4">
        <FieldLegend>
          {locale === "zh-CN" ? "筛选条件" : "Refine results"}
        </FieldLegend>
        <FieldGroup className="gap-4">
          <Field>
            <FieldLabel>{locale === "zh-CN" ? "关键词" : "Keyword"}</FieldLabel>
            <ToolbarSearchInput
              value={search}
              onChange={onSearchChange}
              onClear={() => onSearchChange("")}
              placeholder={
                locale === "zh-CN"
                  ? "渠道 / 协议 / 模型"
                  : "Channel / protocol / model"
              }
              className="max-w-none"
            />
          </Field>

          <Field>
            <FieldLabel>{locale === "zh-CN" ? "状态" : "Status"}</FieldLabel>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {[
                {
                  key: "all" as const,
                  label: locale === "zh-CN" ? "全部" : "All",
                },
                {
                  key: "enabled" as const,
                  label: locale === "zh-CN" ? "启用" : "Enabled",
                },
                {
                  key: "disabled" as const,
                  label: locale === "zh-CN" ? "停用" : "Disabled",
                },
              ].map((option) => (
                <Button
                  key={option.key}
                  type="button"
                  variant={statusFilter === option.key ? "default" : "outline"}
                  size="sm"
                  onClick={() => onStatusChange(option.key)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </Field>

          <Field>
            <FieldLabel htmlFor="channels-protocol-filter">
              {locale === "zh-CN" ? "协议" : "Protocol"}
            </FieldLabel>
            <Select
              value={protocolFilter}
              onValueChange={(value) =>
                onProtocolChange(value as "all" | ProtocolKind)
              }
            >
              <SelectTrigger id="channels-protocol-filter" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">
                  {locale === "zh-CN" ? "全部协议" : "All protocols"}
                </SelectItem>
                {protocolOptions(locale).map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <Field>
            <FieldLabel htmlFor="channels-sort">
              {locale === "zh-CN" ? "排序" : "Sort by"}
            </FieldLabel>
            <Select
              value={sortBy}
              onValueChange={(value) => onSortChange(value as ChannelSort)}
            >
              <SelectTrigger id="channels-sort" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="requests-desc">
                  {locale === "zh-CN" ? "请求优先" : "Requests first"}
                </SelectItem>
                <SelectItem value="models-desc">
                  {locale === "zh-CN" ? "模型优先" : "Models first"}
                </SelectItem>
                <SelectItem value="protocols-desc">
                  {locale === "zh-CN" ? "协议优先" : "Protocols first"}
                </SelectItem>
                <SelectItem value="name-asc">
                  {locale === "zh-CN" ? "名称升序" : "Name asc"}
                </SelectItem>
                <SelectItem value="name-desc">
                  {locale === "zh-CN" ? "名称降序" : "Name desc"}
                </SelectItem>
              </SelectContent>
            </Select>
          </Field>
        </FieldGroup>
      </FieldSet>
    </div>
  );
}
