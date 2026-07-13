import type { Dispatch, SetStateAction } from "react";
import { Filter } from "lucide-react";
import { Button } from "@/components/ui/Button";
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
import type { ProtocolKind, RoutingStrategy } from "@/lib/api";
import { protocolOptions } from "@/lib/protocols";
import type { GroupSort } from "./modelGroupUtils";

interface GroupsFilterPanelProps {
  locale: "zh-CN" | "en-US";
  search: string;
  protocolFilter: "all" | ProtocolKind;
  strategyFilter: "all" | RoutingStrategy;
  sortBy: GroupSort;
  activeFilterCount: number;
  setSearch: Dispatch<SetStateAction<string>>;
  setProtocolFilter: Dispatch<SetStateAction<"all" | ProtocolKind>>;
  setStrategyFilter: Dispatch<SetStateAction<"all" | RoutingStrategy>>;
  setSortBy: Dispatch<SetStateAction<GroupSort>>;
  resetFilters: () => void;
}

/** Render model group search, filtering, and sorting controls. */
export function GroupsFilterPanel({
  locale,
  search,
  protocolFilter,
  strategyFilter,
  sortBy,
  activeFilterCount,
  setSearch,
  setProtocolFilter,
  setStrategyFilter,
  setSortBy,
  resetFilters,
}: GroupsFilterPanelProps) {
  const strategyOptions: Array<{
    key: "all" | RoutingStrategy;
    label: string;
  }> = [
    { key: "all", label: locale === "zh-CN" ? "全部" : "All" },
    {
      key: "round_robin",
      label: locale === "zh-CN" ? "轮询" : "Round Robin",
    },
    {
      key: "failover",
      label: locale === "zh-CN" ? "故障转移" : "Failover",
    },
  ];

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
            onClick={resetFilters}
            disabled={!activeFilterCount && sortBy === "members-desc"}
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
              <FieldLabel>
                {locale === "zh-CN" ? "关键词" : "Keyword"}
              </FieldLabel>
              <ToolbarSearchInput
                value={search}
                onChange={setSearch}
                onClear={() => setSearch("")}
                placeholder={
                  locale === "zh-CN"
                    ? "模型组 / 渠道 / 模型"
                    : "Group / channel / model"
                }
                className="max-w-none"
              />
            </Field>
            <Field>
              <FieldLabel>
                {locale === "zh-CN" ? "协议" : "Protocol"}
              </FieldLabel>
              <Select
                value={protocolFilter}
                onValueChange={(value) =>
                  setProtocolFilter(value as "all" | ProtocolKind)
                }
              >
                <SelectTrigger className="w-full">
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
              <FieldLabel>
                {locale === "zh-CN" ? "策略" : "Strategy"}
              </FieldLabel>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                {strategyOptions.map((option) => (
                  <Button
                    key={option.key}
                    type="button"
                    variant={
                      strategyFilter === option.key ? "default" : "outline"
                    }
                    size="sm"
                    onClick={() => setStrategyFilter(option.key)}
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
            </Field>
            <Field>
              <FieldLabel>{locale === "zh-CN" ? "排序" : "Sort"}</FieldLabel>
              <Select
                value={sortBy}
                onValueChange={(value) => setSortBy(value as GroupSort)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="members-desc">
                    {locale === "zh-CN" ? "成员优先" : "Members first"}
                  </SelectItem>
                  <SelectItem value="enabled-desc">
                    {locale === "zh-CN" ? "启用优先" : "Enabled first"}
                  </SelectItem>
                  <SelectItem value="name-asc">
                    {locale === "zh-CN" ? "名称 A-Z" : "Name A-Z"}
                  </SelectItem>
                  <SelectItem value="name-desc">
                    {locale === "zh-CN" ? "名称 Z-A" : "Name Z-A"}
                  </SelectItem>
                </SelectContent>
              </Select>
            </Field>
          </FieldGroup>
        </FieldSet>
      </div>
    </aside>
  );
}
