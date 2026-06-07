"use client";

import {
  AlertCircle,
  Check,
  GripVertical,
  LayoutGrid,
  Plus,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type {
  ModelGroupCandidateItem,
  ProtocolKind,
  RoutingStrategy,
} from "@/lib/api";
import { isItemValidForProtocols } from "@/lib/api";
import { ModelAvatar } from "@/lib/model-icons";
import { cn } from "@/lib/utils";
import {
  foldedMemberSourceLabel,
  formatMoney,
  metricLabel,
  protocolBadgeClassName,
  protocolLabel,
  strategyOptions,
  type FoldedMember,
} from "./shared";

export function CompactPriceSummary({
  locale,
  inputPrice,
  outputPrice,
  cacheReadPrice,
  cacheWritePrice,
}: {
  locale: "zh-CN" | "en-US";
  inputPrice: number;
  outputPrice: number;
  cacheReadPrice: number;
  cacheWritePrice: number;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="mt-2 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          <span>
            {metricLabel("input", locale)} ${formatMoney(inputPrice)}
          </span>
          <span>
            {metricLabel("output", locale)} ${formatMoney(outputPrice)}
          </span>
          <span>
            {metricLabel("cache_read", locale)} ${formatMoney(cacheReadPrice)}
          </span>
          <span>
            {metricLabel("cache_write", locale)} ${formatMoney(cacheWritePrice)}
          </span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top" align="start">
        <div className="grid gap-1">
          <div>
            {metricLabel("input", locale)}: ${formatMoney(inputPrice)} / 1M
            tokens
          </div>
          <div>
            {metricLabel("output", locale)}: ${formatMoney(outputPrice)} / 1M
            tokens
          </div>
          <div>
            {metricLabel("cache_read", locale)}: ${formatMoney(cacheReadPrice)}{" "}
            / 1M tokens
          </div>
          <div>
            {metricLabel("cache_write", locale)}: $
            {formatMoney(cacheWritePrice)} / 1M tokens
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

export function EditablePriceRow({
  locale,
  primaryLabel,
  primaryValue,
  secondaryLabel,
  secondaryValue,
  onPrimaryChange,
  onSecondaryChange,
}: {
  locale: "zh-CN" | "en-US";
  primaryLabel: "input" | "output";
  primaryValue: string;
  secondaryLabel: "cache_read" | "cache_write";
  secondaryValue: string;
  onPrimaryChange: (value: string) => void;
  onSecondaryChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field className="min-w-0">
        <FieldLabel>${metricLabel(primaryLabel, locale)}</FieldLabel>
        <Input
          className="mt-2"
          value={primaryValue}
          onChange={(event) => onPrimaryChange(event.target.value)}
        />
      </Field>

      <Field className="min-w-0">
        <FieldLabel>${metricLabel(secondaryLabel, locale)}</FieldLabel>
        <Input
          className="mt-2"
          value={secondaryValue}
          onChange={(event) => onSecondaryChange(event.target.value)}
        />
      </Field>
    </div>
  );
}

export function StrategyToggle({
  value,
  locale,
  disabled = false,
  size = "default",
  className,
  onChange,
}: {
  value: RoutingStrategy;
  locale: "zh-CN" | "en-US";
  disabled?: boolean;
  size?: "default" | "sm";
  className?: string;
  onChange: (value: RoutingStrategy) => void;
}) {
  return (
    <ToggleGroup
      type="single"
      value={value}
      onValueChange={(nextValue) => {
        if (nextValue) {
          onChange(nextValue as RoutingStrategy);
        }
      }}
      variant="outline"
      size={size}
      spacing={1}
      className={cn("max-w-full flex-wrap", className)}
    >
      {strategyOptions.map((option) => (
        <ToggleGroupItem
          key={option.value}
          value={option.value}
          disabled={disabled}
          className="max-w-full"
        >
          {locale === "zh-CN" ? option.zh : option.en}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

export function CandidateRow({
  candidate,
  active,
  selectedProtocols,
  locale,
  onClick,
}: {
  candidate: ModelGroupCandidateItem;
  active: boolean;
  selectedProtocols: ProtocolKind[];
  locale: "zh-CN" | "en-US";
  onClick: () => void;
}) {
  const nativeProtocols = candidate.protocols;

  return (
    <Button
      type="button"
      variant="ghost"
      className={cn(
        "h-auto min-h-8 w-full justify-between rounded-md px-3 py-1.5 text-left",
        active ? "cursor-not-allowed opacity-60" : "hover:bg-muted",
      )}
      onClick={onClick}
      disabled={active}
    >
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-foreground">
          {candidate.model_name}
        </div>
      </div>
      <div className="flex min-w-0 shrink-0 flex-wrap items-center justify-end gap-1.5">
        {nativeProtocols.map((p) => {
          const usable = isItemValidForProtocols(p, selectedProtocols);
          return (
            <Badge
              key={p}
              variant="outline"
              className={cn(
                "px-1.5 py-0 text-[10px] font-normal",
                usable
                  ? protocolBadgeClassName(p)
                  : "border-transparent bg-muted/50 text-muted-foreground/50",
              )}
            >
              {protocolLabel(p, locale)}
            </Badge>
          );
        })}
        <span className="text-muted-foreground">
          {active ? (
            <Check size={15} className="text-primary" />
          ) : (
            <Plus size={15} />
          )}
        </span>
      </div>
    </Button>
  );
}

export function FoldedMemberRow({
  member,
  index,
  dragging,
  busy,
  onToggle,
  onRemove,
  onDragStart,
  onDragEnter,
  onDragEnd,
  locale,
}: {
  member: FoldedMember;
  index: number;
  dragging: boolean;
  busy: boolean;
  onToggle: () => void;
  onRemove: () => void;
  onDragStart: () => void;
  onDragEnter: () => void;
  onDragEnd: () => void;
  locale: "zh-CN" | "en-US";
}) {
  const sourceLabel = foldedMemberSourceLabel(member, locale);

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnter={onDragEnter}
      onDragOver={(event) => event.preventDefault()}
      onDragEnd={onDragEnd}
      className={cn(
        "flex min-w-0 items-center gap-2 border-b px-2.5 py-2 transition last:border-b-0",
        dragging && "opacity-60 shadow-sm",
        !member.enabled && "opacity-55",
        member.invalid && "border border-destructive bg-destructive/10",
      )}
    >
      <span className="grid h-5 w-5 shrink-0 place-items-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
        {index + 1}
      </span>
      <span className="cursor-grab text-muted-foreground active:cursor-grabbing">
        <GripVertical size={14} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-foreground">
          {member.model_name}
        </div>
        <div className="truncate text-xs text-muted-foreground">
          {sourceLabel}
          {!member.enabled
            ? ` · ${locale === "zh-CN" ? "已关闭" : "Disabled"}`
            : ""}
        </div>
      </div>
      <div className="flex h-8 w-8 items-center justify-center">
        <Switch
          checked={member.enabled}
          disabled={busy}
          onCheckedChange={onToggle}
        />
      </div>
      {member.invalid ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="grid h-8 w-8 shrink-0 place-items-center text-destructive">
              <AlertCircle size={15} />
            </span>
          </TooltipTrigger>
          <TooltipContent>
            {locale === "zh-CN"
              ? "不适用于当前所选的对外协议"
              : "Invalid for current protocols"}
          </TooltipContent>
        </Tooltip>
      ) : null}
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="text-muted-foreground hover:text-destructive"
        onClick={onRemove}
      >
        <X size={13} />
      </Button>
    </div>
  );
}

export function SeriesChip({
  selected,
  label,
  sampleModel,
  onClick,
  isAll = false,
}: {
  selected: boolean;
  label: string;
  sampleModel: string;
  onClick: () => void;
  isAll?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={cn(
        "group flex min-w-[76px] snap-start items-center justify-center rounded-[22px] border bg-card px-4 py-4 text-center transition-all",
        selected
          ? "border-primary bg-primary/[0.05] shadow-[0_0_0_1px_rgba(37,99,235,0.08)]"
          : "border-border/70 hover:border-primary/25 hover:bg-muted/20",
      )}
    >
      <span
        className={cn(
          "flex size-11 items-center justify-center rounded-2xl border bg-background",
          selected ? "border-primary/20 bg-primary/[0.06]" : "border-border/60",
        )}
      >
        {isAll ? (
          <LayoutGrid
            size={20}
            className={selected ? "text-primary" : "text-muted-foreground"}
          />
        ) : (
          <ModelAvatar name={sampleModel} size={28} />
        )}
      </span>
    </button>
  );
}
